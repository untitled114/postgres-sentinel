-- 03_create_star_schema.sql
-- Dimensional model for analytics

CREATE TABLE IF NOT EXISTS dim_player (
    player_key      SERIAL PRIMARY KEY,
    player_name     VARCHAR(100) NOT NULL,
    team            VARCHAR(10),
    position        VARCHAR(10),
    is_starter      BOOLEAN DEFAULT TRUE,
    row_hash        VARCHAR(64),
    effective_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date        DATE NOT NULL DEFAULT '9999-12-31',
    is_current      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS dim_market (
    market_key      SERIAL PRIMARY KEY,
    market_name     VARCHAR(20) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_book (
    book_key        SERIAL PRIMARY KEY,
    book_name       VARCHAR(50) NOT NULL UNIQUE,
    book_type       VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key        INT PRIMARY KEY,  -- YYYYMMDD
    calendar_date   DATE NOT NULL UNIQUE,
    year            INT NOT NULL,
    quarter         INT NOT NULL,
    month           INT NOT NULL,
    day_of_week     INT NOT NULL,     -- 0=Mon .. 6=Sun
    day_name        VARCHAR(10) NOT NULL,
    is_weekend      BOOLEAN NOT NULL,
    nba_season      VARCHAR(10),      -- e.g. '2025-26'
    season_phase    VARCHAR(20)       -- preseason, regular, playoffs, offseason
);

CREATE TABLE IF NOT EXISTS fact_predictions (
    prediction_key  SERIAL PRIMARY KEY,
    player_key      INT NOT NULL REFERENCES dim_player(player_key),
    market_key      INT NOT NULL REFERENCES dim_market(market_key),
    book_key        INT NOT NULL REFERENCES dim_book(book_key),
    date_key        INT NOT NULL REFERENCES dim_date(date_key),
    model_version   VARCHAR(10) NOT NULL,
    predicted_value REAL,
    line            REAL,
    p_over          REAL,
    edge_pct        REAL,
    actual_value    REAL,
    result          VARCHAR(10),
    conviction      VARCHAR(20),
    tier            VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS model_calibration (
    id              SERIAL PRIMARY KEY,
    model_version   VARCHAR(10) NOT NULL,
    market          VARCHAR(20) NOT NULL,
    probability_bucket REAL NOT NULL,
    predicted_rate  REAL,
    actual_rate     REAL,
    sample_size     INT,
    calculated_date DATE NOT NULL DEFAULT CURRENT_DATE
);
