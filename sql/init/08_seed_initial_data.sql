-- 08_seed_initial_data.sql
-- Seed data so dashboard and APIs have content on first boot

---------------------------------------------------------------------
-- dim_market
---------------------------------------------------------------------
INSERT INTO dim_market (market_name) VALUES
    ('POINTS'),
    ('REBOUNDS')
ON CONFLICT (market_name) DO NOTHING;

---------------------------------------------------------------------
-- dim_book
---------------------------------------------------------------------
INSERT INTO dim_book (book_name, book_type) VALUES
    ('DraftKings',  'sportsbook'),
    ('FanDuel',     'sportsbook'),
    ('BetMGM',      'sportsbook'),
    ('Caesars',     'sportsbook'),
    ('BetRivers',   'sportsbook'),
    ('ESPNBet',     'sportsbook'),
    ('Underdog',    'dfs')
ON CONFLICT (book_name) DO NOTHING;

---------------------------------------------------------------------
-- dim_date  (2025-10-01 through 2026-06-30)
---------------------------------------------------------------------
INSERT INTO dim_date (date_key, calendar_date, year, quarter, month, day_of_week, day_name, is_weekend, nba_season, season_phase)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INT AS date_key,
    d AS calendar_date,
    EXTRACT(YEAR FROM d)::INT AS year,
    EXTRACT(QUARTER FROM d)::INT AS quarter,
    EXTRACT(MONTH FROM d)::INT AS month,
    EXTRACT(ISODOW FROM d)::INT - 1 AS day_of_week,  -- 0=Mon
    TO_CHAR(d, 'Day') AS day_name,
    EXTRACT(ISODOW FROM d) IN (6, 7) AS is_weekend,
    '2025-26' AS nba_season,
    CASE
        WHEN d < '2025-10-22' THEN 'preseason'
        WHEN d <= '2026-04-13' THEN 'regular'
        WHEN d <= '2026-06-20' THEN 'playoffs'
        ELSE 'offseason'
    END AS season_phase
FROM generate_series('2025-10-01'::DATE, '2026-06-30'::DATE, '1 day') AS d
ON CONFLICT (date_key) DO NOTHING;

