import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from fpl_optimizer.api.fpl_client import FPLClient
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

class WildcardOptimizer:
    """Analyzes optimal wildcard timing based on fixtures and form."""
    
    def __init__(self):
        self.fpl = FPLClient()
        
    def get_current_season_data(self):
        """Get current season data including fixtures and form."""
        print("📊 Fetching current season data...")
        
        # Get all data
        bootstrap_data = self.fpl.get_bootstrap_static()
        
        # Current gameweek info
        events = bootstrap_data['events']
        current_gw = next((event for event in events if event['is_current']), None)
        if not current_gw:
            current_gw = next((event for event in events if event['is_next']), events[0])
        
        print(f"📅 Current/Next Gameweek: {current_gw['id']} - {current_gw['name']}")
        
        return bootstrap_data, current_gw['id']
    
    def analyze_fixture_difficulty(self, num_gameweeks=8):
        """Analyze fixture difficulty for upcoming gameweeks."""
        print(f"\n🎯 Analyzing fixture difficulty for next {num_gameweeks} gameweeks...")
        
        try:
            fixtures_df = self.fpl.get_fixtures()
            teams_df = self.fpl.get_teams_df()
            
            # Get current gameweek
            _, current_gw = self.get_current_season_data()
            
            # Filter for upcoming fixtures
            upcoming_fixtures = fixtures_df[
                (fixtures_df['event'] >= current_gw) & 
                (fixtures_df['event'] < current_gw + num_gameweeks) &
                (fixtures_df['finished'] == False)
            ].copy()
            
            if upcoming_fixtures.empty:
                print("⚠️ No upcoming fixtures found")
                return pd.DataFrame()
            
            # Create team fixture difficulty matrix
            team_names = teams_df.set_index('id')['name'].to_dict()
            
            fixture_analysis = []
            
            for team_id in teams_df['id']:
                team_name = team_names[team_id]
                
                # Get home fixtures
                home_fixtures = upcoming_fixtures[upcoming_fixtures['team_h'] == team_id]
                # Get away fixtures  
                away_fixtures = upcoming_fixtures[upcoming_fixtures['team_a'] == team_id]
                
                team_fixtures = []
                total_difficulty = 0
                fixture_count = 0
                
                for _, fixture in home_fixtures.iterrows():
                    difficulty = fixture['team_h_difficulty']
                    opponent = team_names.get(fixture['team_a'], f"Team {fixture['team_a']}")
                    team_fixtures.append(f"vs {opponent} (H) - {difficulty}")
                    total_difficulty += difficulty
                    fixture_count += 1
                
                for _, fixture in away_fixtures.iterrows():
                    difficulty = fixture['team_a_difficulty']
                    opponent = team_names.get(fixture['team_h'], f"Team {fixture['team_h']}")
                    team_fixtures.append(f"@ {opponent} (A) - {difficulty}")
                    total_difficulty += difficulty
                    fixture_count += 1
                
                avg_difficulty = total_difficulty / fixture_count if fixture_count > 0 else 0
                
                fixture_analysis.append({
                    'team': team_name,
                    'fixtures': '; '.join(team_fixtures),
                    'fixture_count': fixture_count,
                    'total_difficulty': total_difficulty,
                    'avg_difficulty': round(avg_difficulty, 2)
                })
            
            fixture_df = pd.DataFrame(fixture_analysis)
            return fixture_df.sort_values('avg_difficulty')
            
        except Exception as e:
            print(f"❌ Error analyzing fixtures: {e}")
            return pd.DataFrame()
    
    def analyze_early_season_form(self):
        """Analyze early season player performance after 2 gameweeks."""
        print("\n📈 Analyzing early season form (2 gameweeks played)...")
        
        players_df = self.fpl.get_players_df()
        
        # Filter active players (played some minutes)
        active_players = players_df[players_df['minutes'] > 0].copy()
        
        if active_players.empty:
            print("⚠️ No player data available")
            return pd.DataFrame()
        
        # Calculate form metrics
        active_players['points_per_90'] = (active_players['total_points'] / active_players['minutes']) * 90
        active_players['points_per_game'] = active_players['total_points'] / 2  # 2 games played
        active_players['minutes_per_game'] = active_players['minutes'] / 2
        
        # Form analysis
        overperformers = active_players[
            (active_players['total_points'] > active_players['ep_this']) &  # Exceeding expected points
            (active_players['minutes'] >= 90)  # Played at least 90 minutes
        ].copy()
        
        underperformers = active_players[
            (active_players['total_points'] < active_players['ep_this'] * 0.7) &  # Significantly under expected
            (active_players['selected_by_percent'] > 5)  # Popular players
        ].copy()
        
        return {
            'all_players': active_players,
            'overperformers': overperformers.sort_values('points_per_90', ascending=False),
            'underperformers': underperformers.sort_values('total_points')
        }
    
    def calculate_wildcard_timing(self):
        """Calculate optimal wildcard timing windows."""
        print("\n🔮 Calculating optimal wildcard timing...")
        
        try:
            # Get fixture difficulty for longer period
            fixture_df = self.analyze_fixture_difficulty(16)  # Look ahead 16 gameweeks
            
            if fixture_df.empty:
                print("⚠️ Cannot calculate wildcard timing without fixture data")
                return {}
            
            # Get current gameweek
            _, current_gw = self.get_current_season_data()
            
            # Define potential wildcard windows
            wildcard_windows = {
                'Early Wildcard (GW4-6)': {
                    'gameweeks': list(range(4, 7)),
                    'pros': ['React to early injuries', 'Capitalize on early form', 'Avoid price rises'],
                    'cons': ['Limited data sample', 'Might miss better opportunities later']
                },
                'International Break (GW7-8)': {
                    'gameweeks': list(range(7, 9)),
                    'pros': ['More data available', 'Post-international break assessment', 'Good fixture swings'],
                    'cons': ['Some price rises already happened', 'Popular timing']
                },
                'October Wildcard (GW9-11)': {
                    'gameweeks': list(range(9, 12)),
                    'pros': ['Solid form data', 'Before difficult fixture periods', 'Champions League impact visible'],
                    'cons': ['Late for early opportunities', 'High ownership changes']
                },
                'Pre-Christmas (GW12-14)': {
                    'gameweeks': list(range(12, 15)),
                    'pros': ['Before fixture congestion', 'Rotation patterns clear', 'Final good opportunity'],
                    'cons': ['Very late first wildcard', 'Missing early value']
                }
            }
            
            # Calculate scores for each window
            window_scores = {}
            
            for window_name, window_data in wildcard_windows.items():
                if min(window_data['gameweeks']) > current_gw + 16:
                    continue
                    
                score = 0
                analysis = []
                
                # Factor 1: Current gameweek timing (earlier is generally better for first WC)
                if min(window_data['gameweeks']) <= current_gw + 6:
                    score += 3
                    analysis.append("✅ Good timing for first wildcard")
                elif min(window_data['gameweeks']) <= current_gw + 10:
                    score += 2
                    analysis.append("⚠️ Moderate timing")
                else:
                    score += 1
                    analysis.append("❌ Late for first wildcard")
                
                # Factor 2: Data availability (more games = better decisions)
                games_played = max(0, min(window_data['gameweeks']) - 1)
                if games_played >= 6:
                    score += 3
                    analysis.append("✅ Sufficient data for decisions")
                elif games_played >= 4:
                    score += 2
                    analysis.append("⚠️ Moderate data available")
                else:
                    score += 1
                    analysis.append("❌ Limited data available")
                
                window_scores[window_name] = {
                    'score': score,
                    'analysis': analysis,
                    'gameweeks': window_data['gameweeks'],
                    'pros': window_data['pros'],
                    'cons': window_data['cons']
                }
            
            return window_scores
            
        except Exception as e:
            print(f"❌ Error calculating wildcard timing: {e}")
            return {}
    
    def get_transfer_recommendations(self):
        """Get immediate transfer recommendations before wildcard."""
        print("\n🔄 Analyzing immediate transfer opportunities...")
        
        form_data = self.analyze_early_season_form()
        if not form_data:
            return {}
        
        # Top targets (good early form, reasonable price)
        targets = form_data['overperformers'][
            (form_data['overperformers']['price'] <= 12) &  # Affordable
            (form_data['overperformers']['total_points'] >= 10)  # Good start
        ].head(10)
        
        # Players to avoid (poor form, high ownership)
        avoid = form_data['underperformers'][
            (form_data['underperformers']['selected_by_percent'] > 10)  # Popular
        ].head(10)
        
        return {
            'top_targets': targets[['web_name', 'team_name', 'position', 'price', 'total_points', 'points_per_90']],
            'avoid_players': avoid[['web_name', 'team_name', 'position', 'price', 'total_points', 'selected_by_percent']]
        }
    
    def run_full_analysis(self):
        """Run complete wildcard timing analysis."""
        print("🏈 FPL WILDCARD TIMING ANALYSIS")
        print("=" * 60)
        
        # Get current data
        bootstrap_data, current_gw = self.get_current_season_data()
        
        # Fixture analysis
        fixture_difficulty = self.analyze_fixture_difficulty()
        if not fixture_difficulty.empty:
            print("\n🎯 FIXTURE DIFFICULTY RANKING (Next 8 GWs)")
            print("=" * 50)
            print("EASIEST FIXTURES:")
            print(fixture_difficulty.head(5)[['team', 'fixture_count', 'avg_difficulty']].to_string(index=False))
            print("\nHARDEST FIXTURES:")
            print(fixture_difficulty.tail(5)[['team', 'fixture_count', 'avg_difficulty']].to_string(index=False))
        
        # Form analysis
        form_analysis = self.analyze_early_season_form()
        if form_analysis:
            print(f"\n📈 EARLY SEASON FORM ANALYSIS")
            print("=" * 50)
            print("TOP OVERPERFORMERS (Points per 90 mins):")
            if not form_analysis['overperformers'].empty:
                print(form_analysis['overperformers'].head(8)[['web_name', 'team_name', 'position', 'total_points', 'points_per_90']].to_string(index=False))
            
            print(f"\nUNDERPERFORMING POPULAR PLAYERS:")
            if not form_analysis['underperformers'].empty:
                print(form_analysis['underperformers'].head(5)[['web_name', 'team_name', 'total_points', 'selected_by_percent']].to_string(index=False))
        
        # Wildcard timing
        wildcard_analysis = self.calculate_wildcard_timing()
        if wildcard_analysis:
            print(f"\n🔮 WILDCARD TIMING RECOMMENDATIONS")
            print("=" * 50)
            
            # Sort by score
            sorted_windows = sorted(wildcard_analysis.items(), key=lambda x: x[1]['score'], reverse=True)
            
            for i, (window_name, data) in enumerate(sorted_windows, 1):
                print(f"\n{i}. {window_name} (Score: {data['score']}/6)")
                print(f"   Gameweeks: {'-'.join(map(str, [min(data['gameweeks']), max(data['gameweeks'])]))}")
                for analysis_point in data['analysis']:
                    print(f"   {analysis_point}")
                print("   PROS:", " | ".join(data['pros']))
                print("   CONS:", " | ".join(data['cons']))
        
        # Transfer recommendations
        transfer_recs = self.get_transfer_recommendations()
        if transfer_recs:
            print(f"\n🔄 IMMEDIATE TRANSFER TARGETS (Before Wildcard)")
            print("=" * 50)
            if not transfer_recs['top_targets'].empty:
                print("TOP TARGETS:")
                print(transfer_recs['top_targets'].to_string(index=False))
            
            if not transfer_recs['avoid_players'].empty:
                print(f"\nPLAYERS TO AVOID:")
                print(transfer_recs['avoid_players'][['web_name', 'team_name', 'total_points', 'selected_by_percent']].to_string(index=False))
        
        print(f"\n" + "=" * 60)
        print("📋 SUMMARY RECOMMENDATION")
        print("=" * 60)
        
        if wildcard_analysis and sorted_windows:
            best_window = sorted_windows[0]
            print(f"🎯 RECOMMENDED WILDCARD TIMING: {best_window[0]}")
            print(f"   Optimal Gameweek Range: GW{min(best_window[1]['gameweeks'])}-{max(best_window[1]['gameweeks'])}")
            print(f"   Confidence Score: {best_window[1]['score']}/6")
            
            if best_window[1]['score'] >= 5:
                print("   📈 HIGH CONFIDENCE - Excellent timing window")
            elif best_window[1]['score'] >= 4:
                print("   📊 MODERATE CONFIDENCE - Good timing window")
            else:
                print("   📉 LOW CONFIDENCE - Consider other options")

# Run the analysis
if __name__ == "__main__":
    optimizer = WildcardOptimizer()
    optimizer.run_full_analysis()
