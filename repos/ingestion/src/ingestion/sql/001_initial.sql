-- Initial DuckDB schema. Future changes require explicit migrations.
CREATE TABLE IF NOT EXISTS players (
    player_id UUID NOT NULL,
    player_name VARCHAR NOT NULL,
    player_short_name VARCHAR NOT NULL,
    external_id VARCHAR NOT NULL,
    slug VARCHAR,
    photo_url VARCHAR,
    PRIMARY KEY (player_id)
);

CREATE TABLE IF NOT EXISTS teams (
    team_id UUID NOT NULL,
    team_name VARCHAR NOT NULL,
    external_id VARCHAR NOT NULL,
    slug VARCHAR,
    profile_url VARCHAR,
    logo_url VARCHAR,
    PRIMARY KEY (team_id)
);

CREATE TABLE IF NOT EXISTS games (
    game_id UUID NOT NULL,
    team_id_1 UUID NOT NULL,
    team_id_2 UUID NOT NULL,
    external_id VARCHAR,
    tournament VARCHAR,
    competition_name VARCHAR,
    venue VARCHAR,
    scheduled_at TIMESTAMPTZ,
    date_time_raw VARCHAR,
    status VARCHAR,
    period INTEGER,
    clock VARCHAR,
    team_1_score INTEGER,
    team_2_score INTEGER,
    team_1_period_scores INTEGER[],
    team_2_period_scores INTEGER[],
    source_url VARCHAR,
    PRIMARY KEY (game_id),
    FOREIGN KEY (team_id_1) REFERENCES teams(team_id),
    FOREIGN KEY (team_id_2) REFERENCES teams(team_id),
    CHECK (team_id_1 <> team_id_2)
);

CREATE TABLE IF NOT EXISTS game_statistics (
    game_id UUID NOT NULL,
    player_id UUID NOT NULL,
    team_id UUID NOT NULL,
    player_name VARCHAR,
    jersey_number VARCHAR,
    position VARCHAR,
    is_starter BOOLEAN,
    minutes_raw VARCHAR,
    seconds_played INTEGER,
    points INTEGER,
    offensive_rebounds INTEGER,
    defensive_rebounds INTEGER,
    rebounds INTEGER,
    assists INTEGER,
    turnovers INTEGER,
    steals INTEGER,
    blocks INTEGER,
    personal_fouls INTEGER,
    fouls_drawn INTEGER,
    plus_minus INTEGER,
    field_goals_made INTEGER,
    field_goals_attempted INTEGER,
    field_goals_percentage DOUBLE,
    two_pointers_made INTEGER,
    two_pointers_attempted INTEGER,
    two_pointers_percentage DOUBLE,
    three_pointers_made INTEGER,
    three_pointers_attempted INTEGER,
    three_pointers_percentage DOUBLE,
    four_pointers_made INTEGER,
    four_pointers_attempted INTEGER,
    four_pointers_percentage DOUBLE,
    free_throws_made INTEGER,
    free_throws_attempted INTEGER,
    free_throws_percentage DOUBLE,
    PRIMARY KEY (game_id, player_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id UUID PRIMARY KEY,
    source VARCHAR NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    records_written INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    source VARCHAR NOT NULL,
    entity VARCHAR NOT NULL,
    external_id VARCHAR NOT NULL,
    payload_json JSON NOT NULL,
    raw_json JSON NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    run_id UUID NOT NULL REFERENCES ingestion_runs(run_id),
    PRIMARY KEY (source, entity, external_id)
);
