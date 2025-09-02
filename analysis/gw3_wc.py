import sys
import os
sys.path.append('src')

from fpl_optimizer.api.fpl_client import FPLClient
import pandas as pd
import numpy as np
from pulp import LpMaximize, LpProblem, LpVariable, lpSum, value, LpStatus
import warnings
warnings.filterwarnings('ignore')

class RealisticTeamOptimizer:
    """Realistic FPL team optimizer that builds viable teams first, then optimizes."""
    
    def __init__(self):
        self.fpl = FPLClient()
        self.budget = 100.0
        self.formation_constraints = {
            'GK': (2, 2),   # Exactly 2 goalkeepers
            'DEF': (5, 5),  # Exactly 5 defenders
            'MID': (5, 5),  # Exactly 5 midfielders
            'FWD': (3, 3)   # Exactly 3 forwards
        }
        
    def get_viable_player_data(self):
        """Get only viable players who have reasonable game time and performance."""
        print("Fetching viable player data with quality filters...")
        
        players_df = self.fpl.get_players_df()
        
        # Clean numeric fields
        numeric_fields = [
            'selected_by_percent', 'ep_this', 'ep_next', 'form',
            'points_per_game', 'total_points', 'minutes', 'goals_scored',
            'assists', 'clean_sheets', 'goals_conceded', 'own_goals',
            'penalties_saved', 'penalties_missed', 'yellow_cards', 'red_cards',
            'saves', 'bonus', 'bps', 'influence', 'creativity', 'threat', 'ict_index',
            'expected_goals', 'expected_assists', 'expected_goal_involvements',
            'expected_goals_conceded'
        ]
        
        for field in numeric_fields:
            if field in players_df.columns:
                players_df[field] = pd.to_numeric(players_df[field], errors='coerce').fillna(0)
        
        # QUALITY FILTERS - Only keep viable players
        viable_players = players_df[
            # Basic viability filters
            (players_df['minutes'] >= 45) |  # Played at least 45 minutes OR
            (players_df['price'] <= 4.5) |   # Cheap bench fodder OR
            (players_df['total_points'] >= 8) # Good early form
        ].copy()
        
        # Remove players with obvious data errors
        viable_players = viable_players[
            viable_players['expected_goals'] <= 10  # Remove inflated xG values
        ]
        
        print(f"Filtered to {len(viable_players)} viable players from {len(players_df)} total")
        
        return viable_players
    
    def calculate_realistic_metrics(self, players_df):
        """Calculate performance metrics with realistic constraints."""
        print("Calculating realistic player metrics...")
        
        players = players_df.copy()
        
        # Safe division with minimum games played
        players['games_played'] = np.maximum(players['minutes'] / 90, 0.5)
        
        # Rate stats per 90 minutes (capped to prevent outliers)
        players['points_per_90'] = np.minimum((players['total_points'] / players['minutes']) * 90, 30)
        players['goals_per_90'] = np.minimum((players['goals_scored'] / players['minutes']) * 90, 3)
        players['assists_per_90'] = np.minimum((players['assists'] / players['minutes']) * 90, 3)
        
        # Expected metrics (capped to realistic values)
        players['xg_per_90'] = np.minimum((players['expected_goals'] / players['minutes']) * 90, 2)
        players['xa_per_90'] = np.minimum((players['expected_assists'] / players['minutes']) * 90, 2)
        players['xgi_per_90'] = players['xg_per_90'] + players['xa_per_90']
        
        # Value metrics
        players['points_per_million'] = players['total_points'] / players['price']
        
        # Form score (using actual form field)
        players['form_score'] = players['form']
        
        # Clean sheet rate for defenders/goalkeepers
        players['clean_sheet_rate'] = players['clean_sheets'] / players['games_played']
        
        return players
    
    def calculate_position_scores(self, players_df):
        """Calculate position-specific scores with realistic weightings."""
        
        position_weights = {
            'GK': {
                'total_points': 0.40,      # Prioritize actual points
                'points_per_million': 0.25, # Value is important for GK
                'clean_sheet_rate': 0.20,  # Clean sheets matter
                'saves': 0.15             # Save points
            },
            'DEF': {
                'total_points': 0.35,
                'points_per_million': 0.20,
                'clean_sheet_rate': 0.20,
                'goals_per_90': 0.15,     # Attacking returns
                'assists_per_90': 0.10
            },
            'MID': {
                'total_points': 0.30,
                'xgi_per_90': 0.25,       # Expected goal involvement
                'points_per_million': 0.20,
                'creativity': 0.15,       # FPL creativity index
                'form_score': 0.10
            },
            'FWD': {
                'total_points': 0.30,
                'xg_per_90': 0.25,        # Expected goals crucial for forwards
                'goals_per_90': 0.20,     # Actual goals
                'points_per_million': 0.15,
                'threat': 0.10            # FPL threat index
            }
        }
        
        players = players_df.copy()
        players['position_score'] = 0.0
        
        for position in position_weights.keys():
            pos_players = players[players['position'] == position].copy()
            
            if pos_players.empty:
                continue
            
            pos_score = 0.0
            
            for metric, weight in position_weights[position].items():
                if metric in pos_players.columns and not pos_players[metric].isna().all():
                    # Normalize to 0-100 scale within position
                    metric_values = pos_players[metric]
                    if metric_values.max() > 0:
                        normalized = (metric_values / metric_values.max()) * 100
                        pos_score += normalized * weight
            
            players.loc[pos_players.index, 'position_score'] = pos_score
        
        return players
    
    def stage1_build_viable_team(self, players_df):
        """Stage 1: Build a viable 15-player team within budget."""
        print("Stage 1: Building viable 15-player team...")
        
        # Clean the dataframe before optimization
        players_clean = players_df.copy()
        
        # Handle NaN and infinite values in position_score
        players_clean['position_score'] = players_clean['position_score'].replace([np.inf, -np.inf], np.nan)
        players_clean = players_clean.dropna(subset=['position_score', 'price'])
        
        # Set minimum score to avoid optimization issues
        players_clean['position_score'] = np.maximum(players_clean['position_score'], 0.1)
        
        print(f"After cleaning: {len(players_clean)} players available for Stage 1")
        
        if len(players_clean) < 15:
            print("Error: Not enough valid players for optimization")
            return None
        
        # Create optimization problem
        prob = LpProblem("FPL_Viable_Team", LpMaximize)
        
        # Decision variables
        player_vars = {}
        for idx, player in players_clean.iterrows():
            player_vars[idx] = LpVariable(f"player_{player['id']}", cat='Binary')
        
        # Objective: Maximize total position scores
        prob += lpSum([players_clean.loc[idx, 'position_score'] * player_vars[idx] 
                      for idx in players_clean.index])
        
        # Budget constraint
        prob += lpSum([players_clean.loc[idx, 'price'] * player_vars[idx] 
                      for idx in players_clean.index]) <= self.budget
        
        # Squad size constraint
        prob += lpSum([player_vars[idx] for idx in players_clean.index]) == 15
        
        # Position constraints (exact requirements)
        for position, (min_count, max_count) in self.formation_constraints.items():
            position_indices = players_clean[players_clean['position'] == position].index
            prob += lpSum([player_vars[idx] for idx in position_indices]) == min_count
        
        # Team constraints (max 3 players per team)
        for team_id in players_clean['team'].unique():
            team_indices = players_clean[players_clean['team'] == team_id].index
            prob += lpSum([player_vars[idx] for idx in team_indices]) <= 3
        
        # Solve
        prob.solve()
        
        if LpStatus[prob.status] != 'Optimal':
            print(f"Warning: Stage 1 optimization status: {LpStatus[prob.status]}")
            return None
        
        # Extract selected players
        selected_indices = []
        for idx in players_clean.index:
            if value(player_vars[idx]) == 1:
                selected_indices.append(idx)
        
        stage1_team = players_clean.loc[selected_indices].copy()
        print(f"Stage 1 complete: {len(stage1_team)} players, £{stage1_team['price'].sum():.1f}m total cost")
        
        return stage1_team
    
    def stage2_apply_differential_optimization(self, stage1_team, all_players):
        """Stage 2: Apply differential bonuses and optimize swaps."""
        print("Stage 2: Applying differential optimization...")
        
        # Add ownership categories with moderate bonuses
        all_players_diff = all_players.copy()
        
        # Moderate differential bonuses (not extreme)
        def get_ownership_multiplier(ownership_pct):
            if ownership_pct < 5:
                return 1.15    # 15% bonus for <5% owned
            elif ownership_pct < 15:
                return 1.08    # 8% bonus for 5-15% owned  
            elif ownership_pct < 30:
                return 1.0     # No bonus for 15-30% owned
            else:
                return 0.95    # 5% penalty for >30% owned
        
        all_players_diff['ownership_multiplier'] = all_players_diff['selected_by_percent'].apply(get_ownership_multiplier)
        all_players_diff['differential_score'] = all_players_diff['position_score'] * all_players_diff['ownership_multiplier']
        
        # Try to make up to 3 beneficial swaps
        optimized_team = stage1_team.copy()
        swaps_made = 0
        max_swaps = 3
        
        for position in ['FWD', 'MID', 'DEF', 'GK']:  # Priority order for swaps
            if swaps_made >= max_swaps:
                break
                
            current_pos_players = optimized_team[optimized_team['position'] == position]
            available_pos_players = all_players_diff[
                (all_players_diff['position'] == position) &
                (~all_players_diff['id'].isin(optimized_team['id']))
            ]
            
            if len(current_pos_players) == 0 or len(available_pos_players) == 0:
                continue
            
            # Find worst current player in position
            worst_current = current_pos_players.loc[current_pos_players['differential_score'].idxmin()]
            
            # Find best available replacement within reasonable price range
            budget_available = self.budget - (optimized_team['price'].sum() - worst_current['price'])
            affordable_replacements = available_pos_players[
                available_pos_players['price'] <= budget_available
            ]
            
            if len(affordable_replacements) == 0:
                continue
                
            best_replacement = affordable_replacements.loc[affordable_replacements['differential_score'].idxmax()]
            
            # Only swap if significant improvement
            if best_replacement['differential_score'] > worst_current['differential_score'] * 1.05:
                print(f"Swap {swaps_made + 1}: {worst_current['web_name']} -> {best_replacement['web_name']}")
                
                # Remove worst player and add best replacement
                optimized_team = optimized_team[optimized_team['id'] != worst_current['id']]
                best_replacement_row = all_players_diff[all_players_diff['id'] == best_replacement['id']]
                optimized_team = pd.concat([optimized_team, best_replacement_row], ignore_index=True)
                
                swaps_made += 1
        
        print(f"Stage 2 complete: Made {swaps_made} differential swaps")
        return optimized_team
    
    def display_realistic_team_analysis(self, selected_team):
        """Display comprehensive but realistic team analysis."""
        print("\n" + "="*80)
        print("REALISTIC FPL WILDCARD TEAM SELECTION")
        print("="*80)
        
        # Team summary by position
        for position in ['GK', 'DEF', 'MID', 'FWD']:
            pos_players = selected_team[selected_team['position'] == position].sort_values('differential_score', ascending=False)
            
            print(f"\n{position} ({len(pos_players)} players):")
            print("-" * 70)
            
            for _, player in pos_players.iterrows():
                ownership = f"{player['selected_by_percent']:.1f}%"
                
                # Position-specific additional info
                extra_info = ""
                if position in ['MID', 'FWD']:
                    if player['xg_per_90'] > 0.1:
                        extra_info += f"xG/90: {player['xg_per_90']:.2f} "
                    if player['xa_per_90'] > 0.1:
                        extra_info += f"xA/90: {player['xa_per_90']:.2f}"
                elif position == 'DEF':
                    if player['clean_sheet_rate'] > 0:
                        extra_info = f"CS Rate: {player['clean_sheet_rate']:.2f}"
                elif position == 'GK':
                    if player['saves'] > 0:
                        extra_info = f"Saves: {player['saves']:.0f}"
                
                print(f"  {player['web_name']:16s} ({player['team_name']:12s}) £{player['price']:4.1f}m "
                      f"Pts: {player['total_points']:2.0f} Own: {ownership:6s} {extra_info}")
        
        # Team summary metrics
        total_cost = selected_team['price'].sum()
        avg_ownership = selected_team['selected_by_percent'].mean()
        attacking_players = selected_team[selected_team['position'].isin(['MID', 'FWD'])]
        total_xg = attacking_players['expected_goals'].sum()
        total_xa = attacking_players['expected_assists'].sum()
        
        print(f"\nTEAM SUMMARY:")
        print(f"Total Cost: £{total_cost:.1f}m (Budget remaining: £{100.0 - total_cost:.1f}m)")
        print(f"Total Points: {selected_team['total_points'].sum():.0f}")
        print(f"Average Ownership: {avg_ownership:.1f}%")
        print(f"Expected Goals (Mid/Fwd): {total_xg:.2f}")
        print(f"Expected Assists (Mid/Fwd): {total_xa:.2f}")
        
        # Ownership distribution
        template_players = selected_team[selected_team['selected_by_percent'] > 20]
        popular_players = selected_team[(selected_team['selected_by_percent'] > 10) & (selected_team['selected_by_percent'] <= 20)]
        differential_players = selected_team[selected_team['selected_by_percent'] <= 10]
        
        print(f"\nOWNERSHIP BREAKDOWN:")
        print(f"Template picks (>20%): {len(template_players)}")
        print(f"Popular picks (10-20%): {len(popular_players)}")  
        print(f"Differential picks (<10%): {len(differential_players)}")
        
        # Show differentials
        if len(differential_players) > 0:
            print(f"\nDIFFERENTIAL PICKS:")
            for _, player in differential_players.iterrows():
                print(f"  {player['web_name']} ({player['team_name']}) - {player['selected_by_percent']:.1f}% owned")
        
        # Team concentration
        team_counts = selected_team['team_name'].value_counts()
        concentrated_teams = team_counts[team_counts >= 2]
        if len(concentrated_teams) > 0:
            print(f"\nTEAM CONCENTRATION:")
            for team, count in concentrated_teams.items():
                print(f"  {team}: {count} players")
        
        return selected_team
    
    def run_realistic_optimization(self):
        """Run the two-stage realistic optimization process."""
        print("Starting Realistic FPL Team Optimization")
        print("="*80)
        
        # Get viable players only
        viable_players = self.get_viable_player_data()
        
        # Calculate realistic metrics
        players_with_metrics = self.calculate_realistic_metrics(viable_players)
        
        # Calculate position-specific scores  
        players_scored = self.calculate_position_scores(players_with_metrics)
        
        # Stage 1: Build viable team
        stage1_team = self.stage1_build_viable_team(players_scored)
        
        if stage1_team is None:
            print("Error: Could not build viable team in Stage 1")
            return None
        
        # Add differential scores to all players for Stage 2
        players_scored['ownership_multiplier'] = players_scored['selected_by_percent'].apply(
            lambda x: 1.15 if x < 5 else (1.08 if x < 15 else (1.0 if x < 30 else 0.95))
        )
        players_scored['differential_score'] = players_scored['position_score'] * players_scored['ownership_multiplier']
        
        # Update stage1 team with differential scores
        stage1_team = players_scored[players_scored['id'].isin(stage1_team['id'])].copy()
        
        # Stage 2: Apply differential optimization
        final_team = self.stage2_apply_differential_optimization(stage1_team, players_scored)
        
        # Display results
        optimized_team = self.display_realistic_team_analysis(final_team)
        
        return optimized_team

# Run the realistic optimization
if __name__ == "__main__":
    optimizer = RealisticTeamOptimizer()
    optimized_team = optimizer.run_realistic_optimization()