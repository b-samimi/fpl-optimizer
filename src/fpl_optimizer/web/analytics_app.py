"""
FPL Analytics Dashboard
Comprehensive data analysis and visualizations for FPL decision making.
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from fpl_optimizer.api.fpl_client import FPLClient
import pandas as pd
import numpy as np
from typing import Dict, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')
CORS(app)

# Initialize FPL client
fpl_client = FPLClient()

class FPLAnalytics:
    """Comprehensive FPL analytics engine."""

    def __init__(self, fpl_client: FPLClient):
        self.client = fpl_client
        self.bootstrap_data = None
        self.players_df = None
        self.teams_df = None
        self.gameweeks_played = None
        self.target_gameweek = None

    def load_data(self):
        """Load all FPL data."""
        try:
            self.bootstrap_data = self.client.get_bootstrap_static()
            self.players_df = pd.DataFrame(self.bootstrap_data['elements'])
            self.teams_df = pd.DataFrame(self.bootstrap_data['teams'])

            # Detect gameweeks
            self._detect_gameweeks()

            # Process data
            self._process_players_data()

            logger.info(f"Loaded {len(self.players_df)} players, GW{self.gameweeks_played} completed")
            return True
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return False

    def _detect_gameweeks(self):
        """Detect completed and target gameweeks."""
        gameweeks_df = pd.DataFrame(self.bootstrap_data['events'])
        gameweeks_df['finished'] = gameweeks_df['finished'].astype(bool)

        finished_gws = gameweeks_df[gameweeks_df['finished'] == True]
        if not finished_gws.empty:
            self.gameweeks_played = len(finished_gws)
            self.target_gameweek = self.gameweeks_played + 1
        else:
            current_gw = gameweeks_df[gameweeks_df['is_current'] == True]
            if not current_gw.empty:
                self.gameweeks_played = max(1, int(current_gw.iloc[0]['id']) - 1)
                self.target_gameweek = int(current_gw.iloc[0]['id'])
            else:
                self.gameweeks_played = 5
                self.target_gameweek = 6

    def _process_players_data(self):
        """Process and enrich player data."""
        # Position mapping
        position_map = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}
        self.players_df['position'] = self.players_df['element_type'].map(position_map)

        # Merge team data
        self.teams_df = self.teams_df.rename(columns={'id': 'team_id', 'name': 'team_name'})
        self.players_df = self.players_df.merge(
            self.teams_df[['team_id', 'team_name', 'short_name']],
            left_on='team',
            right_on='team_id',
            how='left'
        )

        # Calculate metrics
        self.players_df['value'] = self.players_df['now_cost'] / 10
        self.players_df['form_score'] = pd.to_numeric(self.players_df['form'], errors='coerce').fillna(0)
        self.players_df['ppg'] = pd.to_numeric(self.players_df['points_per_game'], errors='coerce').fillna(0)

        # Numeric conversions
        numeric_cols = ['minutes', 'goals_scored', 'assists', 'clean_sheets', 'goals_conceded',
                       'saves', 'expected_goals', 'expected_assists', 'expected_goals_conceded',
                       'total_points', 'starts', 'selected_by_percent']

        for col in numeric_cols:
            if col in self.players_df.columns:
                self.players_df[col] = pd.to_numeric(self.players_df[col], errors='coerce').fillna(0)

    def get_team_reliability_analysis(self):
        """Analyze team defensive and offensive reliability."""
        team_stats = self.players_df.groupby('team').agg({
            'expected_goals': 'sum',
            'expected_goals_conceded': 'sum',
            'goals_scored': 'sum',
            'goals_conceded': 'sum',
            'saves': 'sum',
            'clean_sheets': 'sum'
        }).reset_index()

        team_analysis = team_stats.merge(
            self.teams_df[['team_id', 'team_name', 'short_name']],
            left_on='team',
            right_on='team_id'
        )

        # Calculate per-game metrics
        gw = self.gameweeks_played
        team_analysis['xga_per_90'] = team_analysis['expected_goals_conceded'] / gw
        team_analysis['xg_per_90'] = team_analysis['expected_goals'] / gw
        team_analysis['goals_per_90'] = team_analysis['goals_scored'] / gw
        team_analysis['goals_conceded_per_90'] = team_analysis['goals_conceded'] / gw
        team_analysis['clean_sheet_rate'] = team_analysis['clean_sheets'] / gw

        # Shot estimates
        team_analysis['shots_faced_per_90'] = (team_analysis['saves'] + team_analysis['goals_conceded']) / gw
        team_analysis['shots_per_90'] = team_analysis['expected_goals'] * 8 / gw

        # Efficiency
        team_analysis['defensive_efficiency'] = team_analysis['goals_conceded_per_90'] - team_analysis['xga_per_90']
        team_analysis['offensive_efficiency'] = team_analysis['goals_per_90'] - team_analysis['xg_per_90']

        return team_analysis[[
            'short_name', 'team_name', 'xga_per_90', 'xg_per_90',
            'clean_sheet_rate', 'shots_faced_per_90', 'shots_per_90',
            'defensive_efficiency', 'offensive_efficiency'
        ]].to_dict('records')

    def get_differential_players(self):
        """Identify differential players."""
        active = self.players_df[
            (self.players_df['minutes'] > self.gameweeks_played * 30) &
            (self.players_df['position'] != 'GKP')
        ].copy()

        if active.empty:
            return []

        active['minutes_per_90'] = active['minutes'] / 90
        active['points_per_90'] = active['total_points'] / active['minutes_per_90']
        active['xgi_per_90'] = (active['expected_goals'] + active['expected_assists']) / active['minutes_per_90']

        differentials = active[
            (active['selected_by_percent'] < 15) &
            (active['points_per_90'] >= 4.0) &
            (active['form_score'] >= 3.0)
        ].copy()

        differentials['differential_score'] = (
            differentials['points_per_90'] * 0.4 +
            differentials['xgi_per_90'] * 15 * 0.3 +
            differentials['form_score'] * 0.2 +
            (15 - differentials['selected_by_percent']) * 0.1
        )

        return differentials.nlargest(20, 'differential_score')[[
            'web_name', 'team_name', 'position', 'value', 'total_points',
            'form_score', 'points_per_90', 'selected_by_percent', 'differential_score'
        ]].to_dict('records')

    def get_emerging_players(self):
        """Find emerging FPL assets."""
        outfield = self.players_df[
            (self.players_df['position'] != 'GKP') &
            (self.players_df['minutes'] > 0) &
            (self.players_df['starts'] >= 1)
        ].copy()

        if outfield.empty:
            return []

        outfield['minutes_per_90'] = outfield['minutes'] / 90
        outfield['points_per_90'] = outfield['total_points'] / outfield['minutes_per_90']
        avg_minutes_per_gw = outfield['minutes'] / self.gameweeks_played

        emerging = outfield[
            (outfield['form_score'] >= 4.5) &
            (outfield['points_per_90'] >= 3.5) &
            (avg_minutes_per_gw >= 60) &
            (outfield['selected_by_percent'] < 25) &
            (outfield['total_points'] >= 20)
        ].copy()

        emerging['emergence_score'] = (
            emerging['form_score'] * 0.35 +
            emerging['points_per_90'] * 0.25 +
            (avg_minutes_per_gw[emerging.index] / 90) * 0.25 +
            (25 - emerging['selected_by_percent']) * 0.1 +
            (emerging['expected_goals'] + emerging['expected_assists']) * 2 * 0.05
        )

        return emerging.nlargest(20, 'emergence_score')[[
            'web_name', 'team_name', 'position', 'value', 'total_points',
            'form_score', 'points_per_90', 'selected_by_percent', 'emergence_score'
        ]].to_dict('records')

    def get_shots_analysis(self):
        """Comprehensive shots and xG analysis."""
        active = self.players_df[
            (self.players_df['minutes'] >= 90) &
            (self.players_df['position'] != 'GKP')
        ].copy()

        if active.empty:
            return {
                'by_player': [],
                'by_position': [],
                'team_shots': []
            }

        active['minutes_per_90'] = active['minutes'] / 90

        # Estimate shots from xG (typically 8-10 shots per xG)
        active['estimated_shots'] = active['expected_goals'] * 9
        active['shots_per_90'] = active['estimated_shots'] / active['minutes_per_90']

        # Estimate shots on goal from xG (typically 30-40% of shots)
        active['estimated_shots_on_goal'] = active['expected_goals'] * 3
        active['shots_on_goal_per_90'] = active['estimated_shots_on_goal'] / active['minutes_per_90']

        # xG per 90
        active['xg_per_90'] = active['expected_goals'] / active['minutes_per_90']

        # Player shots analysis (top 30 by shots per 90)
        player_shots_df = active[active['estimated_shots'] > 5].nlargest(30, 'shots_per_90')[[
            'web_name', 'team_name', 'position', 'value', 'shots_per_90',
            'shots_on_goal_per_90', 'xg_per_90', 'goals_scored', 'total_points'
        ]].copy()

        # Convert to native Python types
        player_shots = []
        for _, row in player_shots_df.iterrows():
            player_shots.append({
                'web_name': str(row['web_name']),
                'team_name': str(row['team_name']),
                'position': str(row['position']),
                'value': float(row['value']),
                'shots_per_90': float(row['shots_per_90']),
                'shots_on_goal_per_90': float(row['shots_on_goal_per_90']),
                'xg_per_90': float(row['xg_per_90']),
                'goals_scored': int(row['goals_scored']),
                'total_points': int(row['total_points'])
            })

        # Position-based analysis
        position_stats = []
        for position in ['DEF', 'MID', 'FWD']:
            pos_players = active[active['position'] == position]
            if not pos_players.empty:
                position_stats.append({
                    'position': position,
                    'avg_shots_per_90': float(pos_players['shots_per_90'].mean()),
                    'avg_shots_on_goal_per_90': float(pos_players['shots_on_goal_per_90'].mean()),
                    'avg_xg_per_90': float(pos_players['xg_per_90'].mean()),
                    'total_shots': float(pos_players['estimated_shots'].sum()),
                    'total_goals': int(pos_players['goals_scored'].sum())
                })

        # Team shots analysis
        team_shots_df = active.groupby('team_name').agg({
            'estimated_shots': 'sum',
            'estimated_shots_on_goal': 'sum',
            'expected_goals': 'sum',
            'goals_scored': 'sum'
        }).reset_index()

        team_shots_df['shots_per_90'] = team_shots_df['estimated_shots'] / self.gameweeks_played
        team_shots_df['shots_on_goal_per_90'] = team_shots_df['estimated_shots_on_goal'] / self.gameweeks_played
        team_shots_df['xg_per_90'] = team_shots_df['expected_goals'] / self.gameweeks_played

        team_shots_df = team_shots_df.nlargest(20, 'shots_per_90')

        # Convert to native Python types
        team_shots = []
        for _, row in team_shots_df.iterrows():
            team_shots.append({
                'team_name': str(row['team_name']),
                'shots_per_90': float(row['shots_per_90']),
                'shots_on_goal_per_90': float(row['shots_on_goal_per_90']),
                'xg_per_90': float(row['xg_per_90']),
                'goals_scored': int(row['goals_scored'])
            })

        return {
            'by_player': player_shots,
            'by_position': position_stats,
            'team_shots': team_shots
        }

    def get_top_players_by_position(self):
        """Get top players by each position."""
        result = {}

        for position in ['GKP', 'DEF', 'MID', 'FWD']:
            pos_players = self.players_df[
                (self.players_df['position'] == position) &
                (self.players_df['minutes'] >= self.gameweeks_played * 45)
            ].copy()

            if not pos_players.empty:
                pos_players['score'] = (
                    pos_players['form_score'] * 0.3 +
                    pos_players['ppg'] * 0.4 +
                    pos_players['total_points'] * 0.3
                )

                top_players = pos_players.nlargest(10, 'score')
                result[position] = top_players[[
                    'web_name', 'team_name', 'value', 'total_points',
                    'form_score', 'ppg', 'selected_by_percent'
                ]].to_dict('records')

        return result

# Global analytics instance
analytics = FPLAnalytics(fpl_client)

@app.route('/')
def index():
    """Render analytics dashboard."""
    return render_template('analytics.html')

@app.route('/api/init', methods=['GET'])
def initialize():
    """Initialize analytics data."""
    try:
        success = analytics.load_data()
        return jsonify({
            'success': success,
            'gameweeks_played': analytics.gameweeks_played,
            'target_gameweek': analytics.target_gameweek,
            'total_players': len(analytics.players_df) if success else 0
        })
    except Exception as e:
        logger.error(f"Error initializing: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/team_reliability', methods=['GET'])
def team_reliability():
    """Get team reliability analysis."""
    try:
        data = analytics.get_team_reliability_analysis()
        return jsonify({
            'teams': data,
            'gameweeks_played': analytics.gameweeks_played
        })
    except Exception as e:
        logger.error(f"Error in team reliability: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/differentials', methods=['GET'])
def differentials():
    """Get differential players."""
    try:
        data = analytics.get_differential_players()
        return jsonify({
            'players': data,
            'count': len(data)
        })
    except Exception as e:
        logger.error(f"Error getting differentials: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/emerging_players', methods=['GET'])
def emerging_players():
    """Get emerging players."""
    try:
        data = analytics.get_emerging_players()
        return jsonify({
            'players': data,
            'count': len(data)
        })
    except Exception as e:
        logger.error(f"Error getting emerging players: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/shots_analysis', methods=['GET'])
def shots_analysis():
    """Get comprehensive shots analysis."""
    try:
        data = analytics.get_shots_analysis()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error in shots analysis: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/top_players', methods=['GET'])
def top_players():
    """Get top players by position."""
    try:
        data = analytics.get_top_players_by_position()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting top players: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("Initializing FPL Analytics Dashboard...")
    analytics.load_data()

    app.run(debug=True, host='0.0.0.0', port=5002)
