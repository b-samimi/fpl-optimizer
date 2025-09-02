#!/usr/bin/env python3
"""
FPL Wildcard Optimizer for GW3
Fixed version that handles early season data and builds valid teams
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from fpl_optimizer.api.fpl_client import FPLClient
import pandas as pd
import numpy as np
from pulp import LpMaximize, LpProblem, LpVariable, lpSum, LpStatus, value
import warnings
warnings.filterwarnings('ignore')

class WildcardTeamBuilder:
    """Build optimal FPL team for GW3 wildcard with focus on recovery strategy."""
    
    def __init__(self, budget=100.0):
        self.fpl = FPLClient()
        self.budget = budget
        self.squad_requirements = {
            'GKP': 2,
            'DEF': 5, 
            'MID': 5,
            'FWD': 3
        }
        
    def get_player_metrics(self):
        """Calculate comprehensive player metrics for GW3 optimization."""
        print("📊 Fetching and analyzing player data for GW3 wildcard...")
        
        players_df = self.fpl.get_players_df()
        
        # Basic filtering - be less restrictive initially
        print(f"Total players available: {len(players_df)}")
        
        # Remove only unavailable players
        players_df = players_df[
            (players_df['status'] != 'u') &  # Not unavailable
            (players_df['status'] != 'n')     # Not not in squad
        ].copy()
        
        print(f"After removing unavailable: {len(players_df)}")
        
        # Handle players with no minutes differently
        # Some good players might not have played yet due to late transfers
        players_df['games_played'] = np.maximum(0.5, players_df['minutes'] / 90)
        
        # Calculate metrics with safety for division by zero
        players_df['points_per_game'] = np.where(
            players_df['games_played'] > 0,
            players_df['total_points'] / players_df['games_played'],
            players_df['total_points']  # Use total points if no games
        )
        
        players_df['points_per_million'] = players_df['total_points'] / players_df['price']
        
        # Handle form safely
        players_df['form_score'] = pd.to_numeric(players_df['form'], errors='coerce').fillna(0)
        
        # Expected points handling
        players_df['ep_this_clean'] = pd.to_numeric(players_df.get('ep_this', 0), errors='coerce').fillna(0)
        players_df['ep_next_clean'] = pd.to_numeric(players_df.get('ep_next', 0), errors='coerce').fillna(0)
        
        # Price change potential
        players_df['price_change_potential'] = (
            players_df.get('transfers_in_event', 0) - players_df.get('transfers_out_event', 0)
        ) / 100000
        
        # Simple scoring system for players
        # Give some score even to players who haven't played yet
        players_df['wildcard_score'] = (
            players_df['total_points'] * 0.3 +
            players_df['form_score'] * 2 +
            players_df['ep_next_clean'] * 0.5 +
            players_df['points_per_million'] * 5 +
            players_df['price_change_potential'] * 0.1
        )
        
        # For players with 0 minutes, use expected points more heavily
        no_minutes_mask = players_df['minutes'] == 0
        players_df.loc[no_minutes_mask, 'wildcard_score'] = (
            players_df.loc[no_minutes_mask, 'ep_next_clean'] * 2 +
            players_df.loc[no_minutes_mask, 'selected_by_percent'] * 0.1
        )
        
        # Ensure no NaN values in wildcard_score
        players_df['wildcard_score'] = players_df['wildcard_score'].fillna(0)
        
        print(f"Players with wildcard_score > 0: {len(players_df[players_df['wildcard_score'] > 0])}")
        
        return players_df
    
    def check_squad_viability(self, players_df):
        """Check if we have enough players to build a valid squad."""
        print("\n🔍 Checking squad viability...")
        
        for position, required in self.squad_requirements.items():
            available = len(players_df[players_df['position'] == position])
            affordable = len(players_df[
                (players_df['position'] == position) & 
                (players_df['price'] <= self.budget/15 * 2)  # Rough affordability check
            ])
            print(f"{position}: {available} available, {affordable} affordable (need {required})")
            
            if available < required:
                print(f"❌ Not enough {position} players available!")
                return False
        
        # Check if total cost of cheapest valid team is within budget
        min_cost = 0
        for position, required in self.squad_requirements.items():
            cheapest = players_df[players_df['position'] == position].nsmallest(required, 'price')
            if len(cheapest) < required:
                print(f"❌ Cannot find {required} {position} players")
                return False
            min_cost += cheapest['price'].sum()
        
        print(f"Minimum possible team cost: £{min_cost:.1f}m (Budget: £{self.budget}m)")
        if min_cost > self.budget:
            print("❌ Even cheapest valid team exceeds budget!")
            return False
            
        return True
    
    def optimize_team_selection(self, players_df):
        """Use linear programming to select optimal 15-player squad."""
        print("\n🔧 Optimizing team selection...")
        
        # First check viability
        if not self.check_squad_viability(players_df):
            print("Cannot build valid squad with current player pool")
            return pd.DataFrame()
        
        # Filter to reasonable players to reduce problem size
        # Keep best players by position and some budget options
        filtered_players = []
        for position in ['GKP', 'DEF', 'MID', 'FWD']:
            pos_players = players_df[players_df['position'] == position].copy()
            
            # Take top scorers and some cheap options
            top_scorers = pos_players.nlargest(20, 'wildcard_score')
            cheap_options = pos_players.nsmallest(10, 'price')
            mid_price = pos_players[
                (pos_players['price'] >= pos_players['price'].quantile(0.3)) &
                (pos_players['price'] <= pos_players['price'].quantile(0.7))
            ].nlargest(10, 'wildcard_score')
            
            combined = pd.concat([top_scorers, cheap_options, mid_price]).drop_duplicates()
            filtered_players.append(combined)
        
        players_df = pd.concat(filtered_players).drop_duplicates()
        print(f"Optimizing with {len(players_df)} players")
        
        # Create the problem
        prob = LpProblem("FPL_Wildcard", LpMaximize)
        
        # Decision variables
        player_vars = {}
        for idx in players_df.index:
            player_vars[idx] = LpVariable(f"player_{idx}", cat='Binary')
        
        # Objective: maximize wildcard score
        prob += lpSum([
            players_df.loc[idx, 'wildcard_score'] * player_vars[idx]
            for idx in players_df.index
        ])
        
        # Constraints
        
        # Total squad size = 15
        prob += lpSum([player_vars[idx] for idx in players_df.index]) == 15
        
        # Budget constraint
        prob += lpSum([
            players_df.loc[idx, 'price'] * player_vars[idx]
            for idx in players_df.index
        ]) <= self.budget
        
        # Position constraints
        for position, count in self.squad_requirements.items():
            pos_players_idx = players_df[players_df['position'] == position].index
            prob += lpSum([player_vars[idx] for idx in pos_players_idx]) == count
        
        # Maximum 3 players per team
        for team_id in players_df['team'].unique():
            team_players_idx = players_df[players_df['team'] == team_id].index
            if len(team_players_idx) > 0:
                prob += lpSum([player_vars[idx] for idx in team_players_idx]) <= 3
        
        # Solve
        status = prob.solve()
        
        print(f"Optimization status: {LpStatus[status]}")
        
        if status != 1:  # Not optimal
            print("❌ Could not find optimal solution")
            # Try with relaxed budget
            print("Trying with relaxed constraints...")
            return self.build_budget_team(players_df)
        
        # Extract solution
        selected_indices = [idx for idx in players_df.index if player_vars[idx].varValue == 1]
        selected_team = players_df.loc[selected_indices].copy()
        
        total_cost = selected_team['price'].sum()
        print(f"✅ Team selected! Total cost: £{total_cost:.1f}m")
        
        return selected_team
    
    def build_budget_team(self, players_df):
        """Fallback method to build a valid team within budget."""
        print("\n🔨 Building team with simplified approach...")
        
        selected_team = []
        remaining_budget = self.budget
        
        for position, count in self.squad_requirements.items():
            pos_players = players_df[
                (players_df['position'] == position) &
                (~players_df.index.isin([p for p in selected_team]))
            ].copy()
            
            # Calculate value score
            pos_players['value_score'] = pos_players['wildcard_score'] / (pos_players['price'] + 1)
            pos_players = pos_players.sort_values('value_score', ascending=False)
            
            selected_count = 0
            for idx, player in pos_players.iterrows():
                if selected_count >= count:
                    break
                    
                # Check team limit
                current_team_players = [p for p in selected_team 
                                       if players_df.loc[p, 'team'] == player['team']]
                if len(current_team_players) >= 3:
                    continue
                
                # Check budget
                remaining_after = remaining_budget - player['price']
                positions_left = sum(self.squad_requirements.values()) - len(selected_team) - 1
                
                if positions_left > 0:
                    avg_price_needed = remaining_after / positions_left
                    if avg_price_needed < 4.0:  # Minimum viable price
                        continue
                
                selected_team.append(idx)
                remaining_budget = remaining_after
                selected_count += 1
        
        if len(selected_team) == 15:
            return players_df.loc[selected_team]
        else:
            print(f"❌ Could only select {len(selected_team)} players")
            return pd.DataFrame()
    
    def suggest_starting_11(self, squad_df):
        """Suggest best starting 11 and captain choices."""
        if squad_df.empty:
            return None
            
        print("\n⚽ Selecting optimal starting XI...")
        
        # Sort by score
        squad_df = squad_df.sort_values('wildcard_score', ascending=False)
        
        # Try different formations
        formations = [
            {'DEF': 3, 'MID': 5, 'FWD': 2},  # 3-5-2
            {'DEF': 3, 'MID': 4, 'FWD': 3},  # 3-4-3  
            {'DEF': 4, 'MID': 4, 'FWD': 2},  # 4-4-2
            {'DEF': 4, 'MID': 3, 'FWD': 3},  # 4-3-3
            {'DEF': 5, 'MID': 3, 'FWD': 2},  # 5-3-2
        ]
        
        best_lineup = None
        best_score = 0
        
        for formation in formations:
            lineup_indices = []
            lineup_score = 0
            
            # Add goalkeeper (always 1)
            gk = squad_df[squad_df['position'] == 'GKP'].head(1)
            if len(gk) > 0:
                lineup_indices.extend(gk.index.tolist())
                lineup_score += gk['wildcard_score'].sum()
            
            # Add outfield players
            for pos_code, pos_count in formation.items():
                pos_map = {'DEF': 'DEF', 'MID': 'MID', 'FWD': 'FWD'}
                players = squad_df[squad_df['position'] == pos_map[pos_code]].head(pos_count)
                lineup_indices.extend(players.index.tolist())
                lineup_score += players['wildcard_score'].sum()
            
            if lineup_score > best_score and len(lineup_indices) == 11:
                best_score = lineup_score
                best_lineup = {
                    'formation': formation,
                    'indices': lineup_indices
                }
        
        if not best_lineup:
            return None
        
        starting_11 = squad_df.loc[best_lineup['indices']]
        bench = squad_df[~squad_df.index.isin(best_lineup['indices'])]
        
        # Captain selection
        captain_options = starting_11.nlargest(3, 'wildcard_score')
        captain = captain_options.iloc[0] if len(captain_options) > 0 else None
        vice_captain = captain_options.iloc[1] if len(captain_options) > 1 else None
        
        return {
            'formation': best_lineup['formation'],
            'starting_11': starting_11,
            'bench': bench.sort_values('wildcard_score', ascending=False),
            'captain': captain,
            'vice_captain': vice_captain
        }
    
    def run_complete_wildcard_analysis(self):
        """Execute complete wildcard analysis and team building."""
        print("🎯 FPL WILDCARD TEAM BUILDER - GW3 RECOVERY STRATEGY")
        print("=" * 60)
        
        # Get player data
        players_df = self.get_player_metrics()
        
        if players_df.empty:
            print("❌ No player data available")
            return None
        
        # Optimize team
        optimal_squad = self.optimize_team_selection(players_df)
        
        if optimal_squad.empty:
            print("\n❌ Failed to build a valid team")
            return None
        
        # Get lineup
        lineup = self.suggest_starting_11(optimal_squad)
        
        if not lineup:
            print("❌ Could not determine starting lineup")
            return None
        
        # Display results
        print("\n" + "=" * 60)
        print("📋 YOUR OPTIMAL WILDCARD SQUAD")
        print("=" * 60)
        
        total_cost = optimal_squad['price'].sum()
        print(f"\n💰 Total Squad Value: £{total_cost:.1f}m / £{self.budget}m")
        print(f"💵 Remaining Budget: £{self.budget - total_cost:.1f}m\n")
        
        # Show squad by position
        for position in ['GKP', 'DEF', 'MID', 'FWD']:
            print(f"\n{position}:")
            print("-" * 50)
            pos_players = optimal_squad[optimal_squad['position'] == position].sort_values('wildcard_score', ascending=False)
            
            for idx, player in pos_players.iterrows():
                # Determine if starting or bench
                if idx in lineup['starting_11'].index:
                    status = "⭐"
                else:
                    status = "🪑"
                
                # Captain/vice captain badges
                badges = ""
                if lineup['captain'] is not None and idx == lineup['captain'].name:
                    badges = " (C)"
                elif lineup['vice_captain'] is not None and idx == lineup['vice_captain'].name:
                    badges = " (VC)"
                
                # Player info
                name_display = f"{player['web_name'][:15]:<15}"
                team_display = f"{player.get('team_short', player.get('team_name', 'UNK'))[:3]:<3}"
                
                print(f"{status} {name_display} {team_display} £{player['price']:>4.1f}m  "
                      f"Pts:{player['total_points']:>3.0f}  "
                      f"Own:{player.get('selected_by_percent', 0):>4.1f}%{badges}")
        
        # Formation
        print("\n" + "=" * 60)
        print("⚽ RECOMMENDED LINEUP")
        print("=" * 60)
        
        if lineup['formation']:
            formation_str = f"1-{lineup['formation']['DEF']}-{lineup['formation']['MID']}-{lineup['formation']['FWD']}"
            print(f"Formation: {formation_str}")
        
        if lineup['captain'] is not None:
            print(f"\n👑 Captain: {lineup['captain']['web_name']} "
                  f"({lineup['captain'].get('team_short', 'UNK')}) "
                  f"- {lineup['captain']['total_points']} pts")
        
        if lineup['vice_captain'] is not None:
            print(f"🎖️  Vice: {lineup['vice_captain']['web_name']} "
                  f"({lineup['vice_captain'].get('team_short', 'UNK')}) "
                  f"- {lineup['vice_captain']['total_points']} pts")
        
        # Bench order
        print(f"\n🪑 BENCH ORDER:")
        for i, (idx, player) in enumerate(lineup['bench'].iterrows(), 1):
            print(f"{i}. {player['web_name']} ({player['position']}) - £{player['price']:.1f}m")
        
        # Recovery strategy
        print("\n" + "=" * 60)
        print("🚀 MINI-LEAGUE RECOVERY STRATEGY")
        print("=" * 60)
        
        print("\n1️⃣  IMMEDIATE ACTIONS (GW3-5):")
        print("   • Activate wildcard before GW3 deadline")
        print("   • Monitor early team news for captain choice")
        print("   • Track price changes daily")
        
        print("\n2️⃣  SHORT-TERM STRATEGY (GW4-8):")
        print("   • Bank transfers unless injuries/suspensions")
        print("   • Target 1-2 price rises per gameweek")
        print("   • Captain differentials when viable")
        
        print("\n3️⃣  CHIP USAGE:")
        print("   • Bench Boost: Save for double gameweek")
        print("   • Triple Captain: Premium player in DGW")
        print("   • Free Hit: Blank gameweek or emergency")
        print("   • 2nd Wildcard: Around GW16-20")
        
        # Key differentials in squad
        differentials = optimal_squad[optimal_squad.get('selected_by_percent', 0) < 10]
        if len(differentials) > 0:
            print(f"\n🎲 YOUR DIFFERENTIAL PICKS (<10% owned):")
            for _, player in differentials.head(5).iterrows():
                print(f"   • {player['web_name']} ({player.get('team_short', 'UNK')}) "
                      f"- {player.get('selected_by_percent', 0):.1f}% owned")
        
        print("\n" + "=" * 60)
        print("✅ TEAM READY FOR WILDCARD ACTIVATION!")
        print("=" * 60)
        
        return optimal_squad

# Run the optimizer
if __name__ == "__main__":
    builder = WildcardTeamBuilder(budget=100.0)
    optimal_team = builder.run_complete_wildcard_analysis()