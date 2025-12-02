"""Check the new Meetup GraphQL schema."""
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

MEETUP_API_TOKEN = os.getenv("MEETUP_API_TOKEN")
MEETUP_API_ENDPOINT = "https://api.meetup.com/gql-ext"

# Query to get Event type fields
EVENT_TYPE_QUERY = """
{
  __type(name: "Event") {
    name
    fields {
      name
      type { name kind ofType { name kind } }
    }
  }
}
"""

# Query to get eventSearch details
EVENT_SEARCH_QUERY = """
{
  __type(name: "Query") {
    fields {
      name
      args {
        name
        type { name kind ofType { name kind ofType { name kind } } }
      }
    }
  }
}
"""

# Query to get EventSearchFilter type
FILTER_TYPE_QUERY = """
{
  __type(name: "EventSearchFilter") {
    name
    inputFields {
      name
      type { name kind ofType { name kind } }
    }
  }
}
"""

headers = {
    "Authorization": f"Bearer {MEETUP_API_TOKEN}",
    "Content-Type": "application/json",
}

def run_query(query, name):
    print(f"\n{'='*60}")
    print(f"{name}")
    print('='*60)
    response = requests.post(
        MEETUP_API_ENDPOINT,
        headers=headers,
        json={"query": query},
        timeout=30,
    )
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2))
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

run_query(EVENT_TYPE_QUERY, "Event Type Fields")
run_query(FILTER_TYPE_QUERY, "EventSearchFilter Type")
run_query(EVENT_SEARCH_QUERY, "Query Fields with Args")
