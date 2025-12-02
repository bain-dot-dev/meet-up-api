"""
fetch_university_events.py

Dynamically fetches Meetup events for universities stored in Supabase.
Reads university locations from staging_meetup.feed_source_university table
and fetches events for each active university.

Requirements:
    pip install requests python-dotenv supabase

Environment Variables:
    MEETUP_API_TOKEN - Your Meetup OAuth 2.0 access token
    MEETUP_API_ENDPOINT - GraphQL endpoint (default: https://api.meetup.com/gql-ext)
    SUPABASE_URL - Your Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY - Your Supabase service role key

Usage:
    python fetch_university_events.py
"""

import json
import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime

import requests
from dotenv import load_dotenv
from supabase import create_client, Client

# Meetup API uses MILES (not kilometers) with a silent cap at 100 miles
MAX_RADIUS_MILES = 100

# Load environment variables from .env file
load_dotenv()

# Configuration
MEETUP_API_TOKEN = os.getenv("MEETUP_API_TOKEN")
MEETUP_API_ENDPOINT = os.getenv("MEETUP_API_ENDPOINT", "https://api.meetup.com/gql-ext")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# ============================================================================
# CONFIGURATION
# ============================================================================
# Search radius around each university (in miles, max 100)
SEARCH_RADIUS_MILES = 10

# Use a very broad search term to get all events
SEARCH_QUERY = "events"

# Number of events to fetch per page (max 100)
EVENTS_PER_PAGE = 100

# Maximum number of pages to fetch per university
MAX_PAGES_PER_UNIVERSITY = 10

# Limit number of universities to process (for testing)
# Set to None to process all active universities
UNIVERSITY_LIMIT = 5  # Change to a number like 5 for testing

# ============================================================================

# GraphQL query for searching events
SEARCH_EVENTS_QUERY = """
query($filter: EventSearchFilter!, $first: Int, $after: String) {
  eventSearch(filter: $filter, first: $first, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      cursor
      node {
        id
        title
        eventUrl
        description
        dateTime
        eventType
        featuredEventPhoto {
          id
          baseUrl
        }
        group {
          id
          name
          urlname
          keyGroupPhoto {
            id
            baseUrl
          }
        }
        venues {
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
"""


def init_supabase() -> Client:
    """
    Initialize Supabase client.

    Returns:
        Supabase client instance

    Raises:
        SystemExit: If credentials are missing
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set", file=sys.stderr)
        sys.exit(1)

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def fetch_active_universities(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Fetch active universities from Supabase.

    Args:
        limit: Optional limit on number of universities to fetch

    Returns:
        List of university dicts with name, latitude, longitude

    Raises:
        SystemExit: If the query fails
    """
    print("Fetching active universities from Supabase...", file=sys.stderr)

    try:
        supabase = init_supabase()

        # Query active universities from staging_meetup schema
        # NOTE: staging_meetup schema must be exposed in Supabase API settings
        # Go to Settings → API → Exposed schemas and add 'staging_meetup'
        query = supabase.schema("staging_meetup").table("feed_source_university") \
            .select("name, latitude, longitude") \
            .eq("status", "active")

        if limit:
            query = query.limit(limit)

        response = query.execute()

        universities = response.data

        if not universities:
            print("WARNING: No active universities found in database", file=sys.stderr)
            return []

        print(f"✓ Found {len(universities)} active universities", file=sys.stderr)

        # Validate that required fields are present
        valid_universities = []
        for uni in universities:
            if uni.get("name") and uni.get("latitude") is not None and uni.get("longitude") is not None:
                valid_universities.append({
                    "name": uni["name"],
                    "latitude": uni["latitude"],
                    "longitude": uni["longitude"]
                })
            else:
                print(f"WARNING: Skipping university with missing data: {uni}", file=sys.stderr)

        return valid_universities

    except Exception as e:
        print(f"ERROR: Failed to fetch universities from Supabase - {e}", file=sys.stderr)
        sys.exit(1)


