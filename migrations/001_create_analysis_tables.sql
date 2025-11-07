-- Analysis tables for CS:GO match predictions

-- Teams table to store team information
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    acronym VARCHAR(10),
    image_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Team statistics table
CREATE TABLE IF NOT EXISTS team_stats (
    team_id INTEGER PRIMARY KEY REFERENCES teams(id),
    total_matches INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0,
    rounds_won INTEGER DEFAULT 0,
    rounds_lost INTEGER DEFAULT 0,
    win_rate DECIMAL(5,2),
    avg_rounds_won DECIMAL(5,2),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_team_stats_team FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
);

-- Historical matches for analysis
CREATE TABLE IF NOT EXISTS historical_matches (
    id INTEGER PRIMARY KEY,
    team1_id INTEGER NOT NULL REFERENCES teams(id),
    team2_id INTEGER NOT NULL REFERENCES teams(id),
    winner_id INTEGER REFERENCES teams(id),
    team1_score INTEGER,
    team2_score INTEGER,
    played_at TIMESTAMP WITH TIME ZONE,
    map_name VARCHAR(50),
    event_name VARCHAR(255),
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_historical_team1 FOREIGN KEY (team1_id) REFERENCES teams(id),
    CONSTRAINT fk_historical_team2 FOREIGN KEY (team2_id) REFERENCES teams(id),
    CONSTRAINT fk_historical_winner FOREIGN KEY (winner_id) REFERENCES teams(id)
);

-- Match predictions table
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id),
    predicted_winner_id INTEGER REFERENCES teams(id),
    confidence_score DECIMAL(5,2),
    predicted_team1_score INTEGER,
    predicted_team2_score INTEGER,
    prediction_model VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_predictions_match FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
    CONSTRAINT fk_predictions_winner FOREIGN KEY (predicted_winner_id) REFERENCES teams(id)
);

-- Create indexes for performance
CREATE INDEX idx_historical_matches_teams ON historical_matches(team1_id, team2_id);
CREATE INDEX idx_historical_matches_winner ON historical_matches(winner_id);
CREATE INDEX idx_historical_matches_played_at ON historical_matches(played_at);
CREATE INDEX idx_predictions_match ON predictions(match_id);
CREATE INDEX idx_team_stats_win_rate ON team_stats(win_rate DESC);