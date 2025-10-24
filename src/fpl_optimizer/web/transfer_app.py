"""
FPL Transfer Review Web Application
A Flask-based web app for reviewing player data and making transfer decisions.
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from fpl_optimizer.api.fpl_client import FPLClient
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
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

class TransferAnalyzer:
    """Analyze player data and provide transfer recommendations."""

    def __init__(self, fpl_client: FPLClient):
        self.client = fpl_client
        self.bootstrap_data = None
        self.players_df = None
        self.teams_df = None

    def load_data(self):
        """Load FPL bootstrap data."""
        try:
            self.bootstrap_data = self.client.get_bootstrap_static()
            self.players_df = pd.DataFrame(self.bootstrap_data['elements'])
            self.teams_df = pd.DataFrame(self.bootstrap_data['teams'])

            # Merge team names
            self.teams_df = self.teams_df.rename(columns={'id': 'team_id', 'name': 'team_name'})
            self.players_df = self.players_df.merge(
                self.teams_df[['team_id', 'team_name', 'short_name']],
                left_on='team',
                right_on='team_id',
                how='left'
            )

            # Add position names
            position_map = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}
            self.players_df['position_name'] = self.players_df['element_type'].map(position_map)

            # Calculate key metrics
            self.players_df['value'] = self.players_df['now_cost'] / 10
            self.players_df['form_score'] = self.players_df['form'].astype(float)
            self.players_df['ppg'] = self.players_df['points_per_game'].astype(float)
            self.players_df['selected_by'] = self.players_df['selected_by_percent'].astype(float)

            # Calculate value score
            self.players_df['value_score'] = (
                self.players_df['ppg'] * 10 +
                self.players_df['form_score'] * 5 -
                self.players_df['value']
            )

            logger.info(f"Loaded {len(self.players_df)} players from FPL API")
            return True

        except Exception as e:
            logger.error(f"Error loading FPL data: {e}")
            return False

    def get_current_gameweek(self) -> Optional[int]:
        """Get the current or next gameweek."""
        if not self.bootstrap_data:
            return None

        for event in self.bootstrap_data['events']:
            if event['is_current']:
                return event['id']

        for event in self.bootstrap_data['events']:
            if event['is_next']:
                return event['id']

        return None

    def get_my_team(self, manager_id: int) -> pd.DataFrame:
        """Get current team for a manager."""
        try:
            current_gw = self.get_current_gameweek()
            if not current_gw:
                logger.error("Could not determine current gameweek")
                return pd.DataFrame()

            picks_data = self.client.get_manager_picks(manager_id, current_gw)
            pick_ids = [pick['element'] for pick in picks_data['picks']]

            my_team = self.players_df[self.players_df['id'].isin(pick_ids)].copy()
            my_team = my_team.sort_values('element_type')

            return my_team

        except Exception as e:
            logger.error(f"Error getting team for manager {manager_id}: {e}")
            return pd.DataFrame()

    def analyze_player(self, player_row: pd.Series) -> Dict:
        """Analyze a single player and identify issues."""
        issues = []
        priority = 0

        # Check injury status
        if player_row['chance_of_playing_next_round'] is not None:
            chance = player_row['chance_of_playing_next_round']
            if chance < 75:
                issues.append({
                    'type': 'injury',
                    'severity': 'high' if chance < 50 else 'medium',
                    'message': f"{chance}% chance of playing"
                })
                priority += 3 if chance < 50 else 2

        # Check form
        if player_row['form_score'] < 2.0 and player_row['total_points'] > 10:
            issues.append({
                'type': 'form',
                'severity': 'medium',
                'message': f"Poor form ({player_row['form_score']:.1f})"
            })
            priority += 2

        # Check if player hasn't played
        current_gw = self.get_current_gameweek()
        if player_row['minutes'] == 0 and current_gw and current_gw > 3:
            issues.append({
                'type': 'minutes',
                'severity': 'high',
                'message': "No minutes played"
            })
            priority += 3

        # Check status
        if player_row['status'] != 'a':
            status_map = {'i': 'Injured', 'd': 'Doubtful', 's': 'Suspended', 'u': 'Unavailable'}
            status_text = status_map.get(player_row['status'], player_row['status'])
            issues.append({
                'type': 'status',
                'severity': 'high',
                'message': f"Status: {status_text}"
            })
            priority += 3

        return {
            'issues': issues,
            'priority': priority,
            'has_issues': len(issues) > 0
        }

    def get_replacements(self, player_row: pd.Series, max_price: float = None, limit: int = 5) -> List[Dict]:
        """Find replacement players for a given player."""
        if max_price is None:
            max_price = player_row['value'] + 1.0  # Allow 1M extra

        # Filter by position and price
        replacements = self.players_df[
            (self.players_df['element_type'] == player_row['element_type']) &
            (self.players_df['id'] != player_row['id']) &
            (self.players_df['value'] <= max_price) &
            (self.players_df['status'] == 'a') &
            (self.players_df['minutes'] > 0)
        ].copy()

        # Score replacements
        replacements['replacement_score'] = (
            replacements['form_score'] * 2 +
            replacements['ppg'] * 3 +
            replacements['selected_by'] * 0.1 -
            (replacements['value'] - player_row['value']) * 0.5
        )

        # Get top replacements
        top_replacements = replacements.nlargest(limit, 'replacement_score')

        return top_replacements[[
            'id', 'web_name', 'team_name', 'value', 'form_score',
            'ppg', 'total_points', 'selected_by', 'replacement_score'
        ]].to_dict('records')

    def get_player_stats(self, player_id: int) -> Optional[Dict]:
        """Get detailed stats for a specific player."""
        player = self.players_df[self.players_df['id'] == player_id]

        if player.empty:
            return None

        player = player.iloc[0]

        return {
            'id': int(player['id']),
            'name': player['web_name'],
            'full_name': f"{player['first_name']} {player['second_name']}",
            'team': player['team_name'],
            'position': player['position_name'],
            'value': float(player['value']),
            'total_points': int(player['total_points']),
            'form': float(player['form_score']),
            'ppg': float(player['ppg']),
            'selected_by': float(player['selected_by']),
            'minutes': int(player['minutes']),
            'goals_scored': int(player['goals_scored']),
            'assists': int(player['assists']),
            'clean_sheets': int(player['clean_sheets']),
            'bonus': int(player['bonus']),
            'status': player['status'],
            'chance_of_playing': player['chance_of_playing_next_round'],
            'news': player.get('news', ''),
            'value_score': float(player['value_score'])
        }

# Global analyzer instance
analyzer = TransferAnalyzer(fpl_client)

@app.route('/')
def index():
    """Render the main page."""
    return render_template('transfer_review.html')

@app.route('/api/init', methods=['POST'])
def initialize():
    """Initialize the app with FPL data."""
    try:
        success = analyzer.load_data()
        current_gw = analyzer.get_current_gameweek()

        return jsonify({
            'success': success,
            'current_gameweek': current_gw,
            'total_players': len(analyzer.players_df) if success else 0
        })
    except Exception as e:
        logger.error(f"Error initializing: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/team/<int:manager_id>', methods=['GET'])
def get_team(manager_id):
    """Get current team for a manager with analysis."""
    try:
        if analyzer.players_df is None:
            analyzer.load_data()

        team_df = analyzer.get_my_team(manager_id)

        if team_df.empty:
            return jsonify({'error': 'Team not found or empty'}), 404

        # Analyze each player
        team_data = []
        for _, player in team_df.iterrows():
            analysis = analyzer.analyze_player(player)

            player_data = {
                'id': int(player['id']),
                'name': player['web_name'],
                'team': player['team_name'],
                'position': player['position_name'],
                'value': float(player['value']),
                'total_points': int(player['total_points']),
                'form': float(player['form_score']),
                'ppg': float(player['ppg']),
                'minutes': int(player['minutes']),
                'selected_by': float(player['selected_by']),
                'analysis': analysis
            }
            team_data.append(player_data)

        # Calculate team stats
        team_stats = {
            'total_value': float(team_df['value'].sum()),
            'total_points': int(team_df['total_points'].sum()),
            'avg_form': float(team_df['form_score'].mean()),
            'avg_ppg': float(team_df['ppg'].mean()),
            'players_with_issues': sum(1 for p in team_data if p['analysis']['has_issues'])
        }

        return jsonify({
            'team': team_data,
            'stats': team_stats
        })

    except Exception as e:
        logger.error(f"Error getting team: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/replacements/<int:player_id>', methods=['GET'])
def get_player_replacements(player_id):
    """Get replacement suggestions for a player."""
    try:
        max_price = request.args.get('max_price', type=float)

        player = analyzer.players_df[analyzer.players_df['id'] == player_id]
        if player.empty:
            return jsonify({'error': 'Player not found'}), 404

        player_row = player.iloc[0]
        replacements = analyzer.get_replacements(player_row, max_price)

        return jsonify({
            'player': {
                'id': int(player_row['id']),
                'name': player_row['web_name'],
                'value': float(player_row['value'])
            },
            'replacements': replacements
        })

    except Exception as e:
        logger.error(f"Error getting replacements: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/players/search', methods=['GET'])
def search_players():
    """Search for players by name or filters."""
    try:
        query = request.args.get('q', '').lower()
        position = request.args.get('position')
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        sort_by = request.args.get('sort', 'value_score')
        limit = request.args.get('limit', 20, type=int)

        # Start with all players
        filtered = analyzer.players_df.copy()

        # Apply filters
        if query:
            filtered = filtered[
                filtered['web_name'].str.lower().str.contains(query) |
                filtered['team_name'].str.lower().str.contains(query)
            ]

        if position:
            filtered = filtered[filtered['position_name'] == position.upper()]

        if min_price:
            filtered = filtered[filtered['value'] >= min_price]

        if max_price:
            filtered = filtered[filtered['value'] <= max_price]

        # Sort
        if sort_by in filtered.columns:
            filtered = filtered.sort_values(sort_by, ascending=False)

        # Limit results
        filtered = filtered.head(limit)

        # Format results
        results = []
        for _, player in filtered.iterrows():
            results.append({
                'id': int(player['id']),
                'name': player['web_name'],
                'team': player['team_name'],
                'position': player['position_name'],
                'value': float(player['value']),
                'total_points': int(player['total_points']),
                'form': float(player['form_score']),
                'ppg': float(player['ppg']),
                'selected_by': float(player['selected_by']),
                'value_score': float(player['value_score'])
            })

        return jsonify({
            'results': results,
            'count': len(results)
        })

    except Exception as e:
        logger.error(f"Error searching players: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/player/<int:player_id>', methods=['GET'])
def get_player_details(player_id):
    """Get detailed information about a specific player."""
    try:
        stats = analyzer.get_player_stats(player_id)

        if not stats:
            return jsonify({'error': 'Player not found'}), 404

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting player details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/top_players', methods=['GET'])
def get_top_players():
    """Get top players by various metrics."""
    try:
        category = request.args.get('category', 'value_score')
        position = request.args.get('position')
        limit = request.args.get('limit', 10, type=int)

        filtered = analyzer.players_df.copy()

        if position:
            filtered = filtered[filtered['position_name'] == position.upper()]

        # Get top players
        top = filtered.nlargest(limit, category)

        results = []
        for _, player in top.iterrows():
            results.append({
                'id': int(player['id']),
                'name': player['web_name'],
                'team': player['team_name'],
                'position': player['position_name'],
                'value': float(player['value']),
                'total_points': int(player['total_points']),
                'form': float(player['form_score']),
                'ppg': float(player['ppg']),
                'selected_by': float(player['selected_by']),
                category: float(player[category])
            })

        return jsonify({
            'category': category,
            'position': position,
            'players': results
        })

    except Exception as e:
        logger.error(f"Error getting top players: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Initialize data on startup
    logger.info("Initializing FPL Transfer Review App...")
    analyzer.load_data()

    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5001)
