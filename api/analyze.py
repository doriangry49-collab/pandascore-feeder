import os
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from .services.analysis import AnalysisService

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
            
            # Initialize analysis service
            analysis_service = AnalysisService(database_url)

            # Route based on query parameters
            if 'team_id' in query:
                # Single team analysis
                team_id = int(query['team_id'][0])
                response_data = {
                    'form': analysis_service.get_team_form(team_id),
                    'map_performance': analysis_service.get_map_performance(team_id)
                }
            elif 'team1_id' in query and 'team2_id' in query:
                # Head-to-head analysis
                team1_id = int(query['team1_id'][0])
                team2_id = int(query['team2_id'][0])
                response_data = analysis_service.analyze_teams(team1_id, team2_id)
            else:
                self.send_error(400, "Missing required parameters. Use either 'team_id' for single team analysis or 'team1_id' and 'team2_id' for head-to-head analysis")
                return

            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode())

        except Exception as e:
            self.send_error(500, str(e))