---------------------------------------------------------------------
-- predictions  (~50 rows, realistic NBA player props)
---------------------------------------------------------------------
INSERT INTO predictions (player_name, market, model_version, predicted_value, line, p_over, edge_pct, direction, actual_value, result, game_date, created_at) VALUES
    -- 2026-03-20 games (POINTS)
    ('Luka Doncic',       'POINTS',   'xl', 33.2, 31.5, 0.72, 5.4,  'OVER',  35, 'win',  '2026-03-20', '2026-03-20 14:00:00+00'),
    ('Jayson Tatum',      'POINTS',   'v3', 28.7, 27.5, 0.68, 4.4,  'OVER',  30, 'win',  '2026-03-20', '2026-03-20 14:00:00+00'),
    ('Shai Gilgeous-Alexander', 'POINTS', 'xl', 31.5, 30.5, 0.65, 3.3, 'OVER', 28, 'loss', '2026-03-20', '2026-03-20 14:00:00+00'),
    ('Anthony Edwards',   'POINTS',   'v3', 26.1, 25.5, 0.62, 2.4,  'OVER',  29, 'win',  '2026-03-20', '2026-03-20 14:00:00+00'),
    ('Nikola Jokic',      'POINTS',   'xl', 27.8, 26.5, 0.71, 4.9,  'OVER',  31, 'win',  '2026-03-20', '2026-03-20 14:00:00+00'),
    ('Tyrese Haliburton', 'POINTS',   'v3', 21.3, 20.5, 0.64, 3.9,  'OVER',  18, 'loss', '2026-03-20', '2026-03-20 14:00:00+00'),
    ('Donovan Mitchell',  'POINTS',   'xl', 25.4, 24.5, 0.66, 3.7,  'OVER',  27, 'win',  '2026-03-20', '2026-03-20 14:00:00+00'),
    ('LeBron James',      'POINTS',   'v3', 26.9, 25.5, 0.70, 5.5,  'OVER',  28, 'win',  '2026-03-20', '2026-03-20 14:00:00+00'),

    -- 2026-03-20 games (REBOUNDS)
    ('Nikola Jokic',      'REBOUNDS', 'xl', 12.8, 11.5, 0.78, 11.3, 'OVER',  14, 'win',  '2026-03-20', '2026-03-20 14:00:00+00'),
    ('Anthony Davis',     'REBOUNDS', 'v3', 11.4, 10.5, 0.72, 8.6,  'OVER',  12, 'win',  '2026-03-20', '2026-03-20 14:00:00+00'),
    ('Domantas Sabonis',  'REBOUNDS', 'xl', 13.1, 12.5, 0.67, 4.8,  'OVER',  11, 'loss', '2026-03-20', '2026-03-20 14:00:00+00'),
    ('Giannis Antetokounmpo', 'REBOUNDS', 'v3', 11.9, 11.5, 0.61, 3.5, 'OVER', 13, 'win', '2026-03-20', '2026-03-20 14:00:00+00'),

    -- 2026-03-19 games (POINTS)
    ('Stephen Curry',     'POINTS',   'xl', 27.5, 26.5, 0.69, 3.8,  'OVER',  32, 'win',  '2026-03-19', '2026-03-19 14:00:00+00'),
    ('Kevin Durant',      'POINTS',   'v3', 28.3, 27.5, 0.66, 2.9,  'OVER',  25, 'loss', '2026-03-19', '2026-03-19 14:00:00+00'),
    ('Devin Booker',      'POINTS',   'xl', 26.1, 25.5, 0.63, 2.4,  'OVER',  28, 'win',  '2026-03-19', '2026-03-19 14:00:00+00'),
    ('Trae Young',        'POINTS',   'v3', 27.4, 26.5, 0.68, 3.4,  'OVER',  30, 'win',  '2026-03-19', '2026-03-19 14:00:00+00'),
    ('Ja Morant',         'POINTS',   'xl', 25.8, 24.5, 0.71, 5.3,  'OVER',  27, 'win',  '2026-03-19', '2026-03-19 14:00:00+00'),
    ('Damian Lillard',    'POINTS',   'v3', 25.2, 24.5, 0.63, 2.9,  'OVER',  22, 'loss', '2026-03-19', '2026-03-19 14:00:00+00'),
    ('Joel Embiid',       'POINTS',   'xl', 33.1, 31.5, 0.74, 5.1,  'OVER',  36, 'win',  '2026-03-19', '2026-03-19 14:00:00+00'),
    ('De''Aaron Fox',     'POINTS',   'v3', 26.7, 25.5, 0.67, 4.7,  'OVER',  29, 'win',  '2026-03-19', '2026-03-19 14:00:00+00'),

    -- 2026-03-19 games (REBOUNDS)
    ('Rudy Gobert',       'REBOUNDS', 'xl', 12.3, 11.5, 0.70, 7.0,  'OVER',  13, 'win',  '2026-03-19', '2026-03-19 14:00:00+00'),
    ('Bam Adebayo',       'REBOUNDS', 'v3', 10.8, 10.5, 0.59, 2.9,  'OVER',  9,  'loss', '2026-03-19', '2026-03-19 14:00:00+00'),
    ('Karl-Anthony Towns','REBOUNDS', 'xl', 11.6, 10.5, 0.73, 10.5, 'OVER',  12, 'win',  '2026-03-19', '2026-03-19 14:00:00+00'),

    -- 2026-03-18 games (POINTS)
    ('Luka Doncic',       'POINTS',   'v3', 32.8, 31.5, 0.70, 4.1,  'OVER',  34, 'win',  '2026-03-18', '2026-03-18 14:00:00+00'),
    ('Jayson Tatum',      'POINTS',   'xl', 29.1, 27.5, 0.72, 5.8,  'OVER',  26, 'loss', '2026-03-18', '2026-03-18 14:00:00+00'),
    ('Anthony Edwards',   'POINTS',   'v3', 25.9, 25.5, 0.58, 1.6,  'OVER',  27, 'win',  '2026-03-18', '2026-03-18 14:00:00+00'),
    ('Nikola Jokic',      'POINTS',   'xl', 28.2, 26.5, 0.73, 6.4,  'OVER',  29, 'win',  '2026-03-18', '2026-03-18 14:00:00+00'),
    ('Donovan Mitchell',  'POINTS',   'v3', 24.8, 24.5, 0.56, 1.2,  'OVER',  23, 'loss', '2026-03-18', '2026-03-18 14:00:00+00'),
    ('LeBron James',      'POINTS',   'xl', 27.1, 25.5, 0.72, 6.3,  'OVER',  30, 'win',  '2026-03-18', '2026-03-18 14:00:00+00'),

    -- 2026-03-18 games (REBOUNDS)
    ('Nikola Jokic',      'REBOUNDS', 'v3', 13.0, 11.5, 0.80, 13.0, 'OVER',  15, 'win',  '2026-03-18', '2026-03-18 14:00:00+00'),
    ('Anthony Davis',     'REBOUNDS', 'xl', 11.2, 10.5, 0.68, 6.7,  'OVER',  11, 'win',  '2026-03-18', '2026-03-18 14:00:00+00'),
    ('Giannis Antetokounmpo', 'REBOUNDS', 'v3', 12.1, 11.5, 0.63, 5.2, 'OVER', 10, 'loss', '2026-03-18', '2026-03-18 14:00:00+00'),

    -- 2026-03-17 games
    ('Stephen Curry',     'POINTS',   'xl', 28.0, 26.5, 0.71, 5.7,  'OVER',  31, 'win',  '2026-03-17', '2026-03-17 14:00:00+00'),
    ('Kevin Durant',      'POINTS',   'v3', 27.9, 27.5, 0.57, 1.5,  'OVER',  29, 'win',  '2026-03-17', '2026-03-17 14:00:00+00'),
    ('Trae Young',        'POINTS',   'xl', 26.8, 26.5, 0.55, 1.1,  'OVER',  24, 'loss', '2026-03-17', '2026-03-17 14:00:00+00'),
    ('Joel Embiid',       'POINTS',   'v3', 32.5, 31.5, 0.68, 3.2,  'OVER',  35, 'win',  '2026-03-17', '2026-03-17 14:00:00+00'),
    ('Ja Morant',         'POINTS',   'xl', 25.3, 24.5, 0.66, 3.3,  'OVER',  26, 'win',  '2026-03-17', '2026-03-17 14:00:00+00'),

    -- 2026-03-16 games
    ('Luka Doncic',       'POINTS',   'xl', 33.5, 31.5, 0.75, 6.3,  'OVER',  37, 'win',  '2026-03-16', '2026-03-16 14:00:00+00'),
    ('Shai Gilgeous-Alexander', 'POINTS', 'v3', 32.0, 30.5, 0.71, 4.9, 'OVER', 33, 'win', '2026-03-16', '2026-03-16 14:00:00+00'),
    ('Jayson Tatum',      'POINTS',   'xl', 28.4, 27.5, 0.64, 3.3,  'OVER',  25, 'loss', '2026-03-16', '2026-03-16 14:00:00+00'),
    ('Nikola Jokic',      'REBOUNDS', 'xl', 12.5, 11.5, 0.74, 8.7,  'OVER',  14, 'win',  '2026-03-16', '2026-03-16 14:00:00+00'),
    ('Domantas Sabonis',  'REBOUNDS', 'v3', 12.8, 12.5, 0.59, 2.4,  'OVER',  13, 'win',  '2026-03-16', '2026-03-16 14:00:00+00'),
    ('Rudy Gobert',       'REBOUNDS', 'xl', 11.9, 11.5, 0.62, 3.5,  'OVER',  10, 'loss', '2026-03-16', '2026-03-16 14:00:00+00'),

    -- 2026-03-15 games
    ('Anthony Edwards',   'POINTS',   'xl', 26.4, 25.5, 0.65, 3.5,  'OVER',  28, 'win',  '2026-03-15', '2026-03-15 14:00:00+00'),
    ('Damian Lillard',    'POINTS',   'v3', 25.6, 24.5, 0.67, 4.5,  'OVER',  27, 'win',  '2026-03-15', '2026-03-15 14:00:00+00'),
    ('Devin Booker',      'POINTS',   'xl', 25.8, 25.5, 0.56, 1.2,  'OVER',  24, 'loss', '2026-03-15', '2026-03-15 14:00:00+00'),
    ('De''Aaron Fox',     'POINTS',   'v3', 27.0, 25.5, 0.70, 5.9,  'OVER',  30, 'win',  '2026-03-15', '2026-03-15 14:00:00+00'),
    ('Bam Adebayo',       'REBOUNDS', 'xl', 10.9, 10.5, 0.60, 3.8,  'OVER',  11, 'win',  '2026-03-15', '2026-03-15 14:00:00+00'),
    ('Karl-Anthony Towns','REBOUNDS', 'v3', 11.3, 10.5, 0.71, 7.6,  'OVER',  12, 'win',  '2026-03-15', '2026-03-15 14:00:00+00');


