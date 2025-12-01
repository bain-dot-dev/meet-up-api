# Meetup GraphQL API to Supabase Integration

Production-ready Python scripts for fetching public Meetup events via the Meetup GraphQL API and storing them in Supabase.

## Features

- **Configuration-based approach** - Define locations and topics in code, no CLI arguments needed
- Fetch Meetup events by location (lat/lon/radius) with multiple topics
- Fetch Meetup events by global topics (no location filtering)
- Cursor-based pagination (up to 1000 events per search)
- Automatic event deduplication across multiple searches
- Batch upsert to Supabase (100 events per batch)
- Full type hints and comprehensive error handling
- Simple one-command execution

## Prerequisites

- Python 3.10 or higher
- Meetup OAuth 2.0 access token
- Supabase account with a project created

## Installation

### 1. Clone or Download This Repository

```bash
cd meet-up-api
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials:

```env
MEETUP_API_TOKEN=your_meetup_oauth2_token_here
MEETUP_API_ENDPOINT=https://api.meetup.com/gql
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
```

**How to get credentials:**

- **Meetup API Token**: Visit [Meetup OAuth Consumers](https://secure.meetup.com/meetup_api/oauth_consumers/) to create an OAuth consumer and generate an access token
- **Supabase URL & Key**: Found in your Supabase project settings under API

### 4. Create the Database Schema

1. Log in to your Supabase project
2. Navigate to the SQL Editor
3. Copy and paste the contents of `schema.sql`
4. Execute the SQL script

This will create the `meetup_events` table with proper indexes.

## Usage

### Script 1: Test Meetup API (Configuration-Based Testing)

A configurable test script to verify your Meetup API connection. Define multiple test queries in the code:

Open [test_meetup_events.py](test_meetup_events.py) and configure your test queries:

```python
TEST_QUERIES: List[TestQuery] = [
    {
        "name": "San Francisco Tech Events",
        "topic": "tech",
        "lat": 37.7749,
        "lon": -122.4194,
        "radius_km": 50,
    },
    {
        "name": "New York AI Events",
        "topic": "ai",
        "lat": 40.7128,
        "lon": -74.0060,
        "radius_km": 50,
    },
    # Add more test queries or comment out ones you don't want
]
```

Then run:

```bash
python test_meetup_events.py
```

This will:
- Run all configured test queries
- Print a summary of events for each test
- Output full JSON responses
- Show test success/failure statistics

### Script 2: Fetch and Store Events in Supabase (Configuration-Based)

The main script uses a **configuration-based approach** - no command-line arguments needed!

#### Step 1: Configure Your Locations and Topics

Open [meetup_events_to_supabase.py](meetup_events_to_supabase.py) and edit the `LOCATIONS` and `GLOBAL_TOPICS` configuration:

```python
# Define locations you want to search
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
    # Add more locations or comment out ones you don't want
]

# Define global topics (no location filter)
GLOBAL_TOPICS: List[str] = [
    # "blockchain",
    # "web3",
]
```

#### Step 2: Run the Script

Simply run the script - it will automatically fetch all configured locations and topics:

```bash
python meetup_events_to_supabase.py
```

**What it does:**
- Fetches events for each topic in each configured location
- Fetches events for global topics (if configured)
- Deduplicates events automatically (same event won't be stored twice)
- Upserts all unique events to Supabase in batches

**To disable a location or topic:**
- Comment it out with `#` or remove it from the list
- Example:
  ```python
  LOCATIONS: List[LocationConfig] = [
      # {
      #     "name": "Austin",  # Commented out - won't fetch
      #     ...
      # },
  ]
  ```

## Database Schema

The `meetup_events` table includes:

**Core Event Data:**
- `id` (TEXT, PRIMARY KEY) - Meetup event ID
- `title`, `description`, `short_description`
- `event_url` - Direct link to the event
- `date_time` (TIMESTAMPTZ) - Event date and time
- `going` (INT) - Number of attendees

**Group Information:**
- `group_id`, `group_name`, `group_urlname`

**Venue Information:**
- `venue_name`, `venue_city`, `venue_state`, `venue_country`
- `venue_lat`, `venue_lon` - Venue coordinates

**Search Context:**
- `topic_keyword` - Topic used in search
- `search_lat`, `search_lon`, `search_radius_km` - Search parameters

**Metadata:**
- `raw_event` (JSONB) - Full event payload for flexibility
- `created_at`, `updated_at` (TIMESTAMPTZ) - Timestamps

**Indexes:**
- Topic keyword, date/time, locations, group ID
- Full-text search on raw JSONB data

## Architecture Overview

### Meetup GraphQL API

**Authentication:**
- OAuth 2.0 bearer token authentication
- Token included in `Authorization: Bearer {TOKEN}` header

**Endpoint:**
- POST requests to `https://api.meetup.com/gql`
- JSON payload with `query` and `variables`

**Query Strategy:**
- Uses `keywordSearch` with `SearchConnectionFilter`
- Supports filtering by `query`, `lat`, `lon`, `radius`, `source: EVENTS`
- Cursor-based pagination with `after` parameter

### Script Architecture

