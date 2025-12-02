"""Test if the Meetup API token is working."""
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

MEETUP_API_TOKEN = os.getenv("MEETUP_API_TOKEN")
MEETUP_API_ENDPOINT = os.getenv("MEETUP_API_ENDPOINT", "https://api.meetup.com/gql-ext")

# Simple test query
TEST_QUERY = """
{
  self {
    id
    name
  }
}
"""

headers = {
    "Authorization": f"Bearer {MEETUP_API_TOKEN}",
    "Content-Type": "application/json",
}

print(f"Testing endpoint: {MEETUP_API_ENDPOINT}")
print(f"Token: {MEETUP_API_TOKEN[:10]}...")
print()

response = requests.post(
    MEETUP_API_ENDPOINT,
    headers=headers,
    json={"query": TEST_QUERY},
    timeout=30,
)

print(f"Status Code: {response.status_code}")
print(f"Response Headers: {dict(response.headers)}")
print(f"\nResponse Body:")
print(response.text)

if response.status_code == 200:
    try:
        data = response.json()
        print("\nParsed JSON:")
        print(json.dumps(data, indent=2))
    except:
        pass
