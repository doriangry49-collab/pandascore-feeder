import os
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
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
            
            # Initialize prediction model
            prediction_model = PredictionModel(database_url)

            if 'match_id' in query:
                # Generate and store prediction for a specific match
                match_id = int(query['match_id'][0])
                team1_id = int(query.get('team1_id', [0])[0])
                team2_id = int(query.get('team2_id', [0])[0])
                
                if not team1_id or not team2_id:
                    self.send_error(400, "team1_id and team2_id are required when using match_id")
                    return
                
                prediction_model.store_prediction(match_id, team1_id, team2_id)
                response_data = {"status": "success", "message": "Prediction stored"}
                
            elif 'team1_id' in query and 'team2_id' in query:
                # Generate prediction for two teams without storing
                team1_id = int(query['team1_id'][0])
                team2_id = int(query['team2_id'][0])
                response_data = prediction_model.predict_match(team1_id, team2_id)
            
            else:
                self.send_error(400, "Missing required parameters. Use either 'match_id' with 'team1_id' and 'team2_id' to store a prediction, or just 'team1_id' and 'team2_id' for a quick prediction")
                return

            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode())

        except Exception as e:
            self.send_error(500, str(e))