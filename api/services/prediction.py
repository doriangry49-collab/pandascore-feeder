import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

class PredictionModel:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.scaler = StandardScaler()
        self._train_model()

    def _get_db_connection(self):
        return psycopg2.connect(self.database_url)

    def _prepare_match_features(self, team1_id: int, team2_id: int) -> pd.DataFrame:
        """
        Prepare features for a single match prediction
        """
        with self._get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get team stats
                cur.execute("""
                    SELECT 
                        t.id as team_id,
                        t.name as team_name,
                        ts.total_matches,
                        ts.wins,
                        ts.losses,
                        ts.rounds_won,
                        ts.rounds_lost,
                        ts.win_rate,
                        ts.avg_rounds_won
                    FROM teams t
                    LEFT JOIN team_stats ts ON t.id = ts.team_id
                    WHERE t.id IN (%s, %s)
                """, (team1_id, team2_id))
                
                team_stats = {row['team_id']: row for row in cur.fetchall()}

                # Get recent form (last 5 matches)
                def get_recent_form(team_id):
                    cur.execute("""
                        SELECT 
                            winner_id = %s as won,
                            CASE 
                                WHEN team1_id = %s THEN team1_score 
                                ELSE team2_score 
                            END as team_score,
                            CASE 
                                WHEN team1_id = %s THEN team2_score 
                                ELSE team1_score 
                            END as opponent_score
                        FROM historical_matches
                        WHERE (team1_id = %s OR team2_id = %s)
                        AND played_at < NOW()
                        ORDER BY played_at DESC
                        LIMIT 5
                    """, (team_id, team_id, team_id, team_id, team_id))
                    return cur.fetchall()

                team1_form = get_recent_form(team1_id)
                team2_form = get_recent_form(team2_id)

                # Get head-to-head history
                cur.execute("""
                    SELECT 
                        winner_id,
                        team1_id,
                        team1_score,
                        team2_score
                    FROM historical_matches
                    WHERE (team1_id = %s AND team2_id = %s)
                        OR (team1_id = %s AND team2_id = %s)
                    AND played_at < NOW()
                    ORDER BY played_at DESC
                    LIMIT 5
                """, (team1_id, team2_id, team2_id, team1_id))
                
                h2h_matches = cur.fetchall()

        # Calculate features
        features = {
            # Team 1 stats
            'team1_win_rate': team_stats[team1_id]['win_rate'] if team1_id in team_stats else 50,
            'team1_avg_rounds': team_stats[team1_id]['avg_rounds_won'] if team1_id in team_stats else 0,
            'team1_total_matches': team_stats[team1_id]['total_matches'] if team1_id in team_stats else 0,
            
            # Team 2 stats
            'team2_win_rate': team_stats[team2_id]['win_rate'] if team2_id in team_stats else 50,
            'team2_avg_rounds': team_stats[team2_id]['avg_rounds_won'] if team2_id in team_stats else 0,
            'team2_total_matches': team_stats[team2_id]['total_matches'] if team2_id in team_stats else 0,
            
            # Recent form features
            'team1_recent_wins': sum(1 for m in team1_form if m['won']),
            'team1_recent_avg_score': np.mean([m['team_score'] for m in team1_form]) if team1_form else 0,
            'team1_recent_avg_diff': np.mean([m['team_score'] - m['opponent_score'] for m in team1_form]) if team1_form else 0,
            
            'team2_recent_wins': sum(1 for m in team2_form if m['won']),
            'team2_recent_avg_score': np.mean([m['team_score'] for m in team2_form]) if team2_form else 0,
            'team2_recent_avg_diff': np.mean([m['team_score'] - m['opponent_score'] for m in team2_form]) if team2_form else 0,
            
            # Head-to-head features
            'h2h_matches': len(h2h_matches),
            'h2h_team1_wins': sum(1 for m in h2h_matches if m['winner_id'] == team1_id),
            'h2h_avg_score_diff': np.mean([
                (m['team1_score'] - m['team2_score']) if m['team1_id'] == team1_id 
                else (m['team2_score'] - m['team1_score']) 
                for m in h2h_matches
            ]) if h2h_matches else 0
        }
        
        return pd.DataFrame([features])

    def _train_model(self):
        """
        Train the prediction model using historical match data
        """
        with self._get_db_connection() as conn:
            # Load all completed matches with sufficient history
            query = """
                SELECT 
                    hm.*,
                    t1s.win_rate as team1_win_rate,
                    t1s.avg_rounds_won as team1_avg_rounds,
                    t1s.total_matches as team1_total_matches,
                    t2s.win_rate as team2_win_rate,
                    t2s.avg_rounds_won as team2_avg_rounds,
                    t2s.total_matches as team2_total_matches
                FROM historical_matches hm
                JOIN team_stats t1s ON hm.team1_id = t1s.team_id
                JOIN team_stats t2s ON hm.team2_id = t2s.team_id
                WHERE hm.played_at < NOW()
                AND hm.winner_id IS NOT NULL
                ORDER BY hm.played_at DESC
                LIMIT 1000
            """
            matches_df = pd.read_sql(query, conn)
            
            if len(matches_df) < 100:  # Not enough data to train
                return
            
            # Prepare features and target variables
            X = matches_df[[
                'team1_win_rate', 'team1_avg_rounds', 'team1_total_matches',
                'team2_win_rate', 'team2_avg_rounds', 'team2_total_matches'
            ]]
            y = matches_df[['team1_score', 'team2_score']]
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Train model
            self.model.fit(X_scaled, y)

    def predict_match(self, team1_id: int, team2_id: int) -> Dict:
        """
        Predict the outcome of a match between two teams
        """
        # Prepare features for prediction
        features_df = self._prepare_match_features(team1_id, team2_id)
        features_scaled = self.scaler.transform(features_df)
        
        # Make prediction
        predicted_scores = self.model.predict(features_scaled)[0]
        team1_score, team2_score = map(lambda x: max(0, round(x)), predicted_scores)
        
        # Calculate win probability based on feature importance
        team1_features = features_df.iloc[0]
        win_probability = 50 + (
            (team1_features['team1_win_rate'] - team1_features['team2_win_rate']) * 0.3 +
            (team1_features['team1_recent_wins'] - team1_features['team2_recent_wins']) * 10 +
            (team1_features['team1_recent_avg_diff'] - team1_features['team2_recent_avg_diff']) * 2 +
            (team1_features['h2h_avg_score_diff']) * 5
        )
        win_probability = max(5, min(95, win_probability))  # Clip between 5% and 95%
        
        return {
            'predicted_score': {
                'team1': int(team1_score),
                'team2': int(team2_score)
            },
            'win_probability': {
                'team1': round(win_probability, 2),
                'team2': round(100 - win_probability, 2)
            },
            'confidence': round(
                max(win_probability, 100 - win_probability) / 100 * 
                (1 - abs(team1_score - team2_score) / max(team1_score + team2_score, 1)), 
                2
            )
        }

    def store_prediction(self, match_id: int, team1_id: int, team2_id: int) -> None:
        """
        Generate and store prediction for a match
        """
        prediction = self.predict_match(team1_id, team2_id)
        
        with self._get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO predictions 
                    (match_id, predicted_winner_id, confidence_score, 
                     predicted_team1_score, predicted_team2_score, prediction_model)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (match_id) DO UPDATE SET
                        predicted_winner_id = EXCLUDED.predicted_winner_id,
                        confidence_score = EXCLUDED.confidence_score,
                        predicted_team1_score = EXCLUDED.predicted_team1_score,
                        predicted_team2_score = EXCLUDED.predicted_team2_score,
                        prediction_model = EXCLUDED.prediction_model,
                        created_at = NOW()
                """, (
                    match_id,
                    team1_id if prediction['win_probability']['team1'] > 50 else team2_id,
                    prediction['confidence'],
                    prediction['predicted_score']['team1'],
                    prediction['predicted_score']['team2'],
                    'random_forest_v1'
                ))