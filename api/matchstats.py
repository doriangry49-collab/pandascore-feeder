import os
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from .services.analysis import AnalysisService
from .services.prediction import PredictionModel

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Check required environment variables
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                self.send_error(500, "Missing DATABASE_URL environment variable")
                return

            # Parse query parameters
            query = parse_qs(urlparse(self.path).query)

            # Initialize services
            analysis_service = AnalysisService(database_url)
            prediction_model = PredictionModel(database_url)

            if 'match_id' in query:
                # Full match analysis
                match_id = int(query['match_id'][0])
                response_data = self._analyze_match(match_id, analysis_service, prediction_model)
            
            elif 'team1_id' in query and 'team2_id' in query:
                # Quick analysis without storing
                team1_id = int(query['team1_id'][0])
                team2_id = int(query['team2_id'][0])
                response_data = self._analyze_teams(team1_id, team2_id, analysis_service, prediction_model)

            elif 'team_id' in query:
                # Single team analysis
                team_id = int(query['team_id'][0])
                response_data = self._analyze_team(team_id, analysis_service, prediction_model)
            
            else:
                self.send_error(400, "Missing required parameters. Use either 'match_id', 'team_id', or 'team1_id' and 'team2_id'")
                return

            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode())

        except Exception as e:
            self.send_error(500, str(e))

    def _fetch_match_details(self, match_id: int):
        """Fetch basic match details from database"""
        import psycopg2
        import psycopg2.extras

        database_url = os.getenv('DATABASE_URL')
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT m.*, 
                           t1.name as team1_name, t1.image_url as team1_image,
                           t2.name as team2_name, t2.image_url as team2_image
                    FROM matches m
                    LEFT JOIN teams t1 ON m.team1_id = t1.id
                    LEFT JOIN teams t2 ON m.team2_id = t2.id
                    WHERE m.id = %s
                """, (match_id,))
                match = cur.fetchone()
                return dict(match) if match else None

    def _analyze_match(self, match_id: int, analysis_service: AnalysisService, prediction_model: PredictionModel):
        """Full analysis for a specific match"""
        # Get match details
        match = self._fetch_match_details(match_id)
        if not match:
            return {"error": "Match not found"}

        team1_id = match['team1_id']
        team2_id = match['team2_id']

        # Get all analyses
        analysis = self._analyze_teams(team1_id, team2_id, analysis_service, prediction_model)
        
        # Add match details
        analysis['match'] = {
            'id': match_id,
            'scheduled_at': match['scheduled_at'].isoformat() if match['scheduled_at'] else None,
            'team1': {
                'id': team1_id,
                'name': match['team1_name'],
                'image_url': match['team1_image']
            },
            'team2': {
                'id': team2_id,
                'name': match['team2_name'],
                'image_url': match['team2_image']
            },
            'event': {
                'name': match.get('league_name'),
                'series': match.get('series_name')
            }
        }

        # Store prediction
        prediction_model.store_prediction(match_id, team1_id, team2_id)

        return analysis

    def _analyze_teams(self, team1_id: int, team2_id: int, analysis_service: AnalysisService, prediction_model: PredictionModel):
        """Analysis of two teams (for match prediction)"""
        return {
            # Team form and performance analysis
            'analysis': analysis_service.analyze_teams(team1_id, team2_id),
            
            # Map performance comparison
            'maps': {
                'team1': analysis_service.get_map_performance(team1_id),
                'team2': analysis_service.get_map_performance(team2_id)
            },
            
            # Match prediction
            'prediction': prediction_model.predict_match(team1_id, team2_id)
        }

    def _analyze_team(self, team_id: int, analysis_service: AnalysisService, prediction_model: PredictionModel):
        """Detailed analysis of a single team"""
        return {
            'form': analysis_service.get_team_form(team_id),
            'maps': analysis_service.get_map_performance(team_id),
            
            # Get recent matches from form analysis
            'recent_matches': analysis_service.get_team_form(team_id, last_n_matches=10)['recent_results'],
            
            # Include upcoming matches if available
            'upcoming_matches': self._get_upcoming_matches(team_id)
        }

    def _get_upcoming_matches(self, team_id: int):
        """Fetch upcoming matches for a team"""
        import psycopg2
        import psycopg2.extras

        database_url = os.getenv('DATABASE_URL')
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT m.id, m.scheduled_at, m.league_name,
                           t1.name as team1_name, t1.image_url as team1_image,
                           t2.name as team2_name, t2.image_url as team2_image,
                           p.predicted_team1_score, p.predicted_team2_score,
                           p.confidence_score
                    FROM matches m
                    LEFT JOIN teams t1 ON m.team1_id = t1.id
                    LEFT JOIN teams t2 ON m.team2_id = t2.id
                    LEFT JOIN predictions p ON m.id = p.match_id
                    WHERE (m.team1_id = %s OR m.team2_id = %s)
                      AND m.scheduled_at > NOW()
                    ORDER BY m.scheduled_at ASC
                    LIMIT 5
                """, (team_id, team_id))
                
                matches = []
                for match in cur.fetchall():
                    matches.append({
                        'id': match['id'],
                        'scheduled_at': match['scheduled_at'].isoformat() if match['scheduled_at'] else None,
                        'league_name': match['league_name'],
                        'team1': {
                            'name': match['team1_name'],
                            'image_url': match['team1_image']
                        },
                        'team2': {
                            'name': match['team2_name'],
                            'image_url': match['team2_image']
                        },
                        'prediction': {
                            'team1_score': match['predicted_team1_score'],
                            'team2_score': match['predicted_team2_score'],
                            'confidence': match['confidence_score']
                        } if match['predicted_team1_score'] is not None else None
                    })
                return matches