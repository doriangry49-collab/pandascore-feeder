import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

class AnalysisService:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def _get_db_connection(self):
        return psycopg2.connect(self.database_url)

    def get_team_form(self, team_id: int, last_n_matches: int = 5) -> Dict:
        """
        Calculates team's recent form based on last N matches
        Returns form score (0-100) and recent match results
        """
        with self._get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get last N matches
                cur.execute("""
                    SELECT 
                        id,
                        winner_id,
                        team1_id,
                        team2_id,
                        team1_score,
                        team2_score,
                        played_at
                    FROM historical_matches
                    WHERE (team1_id = %s OR team2_id = %s)
                    AND played_at < NOW()
                    ORDER BY played_at DESC
                    LIMIT %s
                """, (team_id, team_id, last_n_matches))
                
                matches = cur.fetchall()

                # Calculate form metrics
                form_score = 0
                recent_results = []
                
                for match in matches:
                    # Determine if team was team1 or team2
                    is_team1 = match['team1_id'] == team_id
                    team_score = match['team1_score'] if is_team1 else match['team2_score']
                    opponent_score = match['team2_score'] if is_team1 else match['team1_score']
                    
                    # Calculate match result
                    won = match['winner_id'] == team_id
                    score_diff = team_score - opponent_score
                    
                    # Add to form score (weighted by recency)
                    weight = 1 + (0.2 * (len(matches) - len(recent_results)))  # More recent matches count more
                    if won:
                        # Win gives 20 points, boosted by score difference
                        form_score += (20 + min(score_diff * 2, 10)) * weight
                    else:
                        # Loss takes away points, but less if it was close
                        form_score -= (10 - min(abs(score_diff), 5)) * weight
                    
                    recent_results.append({
                        'match_id': match['id'],
                        'won': won,
                        'score': f"{team_score}-{opponent_score}",
                        'played_at': match['played_at'].isoformat()
                    })

                # Normalize form score to 0-100 range
                max_possible = sum((20 + 10) * (1 + 0.2 * i) for i in range(len(matches)))
                min_possible = -sum((10) * (1 + 0.2 * i) for i in range(len(matches)))
                form_score = max(0, min(100, ((form_score - min_possible) / (max_possible - min_possible)) * 100))

                return {
                    'form_score': round(form_score, 2),
                    'recent_results': recent_results
                }

    def get_head_to_head(self, team1_id: int, team2_id: int, last_n_matches: int = 5) -> Dict:
        """
        Analyzes head-to-head history between two teams
        """
        with self._get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        id,
                        winner_id,
                        team1_id,
                        team2_id,
                        team1_score,
                        team2_score,
                        played_at,
                        map_name,
                        event_name
                    FROM historical_matches
                    WHERE (team1_id = %s AND team2_id = %s)
                        OR (team1_id = %s AND team2_id = %s)
                    AND played_at < NOW()
                    ORDER BY played_at DESC
                    LIMIT %s
                """, (team1_id, team2_id, team2_id, team1_id, last_n_matches))
                
                matches = cur.fetchall()

                # Calculate H2H stats
                team1_wins = 0
                team2_wins = 0
                total_maps = 0
                recent_matches = []

                for match in matches:
                    # Standardize the results to team1's perspective
                    if match['team1_id'] == team1_id:
                        team1_score = match['team1_score']
                        team2_score = match['team2_score']
                    else:
                        team1_score = match['team2_score']
                        team2_score = match['team1_score']

                    if match['winner_id'] == team1_id:
                        team1_wins += 1
                    elif match['winner_id'] == team2_id:
                        team2_wins += 1

                    total_maps += 1
                    
                    recent_matches.append({
                        'match_id': match['id'],
                        'score': f"{team1_score}-{team2_score}",
                        'winner': 'team1' if match['winner_id'] == team1_id else 'team2',
                        'map': match['map_name'],
                        'event': match['event_name'],
                        'played_at': match['played_at'].isoformat()
                    })

                return {
                    'total_matches': total_maps,
                    'team1_wins': team1_wins,
                    'team2_wins': team2_wins,
                    'team1_win_rate': round(team1_wins / total_maps * 100, 2) if total_maps > 0 else 0,
                    'recent_matches': recent_matches
                }

    def get_map_performance(self, team_id: int) -> Dict:
        """
        Analyzes team's performance on different maps
        """
        with self._get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        map_name,
                        COUNT(*) as total_matches,
                        SUM(CASE WHEN winner_id = %s THEN 1 ELSE 0 END) as wins,
                        SUM(CASE 
                            WHEN team1_id = %s THEN team1_score 
                            ELSE team2_score 
                        END) as rounds_won,
                        SUM(CASE 
                            WHEN team1_id = %s THEN team2_score 
                            ELSE team1_score 
                        END) as rounds_lost
                    FROM historical_matches
                    WHERE (team1_id = %s OR team2_id = %s)
                        AND map_name IS NOT NULL
                    GROUP BY map_name
                    HAVING COUNT(*) >= 3
                    ORDER BY (SUM(CASE WHEN winner_id = %s THEN 1 ELSE 0 END)::float / COUNT(*)) DESC
                """, (team_id, team_id, team_id, team_id, team_id, team_id))
                
                maps = cur.fetchall()
                
                return [{
                    'map_name': m['map_name'],
                    'total_matches': m['total_matches'],
                    'wins': m['wins'],
                    'losses': m['total_matches'] - m['wins'],
                    'win_rate': round(m['wins'] / m['total_matches'] * 100, 2),
                    'avg_rounds_won': round(m['rounds_won'] / m['total_matches'], 2),
                    'avg_rounds_lost': round(m['rounds_lost'] / m['total_matches'], 2)
                } for m in maps]

    def analyze_teams(self, team1_id: int, team2_id: int) -> Dict:
        """
        Comprehensive analysis of two teams for an upcoming match
        """
        # Get individual team forms
        team1_form = self.get_team_form(team1_id)
        team2_form = self.get_team_form(team2_id)
        
        # Get head-to-head history
        h2h = self.get_head_to_head(team1_id, team2_id)
        
        # Get map performances
        team1_maps = self.get_map_performance(team1_id)
        team2_maps = self.get_map_performance(team2_id)
        
        # Find common strong/weak maps
        team1_map_dict = {m['map_name']: m for m in team1_maps}
        team2_map_dict = {m['map_name']: m for m in team2_maps}
        
        common_maps = []
        for map_name in set(team1_map_dict.keys()) & set(team2_map_dict.keys()):
            t1_stats = team1_map_dict[map_name]
            t2_stats = team2_map_dict[map_name]
            common_maps.append({
                'map_name': map_name,
                'team1_win_rate': t1_stats['win_rate'],
                'team2_win_rate': t2_stats['win_rate'],
                'team1_avg_rounds': t1_stats['avg_rounds_won'],
                'team2_avg_rounds': t2_stats['avg_rounds_won']
            })
        
        return {
            'team1_form': team1_form,
            'team2_form': team2_form,
            'head_to_head': h2h,
            'map_analysis': {
                'team1_maps': team1_maps,
                'team2_maps': team2_maps,
                'common_maps': sorted(common_maps, 
                                   key=lambda x: abs(x['team1_win_rate'] - x['team2_win_rate']),
                                   reverse=True)
            }
        }