---------------------------------------------------------------------
-- line_snapshots  (~200 rows across multiple books)
---------------------------------------------------------------------
DO $$
DECLARE
    v_players TEXT[] := ARRAY[
        'Luka Doncic', 'Jayson Tatum', 'Shai Gilgeous-Alexander', 'Anthony Edwards',
        'Nikola Jokic', 'Stephen Curry', 'Kevin Durant', 'Devin Booker',
        'Trae Young', 'Ja Morant', 'LeBron James', 'Joel Embiid',
        'Donovan Mitchell', 'Damian Lillard', 'De''Aaron Fox', 'Tyrese Haliburton',
        'Anthony Davis', 'Giannis Antetokounmpo', 'Domantas Sabonis', 'Rudy Gobert'
    ];
    v_books TEXT[] := ARRAY['DraftKings', 'FanDuel', 'BetMGM', 'Caesars', 'BetRivers', 'ESPNBet', 'Underdog'];
    v_base_lines REAL[] := ARRAY[31.5, 27.5, 30.5, 25.5, 26.5, 26.5, 27.5, 25.5, 26.5, 24.5, 25.5, 31.5, 24.5, 24.5, 25.5, 20.5, 10.5, 11.5, 12.5, 11.5];
    v_markets TEXT[] := ARRAY['POINTS','POINTS','POINTS','POINTS','POINTS','POINTS','POINTS','POINTS','POINTS','POINTS','POINTS','POINTS','POINTS','POINTS','POINTS','POINTS','REBOUNDS','REBOUNDS','REBOUNDS','REBOUNDS'];
    v_player TEXT;
    v_book TEXT;
    v_base REAL;
    v_mkt TEXT;
    i INT;
    j INT;
    v_offset REAL;
