import os
import requests
import psycopg2
import psycopg2.extras
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Check required environment variables
            api_key = os.getenv('PANDASCORE_API_KEY')
            database_url = os.getenv('DATABASE_URL')
            
            if not api_key or not database_url:
                self.send_error(500, "Missing required environment variables")
                return

            # Parse query parameters
            query = parse_qs(urlparse(self.path).query)
            team_id = query.get('team_id', [None])[0]

            # If team_id provided, fetch specific team stats
            if team_id:
                response_data = self.fetch_team_stats(api_key, database_url, team_id)
            else:
                # Otherwise fetch all teams' stats
                response_data = self.fetch_all_teams(api_key, database_url)

            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode())

        except Exception as e:
            self.send_error(500, str(e))

    def fetch_team_stats(self, api_key, database_url, team_id):
        # Fetch team details from PandaScore
        headers = {'Authorization': f'Bearer {api_key}'}
        team_url = f'https://api.pandascore.co/csgo/teams/{team_id}'
        team_response = requests.get(team_url, headers=headers)
        
        if team_response.status_code != 200:
            raise Exception(f"Error fetching team data: {team_response.text}")

        team_data = team_response.json()

        # Fetch team's past matches
        matches_url = f'https://api.pandascore.co/csgo/matches/past?filter[team_id]={team_id}&page[size]=50'
        matches_response = requests.get(matches_url, headers=headers)
        
        if matches_response.status_code != 200:
            raise Exception(f"Error fetching match data: {matches_response.text}")

        matches_data = matches_response.json()

        # Calculate stats
        total_matches = len(matches_data)
        wins = sum(1 for match in matches_data if match['winner_id'] == int(team_id))
        losses = total_matches - wins
        rounds = [(match.get('results', [{'score': 0}])[0]['score'], 
                  match.get('results', [{'score': 0}, {'score': 0}])[1]['score'])
                 for match in matches_data]
        
        rounds_won = sum(r[0] if match['winner_id'] == int(team_id) else r[1] 
                        for r, match in zip(rounds, matches_data))
        rounds_lost = sum(r[1] if match['winner_id'] == int(team_id) else r[0] 
                         for r, match in zip(rounds, matches_data))

        # Store team and stats in database
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                # Insert/update team
                cur.execute("""
                    INSERT INTO teams (id, name, acronym, image_url)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        acronym = EXCLUDED.acronym,
                        image_url = EXCLUDED.image_url
                """, (team_id, team_data['name'], team_data.get('acronym'), team_data.get('image_url')))

                # Insert/update team stats
                cur.execute("""
                    INSERT INTO team_stats 
                    (team_id, total_matches, wins, losses, rounds_won, rounds_lost, win_rate, avg_rounds_won)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (team_id) DO UPDATE SET
                        total_matches = EXCLUDED.total_matches,
                        wins = EXCLUDED.wins,
                        losses = EXCLUDED.losses,
                        rounds_won = EXCLUDED.rounds_won,
                        rounds_lost = EXCLUDED.rounds_lost,
                        win_rate = EXCLUDED.win_rate,
                        avg_rounds_won = EXCLUDED.avg_rounds_won,
                        last_updated = NOW()
                """, (
                    team_id, 
                    total_matches,
                    wins,
                    losses,
                    rounds_won,
                    rounds_lost,
                    (wins / total_matches * 100) if total_matches > 0 else 0,
                    (rounds_won / total_matches) if total_matches > 0 else 0
                ))

                # Store historical matches
                for match in matches_data:
                    cur.execute("""
                        INSERT INTO historical_matches 
                        (id, team1_id, team2_id, winner_id, team1_score, team2_score, 
                         played_at, map_name, event_name, raw_data)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                    """, (
                        match['id'],
                        match['opponents'][0]['opponent']['id'] if match.get('opponents') else None,
                        match['opponents'][1]['opponent']['id'] if match.get('opponents') and len(match['opponents']) > 1 else None,
                        match['winner_id'],
                        match.get('results', [{'score': 0}])[0]['score'],
                        match.get('results', [{'score': 0}, {'score': 0}])[1]['score'],
                        match['scheduled_at'],
                        match.get('match_type'),
                        match.get('tournament', {}).get('name'),
                        json.dumps(match)
                    ))

        return {
            'team': team_data,
            'stats': {
                'total_matches': total_matches,
                'wins': wins,
                'losses': losses,
                'rounds_won': rounds_won,
                'rounds_lost': rounds_lost,
                'win_rate': (wins / total_matches * 100) if total_matches > 0 else 0,
                'avg_rounds_won': (rounds_won / total_matches) if total_matches > 0 else 0
            },
            'recent_matches': matches_data[:5]  # Return only most recent 5 matches
        }

    def fetch_all_teams(self, api_key, database_url):
    # Fetch top teams from PandaScore
    headers = {'Authorization': f'Bearer {api_key}'}
        # Use a plain teams list request first (no paging/sort) to avoid
        # parameter-related errors from the PandaScore API.
        teams_url = 'https://api.pandascore.co/csgo/teams'

        # Debugging logs (safe: do not print the full API key)
        try:
            key_len = len(api_key) if api_key else 0
        except Exception:
            key_len = 0
        print(f"[teams] Requesting PandaScore teams list url={teams_url} auth_present={key_len>0} key_len={key_len}")

        try:
            response = requests.get(teams_url, headers=headers, timeout=15)
        except Exception as e:
            # Log the exception to help debugging in production logs
            print(f"[teams] Request exception: {type(e).__name__}: {e}")
            raise

        # Log response status and a short snippet of body for debugging
        resp_snippet = (response.text[:1000] + '...') if response.text and len(response.text) > 1000 else response.text
        print(f"[teams] PandaScore response status={response.status_code} body_snippet={resp_snippet}")

        # If the API returns an error, include HTTP status for easier debugging
        if response.status_code != 200:
            raise Exception(f"Error fetching teams data (status={response.status_code}): {response.text}")
        
        if response.status_code != 200:
            raise Exception(f"Error fetching teams data: {response.text}")

        teams_data = response.json()

        # Store teams in database and return basic info
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                for team in teams_data:
                    cur.execute("""
                        INSERT INTO teams (id, name, acronym, image_url)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            name = EXCLUDED.name,
                            acronym = EXCLUDED.acronym,
                            image_url = EXCLUDED.image_url
                    """, (team['id'], team['name'], team.get('acronym'), team.get('image_url')))

        return [{
            'id': team['id'],
            'name': team['name'],
            'acronym': team.get('acronym'),
            'image_url': team.get('image_url'),
            'rating': team.get('rating')
        } for team in teams_data]