def run_graphql_query(query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a GraphQL query against the Meetup API.

    Args:
        query: GraphQL query string
        variables: Variables to pass to the query

    Returns:
        JSON response as a dict

    Raises:
        SystemExit: If the API request fails
    """
    if not MEETUP_API_TOKEN:
        print("ERROR: MEETUP_API_TOKEN environment variable is not set", file=sys.stderr)
        sys.exit(1)

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
            print(
                f"ERROR: HTTP {response.status_code} - {response.text}",
                file=sys.stderr,
            )
            sys.exit(1)

        data = response.json()

        # Check for GraphQL errors
        if "errors" in data:
            print("ERROR: GraphQL errors occurred:", file=sys.stderr)
            print(json.dumps(data["errors"], indent=2), file=sys.stderr)
            sys.exit(1)

        return data

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed - {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON response - {e}", file=sys.stderr)
        sys.exit(1)


def fetch_events_for_university(university: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Fetch all events near a university with pagination.

    Args:
        university: Dict with name, latitude, longitude

    Returns:
        List of event dicts
    """
    name = university["name"]
    lat = university["latitude"]
    lon = university["longitude"]

    # Cap at maximum allowed radius
    radius_miles = min(SEARCH_RADIUS_MILES, MAX_RADIUS_MILES)

    if SEARCH_RADIUS_MILES > MAX_RADIUS_MILES:
        print(f"WARNING: Radius {SEARCH_RADIUS_MILES} miles exceeds maximum of {MAX_RADIUS_MILES} miles. Capping at {MAX_RADIUS_MILES} miles.", file=sys.stderr)

    all_events = []
    page_count = 0
    after_cursor = None

    print(f"\nFetching events near {name}...", file=sys.stderr)
    print(f"  Location: ({lat}, {lon})", file=sys.stderr)
    print(f"  Radius: {radius_miles} miles", file=sys.stderr)

    while page_count < MAX_PAGES_PER_UNIVERSITY:
        variables = {
            "filter": {
                "query": SEARCH_QUERY,
                "lat": lat,
                "lon": lon,
                "radius": radius_miles,
            },
            "first": EVENTS_PER_PAGE,
            "after": after_cursor,
        }

        print(f"  Fetching page {page_count + 1}...", file=sys.stderr)

        result = run_graphql_query(SEARCH_EVENTS_QUERY, variables)

        # Extract events from this page
        event_search = result.get("data", {}).get("eventSearch", {})
        edges = event_search.get("edges", [])

        # Add events to our collection
        for edge in edges:
            node = edge.get("node", {})
            if node and node.get("id"):
                # Add university context to each event
                event_with_context = {
                    "university_name": name,
                    "university_lat": lat,
                    "university_lon": lon,
                    "search_radius_miles": radius_miles,
                    **node
                }
                all_events.append(event_with_context)

        page_count += 1
        print(f"  Page {page_count}: fetched {len(edges)} events (total for this university: {len(all_events)})", file=sys.stderr)

        # Check if there are more pages
        page_info = event_search.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        after_cursor = page_info.get("endCursor")

        if not has_next_page or not after_cursor:
            print(f"  ✓ Reached end of results for {name}", file=sys.stderr)
            break

    if page_count >= MAX_PAGES_PER_UNIVERSITY:
        print(f"  ⚠ Reached maximum page limit ({MAX_PAGES_PER_UNIVERSITY}) for {name}. There may be more events available.", file=sys.stderr)

    print(f"  ✓ Total events found for {name}: {len(all_events)}", file=sys.stderr)

    return all_events


def main() -> None:
    """Main entry point."""
    print(f"{'='*80}", file=sys.stderr)
    print(f"UNIVERSITY EVENTS FETCHER", file=sys.stderr)
    print(f"{'='*80}", file=sys.stderr)
    print(f"Configuration:", file=sys.stderr)
    print(f"  Search radius: {SEARCH_RADIUS_MILES} miles (max: {MAX_RADIUS_MILES})", file=sys.stderr)
    print(f"  Search query: '{SEARCH_QUERY}'", file=sys.stderr)
    print(f"  Events per page: {EVENTS_PER_PAGE}", file=sys.stderr)
    print(f"  Max pages per university: {MAX_PAGES_PER_UNIVERSITY}", file=sys.stderr)
    print(f"  University limit: {UNIVERSITY_LIMIT if UNIVERSITY_LIMIT else 'All'}", file=sys.stderr)
    print(f"{'='*80}\n", file=sys.stderr)

    # Fetch active universities from Supabase
    universities = fetch_active_universities(limit=UNIVERSITY_LIMIT)

    if not universities:
        print("\n⚠ No valid universities to process. Exiting.", file=sys.stderr)
        sys.exit(0)

    all_events = []
    successful_universities = 0
    failed_universities = 0

    # Fetch events for each university
    for i, university in enumerate(universities, 1):
        print(f"\n{'='*80}", file=sys.stderr)
        print(f"Processing University {i}/{len(universities)}: {university['name']}", file=sys.stderr)
        print(f"{'='*80}", file=sys.stderr)

        try:
            events = fetch_events_for_university(university)
            all_events.extend(events)
            successful_universities += 1
        except Exception as e:
            print(f"✗ ERROR processing {university['name']}: {e}", file=sys.stderr)
            failed_universities += 1

    # Prepare result
    result = {
        "metadata": {
            "total_universities_processed": len(universities),
            "successful_universities": successful_universities,
            "failed_universities": failed_universities,
            "total_events": len(all_events),
            "search_radius_miles": SEARCH_RADIUS_MILES,
            "search_query": SEARCH_QUERY,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        },
        "universities": [
            {
                "name": uni["name"],
                "latitude": uni["latitude"],
                "longitude": uni["longitude"]
            }
            for uni in universities
        ],
        "events": all_events,
    }

    # Pretty-print the JSON response to stdout
    print(json.dumps(result, indent=2))

    # Print summary to stderr
    print(f"\n{'='*80}", file=sys.stderr)
    print(f"SUMMARY", file=sys.stderr)
    print(f"{'='*80}", file=sys.stderr)
    print(f"Universities processed: {len(universities)}", file=sys.stderr)
    print(f"  ✓ Successful: {successful_universities}", file=sys.stderr)
    print(f"  ✗ Failed: {failed_universities}", file=sys.stderr)
    print(f"Total events fetched: {len(all_events)}", file=sys.stderr)

    if all_events:
        # Show breakdown by university
        print(f"\nEvents by university:", file=sys.stderr)
        university_counts = {}
        for event in all_events:
            uni_name = event.get("university_name", "Unknown")
            university_counts[uni_name] = university_counts.get(uni_name, 0) + 1

        for uni_name, count in sorted(university_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {uni_name}: {count} events", file=sys.stderr)

    print(f"{'='*80}", file=sys.stderr)


if __name__ == "__main__":
    main()
