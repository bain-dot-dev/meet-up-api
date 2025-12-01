"""
meetup_events_to_supabase.py

Fetches Meetup events via GraphQL API and saves them to Supabase.

Requirements:
    pip install requests python-dotenv supabase

Environment Variables:
    MEETUP_API_TOKEN - Your Meetup OAuth 2.0 access token
    MEETUP_API_ENDPOINT - GraphQL endpoint (default: https://api.meetup.com/gql)
    SUPABASE_URL - Your Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY - Supabase service role key

Usage:
    # Simply run the script - it will fetch all configured locations and topics
    python meetup_events_to_supabase.py

    # Or configure locations and topics in the SEARCH_CONFIG section below
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional, TypedDict

import requests
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Configuration
MEETUP_API_TOKEN = os.getenv("MEETUP_API_TOKEN")
MEETUP_API_ENDPOINT = os.getenv("MEETUP_API_ENDPOINT", "https://api.meetup.com/gql")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Batch size for Supabase upserts
BATCH_SIZE = 100

# Maximum number of pages to fetch (prevents infinite loops)
MAX_PAGES = 10


# ============================================================================
# SEARCH CONFIGURATION
# ============================================================================
# Configure the locations and topics you want to fetch events for.
# Simply comment out or remove any entries you don't want to fetch.
# ============================================================================

class LocationConfig(TypedDict):
    """Configuration for a location search."""
    name: str  # Human-readable name for logging
    lat: float
    lon: float
    radius_km: float
    topics: List[str]  # List of topics to search for in this location


# Define locations you want to search
# Add or remove locations as needed
LOCATIONS: List[LocationConfig] = [
    {
        "name": "San Francisco Bay Area",
        "lat": 37.7749,
        "lon": -122.4194,
        "radius_km": 50,
        "topics": ["tech", "ai", "python", "javascript", "startups"],
    },
    {
        "name": "New York City",
        "lat": 40.7128,
        "lon": -74.0060,
        "radius_km": 50,
        "topics": ["tech", "ai", "machine learning", "fintech"],
    },
    {
        "name": "Austin",
        "lat": 30.2672,
        "lon": -97.7431,
        "radius_km": 40,
        "topics": ["tech", "blockchain", "web3"],
    },
    # Add more locations here
    # {
    #     "name": "Seattle",
    #     "lat": 47.6062,
    #     "lon": -122.3321,
    #     "radius_km": 50,
    #     "topics": ["cloud", "devops", "aws"],
    # },
]

# Define global topics to search (without location filtering)
# These will fetch events from anywhere in the world
# Set to empty list [] if you don't want global topic searches
GLOBAL_TOPICS: List[str] = [
    # "blockchain",
    # "web3",
    # "cryptocurrency",
]

# GraphQL query for searching events
SEARCH_EVENTS_QUERY = """
query($filter: SearchConnectionFilter!, $after: String) {
  keywordSearch(filter: $filter, input: {first: 100, after: $after}) {
    count
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      cursor
      node {
        id
        result {
          ... on Event {
            id
            title
            eventUrl
            description
            shortDescription
            dateTime
            going
            group {
              id
              name
              urlname
            }
            venue {
              name
              lat
              lon
              city
              state
              country
            }
          }
        }
      }
    }
  }
}
"""


def validate_environment() -> None:
    """Validate that all required environment variables are set."""
    missing = []
    if not MEETUP_API_TOKEN:
        missing.append("MEETUP_API_TOKEN")
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_ROLE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")

    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


def get_supabase_client() -> Client:
    """
    Initialize and return a Supabase client.

    Returns:
        Configured Supabase client
    """
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def run_graphql_query(query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a GraphQL query against the Meetup API.

    Args:
        query: GraphQL query string
        variables: Variables to pass to the query

    Returns:
        JSON response as a dict

    Raises:
        Exception: If the API request fails
    """
    headers = {
        "Authorization": f"Bearer {MEETUP_API_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "query": query,
        "variables": variables,
    }

    try:
        response = requests.post(
            MEETUP_API_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

        data = response.json()

        # Check for GraphQL errors
        if "errors" in data:
            error_messages = [err.get("message", str(err)) for err in data["errors"]]
            raise Exception(f"GraphQL errors: {'; '.join(error_messages)}")

        return data

    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {e}")
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse JSON response: {e}")


def normalize_event(
    raw_node: Dict[str, Any],
    topic_keyword: Optional[str],
    search_context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Normalize a raw GraphQL event node into a database-ready dict.

    Args:
        raw_node: Raw event node from GraphQL response
        topic_keyword: The topic keyword used in the search
        search_context: Dict with search_lat, search_lon, search_radius_km

    Returns:
        Normalized event dict matching the meetup_events schema
    """
    result = raw_node.get("result", {})
    if not result:
        return None

    group = result.get("group") or {}
    venue = result.get("venue") or {}

    # Parse dateTime
    date_time = result.get("dateTime")
    if date_time:
        try:
            # Meetup returns ISO 8601 format, parse and convert to timestamp
            date_time = datetime.fromisoformat(date_time.replace("Z", "+00:00")).isoformat()
        except (ValueError, AttributeError):
            date_time = None

    normalized = {
        "id": result.get("id", ""),
        "title": result.get("title", ""),
        "description": result.get("description"),
        "short_description": result.get("shortDescription"),
        "event_url": result.get("eventUrl"),
        "date_time": date_time,
        "going": result.get("going"),
        "group_id": group.get("id"),
        "group_name": group.get("name"),
        "group_urlname": group.get("urlname"),
        "venue_name": venue.get("name"),
        "venue_city": venue.get("city"),
        "venue_state": venue.get("state"),
        "venue_country": venue.get("country"),
        "venue_lat": venue.get("lat"),
        "venue_lon": venue.get("lon"),
        "topic_keyword": topic_keyword,
        "raw_event": result,
    }

    # Add search context if provided
    if search_context:
        normalized["search_lat"] = search_context.get("search_lat")
        normalized["search_lon"] = search_context.get("search_lon")
        normalized["search_radius_km"] = search_context.get("search_radius_km")

    return normalized


def search_events_by_location(
    lat: float,
    lon: float,
    radius_km: float,
    topic_keyword: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search for events by geographic location.

    Args:
        lat: Latitude
        lon: Longitude
        radius_km: Search radius in kilometers
        topic_keyword: Optional topic keyword filter

    Returns:
        List of normalized event dicts
    """
    search_context = {
        "search_lat": lat,
        "search_lon": lon,
        "search_radius_km": radius_km,
    }

    # Use provided keyword or a broad default
    query_keyword = topic_keyword if topic_keyword else "events"

    variables = {
        "filter": {
            "query": query_keyword,
            "lat": lat,
            "lon": lon,
            "radius": radius_km,
            "source": "EVENTS",
        },
        "after": None,
    }

    events = []
    page_count = 0

    print(f"Searching events by location (lat={lat}, lon={lon}, radius={radius_km}km, topic='{query_keyword}')...")

    while page_count < MAX_PAGES:
        try:
            response = run_graphql_query(SEARCH_EVENTS_QUERY, variables)
            data = response.get("data", {}).get("keywordSearch", {})

            edges = data.get("edges", [])
            for edge in edges:
                node = edge.get("node", {})
                normalized = normalize_event(node, topic_keyword, search_context)
                if normalized and normalized.get("id"):
                    events.append(normalized)

            # Check for pagination
            page_info = data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            end_cursor = page_info.get("endCursor")

            page_count += 1
            print(f"  Page {page_count}: fetched {len(edges)} events (total: {len(events)})")

            if not has_next_page or not end_cursor:
                break

            variables["after"] = end_cursor

        except Exception as e:
            print(f"ERROR fetching page {page_count + 1}: {e}", file=sys.stderr)
            break

    return events


def search_events_by_topic(
    topic_keyword: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    radius_km: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Search for events by topic keyword, optionally filtered by location.

    Args:
        topic_keyword: Topic keyword to search for
        lat: Optional latitude for geographic filtering
        lon: Optional longitude for geographic filtering
        radius_km: Optional search radius in kilometers

    Returns:
        List of normalized event dicts
    """
    search_context = None
    if lat is not None and lon is not None and radius_km is not None:
        search_context = {
            "search_lat": lat,
            "search_lon": lon,
            "search_radius_km": radius_km,
        }

    variables = {
        "filter": {
            "query": topic_keyword,
            "source": "EVENTS",
        },
        "after": None,
    }

    # Add location filters if provided
    if search_context:
        variables["filter"]["lat"] = lat
        variables["filter"]["lon"] = lon
        variables["filter"]["radius"] = radius_km

    events = []
    page_count = 0

    location_str = f", lat={lat}, lon={lon}, radius={radius_km}km" if search_context else ""
    print(f"Searching events by topic (topic='{topic_keyword}'{location_str})...")

    while page_count < MAX_PAGES:
        try:
            response = run_graphql_query(SEARCH_EVENTS_QUERY, variables)
            data = response.get("data", {}).get("keywordSearch", {})

            edges = data.get("edges", [])
            for edge in edges:
                node = edge.get("node", {})
                normalized = normalize_event(node, topic_keyword, search_context)
                if normalized and normalized.get("id"):
                    events.append(normalized)

            # Check for pagination
            page_info = data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            end_cursor = page_info.get("endCursor")

            page_count += 1
            print(f"  Page {page_count}: fetched {len(edges)} events (total: {len(events)})")

            if not has_next_page or not end_cursor:
                break

            variables["after"] = end_cursor

        except Exception as e:
            print(f"ERROR fetching page {page_count + 1}: {e}", file=sys.stderr)
            break

    return events


def upsert_events_to_supabase(events: List[Dict[str, Any]]) -> None:
    """
    Upsert events into the Supabase meetup_events table.

    Args:
        events: List of normalized event dicts

    Raises:
        Exception: If the upsert operation fails
    """
    if not events:
        print("No events to upsert.")
        return

    supabase = get_supabase_client()

    total_events = len(events)
    succeeded = 0
    failed = 0

    print(f"\nUpserting {total_events} events to Supabase in batches of {BATCH_SIZE}...")

    # Process in batches
    for i in range(0, total_events, BATCH_SIZE):
        batch = events[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1

        try:
            # Upsert the batch
            response = supabase.table("meetup_events").upsert(batch).execute()

            batch_succeeded = len(batch)
            succeeded += batch_succeeded
            print(f"  Batch {batch_num}: upserted {batch_succeeded} events")

        except Exception as e:
            batch_failed = len(batch)
            failed += batch_failed
            print(f"  Batch {batch_num} FAILED: {e}", file=sys.stderr)

    print(f"\n✓ Upsert complete: {succeeded} succeeded, {failed} failed")


def main() -> None:
    """Main entry point - fetches all configured locations and topics."""
    # Validate environment
    validate_environment()

    print("=" * 80)
    print("MEETUP EVENTS TO SUPABASE - Configuration-Based Fetch")
    print("=" * 80)
    print(f"\nConfigured locations: {len(LOCATIONS)}")
    print(f"Global topics: {len(GLOBAL_TOPICS)}")
    print()

    all_events = []
    total_searches = 0

    # Process location-based searches
    for location in LOCATIONS:
        location_name = location["name"]
        lat = location["lat"]
        lon = location["lon"]
        radius_km = location["radius_km"]
        topics = location["topics"]

        print(f"\n{'='*80}")
        print(f"Processing Location: {location_name}")
        print(f"{'='*80}")

        for topic in topics:
            total_searches += 1
            print(f"\n[{total_searches}] Fetching '{topic}' events in {location_name}...")

            try:
                events = search_events_by_location(
                    lat=lat,
                    lon=lon,
                    radius_km=radius_km,
                    topic_keyword=topic,
                )
                all_events.extend(events)
                print(f"✓ Found {len(events)} events for '{topic}' in {location_name}")
            except Exception as e:
                print(f"✗ ERROR fetching '{topic}' in {location_name}: {e}", file=sys.stderr)

    # Process global topic searches
    if GLOBAL_TOPICS:
        print(f"\n{'='*80}")
        print("Processing Global Topics (No Location Filter)")
        print(f"{'='*80}")

        for topic in GLOBAL_TOPICS:
            total_searches += 1
            print(f"\n[{total_searches}] Fetching '{topic}' events globally...")

            try:
                events = search_events_by_topic(
                    topic_keyword=topic,
                )
                all_events.extend(events)
                print(f"✓ Found {len(events)} events for '{topic}' globally")
            except Exception as e:
                print(f"✗ ERROR fetching global '{topic}': {e}", file=sys.stderr)

    # Deduplicate events by ID (in case same event appears in multiple searches)
    unique_events = {event["id"]: event for event in all_events if event.get("id")}
    unique_events_list = list(unique_events.values())

    print(f"\n{'='*80}")
    print("DEDUPLICATION SUMMARY")
    print(f"{'='*80}")
    print(f"Total events fetched: {len(all_events)}")
    print(f"Unique events: {len(unique_events_list)}")
    print(f"Duplicates removed: {len(all_events) - len(unique_events_list)}")

    # Upsert to Supabase
    if unique_events_list:
        upsert_events_to_supabase(unique_events_list)
        print(f"\n{'='*80}")
        print("FINAL SUMMARY")
        print(f"{'='*80}")
        print(f"Total searches performed: {total_searches}")
        print(f"Unique events upserted to Supabase: {len(unique_events_list)}")
        print(f"{'='*80}")
    else:
        print("\n⚠ No events found matching any configured criteria.")
        print("Tip: Check your LOCATIONS and GLOBAL_TOPICS configuration above.")


if __name__ == "__main__":
    main()
