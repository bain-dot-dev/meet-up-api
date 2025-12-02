"""
san_francisco_events.py

Fetches public Meetup events near San Francisco using the Meetup GraphQL API
and prints them as JSON to stdout.

Requirements:
    pip install requests python-dotenv

Environment Variables:
    MEETUP_API_TOKEN - Your Meetup OAuth 2.0 access token
    MEETUP_API_ENDPOINT - GraphQL endpoint (default: https://api.meetup.com/gql)
"""

import json
import os
import sys
from typing import Dict, Any

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
MEETUP_API_TOKEN = os.getenv("MEETUP_API_TOKEN")
MEETUP_API_ENDPOINT = os.getenv("MEETUP_API_ENDPOINT", "https://api.meetup.com/gql-ext")

# San Francisco coordinates
SF_LAT = 37.7749
SF_LON = -122.4194
SF_RADIUS_KM = 50

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


def get_sf_events() -> Dict[str, Any]:
    """
    Fetch tech events near San Francisco.

    Returns:
        GraphQL response containing events
    """
    variables = {
        "filter": {
            "query": "tech",
            "lat": SF_LAT,
            "lon": SF_LON,
            "radius": SF_RADIUS_KM,
        },
        "first": 20,
    }

    return run_graphql_query(SEARCH_EVENTS_QUERY, variables)


def main() -> None:
    """Main entry point."""
    print(f"Fetching tech events near San Francisco (lat={SF_LAT}, lon={SF_LON}, radius={SF_RADIUS_KM}km)...\n")

    result = get_sf_events()

    # Pretty-print the JSON response
    print(json.dumps(result, indent=2))

    # Print summary
    edges = result.get("data", {}).get("eventSearch", {}).get("edges", [])
    print(f"\n✓ Found {len(edges)} events", file=sys.stderr)


if __name__ == "__main__":
    main()
