"""
location_all_events.py

Fetches ALL public Meetup events near a specific location (without topic filtering)
using the Meetup GraphQL API and prints them as JSON to stdout.

This script is useful for getting a comprehensive list of all events in an area.

Requirements:
    pip install requests python-dotenv

Environment Variables:
    MEETUP_API_TOKEN - Your Meetup OAuth 2.0 access token
    MEETUP_API_ENDPOINT - GraphQL endpoint (default: https://api.meetup.com/gql-ext)

Usage:
    # Edit the LOCATION_* constants below, then run:
    python location_all_events.py
"""

import json
import os
import sys
from typing import Dict, Any

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
# LOCATION CONFIGURATION
# ============================================================================
# Edit these values to search for events near your desired location
# ============================================================================

# Stanford University coordinates
LOCATION_NAME = "Stanford University"
LOCATION_LAT = 37.4275
LOCATION_LON = -122.1697
LOCATION_RADIUS_MILES = 10  # Search radius in miles (max 100)

# Use a very broad search term to get all events
# Options: "events", "meetup", "gathering", or any broad term
SEARCH_QUERY = "events"

# Number of events to fetch per page (max 100)
EVENTS_PER_PAGE = 100

# Maximum number of pages to fetch (to prevent infinite loops)
MAX_PAGES = 10

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


def get_all_location_events() -> Dict[str, Any]:
    """
    Fetch all events near the configured location with pagination.

    Returns:
        Dict containing all events and metadata
    """
    # Cap at maximum allowed radius
    radius_miles = min(LOCATION_RADIUS_MILES, MAX_RADIUS_MILES)

    if LOCATION_RADIUS_MILES > MAX_RADIUS_MILES:
        print(f"WARNING: Radius {LOCATION_RADIUS_MILES} miles exceeds maximum of {MAX_RADIUS_MILES} miles. Capping at {MAX_RADIUS_MILES} miles.", file=sys.stderr)

    all_events = []
    page_count = 0
    after_cursor = None

    print(f"Fetching all events near {LOCATION_NAME}...", file=sys.stderr)
    print(f"Location: ({LOCATION_LAT}, {LOCATION_LON})", file=sys.stderr)
    print(f"Radius: {radius_miles} miles", file=sys.stderr)
    print(f"Search query: '{SEARCH_QUERY}'\n", file=sys.stderr)

    while page_count < MAX_PAGES:
        variables = {
            "filter": {
                "query": SEARCH_QUERY,
                "lat": LOCATION_LAT,
                "lon": LOCATION_LON,
                "radius": radius_miles,
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

        page_count += 1
        print(f"  Page {page_count}: fetched {len(edges)} events (total so far: {len(all_events)})", file=sys.stderr)

        # Check if there are more pages
        page_info = event_search.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        after_cursor = page_info.get("endCursor")

        if not has_next_page or not after_cursor:
            print(f"\n✓ Reached end of results", file=sys.stderr)
            break

    if page_count >= MAX_PAGES:
        print(f"\n⚠ Reached maximum page limit ({MAX_PAGES}). There may be more events available.", file=sys.stderr)

    return {
        "location": {
            "name": LOCATION_NAME,
            "lat": LOCATION_LAT,
            "lon": LOCATION_LON,
            "radius_miles": radius_miles,
        },
        "search_query": SEARCH_QUERY,
        "total_events": len(all_events),
        "pages_fetched": page_count,
        "events": all_events,
    }


def main() -> None:
    """Main entry point."""
    result = get_all_location_events()

    # Pretty-print the JSON response
    print(json.dumps(result, indent=2))

    # Print summary to stderr
    print(f"\n{'='*80}", file=sys.stderr)
    print(f"SUMMARY", file=sys.stderr)
    print(f"{'='*80}", file=sys.stderr)
    print(f"Location: {result['location']['name']}", file=sys.stderr)
    print(f"Coordinates: ({result['location']['lat']}, {result['location']['lon']})", file=sys.stderr)
    print(f"Radius: {result['location']['radius_miles']} miles", file=sys.stderr)
    print(f"Search query: '{result['search_query']}'", file=sys.stderr)
    print(f"Total events found: {result['total_events']}", file=sys.stderr)
    print(f"Pages fetched: {result['pages_fetched']}", file=sys.stderr)
    print(f"{'='*80}", file=sys.stderr)


if __name__ == "__main__":
    main()
