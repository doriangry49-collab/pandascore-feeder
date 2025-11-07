import math
import psycopg2
import psycopg2.extras
from typing import Dict


class PredictionModel:
    """Lightweight heuristic prediction model that avoids heavy ML dependencies.

    Uses stored team stats, recent form and head-to-head aggregates to produce
    a plausible predicted score and win probability. Designed to run in the
    serverless environment without scikit-learn/numpy/pandas.
    """

    def __init__(self, database_url: str):
        self.database_url = database_url

    def _get_db_connection(self):
        return psycopg2.connect(self.database_url)

    def _fetch_team_stats(self, cur, team_id: int):
        cur.execute("""
            SELECT ts.total_matches, ts.wins, ts.losses, ts.rounds_won, ts.rounds_lost, ts.win_rate, ts.avg_rounds_won
            FROM team_stats ts
            WHERE ts.team_id = %s
        """, (team_id,))
        row = cur.fetchone()
        return row if row else None

    def _fetch_recent_form(self, cur, team_id: int, limit: int = 5):
        cur.execute("""
            SELECT winner_id = %s AS won,
                   CASE WHEN team1_id = %s THEN team1_score ELSE team2_score END AS team_score,
                   CASE WHEN team1_id = %s THEN team2_score ELSE team1_score END AS opp_score
            FROM historical_matches
            WHERE (team1_id = %s OR team2_id = %s) AND played_at < NOW()
            ORDER BY played_at DESC
            LIMIT %s
        """, (team_id, team_id, team_id, team_id, team_id, limit))
        return cur.fetchall()

    def _fetch_h2h(self, cur, team1_id: int, team2_id: int, limit: int = 5):
        cur.execute("""
            SELECT winner_id, team1_id, team1_score, team2_score
            FROM historical_matches
            WHERE ((team1_id = %s AND team2_id = %s) OR (team1_id = %s AND team2_id = %s))
              AND played_at < NOW()
            ORDER BY played_at DESC
            LIMIT %s
        """, (team1_id, team2_id, team2_id, team1_id, limit))
        return cur.fetchall()

    def predict_match(self, team1_id: int, team2_id: int) -> Dict:
        """Predict winner/score for a match between team1 and team2.

        Returns a dict with predicted_score, win_probability and confidence.
        """
        with self._get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                t1 = self._fetch_team_stats(cur, team1_id)
                t2 = self._fetch_team_stats(cur, team2_id)

                recent1 = self._fetch_recent_form(cur, team1_id)
                recent2 = self._fetch_recent_form(cur, team2_id)

                h2h = self._fetch_h2h(cur, team1_id, team2_id)

        # Fallback defaults
        t1_win_rate = float(t1['win_rate']) if t1 and t1.get('win_rate') is not None else 50.0
        t2_win_rate = float(t2['win_rate']) if t2 and t2.get('win_rate') is not None else 50.0

        t1_recent_wins = sum(1 for r in recent1 if r.get('won')) if recent1 else 0
        t2_recent_wins = sum(1 for r in recent2 if r.get('won')) if recent2 else 0

        t1_recent_avg_diff = (sum((r['team_score'] - r['opp_score']) for r in recent1) / len(recent1)) if recent1 else 0
        t2_recent_avg_diff = (sum((r['team_score'] - r['opp_score']) for r in recent2) / len(recent2)) if recent2 else 0

        h2h_team1_wins = sum(1 for m in h2h if m['winner_id'] == team1_id)
        h2h_team2_wins = sum(1 for m in h2h if m['winner_id'] == team2_id)

        # Base score (out of 16) starts from 13 (typical CS:GO round targets) and is adjusted
        base_team1 = 13.0 + (t1_win_rate - 50.0) / 20.0 + (t1_recent_wins - t2_recent_wins) * 0.8 + (t1_recent_avg_diff - t2_recent_avg_diff) * 0.15 + (h2h_team1_wins - h2h_team2_wins) * 0.5
        base_team2 = 13.0 + (t2_win_rate - 50.0) / 20.0 + (t2_recent_wins - t1_recent_wins) * 0.8 + (t2_recent_avg_diff - t1_recent_avg_diff) * 0.15 + (h2h_team2_wins - h2h_team1_wins) * 0.5

        # Normalize to 0-16 realistic scores and round
        team1_score = max(0, min(16, round(base_team1)))
        team2_score = max(0, min(16, round(base_team2)))

        # If tie, add small perturbation based on recent form difference
        if team1_score == team2_score:
            if (t1_recent_wins - t2_recent_wins) > 0:
                team1_score = min(16, team1_score + 1)
            elif (t2_recent_wins - t1_recent_wins) > 0:
                team2_score = min(16, team2_score + 1)

        score_diff = team1_score - team2_score

        # Win probability via logistic on score_diff
        prob_team1 = 1.0 / (1.0 + math.exp(-0.4 * score_diff))
        prob_team1_pct = round(prob_team1 * 100, 2)
        prob_team2_pct = round(100 - prob_team1_pct, 2)

        # Confidence: depends on amount of historical data and magnitude of score diff
        data_factor = min(1.0, ( (len(recent1 or []) + len(recent2 or []) + len(h2h or [])) / 15.0 ))
        diff_factor = min(1.0, abs(score_diff) / 8.0)
        confidence = round( (0.4 * data_factor + 0.6 * diff_factor) * 100, 2 )

        return {
            'predicted_score': {'team1': int(team1_score), 'team2': int(team2_score)},
            'win_probability': {'team1': prob_team1_pct, 'team2': prob_team2_pct},
            'confidence': confidence
        }

    def store_prediction(self, match_id: int, team1_id: int, team2_id: int) -> None:
        prediction = self.predict_match(team1_id, team2_id)
        predicted_winner = team1_id if prediction['win_probability']['team1'] > prediction['win_probability']['team2'] else team2_id
        with self._get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO predictions 
                    (match_id, predicted_winner_id, confidence_score, predicted_team1_score, predicted_team2_score, prediction_model)
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
                    predicted_winner,
                    prediction['confidence'],
                    prediction['predicted_score']['team1'],
                    prediction['predicted_score']['team2'],
                    'heuristic_v1'
                ))