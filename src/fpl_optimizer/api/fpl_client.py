import requests
import pandas as pd
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime

class FPLClient:
    """Fantasy Premier League API client for fetching player and team data."""
    
    def __init__(self):
        self.base_url = "https://fantasy.premierleague.com/api/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def get_bootstrap_static(self) -> Dict:
        """Get all static game data including players, teams, and gameweeks."""
        try:
            response = self.session.get(f"{self.base_url}bootstrap-static/", timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching bootstrap data: {e}")
            raise
    
    def get_players_df(self) -> pd.DataFrame:
        """Get all players data as a pandas DataFrame."""
        data = self.get_bootstrap_static()
        players_df = pd.DataFrame(data['elements'])
        
        # Convert price from API format (multiply by 10) to actual price
        players_df['price'] = players_df['now_cost'] / 10.0
        
        # Add team names
        teams_df = pd.DataFrame(data['teams'])
        players_df = players_df.merge(
            teams_df[['id', 'name', 'short_name']], 
            left_on='team', 
            right_on='id', 
            suffixes=('', '_team')
        )
        
        # Add position names
        positions_df = pd.DataFrame(data['element_types'])
        players_df = players_df.merge(
            positions_df[['id', 'singular_name_short']], 
            left_on='element_type', 
            right_on='id', 
            suffixes=('', '_pos')
        )
        
        # Clean up column names
        players_df = players_df.rename(columns={
            'name': 'team_name',
            'short_name': 'team_short',
            'singular_name_short': 'position'
        })
        
        return players_df
    
    def get_teams_df(self) -> pd.DataFrame:
        """Get all teams data as a pandas DataFrame."""
        data = self.get_bootstrap_static()
        return pd.DataFrame(data['teams'])
    
    def get_gameweeks_df(self) -> pd.DataFrame:
        """Get all gameweeks data as a pandas DataFrame."""
        data = self.get_bootstrap_static()
        return pd.DataFrame(data['events'])
    
    def get_player_detailed_stats(self, player_id: int) -> Dict:
        """Get detailed statistics for a specific player."""
        try:
            response = self.session.get(
                f"{self.base_url}element-summary/{player_id}/", 
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching player {player_id} details: {e}")
            raise
    
    def get_fixtures(self) -> pd.DataFrame:
        """Get all fixtures data as a pandas DataFrame."""
        try:
            response = self.session.get(f"{self.base_url}fixtures/", timeout=30)
            response.raise_for_status()
            fixtures_data = response.json()
            return pd.DataFrame(fixtures_data)
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching fixtures: {e}")
            raise
    
    def get_mini_league_standings(self, league_id: int, page: int = 1) -> Dict:
        """Get mini league standings."""
        try:
            response = self.session.get(
                f"{self.base_url}leagues-classic/{league_id}/standings/",
                params={'page_standings': page},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching league {league_id}: {e}")
            raise
    
    def analyze_top_performers(self, metric: str = 'total_points', top_n: int = 10) -> pd.DataFrame:
        """Analyze top performing players by a given metric."""
        players_df = self.get_players_df()
        
        # Filter out players with 0 minutes (haven't played)
        active_players = players_df[players_df['minutes'] > 0].copy()
        
        # Calculate points per million for value analysis
        active_players['points_per_million'] = active_players['total_points'] / active_players['price']
        active_players['points_per_game'] = active_players['total_points'] / (active_players['minutes'] / 90)
        
        # Get top performers
        top_players = active_players.nlargest(top_n, metric)[
            ['web_name', 'team_name', 'position', 'price', 'total_points', 
             'points_per_million', 'goals_scored', 'assists', 'selected_by_percent']
        ]
        
        return top_players.round(2)