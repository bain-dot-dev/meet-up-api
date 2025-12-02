"""
fetch_recent_events.py

Fetches the most recent Meetup events from a wide geographic area,
sorted by date (newest to oldest).

Since Meetup API requires a location, this uses a central location with
maximum radius (100 miles) to capture as many events as possible.

Requirements:
    pip install requests python-dotenv

Environment Variables:
    MEETUP_API_TOKEN - Your Meetup OAuth 2.0 access token
    MEETUP_API_ENDPOINT - GraphQL endpoint (default: https://api.meetup.com/gql-ext)

Usage:
    python fetch_recent_events.py
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, List

import requests
from dotenv import load_dotenv

# Meetup API uses MILES (not kilometers) with a silent cap at 100 miles
MAX_RADIUS_MILES = 100

# Load environment variables from .env file
load_dotenv()

# Configuration
MEETUP_API_TOKEN = os.getenv("MEETUP_API_TOKEN")
MEETUP_API_ENDPOINT = os.getenv("MEETUP_API_ENDPOINT", "https://api.meetup.com/gql-ext")

# ============================================================================
# SEARCH CONFIGURATION
# ============================================================================
# Since Meetup API requires a location, we use a central US location
# with maximum radius to get broad coverage
# ============================================================================

# Central US coordinates (Kansas - geographic center of contiguous US)
SEARCH_LAT = 39.8283
SEARCH_LON = -98.5795
SEARCH_RADIUS_MILES = 100  # Maximum allowed by API

# Very broad search term to get all event types
SEARCH_QUERY = "events"

# Number of events to fetch per page (max 100)
EVENTS_PER_PAGE = 100

# Maximum number of events to fetch total
MAX_EVENTS_TO_FETCH = 1000

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


def fetch_recent_events() -> List[Dict[str, Any]]:
    """
    Fetch recent events with pagination.

    Returns:
        List of event dicts sorted by date (newest to oldest)
    """
    all_events = []
    page_count = 0
    after_cursor = None

    print(f"Fetching up to {MAX_EVENTS_TO_FETCH} recent events...", file=sys.stderr)
    print(f"Search location: ({SEARCH_LAT}, {SEARCH_LON})", file=sys.stderr)
    print(f"Radius: {SEARCH_RADIUS_MILES} miles (maximum)\n", file=sys.stderr)

    max_pages = (MAX_EVENTS_TO_FETCH + EVENTS_PER_PAGE - 1) // EVENTS_PER_PAGE

    while page_count < max_pages and len(all_events) < MAX_EVENTS_TO_FETCH:
        variables = {
            "filter": {
                "query": SEARCH_QUERY,
                "lat": SEARCH_LAT,
                "lon": SEARCH_LON,
                "radius": SEARCH_RADIUS_MILES,
            },
            "first": EVENTS_PER_PAGE,
            "after": after_cursor,
        }

        print(f"Fetching page {page_count + 1}...", file=sys.stderr)

        result = run_graphql_query(SEARCH_EVENTS_QUERY, variables)

        # Extract events from this page
        event_search = result.get("data", {}).get("eventSearch", {})
        edges = event_search.get("edges", [])

        # Add events to our collection
        for edge in edges:
            node = edge.get("node", {})
            if node and node.get("id"):
                all_events.append(node)
                if len(all_events) >= MAX_EVENTS_TO_FETCH:
                    break

        page_count += 1
        print(f"  Page {page_count}: fetched {len(edges)} events (total: {len(all_events)})", file=sys.stderr)

        # Check if there are more pages
        page_info = event_search.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        after_cursor = page_info.get("endCursor")

        if not has_next_page or not after_cursor:
            print(f"\n✓ Reached end of results", file=sys.stderr)
            break

    print(f"\n✓ Fetched {len(all_events)} total events", file=sys.stderr)

    # Sort events by date (newest to oldest)
    print(f"Sorting events by date (newest to oldest)...", file=sys.stderr)

    def get_event_datetime(event):
        """Extract datetime from event for sorting."""
        date_str = event.get("dateTime")
        if date_str:
            try:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        # Return a very old date for events without valid dates
        return datetime(1970, 1, 1)

    all_events.sort(key=get_event_datetime, reverse=True)

    return all_events


def main() -> None:
    """Main entry point."""
    events = fetch_recent_events()

    result = {
        "search_config": {
            "lat": SEARCH_LAT,
            "lon": SEARCH_LON,
            "radius_miles": SEARCH_RADIUS_MILES,
            "query": SEARCH_QUERY,
        },
        "total_events": len(events),
        "sort_order": "newest_to_oldest",
        "events": events,
    }

    # Pretty-print the JSON response
    print(json.dumps(result, indent=2))

    # Print summary to stderr
    print(f"\n{'='*80}", file=sys.stderr)
    print(f"SUMMARY", file=sys.stderr)
    print(f"{'='*80}", file=sys.stderr)
    print(f"Total events fetched: {len(events)}", file=sys.stderr)
    print(f"Sort order: Newest to oldest", file=sys.stderr)

    if events:
        # Show date range
        first_event_date = events[0].get("dateTime", "Unknown")
        last_event_date = events[-1].get("dateTime", "Unknown")
        print(f"Date range: {first_event_date} to {last_event_date}", file=sys.stderr)

        # Show sample of newest events
        print(f"\nNewest 5 events:", file=sys.stderr)
        for i, event in enumerate(events[:5], 1):
            title = event.get("title", "N/A")
            date = event.get("dateTime", "N/A")
            print(f"  {i}. {title} - {date}", file=sys.stderr)

    print(f"{'='*80}", file=sys.stderr)


if __name__ == "__main__":
    main()
