import sys
import os
sys.path.append('src')

from fpl_optimizer.api.fpl_client import FPLClient
import pandas as pd
import numpy as np
from pulp import LpMaximize, LpProblem, LpVariable, lpSum, value, LpStatus
import warnings
warnings.filterwarnings('ignore')

class EnhancedWildcardOptimizer:
    """Enhanced FPL wildcard optimizer for mini-league comeback strategy."""
    
    def __init__(self, gameweek=3, mini_league_mode=True):
        self.fpl = FPLClient()
        self.current_gw = gameweek
        self.mini_league_mode = mini_league_mode
        self.budget = 100.0
        self.formation_constraints = {
            'GK': (2, 2),   # Exactly 2 goalkeepers
            'DEF': (5, 5),  # Exactly 5 defenders
            'MID': (5, 5),  # Exactly 5 midfielders
            'FWD': (3, 3)   # Exactly 3 forwards
        }
        
    def get_enhanced_player_data(self):
        """Get player data with fixture analysis and availability checks."""
        print(f"Fetching enhanced player data for GW{self.current_gw}...")
        
        # Get players data
        players_df = self.fpl.get_players_df()
        
        # Get fixture data for next 4-6 gameweeks
        fixtures_df = self.fpl.get_fixtures_df()
        upcoming_fixtures = fixtures_df[
            (fixtures_df['event'] >= self.current_gw) & 
            (fixtures_df['event'] <= self.current_gw + 5)
        ]
        
        # Clean numeric fields
        numeric_fields = [
            'selected_by_percent', 'ep_this', 'ep_next', 'form',
            'points_per_game', 'total_points', 'minutes', 'goals_scored',
            'assists', 'clean_sheets', 'goals_conceded', 'own_goals',
            'penalties_saved', 'penalties_missed', 'yellow_cards', 'red_cards',
            'saves', 'bonus', 'bps', 'influence', 'creativity', 'threat', 'ict_index',
            'expected_goals', 'expected_assists', 'expected_goal_involvements',
            'expected_goals_conceded', 'now_cost'
        ]
        
        for field in numeric_fields:
            if field in players_df.columns:
                players_df[field] = pd.to_numeric(players_df[field], errors='coerce').fillna(0)
        
        # Convert price from tenths to actual value
        players_df['price'] = players_df['now_cost'] / 10.0
        
        # CRITICAL: Filter out unavailable players
        available_players = players_df[
            (players_df['status'] != 'u') &  # Not unavailable
            (players_df['status'] != 's') &  # Not suspended
            (players_df['chance_of_playing_this_round'] != 0)  # Has chance to play
        ].copy()
        
        # Enhanced viability filters for GW3 onwards
        viable_players = available_players[
            # More aggressive filtering for established viability
            (available_players['minutes'] >= 90) |  # Played at least 90 minutes OR
            (available_players['price'] <= 4.5) |   # Cheap bench fodder OR
            (available_players['total_points'] >= 10) |  # Good early form OR
            (available_players['ep_next'] >= 3.0)  # High expected points next GW
        ].copy()
        
        print(f"Filtered to {len(viable_players)} viable players from {len(players_df)} total")
        
        return viable_players, upcoming_fixtures
    
    def calculate_fixture_difficulty(self, players_df, fixtures_df):
        """Calculate fixture difficulty and strength for next 4-6 gameweeks."""
        print("Calculating fixture difficulty ratings...")
        
        # Get team strength from recent performance
        team_stats = players_df.groupby('team').agg({
            'goals_scored': 'sum',
            'goals_conceded': 'sum',
            'clean_sheets': 'sum',
            'total_points': 'mean'
        }).reset_index()
        
        # Create team strength ratings (normalized 1-5 scale)
        team_stats['attack_strength'] = ((team_stats['goals_scored'] - team_stats['goals_scored'].min()) / 
                                       (team_stats['goals_scored'].max() - team_stats['goals_scored'].min()) * 4) + 1
        
        team_stats['defense_strength'] = 5 - ((team_stats['goals_conceded'] - team_stats['goals_conceded'].min()) / 
                                            (team_stats['goals_conceded'].max() - team_stats['goals_conceded'].min()) * 4)
        
        # Calculate fixture difficulty for each team
        fixture_ratings = {}
        
        for team_id in players_df['team'].unique():
            team_fixtures = fixtures_df[
                ((fixtures_df['team_h'] == team_id) | (fixtures_df['team_a'] == team_id)) &
                (fixtures_df['event'] >= self.current_gw) &
                (fixtures_df['event'] <= self.current_gw + 3)  # Next 4 GWs
            ].copy()
            
            if team_fixtures.empty:
                fixture_ratings[team_id] = {'difficulty': 3.0, 'home_games': 0}
                continue
            
            difficulties = []
            home_games = 0
            
            for _, fixture in team_fixtures.iterrows():
                if fixture['team_h'] == team_id:  # Home game
                    opponent_id = fixture['team_a']
                    home_games += 1
                    difficulty_modifier = -0.3  # Home advantage
                else:  # Away game
                    opponent_id = fixture['team_h']
                    difficulty_modifier = 0.3   # Away disadvantage
                
                # Get opponent strength
                opponent_strength = team_stats[team_stats['team'] == opponent_id]['defense_strength'].values
                if len(opponent_strength) > 0:
                    base_difficulty = opponent_strength[0]
                else:
                    base_difficulty = 3.0
                
                difficulties.append(max(1, min(5, base_difficulty + difficulty_modifier)))
            
            avg_difficulty = np.mean(difficulties) if difficulties else 3.0
            fixture_ratings[team_id] = {
                'difficulty': avg_difficulty,
                'home_games': home_games,
                'fixture_count': len(difficulties)
            }
        
        # Add fixture metrics to players
        players_df['fixture_difficulty'] = players_df['team'].map(
            lambda x: fixture_ratings.get(x, {}).get('difficulty', 3.0)
        )
        players_df['home_games_next4'] = players_df['team'].map(
            lambda x: fixture_ratings.get(x, {}).get('home_games', 0)
        )
        
        return players_df
    
    def calculate_enhanced_metrics(self, players_df):
        """Calculate enhanced performance metrics with recent form emphasis."""
        print("Calculating enhanced player metrics with form focus...")
        
        players = players_df.copy()
        
        # Safe division with minimum games played
        players['games_played'] = np.maximum(players['minutes'] / 90, 0.5)
        
        # Recent form metrics (last 3-4 games more heavily weighted)
        players['recent_form_multiplier'] = np.where(
            players['form'] >= 6, 1.2,  # Excellent form
            np.where(players['form'] >= 4, 1.0,  # Good form  
                   np.where(players['form'] >= 2, 0.9, 0.8))  # Poor form
        )
        
        # Enhanced rate stats per 90 minutes
        players['points_per_90'] = np.minimum((players['total_points'] / players['minutes']) * 90, 25)
        players['goals_per_90'] = np.minimum((players['goals_scored'] / players['minutes']) * 90, 2.5)
        players['assists_per_90'] = np.minimum((players['assists'] / players['minutes']) * 90, 2.5)
        
        # Expected metrics with form adjustment
        players['xg_per_90'] = np.minimum((players['expected_goals'] / players['minutes']) * 90, 1.5)
        players['xa_per_90'] = np.minimum((players['expected_assists'] / players['minutes']) * 90, 1.5)
        players['xgi_per_90'] = players['xg_per_90'] + players['xa_per_90']
        
        # Enhanced value metrics
        players['points_per_million'] = players['total_points'] / players['price']
        players['form_per_million'] = players['form'] / players['price']
        
        # Fixture-adjusted expected points
        fixture_multiplier = np.where(
            players['fixture_difficulty'] <= 2.5, 1.15,  # Easy fixtures
            np.where(players['fixture_difficulty'] <= 3.5, 1.0, 0.85)  # Hard fixtures
        )
        
        players['fixture_adjusted_ep'] = players['ep_next'] * fixture_multiplier
        
        # Differential potential (for mini-league mode)
        if self.mini_league_mode:
            players['differential_potential'] = np.where(
                players['selected_by_percent'] < 8, 1.25,  # High differential
                np.where(players['selected_by_percent'] < 20, 1.1, 0.95)  # Template penalty
            )
        else:
            players['differential_potential'] = 1.0
        
        return players
    
    def calculate_position_scores(self, players_df):
        """Calculate enhanced position-specific scores."""
        
        position_weights = {
            'GK': {
                'fixture_adjusted_ep': 0.30,
                'total_points': 0.25,
                'points_per_million': 0.20,
                'clean_sheet_rate': 0.15,
                'saves': 0.10
            },
            'DEF': {
                'fixture_adjusted_ep': 0.25,
                'total_points': 0.20,
                'points_per_million': 0.15,
                'clean_sheet_rate': 0.15,
                'xgi_per_90': 0.15,
                'recent_form_multiplier': 0.10
            },
            'MID': {
                'fixture_adjusted_ep': 0.30,
                'xgi_per_90': 0.20,
                'points_per_million': 0.15,
                'creativity': 0.15,
                'recent_form_multiplier': 0.10,
                'differential_potential': 0.10
            },
            'FWD': {
                'fixture_adjusted_ep': 0.30,
                'xg_per_90': 0.25,
                'points_per_million': 0.15,
                'goals_per_90': 0.15,
                'threat': 0.10,
                'differential_potential': 0.05
            }
        }
        
        players = players_df.copy()
        players['enhanced_score'] = 0.0
        
        for position in position_weights.keys():
            pos_players = players[players['position'] == position].copy()
            
            if pos_players.empty:
                continue
            
            pos_score = 0.0
            
            for metric, weight in position_weights[position].items():
                if metric in pos_players.columns and not pos_players[metric].isna().all():
                    metric_values = pos_players[metric]
                    if metric_values.max() > metric_values.min():
                        normalized = ((metric_values - metric_values.min()) / 
                                    (metric_values.max() - metric_values.min())) * 100
                        pos_score += normalized * weight
            
            players.loc[pos_players.index, 'enhanced_score'] = pos_score
        
        return players
    
    def build_optimal_team(self, players_df):
        """Build optimal team with enhanced constraints."""
        print("Building optimal wildcard team...")
        
        # Clean the dataframe
        players_clean = players_df.copy()
        players_clean['enhanced_score'] = players_clean['enhanced_score'].replace([np.inf, -np.inf], np.nan)
        players_clean = players_clean.dropna(subset=['enhanced_score', 'price'])
        players_clean['enhanced_score'] = np.maximum(players_clean['enhanced_score'], 0.1)
        
        print(f"Optimizing from {len(players_clean)} clean players")
        
        if len(players_clean) < 15:
            print("Error: Not enough valid players for optimization")
            return None
        
        # Create optimization problem
        prob = LpProblem("FPL_Enhanced_Wildcard", LpMaximize)
        
        # Decision variables
        player_vars = {}
        for idx, player in players_clean.iterrows():
            player_vars[idx] = LpVariable(f"player_{player['id']}", cat='Binary')
        
        # ENHANCED OBJECTIVE: Multiple factors
        objective_terms = []
        
        for idx in players_clean.index:
            player = players_clean.loc[idx]
            
            # Base score
            base_score = player['enhanced_score']
            
            # Bonus for high expected points
            ep_bonus = player['fixture_adjusted_ep'] * 5
            
            # Mini-league differential bonus
            if self.mini_league_mode:
                differential_bonus = (100 - player['selected_by_percent']) * 0.5
            else:
                differential_bonus = 0
            
            # Fixture run bonus
            fixture_bonus = (4 - player['fixture_difficulty']) * 10
            
            total_score = base_score + ep_bonus + differential_bonus + fixture_bonus
            objective_terms.append(total_score * player_vars[idx])
        
        prob += lpSum(objective_terms)
        
        # Standard constraints
        prob += lpSum([players_clean.loc[idx, 'price'] * player_vars[idx] 
                      for idx in players_clean.index]) <= self.budget
        
        prob += lpSum([player_vars[idx] for idx in players_clean.index]) == 15
        
        # Position constraints
        for position, (min_count, max_count) in self.formation_constraints.items():
            position_indices = players_clean[players_clean['position'] == position].index
            prob += lpSum([player_vars[idx] for idx in position_indices]) == min_count
        
        # Team constraints (max 3 players per team)
        for team_id in players_clean['team'].unique():
            team_indices = players_clean[players_clean['team'] == team_id].index
            prob += lpSum([player_vars[idx] for idx in team_indices]) <= 3
        
        # MINI-LEAGUE SPECIFIC CONSTRAINTS
        if self.mini_league_mode:
            # Ensure at least 4 differential picks (<15% ownership)
            differential_indices = players_clean[players_clean['selected_by_percent'] < 15].index
            prob += lpSum([player_vars[idx] for idx in differential_indices]) >= 4
            
            # Limit template picks (>30% ownership) to max 6
            template_indices = players_clean[players_clean['selected_by_percent'] > 30].index
            prob += lpSum([player_vars[idx] for idx in template_indices]) <= 6
        
        # Solve
        print("Solving optimization problem...")
        prob.solve()
        
        if LpStatus[prob.status] != 'Optimal':
            print(f"Warning: Optimization status: {LpStatus[prob.status]}")
            # Try without mini-league constraints
            if self.mini_league_mode:
                print("Retrying without aggressive differential constraints...")
                return self._fallback_optimization(players_clean)
        
        # Extract solution
        selected_indices = []
        for idx in players_clean.index:
            if value(player_vars[idx]) == 1:
                selected_indices.append(idx)
        
        optimal_team = players_clean.loc[selected_indices].copy()
        print(f"Optimization complete: {len(optimal_team)} players, £{optimal_team['price'].sum():.1f}m")
        
        return optimal_team
    
    def _fallback_optimization(self, players_clean):
        """Fallback optimization without aggressive constraints."""
        prob = LpProblem("FPL_Fallback", LpMaximize)
        
        player_vars = {}
        for idx, player in players_clean.iterrows():
            player_vars[idx] = LpVariable(f"player_{player['id']}", cat='Binary')
        
        # Simple objective
        prob += lpSum([players_clean.loc[idx, 'enhanced_score'] * player_vars[idx] 
                      for idx in players_clean.index])
        
        # Basic constraints only
        prob += lpSum([players_clean.loc[idx, 'price'] * player_vars[idx] 
                      for idx in players_clean.index]) <= self.budget
        prob += lpSum([player_vars[idx] for idx in players_clean.index]) == 15
        
        for position, (min_count, max_count) in self.formation_constraints.items():
            position_indices = players_clean[players_clean['position'] == position].index
            prob += lpSum([player_vars[idx] for idx in position_indices]) == min_count
        
        for team_id in players_clean['team'].unique():
            team_indices = players_clean[players_clean['team'] == team_id].index
            prob += lpSum([player_vars[idx] for idx in team_indices]) <= 3
        
        prob.solve()
        
        if LpStatus[prob.status] == 'Optimal':
            selected_indices = [idx for idx in players_clean.index if value(player_vars[idx]) == 1]
            return players_clean.loc[selected_indices].copy()
        
        return None
    
    def display_enhanced_analysis(self, selected_team):
        """Display comprehensive team analysis with mini-league insights."""
        print("\n" + "="*85)
        print(f"ENHANCED WILDCARD TEAM - GAMEWEEK {self.current_gw}")
        if self.mini_league_mode:
            print("🎯 MINI-LEAGUE COMEBACK STRATEGY")
        print("="*85)
        
        # Formation analysis
        formation_count = selected_team.groupby('position').size()
        formation_str = f"{formation_count.get('GK', 0)}-{formation_count.get('DEF', 0)}-{formation_count.get('MID', 0)}-{formation_count.get('FWD', 0)}"
        print(f"Formation: {formation_str}")
        print()
        
        # Team by position with enhanced metrics
        for position in ['GK', 'DEF', 'MID', 'FWD']:
            pos_players = selected_team[selected_team['position'] == position].sort_values('enhanced_score', ascending=False)
            
            if pos_players.empty:
                continue
                
            print(f"{position} ({len(pos_players)} players):")
            print("-" * 80)
            
            for _, player in pos_players.iterrows():
                ownership = f"{player['selected_by_percent']:.1f}%"
                ep_next = f"{player['fixture_adjusted_ep']:.1f}"
                
                # Differential indicator
                diff_indicator = "🔥" if player['selected_by_percent'] < 10 else ("⭐" if player['selected_by_percent'] < 25 else "")
                
                # Position-specific metrics
                if position in ['MID', 'FWD']:
                    extra_info = f"xGI/90: {player['xgi_per_90']:.2f}"
                elif position == 'DEF':
                    cs_rate = player.get('clean_sheet_rate', 0)
                    extra_info = f"CS Rate: {cs_rate:.2f}"
                else:  # GK
                    extra_info = f"Saves: {player.get('saves', 0):.0f}"
                
                fixture_info = f"FDR: {player['fixture_difficulty']:.1f}"
                
                print(f"  {diff_indicator}{player['web_name']:18s} ({player['team_name']:12s}) "
                      f"£{player['price']:4.1f}m EP: {ep_next:>4s} Own: {ownership:>6s} "
                      f"{fixture_info} {extra_info}")
        
        # Team summary
        total_cost = selected_team['price'].sum()
        avg_ownership = selected_team['selected_by_percent'].mean()
        total_ep = selected_team['fixture_adjusted_ep'].sum()
        
        print(f"\n📊 TEAM METRICS:")
        print(f"Total Cost: £{total_cost:.1f}m (Remaining: £{100.0 - total_cost:.1f}m)")
        print(f"Expected Points (Next GW): {total_ep:.1f}")
        print(f"Average Ownership: {avg_ownership:.1f}%")
        
        # Differential analysis
        differentials = selected_team[selected_team['selected_by_percent'] < 15]
        template = selected_team[selected_team['selected_by_percent'] > 25]
        
        print(f"\n🎯 OWNERSHIP STRATEGY:")
        print(f"Differential picks (<15%): {len(differentials)} players")
        print(f"Template picks (>25%): {len(template)} players")
        
        if len(differentials) > 0:
            print(f"\n🔥 KEY DIFFERENTIALS:")
            for _, player in differentials.nsmallest(5, 'selected_by_percent').iterrows():
                print(f"  {player['web_name']} ({player['team_name']}) - {player['selected_by_percent']:.1f}% owned, EP: {player['fixture_adjusted_ep']:.1f}")
        
        # Fixture analysis
        easy_fixtures = selected_team[selected_team['fixture_difficulty'] <= 2.5]
        if len(easy_fixtures) > 0:
            print(f"\n✅ PLAYERS WITH GOOD FIXTURES:")
            for _, player in easy_fixtures.nsmallest(5, 'fixture_difficulty').iterrows():
                print(f"  {player['web_name']} ({player['team_name']}) - FDR: {player['fixture_difficulty']:.1f}")
        
        # Team concentration
        team_counts = selected_team['team_name'].value_counts()
        concentrated_teams = team_counts[team_counts >= 2]
        if len(concentrated_teams) > 0:
            print(f"\n🏟️  TEAM CONCENTRATION:")
            for team, count in concentrated_teams.items():
                team_players = selected_team[selected_team['team_name'] == team]
                avg_difficulty = team_players['fixture_difficulty'].mean()
                print(f"  {team}: {count} players (Avg FDR: {avg_difficulty:.1f})")
        
        return selected_team
    
    def run_enhanced_optimization(self):
        """Run the enhanced wildcard optimization."""
        print(f"🚀 Starting Enhanced Wildcard Optimization for GW{self.current_gw}")
        if self.mini_league_mode:
            print("🎯 Mini-league comeback mode activated!")
        print("="*85)
        
        # Get enhanced data
        players_df, fixtures_df = self.get_enhanced_player_data()
        
        # Add fixture analysis
        players_with_fixtures = self.calculate_fixture_difficulty(players_df, fixtures_df)
        
        # Calculate enhanced metrics
        players_with_metrics = self.calculate_enhanced_metrics(players_with_fixtures)
        
        # Calculate position scores
        players_scored = self.calculate_position_scores(players_with_metrics)
        
        # Build optimal team
        optimal_team = self.build_optimal_team(players_scored)
        
        if optimal_team is None:
            print("❌ Error: Could not build optimal team")
            return None
        
        # Display analysis
        final_team = self.display_enhanced_analysis(optimal_team)
        
        print(f"\n✅ Wildcard team optimization complete!")
        print("💡 Remember to check for any last-minute injury news before confirming transfers!")
        
        return final_team

# Usage
if __name__ == "__main__":
    # For mini-league comeback (more aggressive differentials)
    optimizer = EnhancedWildcardOptimizer(gameweek=3, mini_league_mode=True)
    
    # For conservative approach (less risky)
    # optimizer = EnhancedWildcardOptimizer(gameweek=3, mini_league_mode=False)
    
    optimized_team = optimizer.run_enhanced_optimization()