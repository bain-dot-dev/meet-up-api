-- Supabase Schema for Meetup Events
-- Run this script in your Supabase SQL Editor

-- Create the staging schema
CREATE SCHEMA IF NOT EXISTS staging_meetup;

-- Main table for storing Meetup events
CREATE TABLE IF NOT EXISTS staging_meetup.meetup_events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    event_url TEXT,
    date_time TIMESTAMPTZ,
    group_id TEXT,
    group_name TEXT,
    group_urlname TEXT,
    venue_name TEXT,
    venue_city TEXT,
    venue_state TEXT,
    venue_country TEXT,
    venue_lat DOUBLE PRECISION,
    venue_lon DOUBLE PRECISION,
    topic_keyword TEXT,
    search_lat DOUBLE PRECISION,
    search_lon DOUBLE PRECISION,
    search_radius_km DOUBLE PRECISION,
    raw_event JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for topic-based queries
CREATE INDEX IF NOT EXISTS idx_meetup_events_topic_keyword
ON staging_meetup.meetup_events(topic_keyword);

-- Index for date-based queries
CREATE INDEX IF NOT EXISTS idx_meetup_events_date_time
ON staging_meetup.meetup_events(date_time DESC);

-- Index for location-based queries
CREATE INDEX IF NOT EXISTS idx_meetup_events_search_location
ON staging_meetup.meetup_events(search_lat, search_lon);

-- Index for venue location queries
CREATE INDEX IF NOT EXISTS idx_meetup_events_venue_location
ON staging_meetup.meetup_events(venue_lat, venue_lon);

-- Index for group queries
CREATE INDEX IF NOT EXISTS idx_meetup_events_group_id
ON staging_meetup.meetup_events(group_id);

-- GIN index for full-text search on raw_event JSONB
CREATE INDEX IF NOT EXISTS idx_meetup_events_raw_event
ON staging_meetup.meetup_events USING GIN(raw_event);

-- Composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_meetup_events_topic_date
ON staging_meetup.meetup_events(topic_keyword, date_time DESC);

-- Trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_meetup_events_updated_at
BEFORE UPDATE ON staging_meetup.meetup_events
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
