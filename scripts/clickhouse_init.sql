-- ClickHouse initialization for Life Stream module
-- Creates database and tables for high-performance event storage

CREATE DATABASE IF NOT EXISTS life_stream;

-- Main events table with MergeTree engine for fast aggregations
CREATE TABLE IF NOT EXISTS life_stream.events
(
    -- Primary identifiers
    id UUID DEFAULT generateUUIDv4(),
    user_id UUID,
    
    -- Timestamp with millisecond precision
    timestamp DateTime64(3) DEFAULT now64(3),
    
    -- Event classification
    event_type LowCardinality(String),  -- 'geo', 'transaction', 'health', 'social', 'purchase'
    event_subtype LowCardinality(String) DEFAULT '',  -- more specific type
    
    -- Source information
    source LowCardinality(String) DEFAULT 'api',  -- 'api', 'mobile', 'wearable', 'import'
    device_id String DEFAULT '',
    
    -- Geo data (nullable for non-geo events)
    latitude Nullable(Float64),
    longitude Nullable(Float64),
    accuracy Nullable(Float32),  -- GPS accuracy in meters
    altitude Nullable(Float32),
    speed Nullable(Float32),  -- m/s
    
    -- Payload as JSON for flexible schema
    payload String DEFAULT '{}',  -- JSON with event-specific data
    
    -- Metadata
    created_at DateTime64(3) DEFAULT now64(3),
    processed Bool DEFAULT false,
    
    -- Indexing hints
    INDEX idx_event_type event_type TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_payload payload TYPE tokenbf_v1(10240, 3, 0) GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (user_id, timestamp, event_type)
TTL timestamp + INTERVAL 2 YEAR  -- Keep data for 2 years
SETTINGS index_granularity = 8192;

-- Materialized view for geo aggregations (hourly location summary)
CREATE TABLE IF NOT EXISTS life_stream.geo_hourly
(
    user_id UUID,
    hour DateTime,
    center_lat Float64,
    center_lon Float64,
    points_count UInt32,
    total_distance Float64,
    avg_speed Float32,
    max_speed Float32
)
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(hour)
ORDER BY (user_id, hour);

CREATE MATERIALIZED VIEW IF NOT EXISTS life_stream.geo_hourly_mv
TO life_stream.geo_hourly
AS SELECT
    user_id,
    toStartOfHour(timestamp) AS hour,
    avg(latitude) AS center_lat,
    avg(longitude) AS center_lon,
    count() AS points_count,
    0 AS total_distance,  -- Will be calculated by pattern miner
    avg(speed) AS avg_speed,
    max(speed) AS max_speed
FROM life_stream.events
WHERE event_type = 'geo' AND latitude IS NOT NULL
GROUP BY user_id, hour;

-- Table for discovered patterns and insights
CREATE TABLE IF NOT EXISTS life_stream.patterns
(
    id UUID DEFAULT generateUUIDv4(),
    user_id UUID,
    pattern_type LowCardinality(String),  -- 'location_cluster', 'routine', 'habit', 'anomaly'
    name String,
    description String,
    confidence Float32,  -- 0.0 to 1.0
    
    -- Pattern data
    data String DEFAULT '{}',  -- JSON with pattern-specific data
    
    -- Location clusters
    center_lat Nullable(Float64),
    center_lon Nullable(Float64),
    radius Nullable(Float32),
    
    -- Time patterns
    time_pattern String DEFAULT '',  -- Cron-like pattern
    frequency_per_week Float32 DEFAULT 0,
    
    -- Validity
    first_seen DateTime64(3),
    last_seen DateTime64(3),
    occurrences UInt32 DEFAULT 1,
    is_active Bool DEFAULT true,
    
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMM(created_at)
ORDER BY (user_id, pattern_type, name);

-- Table for AI-generated insights (linked to Neo4j)
CREATE TABLE IF NOT EXISTS life_stream.insights
(
    id UUID DEFAULT generateUUIDv4(),
    user_id UUID,
    neo4j_node_id String DEFAULT '',  -- Reference to Neo4j node
    
    insight_type LowCardinality(String),  -- 'habit', 'preference', 'relationship', 'routine'
    title String,
    description String,
    
    -- Evidence
    evidence_event_ids Array(UUID),
    evidence_count UInt32,
    time_range_start DateTime64(3),
    time_range_end DateTime64(3),
    
    -- AI metadata
    ai_model String DEFAULT 'gemini-1.5-flash',
    confidence Float32,
    reasoning String DEFAULT '',
    
    created_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (user_id, insight_type, created_at);

-- Purchases aggregate by category
CREATE TABLE IF NOT EXISTS life_stream.purchase_stats
(
    user_id UUID,
    date Date,
    category LowCardinality(String),
    total_amount Decimal64(2),
    transaction_count UInt32
)
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (user_id, date, category);

CREATE MATERIALIZED VIEW IF NOT EXISTS life_stream.purchase_stats_mv
TO life_stream.purchase_stats
AS SELECT
    user_id,
    toDate(timestamp) AS date,
    JSONExtractString(payload, 'category') AS category,
    toDecimal64(JSONExtractFloat(payload, 'amount'), 2) AS total_amount,
    1 AS transaction_count
FROM life_stream.events
WHERE event_type IN ('purchase', 'transaction');
