import pandas as pd
import numpy as np
import requests
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

class FPLNailedPlayersOptimizer:
    """
    FPL optimizer that focuses on consistently playing players only.
    Filters out rotation risks and benchwarmers.
    """
    
    def __init__(self):
        self.base_url = "https://fantasy.premierleague.com/api/"
        
    def fetch_fpl_data(self):
        """Fetch FPL data with focus on playing time."""
        print("Fetching FPL data...")
        
        response = requests.get(f"{self.base_url}bootstrap-static/")
        data = response.json()
        
        players_df = pd.DataFrame(data['elements'])
        teams_df = pd.DataFrame(data['teams'])
        
        # Position mapping
        position_mapping = {1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD'}
        
        # Merge team data
        players_df = players_df.merge(
            teams_df[['id', 'name', 'short_name']], 
            left_on='team', right_on='id', suffixes=('', '_team')
        )
        
        players_df['position'] = players_df['element_type'].map(position_mapping)
        players_df['price'] = players_df['now_cost'] / 10.0
        players_df['team_name'] = players_df['name']
        
        return players_df, teams_df
    
    def filter_nailed_players(self, players_df: pd.DataFrame) -> pd.DataFrame:
        """Filter for consistently playing players only."""
        print("Filtering for nailed-on players...")
        
        # Convert all necessary columns to numeric
        numeric_cols = ['minutes', 'starts', 'total_points', 'form', 'selected_by_percent', 
                       'goals_scored', 'assists', 'clean_sheets', 'expected_goals', 'expected_assists',
                       'saves', 'penalties_saved', 'goals_conceded', 'yellow_cards', 'red_cards']
        
        for col in numeric_cols:
            if col in players_df.columns:
                players_df[col] = pd.to_numeric(players_df[col], errors='coerce').fillna(0)
        
        # Calculate playing consistency metrics
        gameweeks_played = 4  # Assuming 4 GWs so far
        players_df['minutes_per_gw'] = players_df['minutes'] / gameweeks_played
        players_df['start_percentage'] = (players_df['starts'] / gameweeks_played) * 100
        
        # Nailed-on criteria (adjust these based on your risk tolerance)
        nailed_criteria = {
            'GK': {
                'min_minutes_per_gw': 70,  # At least ~80 minutes per gameweek on average
                'min_starts': 3,           # Started at least 3/4 games
                'min_total_minutes': 270   # At least 270 total minutes
            },
            'DEF': {
                'min_minutes_per_gw': 60,  # Defenders can be subbed more
                'min_starts': 2,           # At least 2 starts
                'min_total_minutes': 180
            },
            'MID': {
                'min_minutes_per_gw': 50,  # Some rotation expected
                'min_starts': 2,
                'min_total_minutes': 150
            },
            'FWD': {
                'min_minutes_per_gw': 45,  # Forwards often rotated
                'min_starts': 2,
                'min_total_minutes': 120
            }
        }
        
        nailed_players = []
        
        for position, criteria in nailed_criteria.items():
            pos_players = players_df[players_df['position'] == position].copy()
            
            # Apply nailed-on filters
            nailed_pos = pos_players[
                (pos_players['minutes_per_gw'] >= criteria['min_minutes_per_gw']) &
                (pos_players['starts'] >= criteria['min_starts']) &
                (pos_players['minutes'] >= criteria['min_total_minutes']) &
                (pos_players['total_points'] > 0)  # Must have scored some points
            ]
            
            print(f"  {position}: {len(nailed_pos)}/{len(pos_players)} players are nailed-on")
            nailed_players.append(nailed_pos)
        
        nailed_df = pd.concat(nailed_players, ignore_index=True) if nailed_players else pd.DataFrame()
        
        # Add form filter - remove players with very poor recent form
        if not nailed_df.empty and 'form' in nailed_df.columns:
            nailed_df = nailed_df[nailed_df['form'] > 0.5]  # At least some recent form
        
        return nailed_df
    
    def get_fixture_difficulty(self, teams_df: pd.DataFrame) -> pd.DataFrame:
        """Get fixture difficulty analysis for next 5 gameweeks."""
        print("Analyzing fixture difficulty...")
        
        try:
            # Get fixtures
            fixtures_response = requests.get(f"{self.base_url}fixtures/")
            fixtures_df = pd.DataFrame(fixtures_response.json())
            
            # Convert to numeric
            fixtures_df['event'] = pd.to_numeric(fixtures_df['event'], errors='coerce')
            fixtures_df['team_h_difficulty'] = pd.to_numeric(fixtures_df['team_h_difficulty'], errors='coerce')
            fixtures_df['team_a_difficulty'] = pd.to_numeric(fixtures_df['team_a_difficulty'], errors='coerce')
            
            current_gw = 5  # Starting from GW5
            upcoming_fixtures = fixtures_df[
                (fixtures_df['event'] >= current_gw) & 
                (fixtures_df['event'] < current_gw + 5) &
                (fixtures_df['event'].notna())
            ].copy()
            
            fixture_analysis = {}
            
            for _, team in teams_df.iterrows():
                team_id = team['id']
                team_fixtures = upcoming_fixtures[
                    (upcoming_fixtures['team_h'] == team_id) | 
                    (upcoming_fixtures['team_a'] == team_id)
                ]
                
                difficulties = []
                fixture_count = 0
                
                for _, fixture in team_fixtures.iterrows():
                    if fixture['team_h'] == team_id:  # Home game
                        difficulty = fixture['team_h_difficulty']
                    else:  # Away game
                        difficulty = fixture['team_a_difficulty']
                    
                    if pd.notna(difficulty):
                        difficulties.append(difficulty)
                        fixture_count += 1
                
                if difficulties:
                    avg_difficulty = np.mean(difficulties)
                    median_difficulty = np.median(difficulties)
                else:
                    avg_difficulty = 3.0  # Default neutral
                    median_difficulty = 3.0
                
                fixture_analysis[team_id] = {
                    'avg_difficulty': avg_difficulty,
                    'median_difficulty': median_difficulty,
                    'fixture_count': fixture_count,
                    'difficulty_rating': 'EASY' if avg_difficulty < 2.5 else 'MEDIUM' if avg_difficulty < 3.5 else 'HARD'
                }
            
            return pd.DataFrame(fixture_analysis).T
            
        except Exception as e:
            print(f"Could not fetch fixtures: {e}")
            # Return default fixture analysis
            default_fixture = {
                'avg_difficulty': 3.0,
                'median_difficulty': 3.0,
                'fixture_count': 5,
                'difficulty_rating': 'MEDIUM'
            }
            
            fixture_analysis = {}
            for _, team in teams_df.iterrows():
                fixture_analysis[team['id']] = default_fixture
            
            return pd.DataFrame(fixture_analysis).T

    def calculate_player_scores(self, players_df: pd.DataFrame, fixture_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate comprehensive scores for nailed players including defensive contributions."""
        print("Calculating player scores with defensive contributions...")
        
        players_df = players_df.copy()
        
        # Basic metrics
        players_df['points_per_game'] = np.where(
            players_df['starts'] > 0,
            players_df['total_points'] / players_df['starts'],
            0
        )
        
        players_df['points_per_90'] = np.where(
            players_df['minutes'] > 0,
            players_df['total_points'] * 90 / players_df['minutes'],
            0
        )
        
        # Defensive contribution points calculation
        players_df['defensive_points'] = (
            players_df['clean_sheets'] * 4 +           # Clean sheet points
            players_df['goals_conceded'] * -1 +        # Points lost for goals conceded (GK/DEF)
            players_df['saves'].fillna(0) * 0.33 +     # Save points (GK mainly)
            players_df['penalties_saved'].fillna(0) * 5 +  # Penalty save bonus
            players_df['yellow_cards'].fillna(0) * -1 +     # Yellow card penalty
            players_df['red_cards'].fillna(0) * -3          # Red card penalty
        )
        
        # Merge fixture difficulty
        players_df = players_df.merge(
            fixture_df.reset_index().rename(columns={'index': 'team'}),
            on='team', how='left'
        )
        
        # Fill missing fixture data
        players_df['avg_difficulty'] = players_df['avg_difficulty'].fillna(3.0)
        players_df['median_difficulty'] = players_df['median_difficulty'].fillna(3.0)
        players_df['difficulty_rating'] = players_df['difficulty_rating'].fillna('MEDIUM')
        
        # Position-specific scoring with fixture adjustments
        position_weights = {
            'GK': {
                'total_points': 1.0,
                'defensive_points': 1.2,
                'clean_sheets': 4.0,
                'saves': 0.33,
                'form': 0.8,
                'minutes_per_gw': 0.02,
                'fixture_bonus': 0.5  # Easier fixtures = more clean sheet potential
            },
            'DEF': {
                'total_points': 1.0,
                'defensive_points': 1.0,
                'clean_sheets': 3.0,
                'goals_scored': 6.0,
                'assists': 3.0,
                'form': 0.8,
                'expected_goals': 5.0,
                'minutes_per_gw': 0.02,
                'fixture_bonus': 0.4
            },
            'MID': {
                'total_points': 1.0,
                'defensive_points': 0.3,  # Some defensive contribution for midfielders
                'goals_scored': 4.0,
                'assists': 3.0,
                'expected_goals': 4.0,
                'expected_assists': 3.0,
                'form': 1.0,
                'minutes_per_gw': 0.02,
                'fixture_bonus': 0.2
            },
            'FWD': {
                'total_points': 1.0,
                'goals_scored': 3.5,
                'assists': 2.0,
                'expected_goals': 5.0,
                'form': 1.2,
                'minutes_per_gw': 0.03,
                'fixture_bonus': 0.1
            }
        }
        
        players_df['quality_score'] = 0
        
        for position, weights in position_weights.items():
            mask = players_df['position'] == position
            
            if mask.any():
                score = 0
                for metric, weight in weights.items():
                    if metric == 'fixture_bonus':
                        # Easier fixtures get bonus (lower difficulty = higher bonus)
                        fixture_bonus = (4 - players_df.loc[mask, 'avg_difficulty']) * weight
                        score += fixture_bonus
                    elif metric in players_df.columns:
                        # Normalize metrics and apply weights
                        metric_values = players_df.loc[mask, metric].fillna(0)
                        score += metric_values * weight
                
                players_df.loc[mask, 'quality_score'] = score
        
        return players_df.sort_values('quality_score', ascending=False)
    
    def get_best_by_position(self, players_df: pd.DataFrame, top_n: int = 15) -> Dict:
        """Get the best nailed-on players by position with enhanced metrics."""
        
        best_players = {}
        
        for position in ['GK', 'DEF', 'MID', 'FWD']:
            pos_players = players_df[players_df['position'] == position].copy()
            
            if len(pos_players) == 0:
                best_players[position] = pd.DataFrame()
                continue
            
            # Sort by quality score and select top players
            top_pos_players = pos_players.nlargest(top_n, 'quality_score')
            
            # Base display columns
            display_cols = ['web_name', 'team_name', 'price', 'total_points', 'quality_score', 
                           'form', 'minutes', 'starts', 'minutes_per_gw', 'start_percentage', 
                           'selected_by_percent', 'avg_difficulty', 'median_difficulty', 'difficulty_rating']
            
            # Add defensive contribution for GK, DEF, MID
            if position in ['GK', 'DEF', 'MID']:
                display_cols.extend(['defensive_points', 'clean_sheets'])
            
            # Add position-specific stats
            if position == 'GK':
                display_cols.extend(['saves', 'penalties_saved'])
            elif position == 'DEF':
                display_cols.extend(['goals_scored', 'assists', 'expected_goals', 'expected_assists'])
            elif position in ['MID', 'FWD']:
                display_cols.extend(['goals_scored', 'assists', 'expected_goals', 'expected_assists'])
            
            # Filter columns that exist
            available_cols = [col for col in display_cols if col in top_pos_players.columns]
            best_players[position] = top_pos_players[available_cols].round(2)
        
        return best_players
    
    def analyze_player_reliability(self, players_df: pd.DataFrame) -> Dict:
        """Analyze reliability metrics for players."""
        
        reliability_analysis = {}
        
        for position in ['GK', 'DEF', 'MID', 'FWD']:
            pos_players = players_df[players_df['position'] == position]
            
            if len(pos_players) == 0:
                continue
            
            # Get top 10 by quality score
            top_players = pos_players.nlargest(10, 'quality_score')
            
            reliability_data = []
            for _, player in top_players.iterrows():
                reliability_score = (
                    player['start_percentage'] * 0.4 +
                    (player['minutes_per_gw'] / 90) * 100 * 0.3 +
                    min(player['form'] * 10, 100) * 0.2 +
                    min(player['selected_by_percent'], 50) * 0.1
                )
                
                reliability_data.append({
                    'player': player['web_name'],
                    'team': player['team_name'],
                    'price': player['price'],
                    'reliability_score': round(reliability_score, 1),
                    'start_rate': f"{player['start_percentage']:.0f}%",
                    'mins_per_gw': round(player['minutes_per_gw'], 0),
                    'form': player['form'],
                    'ownership': f"{player['selected_by_percent']:.1f}%"
                })
            
            reliability_analysis[position] = pd.DataFrame(reliability_data)
        
        return reliability_analysis
    
    def display_recommendations(self, best_players: Dict, reliability_analysis: Dict):
        """Display the best nailed-on players by position with enhanced metrics."""
        
        print("\n" + "="*100)
        print("BEST NAILED-ON PLAYERS BY POSITION (Enhanced with Defensive Points & Fixtures)")
        print("="*100)
        
        recommendations = {
            'GK': [],
            'DEF': [],
            'MID': [],
            'FWD': []
        }
        
        for position in ['GK', 'DEF', 'MID', 'FWD']:
            print(f"\n🎯 {position} - TOP NAILED-ON PICKS:")
            print("-" * 80)
            
            if position not in best_players or best_players[position].empty:
                print("   No reliable players found for this position")
                continue
            
            top_players = best_players[position].head(10)
            
            for i, (_, player) in enumerate(top_players.iterrows(), 1):
                # Create player summary
                summary = f"£{player['price']:.1f}m | {player['total_points']} pts | Form: {player['form']:.1f}"
                
                # Add defensive contribution for relevant positions
                if position in ['GK', 'DEF', 'MID'] and 'defensive_points' in player:
                    def_pts = player.get('defensive_points', 0)
                    summary += f" | Def: {def_pts:.1f}"
                
                # Add position-specific stats
                if position == 'GK':
                    cs = player.get('clean_sheets', 0)
                    saves = player.get('saves', 0)
                    penalties_saved = player.get('penalties_saved', 0)
                    summary += f" | {cs} CS | {saves} saves"
                    if penalties_saved > 0:
                        summary += f" | {penalties_saved} pen saves"
                elif position == 'DEF':
                    cs = player.get('clean_sheets', 0)
                    goals = player.get('goals_scored', 0)
                    assists = player.get('assists', 0)
                    xg = player.get('expected_goals', 0)
                    xa = player.get('expected_assists', 0)
                    summary += f" | {cs} CS | {goals}G {assists}A | xG:{xg:.1f} xA:{xa:.1f}"
                else:  # MID/FWD
                    goals = player.get('goals_scored', 0)
                    assists = player.get('assists', 0)
                    xg = player.get('expected_goals', 0)
                    xa = player.get('expected_assists', 0)
                    summary += f" | {goals}G {assists}A | xG:{xg:.1f} xA:{xa:.1f}"
                
                # Playing time and fixture info
                start_rate = player.get('start_percentage', 0)
                mins_per_gw = player.get('minutes_per_gw', 0)
                avg_diff = player.get('avg_difficulty', 3.0)
                med_diff = player.get('median_difficulty', 3.0)
                diff_rating = player.get('difficulty_rating', 'MEDIUM')
                
                # Fixture difficulty color coding
                if diff_rating == 'EASY':
                    fixture_emoji = '🟢'
                elif diff_rating == 'MEDIUM':
                    fixture_emoji = '🟡'
                else:
                    fixture_emoji = '🔴'
                
                # Recommendation level
                if i <= 3:
                    level = "🌟 PREMIUM PICK"
                elif i <= 6:
                    level = "✅ SOLID PICK"
                else:
                    level = "💡 CONSIDER"
                
                print(f"   {i:2d}. {level}")
                print(f"       {player['web_name']} ({player['team_name']})")
                print(f"       {summary}")
                print(f"       Playing: {start_rate:.0f}% starts | {mins_per_gw:.0f} mins/GW")
                print(f"       Fixtures: {fixture_emoji} {diff_rating} (Avg: {avg_diff:.1f}, Med: {med_diff:.1f})")
                
                # Add to recommendations for summary
                if i <= 5:
                    recommendations[position].append({
                        'name': player['web_name'],
                        'team': player['team_name'],
                        'price': player['price'],
                        'summary': summary,
                        'fixture_rating': diff_rating,
                        'defensive_points': player.get('defensive_points', 0) if position in ['GK', 'DEF', 'MID'] else None
                    })
                
                print()
        
        # Enhanced recommendations summary
        print("\n" + "="*100)
        print("🏆 TOP WILDCARD RECOMMENDATIONS (NAILED-ON + FIXTURES + DEFENSIVE VALUE)")
        print("="*100)
        
        for position in ['GK', 'DEF', 'MID', 'FWD']:
            if recommendations[position]:
                print(f"\n{position} - TOP 3 RECOMMENDATIONS:")
                for i, player in enumerate(recommendations[position][:3], 1):
                    fixture_info = f"({player['fixture_rating']} fixtures)"
                    defensive_info = ""
                    if player['defensive_points'] is not None:
                        defensive_info = f" | Def pts: {player['defensive_points']:.1f}"
                    
                    print(f"   {i}. {player['name']} ({player['team']}) - {player['summary']} {fixture_info}{defensive_info}")
        
        # Fixture difficulty summary
        print(f"\n📅 FIXTURE DIFFICULTY LEGEND:")
        print(f"   🟢 EASY: Avg difficulty < 2.5 (Great for clean sheets/goals)")
        print(f"   🟡 MEDIUM: Avg difficulty 2.5-3.5 (Balanced fixtures)")
        print(f"   🔴 HARD: Avg difficulty > 3.5 (Tough opponents ahead)")
        
        print(f"\n🛡️ DEFENSIVE POINTS BREAKDOWN:")
        print(f"   • Clean Sheets: +4 pts each")
        print(f"   • Goals Conceded: -1 pt each (GK/DEF)")
        print(f"   • Saves: +0.33 pts each (mainly GK)")
        print(f"   • Penalty Saves: +5 pts each")
        print(f"   • Yellow Cards: -1 pt each")
        print(f"   • Red Cards: -3 pts each")
        
        print(f"\n💡 KEY ENHANCED PRINCIPLES:")
        print(f"   • Prioritize players with good defensive contribution")
        print(f"   • Easy fixtures boost goalkeeper and defender appeal")
        print(f"   • Consider both attacking and defensive potential")
        print(f"   • Fixture difficulty affects clean sheet probability")
        
        return recommendations
    
    def run_analysis(self):
        """Run the complete nailed players analysis with enhanced metrics."""
        print("Starting Enhanced FPL Nailed-On Players Analysis...")
        
        # Fetch data
        players_df, teams_df = self.fetch_fpl_data()
        
        # Get fixture difficulty
        fixture_df = self.get_fixture_difficulty(teams_df)
        
        # Filter for nailed players
        nailed_players = self.filter_nailed_players(players_df)
        
        if nailed_players.empty:
            print("No nailed-on players found with current criteria!")
            return None
        
        # Calculate scores with fixtures and defensive contributions
        scored_players = self.calculate_player_scores(nailed_players, fixture_df)
        
        # Get best by position
        best_players = self.get_best_by_position(scored_players)
        
        # Analyze reliability
        reliability_analysis = self.analyze_player_reliability(scored_players)
        
        # Display recommendations
        recommendations = self.display_recommendations(best_players, reliability_analysis)
        
        return {
            'best_players': best_players,
            'recommendations': recommendations,
            'reliability_analysis': reliability_analysis,
            'fixture_analysis': fixture_df
        }

# Usage
if __name__ == "__main__":
    optimizer = FPLNailedPlayersOptimizer()
    results = optimizer.run_analysis()
    
    print("\n" + "="*50)
    print("✅ Analysis complete!")
    print("Focus on the TOP 3 recommendations per position")
    print("These players have the best combination of:")
    print("  • Consistent playing time") 
    print("  • Good form and points")
    print("  • Low rotation risk")
    print("="*50)