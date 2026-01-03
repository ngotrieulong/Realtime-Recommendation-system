-- ============================================================================
-- ENHANCED POSTGRESQL SCHEMA - Movie Recommendation System
-- ============================================================================
-- Includes:
--   1. Core tables (movies, user_profiles, interactions)
--   2. Analytics tables (recommendation_logs, recommendation_feedback)
--   3. Performance optimizations (indexes, partitioning)
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- CORE TABLES - Online Layer
-- ============================================================================

-- Movies table with vector embeddings
CREATE TABLE IF NOT EXISTS movies (
    movie_id            VARCHAR(100) PRIMARY KEY,
    title               VARCHAR(500) NOT NULL,
    description         TEXT,
    genres              JSONB,
    release_year        INTEGER,
    director            VARCHAR(200),
    actors              JSONB,
    avg_rating          FLOAT DEFAULT 0.0,
    total_ratings       INTEGER DEFAULT 0,
    
    -- Vector embedding (768 dimensions for sentence-transformers)
    embedding           VECTOR(768),
    
    -- Metadata
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- Indexes for movies
CREATE INDEX idx_movies_genres ON movies USING GIN (genres);
CREATE INDEX idx_movies_release_year ON movies (release_year);
CREATE INDEX idx_movies_avg_rating ON movies (avg_rating DESC);

-- HNSW index for fast vector similarity search
CREATE INDEX idx_movies_embedding ON movies USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

COMMENT ON TABLE movies IS 'Movie catalog with ML embeddings for similarity search';
COMMENT ON COLUMN movies.embedding IS 'Sentence-BERT embedding (768-dim) for semantic similarity';


-- User profiles with preference vectors
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id                 VARCHAR(100) PRIMARY KEY,
    
    -- Preference vector (exponential moving average of movie embeddings)
    preference_vector       VECTOR(768),
    
    -- Statistics
    total_interactions      INTEGER DEFAULT 0,
    last_interaction_at     TIMESTAMP,
    
    -- Metadata
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

-- Indexes for user_profiles
CREATE INDEX idx_user_profiles_last_interaction ON user_profiles (last_interaction_at DESC);

COMMENT ON TABLE user_profiles IS 'User taste profiles built from interaction history';
COMMENT ON COLUMN user_profiles.preference_vector IS 'Weighted average of interacted movie embeddings';


-- Real-time user interactions (rolling 48-hour window)
CREATE TABLE IF NOT EXISTS rt_user_interactions (
    id                      BIGSERIAL PRIMARY KEY,
    user_id                 VARCHAR(100) NOT NULL,
    movie_id                VARCHAR(100) NOT NULL,
    interaction_type        VARCHAR(20) NOT NULL,  -- click, view, play, rate, favorite
    rating                  INTEGER CHECK (rating >= 1 AND rating <= 5),
    watch_duration_sec      INTEGER,
    session_id              VARCHAR(100),
    
    timestamp               TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE
);

-- Indexes for rt_user_interactions
CREATE INDEX idx_rt_interactions_user_time ON rt_user_interactions (user_id, timestamp DESC);
CREATE INDEX idx_rt_interactions_movie ON rt_user_interactions (movie_id);
CREATE INDEX idx_rt_interactions_timestamp ON rt_user_interactions (timestamp DESC);
CREATE INDEX idx_rt_interactions_type ON rt_user_interactions (interaction_type);

COMMENT ON TABLE rt_user_interactions IS 'Hot storage for recent interactions (24-48h retention)';
COMMENT ON COLUMN rt_user_interactions.interaction_type IS 'User action: click, view, play, rate, favorite';


-- Batch recommendations (pre-computed from ALS model)
CREATE TABLE IF NOT EXISTS batch_recommendations (
    user_id                 VARCHAR(100) PRIMARY KEY,
    
    recommendations         JSONB NOT NULL,  -- [{"movie_id": "m001", "score": 0.95}, ...]
    
    -- Metadata
    algorithm               VARCHAR(50) DEFAULT 'als_collaborative',
    model_version           VARCHAR(100),
    computed_at             TIMESTAMP DEFAULT NOW(),
    expires_at              TIMESTAMP,
    
    -- Quality metrics
    coverage_score          FLOAT,  -- How many candidate movies considered
    diversity_score         FLOAT   -- Genre diversity in recommendations
);

-- Indexes for batch_recommendations
CREATE INDEX idx_batch_recs_computed_at ON batch_recommendations (computed_at DESC);
CREATE INDEX idx_batch_recs_expires_at ON batch_recommendations (expires_at);

COMMENT ON TABLE batch_recommendations IS 'Pre-computed recommendations from nightly batch job';
COMMENT ON COLUMN batch_recommendations.recommendations IS 'Top 50 recommended movies with scores';


-- ============================================================================
-- ANALYTICS TABLES - Offline Layer
-- ============================================================================

-- Recommendation logs (what we served to users)
CREATE TABLE IF NOT EXISTS recommendation_logs (
    id                      BIGSERIAL PRIMARY KEY,
    
    -- User context
    user_id                 VARCHAR(100) NOT NULL,
    session_id              VARCHAR(100),
    
    -- What was recommended
    recommended_movies      JSONB NOT NULL,  -- Full recommendation list
    
    -- How it was generated
    algorithm_source        VARCHAR(50),   -- 'realtime', 'batch', 'hybrid', 'popular'
    algorithm_version       VARCHAR(50),
    model_id                VARCHAR(100),  -- Link to model file in S3
    
    -- Request context
    context                 JSONB,  -- device, page, ab_test_group, etc.
    
    -- Performance metrics
    total_candidates        INTEGER,
    computation_time_ms     INTEGER,
    cache_hit               BOOLEAN DEFAULT FALSE,
    
    -- Timestamp
    timestamp               TIMESTAMP DEFAULT NOW()
);

-- Indexes for recommendation_logs
CREATE INDEX idx_rec_logs_user_time ON recommendation_logs (user_id, timestamp DESC);
CREATE INDEX idx_rec_logs_timestamp ON recommendation_logs (timestamp DESC);
CREATE INDEX idx_rec_logs_algorithm ON recommendation_logs (algorithm_source, timestamp DESC);
CREATE INDEX idx_rec_logs_session ON recommendation_logs (session_id);

-- Partitioning by month for efficient queries (optional, for high volume)
-- ALTER TABLE recommendation_logs PARTITION BY RANGE (timestamp);

COMMENT ON TABLE recommendation_logs IS 'Audit log of all recommendations served to users';
COMMENT ON COLUMN recommendation_logs.algorithm_source IS 'realtime (L2), batch (L3), hybrid, or popular';


-- Recommendation feedback (user responses to recommendations)
CREATE TABLE IF NOT EXISTS recommendation_feedback (
    id                      BIGSERIAL PRIMARY KEY,
    
    -- Link back to recommendation
    rec_log_id              BIGINT NOT NULL,
    
    -- Which movie in the recommendation list
    movie_id                VARCHAR(100) NOT NULL,
    position_in_list        INTEGER,  -- 1-based position (1 = first)
    
    -- User action
    event_type              VARCHAR(50),  -- 'click', 'view', 'play', 'rate', 'skip', 'favorite'
    rating                  INTEGER CHECK (rating >= 1 AND rating <= 5),
    watch_duration_sec      INTEGER,
    
    -- Timing
    timestamp               TIMESTAMP DEFAULT NOW(),
    time_to_event_sec       INTEGER,  -- Time from recommendation to this event
    
    -- Context
    session_id              VARCHAR(100),
    
    FOREIGN KEY (rec_log_id) REFERENCES recommendation_logs(id) ON DELETE CASCADE,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE
);

-- Indexes for recommendation_feedback
CREATE INDEX idx_rec_feedback_rec_log ON recommendation_feedback (rec_log_id);
CREATE INDEX idx_rec_feedback_movie ON recommendation_feedback (movie_id);
CREATE INDEX idx_rec_feedback_event_type ON recommendation_feedback (event_type, timestamp DESC);
CREATE INDEX idx_rec_feedback_timestamp ON recommendation_feedback (timestamp DESC);

COMMENT ON TABLE recommendation_feedback IS 'User responses to specific recommendations (for CTR, conversion tracking)';
COMMENT ON COLUMN recommendation_feedback.position_in_list IS '1-based position for analyzing position bias';


-- Model performance logs (batch job metrics)
CREATE TABLE IF NOT EXISTS model_performance_logs (
    id                      BIGSERIAL PRIMARY KEY,
    
    model_id                VARCHAR(100) NOT NULL,
    algorithm               VARCHAR(50),
    
    -- Training metrics
    rmse                    FLOAT,
    mae                     FLOAT,
    coverage                FLOAT,  -- % of users with recommendations
    
    -- Training details
    total_users_trained     INTEGER,
    total_interactions      BIGINT,
    training_duration_sec   INTEGER,
    
    -- Hyperparameters
    hyperparameters         JSONB,
    
    -- Timestamp
    trained_at              TIMESTAMP DEFAULT NOW()
);

-- Indexes for model_performance_logs
CREATE INDEX idx_model_perf_trained_at ON model_performance_logs (trained_at DESC);
CREATE INDEX idx_model_perf_model_id ON model_performance_logs (model_id);

COMMENT ON TABLE model_performance_logs IS 'Historical tracking of model quality over time';


-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function: Get similar movies using cosine similarity
CREATE OR REPLACE FUNCTION get_similar_movies(
    query_vector VECTOR(768),
    limit_count INTEGER DEFAULT 50,
    excluded_movie_ids VARCHAR[] DEFAULT '{}'
)
RETURNS TABLE (
    movie_id VARCHAR,
    title VARCHAR,
    similarity_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.movie_id,
        m.title,
        1 - (m.embedding <=> query_vector) AS similarity_score
    FROM movies m
    WHERE m.movie_id != ALL(excluded_movie_ids)
    ORDER BY m.embedding <=> query_vector
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_similar_movies IS 'Find similar movies using vector similarity (cosine distance)';


-- Function: Update user preference vector (exponential moving average)
CREATE OR REPLACE FUNCTION update_user_preference(
    p_user_id VARCHAR,
    p_movie_embedding VECTOR(768),
    p_weight FLOAT DEFAULT 0.1
)
RETURNS VOID AS $$
DECLARE
    current_vector VECTOR(768);
    new_vector VECTOR(768);
BEGIN
    -- Get current preference vector
    SELECT preference_vector INTO current_vector
    FROM user_profiles
    WHERE user_id = p_user_id;
    
    -- If user has no profile yet, use movie embedding directly
    IF current_vector IS NULL THEN
        new_vector := p_movie_embedding;
    ELSE
        -- Exponential moving average: new = (1 - weight) * old + weight * new_movie
        -- Note: Vector arithmetic in pgvector
        SELECT ((1 - p_weight) * current_vector + p_weight * p_movie_embedding)::VECTOR(768) INTO new_vector;
    END IF;
    
    -- Upsert user profile
    INSERT INTO user_profiles (user_id, preference_vector, total_interactions, last_interaction_at, updated_at)
    VALUES (p_user_id, new_vector, 1, NOW(), NOW())
    ON CONFLICT (user_id) DO UPDATE
    SET preference_vector = new_vector,
        total_interactions = user_profiles.total_interactions + 1,
        last_interaction_at = NOW(),
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_user_preference IS 'Update user taste vector with exponential moving average';


-- ============================================================================
-- SAMPLE DATA
-- ============================================================================

-- Insert sample movies with embeddings
INSERT INTO movies (movie_id, title, description, genres, release_year, director, embedding) VALUES
(
    'm001',
    'The Shawshank Redemption',
    'Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.',
    '["Drama"]',
    1994,
    'Frank Darabont',
    -- Mock embedding (in production, generate with Sentence-BERT)
    ARRAY(SELECT random() FROM generate_series(1, 768))::VECTOR(768)
),
(
    'm002',
    'Interstellar',
    'A team of explorers travel through a wormhole in space in an attempt to ensure humanity''s survival.',
    '["Sci-Fi", "Drama", "Adventure"]',
    2014,
    'Christopher Nolan',
    ARRAY(SELECT random() FROM generate_series(1, 768))::VECTOR(768)
),
(
    'm003',
    'The Matrix',
    'A computer hacker learns from mysterious rebels about the true nature of his reality and his role in the war against its controllers.',
    '["Sci-Fi", "Action"]',
    1999,
    'Lana Wachowski, Lilly Wachowski',
    ARRAY(SELECT random() FROM generate_series(1, 768))::VECTOR(768)
),
(
    'm004',
    'Inception',
    'A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea.',
    '["Sci-Fi", "Thriller", "Action"]',
    2010,
    'Christopher Nolan',
    ARRAY(SELECT random() FROM generate_series(1, 768))::VECTOR(768)
),
(
    'm005',
    'The Dark Knight',
    'When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest tests.',
    '["Action", "Crime", "Drama"]',
    2008,
    'Christopher Nolan',
    ARRAY(SELECT random() FROM generate_series(1, 768))::VECTOR(768)
)
ON CONFLICT (movie_id) DO NOTHING;

-- Insert sample user profile
INSERT INTO user_profiles (user_id, preference_vector, total_interactions, last_interaction_at) VALUES
(
    'user_demo',
    ARRAY(SELECT random() FROM generate_series(1, 768))::VECTOR(768),
    10,
    NOW() - INTERVAL '1 hour'
)
ON CONFLICT (user_id) DO NOTHING;

-- Insert sample interactions
INSERT INTO rt_user_interactions (user_id, movie_id, interaction_type, rating, timestamp) VALUES
('user_demo', 'm002', 'click', NULL, NOW() - INTERVAL '2 hours'),
('user_demo', 'm002', 'view', NULL, NOW() - INTERVAL '2 hours'),
('user_demo', 'm002', 'play', NULL, NOW() - INTERVAL '2 hours'),
('user_demo', 'm002', 'rate', 5, NOW() - INTERVAL '1 hour')
ON CONFLICT DO NOTHING;

-- Insert sample batch recommendations
INSERT INTO batch_recommendations (user_id, recommendations, algorithm, model_version, computed_at, expires_at) VALUES
(
    'user_demo',
    '[
        {"movie_id": "m003", "score": 0.94, "title": "The Matrix"},
        {"movie_id": "m004", "score": 0.91, "title": "Inception"},
        {"movie_id": "m005", "score": 0.88, "title": "The Dark Knight"}
    ]'::JSONB,
    'als_collaborative',
    'als_20250102_02am',
    NOW(),
    NOW() + INTERVAL '24 hours'
)
ON CONFLICT (user_id) DO NOTHING;


-- ============================================================================
-- ANALYTICS VIEWS (Optional - for easy querying)
-- ============================================================================

-- View: CTR by algorithm source
CREATE OR REPLACE VIEW v_ctr_by_algorithm AS
SELECT 
    l.algorithm_source,
    COUNT(DISTINCT l.id) as total_recommendations,
    COUNT(DISTINCT CASE WHEN f.event_type = 'click' THEN l.id END) as clicked_recommendations,
    ROUND(
        COUNT(DISTINCT CASE WHEN f.event_type = 'click' THEN l.id END) * 100.0 / 
        NULLIF(COUNT(DISTINCT l.id), 0),
        2
    ) as ctr_percent
FROM recommendation_logs l
LEFT JOIN recommendation_feedback f ON l.id = f.rec_log_id
WHERE l.timestamp > NOW() - INTERVAL '7 days'
GROUP BY l.algorithm_source;

COMMENT ON VIEW v_ctr_by_algorithm IS 'Click-through rate comparison across algorithms';


-- View: Position bias analysis
CREATE OR REPLACE VIEW v_position_bias AS
SELECT 
    f.position_in_list,
    COUNT(*) as impressions,
    COUNT(CASE WHEN f.event_type = 'click' THEN 1 END) as clicks,
    ROUND(
        COUNT(CASE WHEN f.event_type = 'click' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(*), 0),
        2
    ) as ctr_percent
FROM recommendation_feedback f
WHERE f.timestamp > NOW() - INTERVAL '7 days'
GROUP BY f.position_in_list
ORDER BY f.position_in_list;

COMMENT ON VIEW v_position_bias IS 'Analyze if users click more on top positions';


-- ============================================================================
-- GRANTS (Security)
-- ============================================================================

-- Grant permissions to application user
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO app_user;


-- ============================================================================
-- MAINTENANCE
-- ============================================================================

-- Analyze tables for query optimization
ANALYZE movies;
ANALYZE user_profiles;
ANALYZE rt_user_interactions;
ANALYZE batch_recommendations;
ANALYZE recommendation_logs;
ANALYZE recommendation_feedback;

COMMENT ON DATABASE postgres IS 'Movie Recommendation System - Enhanced with analytics tracking';