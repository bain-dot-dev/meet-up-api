"""
test_meetup_events.py

Test script to fetch Meetup events using the Meetup GraphQL API and print them as JSON.
Uses a configuration-based approach - just edit the TEST_QUERIES list below.

Requirements:
    pip install requests python-dotenv

Environment Variables:
    MEETUP_API_TOKEN - Your Meetup OAuth 2.0 access token
    MEETUP_API_ENDPOINT - GraphQL endpoint (default: https://api.meetup.com/gql)

Usage:
    # Simply run the script - it will test all configured queries
    python test_meetup_events.py
"""

import json
import os
import sys
from typing import Dict, Any, List, TypedDict, Optional

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
MEETUP_API_TOKEN = os.getenv("MEETUP_API_TOKEN")
MEETUP_API_ENDPOINT = os.getenv("MEETUP_API_ENDPOINT", "https://api.meetup.com/gql-ext")


# ============================================================================
# TEST CONFIGURATION
# ============================================================================
# Configure the test queries you want to run.
# Simply comment out or remove any queries you don't want to test.
# ============================================================================

class TestQuery(TypedDict):
    """Configuration for a test query."""
    name: str  # Human-readable name for the test
    topic: str  # Topic keyword to search for
    lat: Optional[float]  # Optional latitude
    lon: Optional[float]  # Optional longitude
    radius_km: Optional[float]  # Optional search radius in km


# Define test queries
# Add or remove queries as needed
TEST_QUERIES: List[TestQuery] = [
    {
        "name": "Data Science and Coffee",
        "topic": "Data Science and Coffee",
        "lat": None,
        "lon": None,
        "radius_km": None
    },
    {
        "name": "New York AI Events",
        "topic": "ai",
        "lat": 40.7128,
        "lon": -74.0060,
        "radius_km": 50,
    },
    {
        "name": "Austin Python Events",
        "topic": "python",
        "lat": 30.2672,
        "lon": -97.7431,
        "radius_km": 40,
    },
    # Global search (no location filter)
    # {
    #     "name": "Global Blockchain Events",
    #     "topic": "blockchain",
    #     "lat": None,
    #     "lon": None,
    #     "radius_km": None,
    # },
]


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
        group {
          id
          name
          urlname
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


# Default location for global searches (San Francisco)
DEFAULT_LAT = 37.7749
DEFAULT_LON = -122.4194
DEFAULT_RADIUS_KM = 100


def fetch_events(test_query: TestQuery) -> Dict[str, Any]:
    """
    Fetch events based on a test query configuration.

    Args:
        test_query: Test query configuration

    Returns:
        GraphQL response containing events
    """
    # lat and lon are required in the new API
    lat = test_query.get("lat") if test_query.get("lat") is not None else DEFAULT_LAT
    lon = test_query.get("lon") if test_query.get("lon") is not None else DEFAULT_LON
    radius = test_query.get("radius_km") if test_query.get("radius_km") is not None else DEFAULT_RADIUS_KM

    filter_config = {
        "query": test_query["topic"],
        "lat": lat,
        "lon": lon,
    }

    # Add radius if provided
    if radius:
        filter_config["radius"] = radius

    variables = {
        "filter": filter_config,
        "first": 20,
    }

    return run_graphql_query(SEARCH_EVENTS_QUERY, variables)


def print_event_summary(events_data: Dict[str, Any]) -> None:
    """
    Print a summary of events from the response.

    Args:
        events_data: GraphQL response data
    """
    event_search = events_data.get("data", {}).get("eventSearch", {})
    edges = event_search.get("edges", [])

    print(f"\nEvents returned in this response: {len(edges)}\n")

    if edges:
        print("Sample events:")
        print("-" * 80)
        for i, edge in enumerate(edges[:5], 1):  # Show first 5 events
            event = edge.get("node", {})
            title = event.get("title", "N/A")
            group_name = event.get("group", {}).get("name", "N/A")
            venues = event.get("venues", [])
            venue = venues[0] if venues else {}
            venue_name = venue.get("name", "N/A")
            city = venue.get("city", "N/A")

            print(f"{i}. {title}")
            print(f"   Group: {group_name}")
            print(f"   Venue: {venue_name}, {city}")
            print()


def main() -> None:
    """Main entry point - runs all configured test queries."""
    print("=" * 80)
    print("MEETUP API TEST - Configuration-Based Testing")
    print("=" * 80)
    print(f"\nConfigured test queries: {len(TEST_QUERIES)}\n")

    if not TEST_QUERIES:
        print("⚠ No test queries configured!")
        print("Edit TEST_QUERIES in this script to add test cases.")
        sys.exit(0)

    all_results = []

    for i, test_query in enumerate(TEST_QUERIES, 1):
        test_name = test_query["name"]
        topic = test_query["topic"]
        lat = test_query.get("lat")
        lon = test_query.get("lon")
        radius_km = test_query.get("radius_km")

        print(f"\n{'='*80}")
        print(f"Test {i}/{len(TEST_QUERIES)}: {test_name}")
        print(f"{'='*80}")

        if lat and lon and radius_km:
            print(f"Topic: '{topic}' | Location: ({lat}, {lon}) | Radius: {radius_km}km")
        else:
            print(f"Topic: '{topic}' | Location: Global (no location filter)")

        try:
            result = fetch_events(test_query)
            all_results.append({
                "test_name": test_name,
                "query": test_query,
                "result": result,
            })

            print_event_summary(result)
            print(f"✓ Test '{test_name}' completed successfully")

        except Exception as e:
            print(f"✗ Test '{test_name}' FAILED: {e}", file=sys.stderr)
            all_results.append({
                "test_name": test_name,
                "query": test_query,
                "error": str(e),
            })

    # Print full JSON output
    print(f"\n{'='*80}")
    print("FULL JSON OUTPUT")
    print(f"{'='*80}\n")
    print(json.dumps(all_results, indent=2))

    # Print summary
    successful = sum(1 for r in all_results if "result" in r)
    failed = sum(1 for r in all_results if "error" in r)

    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Total tests: {len(TEST_QUERIES)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