BEGIN
    FOR i IN 1..array_length(v_players, 1) LOOP
        v_player := v_players[i];
        v_base := v_base_lines[i];
        v_mkt := v_markets[i];
        FOR j IN 1..array_length(v_books, 1) LOOP
            v_book := v_books[j];
            -- Vary lines slightly per book: some 0.5 higher, some 0.5 lower
            v_offset := CASE
                WHEN j IN (1, 7) THEN 0.5    -- DK and Underdog often softer
                WHEN j IN (3, 4) THEN -0.5   -- BetMGM, Caesars sharper
                ELSE 0
            END;
            INSERT INTO line_snapshots (player_name, market, book_name, line_value, captured_at)
            VALUES (v_player, v_mkt, v_book, v_base + v_offset, '2026-03-20 12:00:00+00');
            -- Second snapshot 2 hours later with slight movement
            INSERT INTO line_snapshots (player_name, market, book_name, line_value, captured_at)
            VALUES (v_player, v_mkt, v_book, v_base + v_offset + (CASE WHEN j % 3 = 0 THEN 0.5 ELSE 0 END), '2026-03-20 14:00:00+00');
        END LOOP;
    END LOOP;
END $$;


---------------------------------------------------------------------
-- pick_history  (~30 entries)
---------------------------------------------------------------------
INSERT INTO pick_history (player_name, market, direction, conviction, tier, model_version, book_name, line, result, game_date) VALUES
    ('Luka Doncic',       'POINTS',   'OVER', 'STRONG', 'X',    'xl', 'DraftKings', 32.0, 'win',  '2026-03-20'),
    ('Jayson Tatum',      'POINTS',   'OVER', 'LEAN',   'Z',    'v3', 'FanDuel',    27.5, 'win',  '2026-03-20'),
    ('Shai Gilgeous-Alexander', 'POINTS', 'OVER', 'LEAN', 'Z', 'xl', 'BetMGM',     30.0, 'loss', '2026-03-20'),
    ('Anthony Edwards',   'POINTS',   'OVER', 'LEAN',   'A',    'v3', 'Caesars',    25.5, 'win',  '2026-03-20'),
    ('Nikola Jokic',      'POINTS',   'OVER', 'STRONG', 'X',    'xl', 'DraftKings', 27.0, 'win',  '2026-03-20'),
    ('Nikola Jokic',      'REBOUNDS', 'OVER', 'LOCKED', 'META', 'xl', 'Underdog',   12.0, 'win',  '2026-03-20'),
    ('Anthony Davis',     'REBOUNDS', 'OVER', 'STRONG', 'META', 'v3', 'FanDuel',    10.5, 'win',  '2026-03-20'),
    ('LeBron James',      'POINTS',   'OVER', 'STRONG', 'X',    'v3', 'DraftKings', 26.0, 'win',  '2026-03-20'),

    ('Stephen Curry',     'POINTS',   'OVER', 'STRONG', 'X',    'xl', 'FanDuel',    27.0, 'win',  '2026-03-19'),
    ('Joel Embiid',       'POINTS',   'OVER', 'LOCKED', 'X',    'xl', 'DraftKings', 32.0, 'win',  '2026-03-19'),
    ('Trae Young',        'POINTS',   'OVER', 'LEAN',   'Z',    'v3', 'BetRivers',  26.5, 'win',  '2026-03-19'),
    ('Kevin Durant',      'POINTS',   'OVER', 'LEAN',   'A',    'v3', 'Caesars',    27.5, 'loss', '2026-03-19'),
    ('Ja Morant',         'POINTS',   'OVER', 'STRONG', 'X',    'xl', 'Underdog',   25.0, 'win',  '2026-03-19'),
    ('Rudy Gobert',       'REBOUNDS', 'OVER', 'STRONG', 'META', 'xl', 'FanDuel',    11.5, 'win',  '2026-03-19'),
    ('Karl-Anthony Towns','REBOUNDS', 'OVER', 'LOCKED', 'META', 'xl', 'DraftKings', 11.0, 'win',  '2026-03-19'),
    ('Damian Lillard',    'POINTS',   'OVER', 'LEAN',   'Z',    'v3', 'ESPNBet',    24.5, 'loss', '2026-03-19'),

    ('Luka Doncic',       'POINTS',   'OVER', 'STRONG', 'X',    'v3', 'FanDuel',    32.0, 'win',  '2026-03-18'),
    ('Nikola Jokic',      'POINTS',   'OVER', 'STRONG', 'X',    'xl', 'DraftKings', 27.0, 'win',  '2026-03-18'),
    ('Nikola Jokic',      'REBOUNDS', 'OVER', 'LOCKED', 'META', 'v3', 'Underdog',   12.0, 'win',  '2026-03-18'),
    ('LeBron James',      'POINTS',   'OVER', 'STRONG', 'X',    'xl', 'BetRivers',  26.0, 'win',  '2026-03-18'),
    ('Jayson Tatum',      'POINTS',   'OVER', 'LEAN',   'Z',    'xl', 'BetMGM',     27.5, 'loss', '2026-03-18'),
    ('Anthony Edwards',   'POINTS',   'OVER', 'LEAN',   'A',    'v3', 'FanDuel',    25.5, 'win',  '2026-03-18'),

    ('Stephen Curry',     'POINTS',   'OVER', 'STRONG', 'X',    'xl', 'DraftKings', 27.0, 'win',  '2026-03-17'),
    ('Joel Embiid',       'POINTS',   'OVER', 'STRONG', 'X',    'v3', 'FanDuel',    32.0, 'win',  '2026-03-17'),
    ('Kevin Durant',      'POINTS',   'OVER', 'LEAN',   'A',    'v3', 'Caesars',    27.5, 'win',  '2026-03-17'),
    ('Ja Morant',         'POINTS',   'OVER', 'LEAN',   'Z',    'xl', 'Underdog',   25.0, 'win',  '2026-03-17'),
    ('Trae Young',        'POINTS',   'OVER', 'LEAN',   'Z',    'xl', 'ESPNBet',    26.5, 'loss', '2026-03-17'),

    ('Luka Doncic',       'POINTS',   'OVER', 'LOCKED', 'X',    'xl', 'DraftKings', 32.0, 'win',  '2026-03-16'),
    ('Shai Gilgeous-Alexander', 'POINTS', 'OVER', 'STRONG', 'X', 'v3', 'FanDuel', 31.0, 'win', '2026-03-16'),
    ('Nikola Jokic',      'REBOUNDS', 'OVER', 'STRONG', 'META', 'xl', 'Underdog',   12.0, 'win',  '2026-03-16');


