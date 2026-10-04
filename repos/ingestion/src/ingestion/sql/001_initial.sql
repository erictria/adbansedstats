CREATE TABLE IF NOT EXISTS leagues (
    league_id UUID PRIMARY KEY,
    league_name VARCHAR NOT NULL,
    abbreviation VARCHAR, external_id VARCHAR, slug VARCHAR, website_url VARCHAR
);
CREATE TABLE IF NOT EXISTS tournaments (
    tournament_id UUID PRIMARY KEY,
    league_id UUID NOT NULL REFERENCES leagues(league_id),
    tournament_name VARCHAR NOT NULL,
    season VARCHAR, external_id VARCHAR, slug VARCHAR, source_url VARCHAR
);

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
    tournament_id UUID,
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

CREATE TABLE IF NOT EXISTS tournament_teams (
    source VARCHAR,
    retrieved_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    tournament_id UUID NOT NULL,
    team_id UUID NOT NULL,
    PRIMARY KEY (tournament_id, team_id)
);

CREATE TABLE IF NOT EXISTS roster_memberships (
    source VARCHAR,
    retrieved_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    roster_id UUID NOT NULL,
    player_id UUID NOT NULL,
    team_id UUID NOT NULL,
    tournament_id UUID NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    jersey_number VARCHAR,
    PRIMARY KEY (roster_id)
);

CREATE TABLE IF NOT EXISTS source_mappings (
    source VARCHAR NOT NULL,
    retrieved_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    entity_type VARCHAR NOT NULL,
    external_id VARCHAR NOT NULL,
    scope VARCHAR NOT NULL,
    internal_id UUID NOT NULL,
    PRIMARY KEY (source, entity_type, scope, external_id)
);

CREATE TABLE IF NOT EXISTS team_game_statistics (
    source VARCHAR,
    retrieved_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    game_id UUID NOT NULL,
    team_id UUID NOT NULL,
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
    PRIMARY KEY (game_id, team_id)
);
