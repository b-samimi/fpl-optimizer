"""
FPL Weekly Matchup Analyzer and Team Optimizer
This script analyzes player matchups and recommends the best players to pick each gameweek
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime, timedelta
import json

# Import your existing FPL client
from src.fpl_optimizer.api.fpl_client import FPLClient

class FPLMatchupAnalyzer:
    """Analyzes player matchups and recommends optimal team selections."""
    
    def __init__(self):
        self.client = FPLClient()
        self.logger = logging.getLogger(__name__)
        
        # Position constraints for FPL team
        self.POSITION_LIMITS = {
            'GKP': {'min': 2, 'max': 2, 'play': 1},
            'DEF': {'min': 5, 'max': 5, 'play': 3},
            'MID': {'min': 5, 'max': 5, 'play': 4},
            'FWD': {'min': 3, 'max': 3, 'play': 3}
        }
        
        self.BUDGET_LIMIT = 100.0  # £100m budget
        self.SQUAD_SIZE = 15
        
    def calculate_fixture_difficulty(self, fixtures_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate fixture difficulty rating for each team."""
        # Get team strength from bootstrap data
        teams_df = self.client.get_teams_df()
        
        # Create fixture difficulty mapping based on team strength
        fixture_difficulty = {}
        for _, team in teams_df.iterrows():
            # Use FPL's built-in strength ratings
            fixture_difficulty[team['id']] = {
                'home_attack': team.get('strength_attack_home', 1000),
                'home_defence': team.get('strength_defence_home', 1000),
                'away_attack': team.get('strength_attack_away', 1000),
                'away_defence': team.get('strength_defence_away', 1000),
                'overall': team.get('strength_overall_home', 1000) + team.get('strength_overall_away', 1000)
            }
        
        return fixture_difficulty
    
    def get_player_form_score(self, player_data: pd.Series) -> float:
        """Calculate a form score for a player based on recent performance."""
        form_score = 0
        
        # Weight recent form heavily
        form_score += float(player_data.get('form', 0)) * 3
        
        # Consider points per game
        if player_data.get('minutes', 0) > 0:
            points_per_90 = (player_data.get('total_points', 0) / player_data.get('minutes', 1)) * 90
            form_score += points_per_90 * 2
        
        # Factor in expected metrics
        form_score += float(player_data.get('expected_goals', 0)) * 4
        form_score += float(player_data.get('expected_assists', 0)) * 3
        form_score += float(player_data.get('expected_goal_involvements', 0)) * 2
        
        # Bonus for consistent starters
        if player_data.get('starts', 0) > player_data.get('appearances', 0) * 0.8:
            form_score *= 1.2
        
        # Penalty for injury/suspension risk
        if player_data.get('chance_of_playing_next_round', 100) < 100:
            form_score *= (player_data.get('chance_of_playing_next_round', 100) / 100)
        
        return form_score
    
    def analyze_upcoming_fixtures(self, gameweek: int, weeks_ahead: int = 5) -> pd.DataFrame:
        """Analyze upcoming fixtures for each team over the next N gameweeks."""
        fixtures_df = self.client.get_fixtures()
        players_df = self.client.get_players_df()
        
        # Filter fixtures for upcoming gameweeks
        upcoming_fixtures = fixtures_df[
            (fixtures_df['event'] >= gameweek) & 
            (fixtures_df['event'] < gameweek + weeks_ahead)
        ].copy()
        
        # Calculate fixture difficulty
        fixture_difficulty = self.calculate_fixture_difficulty(fixtures_df)
        
        # Create a fixture difficulty score for each player
        player_fixtures = []
        
        for _, player in players_df.iterrows():
            team_id = player['team']
            player_dict = {
                'player_id': player['id'],
                'player_name': player['web_name'],
                'team': player['team_name'],
                'position': player['position'],
                'price': player['price'],
                'form': player['form'],
                'total_points': player['total_points'],
                'selected_by': float(player['selected_by_percent'])
            }
            
            # Get team's upcoming fixtures
            team_fixtures_home = upcoming_fixtures[upcoming_fixtures['team_h'] == team_id]
            team_fixtures_away = upcoming_fixtures[upcoming_fixtures['team_a'] == team_id]
            
            fixture_scores = []
            fixture_opponents = []
            
            # Calculate difficulty for home fixtures
            for _, fixture in team_fixtures_home.iterrows():
                opponent_id = fixture['team_a']
                if opponent_id in fixture_difficulty:
                    # Lower defensive strength = easier for attackers
                    difficulty = 6 - (fixture_difficulty[opponent_id]['away_defence'] / 200)
                    fixture_scores.append(difficulty)
                    fixture_opponents.append(f"vs {fixture.get('team_a', 'TBD')} (H)")
            
            # Calculate difficulty for away fixtures
            for _, fixture in team_fixtures_away.iterrows():
                opponent_id = fixture['team_h']
                if opponent_id in fixture_difficulty:
                    # Away fixtures are generally harder
                    difficulty = 5 - (fixture_difficulty[opponent_id]['home_defence'] / 200)
                    fixture_scores.append(difficulty * 0.85)  # Away penalty
                    fixture_opponents.append(f"@ {fixture.get('team_h', 'TBD')} (A)")
            
            if fixture_scores:
                player_dict['avg_fixture_difficulty'] = np.mean(fixture_scores)
                player_dict['fixture_variance'] = np.std(fixture_scores)
                player_dict['upcoming_fixtures'] = ', '.join(fixture_opponents[:3])
            else:
                player_dict['avg_fixture_difficulty'] = 3  # Neutral if no fixtures
                player_dict['fixture_variance'] = 0
                player_dict['upcoming_fixtures'] = 'No fixtures'
            
            # Calculate form score
            player_dict['form_score'] = self.get_player_form_score(player)
            
            # Calculate overall recommendation score
            player_dict['recommendation_score'] = (
                player_dict['form_score'] * 0.4 +
                player_dict['avg_fixture_difficulty'] * 0.3 +
                (player_dict['total_points'] / max(player.get('minutes', 1) / 90, 1)) * 0.2 +
                (100 - player_dict['selected_by']) * 0.1  # Differential bonus
            )
            
            player_fixtures.append(player_dict)
        
        return pd.DataFrame(player_fixtures)
    
    def recommend_transfers(self, current_team: List[int], gameweek: int, 
                           free_transfers: int = 1, budget: float = 0) -> Dict:
        """Recommend optimal transfers for the upcoming gameweek."""
        analysis_df = self.analyze_upcoming_fixtures(gameweek)
        players_df = self.client.get_players_df()
        
        # Filter out current team players for potential transfers in
        available_players = analysis_df[~analysis_df['player_id'].isin(current_team)]
        current_players = analysis_df[analysis_df['player_id'].isin(current_team)]
        
        # Find underperforming players in current team
        current_players = current_players.sort_values('recommendation_score')
        transfer_out_candidates = current_players.head(free_transfers + 2)
        
        # Find best replacement options
        transfers = []
        remaining_budget = budget
        
        for _, out_player in transfer_out_candidates.iterrows():
            # Find replacement in same position
            position = out_player['position']
            max_price = out_player['price'] + remaining_budget
            
            replacements = available_players[
                (available_players['position'] == position) &
                (available_players['price'] <= max_price)
            ].sort_values('recommendation_score', ascending=False)
            
            if not replacements.empty:
                in_player = replacements.iloc[0]
                
                transfer = {
                    'out': {
                        'name': out_player['player_name'],
                        'team': out_player['team'],
                        'price': out_player['price'],
                        'score': out_player['recommendation_score']
                    },
                    'in': {
                        'name': in_player['player_name'],
                        'team': in_player['team'],
                        'price': in_player['price'],
                        'score': in_player['recommendation_score'],
                        'fixtures': in_player['upcoming_fixtures']
                    },
                    'net_cost': in_player['price'] - out_player['price'],
                    'score_improvement': in_player['recommendation_score'] - out_player['recommendation_score']
                }
                
                transfers.append(transfer)
                remaining_budget -= transfer['net_cost']
                
                if len(transfers) >= free_transfers:
                    break
        
        return {
            'recommended_transfers': transfers[:free_transfers],
            'additional_options': transfers[free_transfers:free_transfers+2] if len(transfers) > free_transfers else []
        }
    
    def optimize_starting_11(self, squad: List[int], gameweek: int) -> Dict:
        """Select the optimal starting 11 from a 15-player squad."""
        analysis_df = self.analyze_upcoming_fixtures(gameweek, weeks_ahead=1)
        squad_df = analysis_df[analysis_df['player_id'].isin(squad)].copy()
        
        # Sort by recommendation score
        squad_df = squad_df.sort_values('recommendation_score', ascending=False)
        
        starting_11 = []
        bench = []
        
        # Select players by position respecting formation constraints
        for position, limits in self.POSITION_LIMITS.items():
            position_players = squad_df[squad_df['position'] == position]
            
            # Add best players to starting 11
            for i, (_, player) in enumerate(position_players.iterrows()):
                if i < limits['play']:
                    starting_11.append(player.to_dict())
                else:
                    bench.append(player.to_dict())
        
        # Determine captain and vice-captain
        starting_11_sorted = sorted(starting_11, key=lambda x: x['recommendation_score'], reverse=True)
        
        return {
            'starting_11': starting_11,
            'bench': sorted(bench, key=lambda x: x['recommendation_score'], reverse=True),
            'captain': starting_11_sorted[0] if starting_11_sorted else None,
            'vice_captain': starting_11_sorted[1] if len(starting_11_sorted) > 1 else None,
            'total_expected_points': sum(p['recommendation_score'] for p in starting_11)
        }
    
    def get_differential_picks(self, gameweek: int, ownership_threshold: float = 10.0) -> pd.DataFrame:
        """Find high-potential players with low ownership (differentials)."""
        analysis_df = self.analyze_upcoming_fixtures(gameweek)
        
        # Filter for low ownership but high potential
        differentials = analysis_df[
            (analysis_df['selected_by'] < ownership_threshold) &
            (analysis_df['form_score'] > analysis_df['form_score'].quantile(0.7))
        ].sort_values('recommendation_score', ascending=False)
        
        return differentials.head(10)[
            ['player_name', 'team', 'position', 'price', 'selected_by', 
             'form_score', 'recommendation_score', 'upcoming_fixtures']
        ]
    
    def analyze_weekly_matchups(self, gameweek: int) -> Dict:
        """Main function to analyze and recommend players for the upcoming gameweek."""
        self.logger.info(f"Analyzing matchups for Gameweek {gameweek}")
        
        # Get top players by position
        analysis_df = self.analyze_upcoming_fixtures(gameweek)
        
        recommendations = {}
        
        for position in ['GKP', 'DEF', 'MID', 'FWD']:
            position_df = analysis_df[analysis_df['position'] == position].sort_values(
                'recommendation_score', ascending=False
            )
            
            recommendations[position] = position_df.head(5)[
                ['player_name', 'team', 'price', 'form_score', 
                 'avg_fixture_difficulty', 'recommendation_score', 'upcoming_fixtures']
            ].to_dict('records')
        
        # Get overall top picks
        top_picks = analysis_df.nlargest(10, 'recommendation_score')[
            ['player_name', 'team', 'position', 'price', 'recommendation_score', 'upcoming_fixtures']
        ]
        
        # Get differentials
        differentials = self.get_differential_picks(gameweek)
        
        return {
            'gameweek': gameweek,
            'analysis_time': datetime.now().isoformat(),
            'top_picks_by_position': recommendations,
            'overall_top_10': top_picks.to_dict('records'),
            'differential_picks': differentials.to_dict('records'),
            'fixture_analysis': {
                'easiest_fixtures': analysis_df.nlargest(5, 'avg_fixture_difficulty')[
                    ['team', 'upcoming_fixtures']
                ].drop_duplicates('team').to_dict('records'),
                'hardest_fixtures': analysis_df.nsmallest(5, 'avg_fixture_difficulty')[
                    ['team', 'upcoming_fixtures']
                ].drop_duplicates('team').to_dict('records')
            }
        }
    
    def generate_weekly_report(self, gameweek: int, output_file: str = None):
        """Generate a comprehensive weekly report with all recommendations."""
        report = self.analyze_weekly_matchups(gameweek)
        
        # Create formatted output
        output = []
        output.append(f"\n{'='*80}")
        output.append(f"FPL GAMEWEEK {gameweek} MATCHUP ANALYSIS")
        output.append(f"Generated: {report['analysis_time']}")
        output.append(f"{'='*80}\n")
        
        # Top picks by position
        output.append("TOP PICKS BY POSITION")
        output.append("-" * 40)
        for position, players in report['top_picks_by_position'].items():
            output.append(f"\n{position}:")
            for player in players:
                output.append(f"  {player['player_name']} ({player['team']}) - £{player['price']}m")
                output.append(f"    Score: {player['recommendation_score']:.2f} | Fixtures: {player['upcoming_fixtures']}")
        
        # Overall top 10
        output.append(f"\n{'='*40}")
        output.append("OVERALL TOP 10 PICKS")
        output.append("-" * 40)
        for i, player in enumerate(report['overall_top_10'], 1):
            output.append(f"{i}. {player['player_name']} ({player['position']}) - {player['team']} - £{player['price']}m")
            output.append(f"   Score: {player['recommendation_score']:.2f}")
        
        # Differential picks
        output.append(f"\n{'='*40}")
        output.append("DIFFERENTIAL PICKS (<10% ownership)")
        output.append("-" * 40)
        for player in report['differential_picks'][:5]:
            output.append(f"• {player['player_name']} ({player['team']}) - {player['selected_by']}% owned")
            output.append(f"  Score: {player['recommendation_score']:.2f}")
        
        # Fixture analysis
        output.append(f"\n{'='*40}")
        output.append("FIXTURE ANALYSIS")
        output.append("-" * 40)
        output.append("\nTeams with EASIEST fixtures:")
        for team in report['fixture_analysis']['easiest_fixtures']:
            output.append(f"  • {team['team']}: {team['upcoming_fixtures']}")
        
        output.append("\nTeams with HARDEST fixtures:")
        for team in report['fixture_analysis']['hardest_fixtures']:
            output.append(f"  • {team['team']}: {team['upcoming_fixtures']}")
        
        report_text = '\n'.join(output)
        
        # Save to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_text)
            self.logger.info(f"Report saved to {output_file}")
        
        # Also save as JSON for programmatic access
        if output_file:
            json_file = output_file.replace('.txt', '.json')
            with open(json_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
        
        return report_text


def main():
    """Main execution function."""
    # Initialize the analyzer
    analyzer = FPLMatchupAnalyzer()
    
    # Get current gameweek (you might want to fetch this dynamically)
    gameweeks_df = analyzer.client.get_gameweeks_df()
    current_gw = gameweeks_df[gameweeks_df['is_current']].iloc[0] if any(gameweeks_df['is_current']) else gameweeks_df.iloc[0]
    current_gameweek = int(current_gw['id'])
    
    print(f"Analyzing for Gameweek {current_gameweek}...")
    
    # Generate and print the weekly report
    report = analyzer.generate_weekly_report(
        gameweek=current_gameweek,
        output_file=f"gameweek_{current_gameweek}_analysis.txt"
    )
    print(report)
    
    # Example: Get transfer recommendations if you have a current team
    # Replace with your actual team IDs
    example_team = []  # Add your player IDs here
    if example_team:
        transfers = analyzer.recommend_transfers(
            current_team=example_team,
            gameweek=current_gameweek,
            free_transfers=1,
            budget=2.0  # £2m in the bank
        )
        
        print("\n" + "="*40)
        print("TRANSFER RECOMMENDATIONS")
        print("-" * 40)
        for transfer in transfers['recommended_transfers']:
            print(f"OUT: {transfer['out']['name']} (£{transfer['out']['price']}m)")
            print(f"IN:  {transfer['in']['name']} (£{transfer['in']['price']}m)")
            print(f"Net cost: £{transfer['net_cost']:.1f}m | Score improvement: {transfer['score_improvement']:.2f}")
            print()


if __name__ == "__main__":
    main()