---------------------------------------------------------------------
-- pipeline_runs (2-3 recent runs)
---------------------------------------------------------------------
INSERT INTO pipeline_runs (dag_name, run_id, started_at, completed_at, status, rows_processed, props_fetched, predictions_generated, error_message) VALUES
    ('nba_full_pipeline', 'run_20260320_0900', '2026-03-20 14:00:00+00', '2026-03-20 14:04:32+00', 'completed', 2629, 2629, 50, NULL),
    ('nba_validation_pipeline', 'run_20260320_0930', '2026-03-20 14:30:00+00', '2026-03-20 14:31:15+00', 'completed', 42, NULL, NULL, NULL),
    ('nba_full_pipeline', 'run_20260321_0900', '2026-03-21 14:00:00+00', NULL, 'running', NULL, NULL, NULL, NULL);


---------------------------------------------------------------------
-- model_performance (7 days showing ~58% win rate)
---------------------------------------------------------------------
INSERT INTO model_performance (model_version, market, period_date, total_picks, wins, losses, win_rate, roi, avg_edge) VALUES
    ('xl', 'POINTS',   '2026-03-20', 8, 5, 3, 0.625, 8.2, 4.1),
    ('v3', 'POINTS',   '2026-03-20', 6, 4, 2, 0.667, 10.5, 3.8),
    ('xl', 'REBOUNDS', '2026-03-20', 4, 3, 1, 0.750, 15.0, 8.2),
    ('v3', 'REBOUNDS', '2026-03-20', 2, 1, 1, 0.500, -2.5, 4.3),
    ('xl', 'POINTS',   '2026-03-19', 7, 4, 3, 0.571, 5.1, 3.9),
    ('v3', 'POINTS',   '2026-03-19', 5, 3, 2, 0.600, 6.8, 3.4),
    ('xl', 'REBOUNDS', '2026-03-19', 3, 2, 1, 0.667, 8.4, 7.0),
    ('xl', 'POINTS',   '2026-03-18', 5, 3, 2, 0.600, 6.0, 5.5),
    ('v3', 'POINTS',   '2026-03-18', 4, 2, 2, 0.500, -1.2, 2.4),
    ('v3', 'REBOUNDS', '2026-03-18', 3, 2, 1, 0.667, 9.3, 7.7),
    ('xl', 'POINTS',   '2026-03-17', 5, 3, 2, 0.600, 5.5, 3.2),
    ('v3', 'POINTS',   '2026-03-17', 4, 3, 1, 0.750, 12.3, 2.8),
    ('xl', 'REBOUNDS', '2026-03-16', 3, 2, 1, 0.667, 7.0, 6.7),
    ('v3', 'REBOUNDS', '2026-03-16', 2, 1, 1, 0.500, -3.0, 2.4);


---------------------------------------------------------------------
-- api_health_log  (healthy APIs)
---------------------------------------------------------------------
INSERT INTO api_health_log (api_name, status, response_ms, checked_at) VALUES
    ('bettingpros',   'healthy', 342.5, '2026-03-21 14:00:00+00'),
    ('draftkings',    'healthy', 215.8, '2026-03-21 14:00:00+00'),
    ('fanduel',       'healthy', 189.2, '2026-03-21 14:00:00+00'),
    ('betmgm',        'healthy', 410.1, '2026-03-21 14:00:00+00'),
    ('underdog',      'healthy', 275.4, '2026-03-21 14:00:00+00'),
    ('espn_scoreboard','healthy', 95.3,  '2026-03-21 14:00:00+00'),
    ('bettingpros',   'healthy', 338.1, '2026-03-21 08:00:00+00'),
    ('draftkings',    'healthy', 220.3, '2026-03-21 08:00:00+00'),
    ('fanduel',       'healthy', 195.7, '2026-03-21 08:00:00+00');