**test_meetup_events.py:**
- Configuration-based test script
- Run multiple test queries with one command
- Prints detailed summaries and full JSON output
- Perfect for testing API connectivity and exploring data
- No database dependency

**meetup_events_to_supabase.py:**
- Configuration-based approach (edit config in code)
- Supports multiple locations with multiple topics each
- Supports global topic searches (no location filter)
- Automatic event deduplication across searches
- Pagination support (up to 10 pages / ~1000 events per search)
- Batch upsert to Supabase (100 events per batch)
- Comprehensive error handling with detailed progress logging

**Key Functions:**
- `run_graphql_query()` - Execute GraphQL queries
- `search_events_by_location()` - Location-based search
- `search_events_by_topic()` - Topic-based search
- `normalize_event()` - Transform GraphQL response to DB schema
- `upsert_events_to_supabase()` - Batch upsert with conflict resolution

## Example Configurations

### Configuration 1: Tech Events in Major Cities

```python
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
]

GLOBAL_TOPICS: List[str] = []  # No global searches
```

**Result:** Fetches 5 topics × 3 cities = 15 searches, all with one command: `python meetup_events_to_supabase.py`

### Configuration 2: Global Blockchain/Web3 Events

```python
LOCATIONS: List[LocationConfig] = []  # No location-based searches

GLOBAL_TOPICS: List[str] = [
    "blockchain",
    "web3",
    "cryptocurrency",
    "ethereum",
]
```

**Result:** Fetches 4 global topic searches (events from anywhere in the world)

### Configuration 3: Mixed - Local + Global

```python
LOCATIONS: List[LocationConfig] = [
    {
        "name": "Boston",
        "lat": 42.3601,
        "lon": -71.0589,
        "radius_km": 30,
        "topics": ["biotech", "healthcare", "medical devices"],
    },
]

GLOBAL_TOPICS: List[str] = [
    "quantum computing",
    "space tech",
]
```

**Result:** 3 local searches + 2 global searches = 5 total searches

## Error Handling

The scripts include comprehensive error handling:

- Missing environment variables → Clear error message and exit
- HTTP errors → Status code and response body logged
- GraphQL errors → Error messages extracted and displayed
- Network timeouts → 30-second timeout with retry suggestion
- Batch upsert failures → Individual batch errors logged, process continues

## Limitations

- Maximum 10 pages per query (~1000 events) to prevent infinite loops
- Meetup API rate limits apply (check Meetup API documentation)
- Requires valid OAuth token (tokens may expire)

## Project Files

- **[test_meetup_events.py](test_meetup_events.py)** - Test script with configurable queries (no database)
- **[meetup_events_to_supabase.py](meetup_events_to_supabase.py)** - Main script to fetch and save events to Supabase
- **[san_francisco_events.py](san_francisco_events.py)** - Legacy simple test (kept for backward compatibility)
- **[schema.sql](schema.sql)** - Supabase database schema
- **[requirements.txt](requirements.txt)** - Python dependencies
- **[.env.example](.env.example)** - Environment variable template

## Troubleshooting

**"Missing required environment variables"**
- Ensure `.env` file exists and contains all required variables
- Check that variable names match exactly

**"HTTP 401 Unauthorized"**
- Meetup API token is invalid or expired
- Regenerate token from Meetup OAuth console

**"GraphQL errors"**
- Query syntax issue (unlikely with provided scripts)
- Invalid filter parameters (check lat/lon/radius values)

**"Supabase connection failed"**
- Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
- Ensure `meetup_events` table exists (run `schema.sql`)

## Automation & Scheduling

Since the script uses a configuration-based approach, it's perfect for automated scheduling:

### Using Cron (Linux/Mac)

```bash
# Run every day at 3 AM
0 3 * * * cd /path/to/meet-up-api && /usr/bin/python3 meetup_events_to_supabase.py >> logs/meetup_sync.log 2>&1
```

### Using Windows Task Scheduler

1. Create a batch file `run_meetup_sync.bat`:
   ```batch
   @echo off
   cd /d "D:\work\capmus\meet-up-api"
   python meetup_events_to_supabase.py >> logs\meetup_sync.log 2>&1
   ```

2. Schedule it in Task Scheduler to run daily

### Using GitHub Actions

Create `.github/workflows/sync_events.yml`:
```yaml
name: Sync Meetup Events
on:
  schedule:
    - cron: '0 3 * * *'  # Daily at 3 AM UTC
  workflow_dispatch:  # Manual trigger

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: python meetup_events_to_supabase.py
        env:
          MEETUP_API_TOKEN: ${{ secrets.MEETUP_API_TOKEN }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
```

## Contributing

This is production-ready code. For improvements:
- Add tests (pytest)
- Implement retry logic for transient failures
- Add logging to files
- Support for incremental updates (date-based filtering)
- Add email/Slack notifications on completion

## License

This code is provided as-is for educational and commercial use.

## Support

For issues with:
- **Meetup API**: Check [Meetup API Documentation](https://www.meetup.com/api/)
- **Supabase**: Check [Supabase Documentation](https://supabase.com/docs)
- **This code**: Review error messages and check environment configuration
