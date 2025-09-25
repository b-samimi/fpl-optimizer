import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging

class MiniLeagueAnalyzer:
    """
    Advanced analytics for FPL mini leagues with competitor analysis,
    transfer tracking, and strategic insights.
    """
    
    def __init__(self, fpl_client):
        self.fpl_client = fpl_client
        self.logger = logging.getLogger(__name__)
        
    def get_league_detailed_data(self, league_id: int) -> Dict:
        """Get comprehensive league data including all managers and their teams."""
        try:
            # Get league standings
            standings = self.fpl_client.get_mini_league_standings(league_id)
            
            # Get detailed data for each manager
            managers_data = []
            for manager in standings['standings']['results']:
                manager_id = manager['entry']
                
                # Get manager's current team
                team_data = self._get_manager_team(manager_id)
                
                # Get manager's gameweek history
                history_data = self._get_manager_history(manager_id)
                
                # Handle different API response formats for names
                first_name = manager.get('player_first_name', manager.get('first_name', 'Unknown'))
                last_name = manager.get('player_last_name', manager.get('last_name', 'Player'))
                
                managers_data.append({
                    'manager_id': manager_id,
                    'manager_name': manager['entry_name'],
                    'player_name': f"{first_name} {last_name}",
                    'total_points': manager['total'],
                    'rank': manager['rank'],
                    'current_team': team_data,
                    'history': history_data
                })
            
            return {
                'league_info': standings['league'],
                'managers': managers_data,
                'last_updated': datetime.now()
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching league data: {e}")
            raise
    
    def _get_manager_team(self, manager_id: int) -> Dict:
        """Get current team for a specific manager."""
        try:
            response = self.fpl_client.session.get(
                f"{self.fpl_client.base_url}entry/{manager_id}/",
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error fetching team for manager {manager_id}: {e}")
            return {}
    
    def _get_manager_history(self, manager_id: int) -> Dict:
        """Get gameweek history for a specific manager."""
        try:
            response = self.fpl_client.session.get(
                f"{self.fpl_client.base_url}entry/{manager_id}/history/",
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error fetching history for manager {manager_id}: {e}")
            return {}
    
    def analyze_league_performance(self, league_data: Dict) -> pd.DataFrame:
        """Analyze overall league performance with key metrics."""
        performance_data = []
        
        for manager in league_data['managers']:
            history = manager.get('history', {})
            current_gw_history = history.get('current', [])
            
            if current_gw_history:
                df_history = pd.DataFrame(current_gw_history)
                
                # Calculate performance metrics
                total_points = manager['total_points']
                avg_points = df_history['points'].mean() if len(df_history) > 0 else 0
                consistency = df_history['points'].std() if len(df_history) > 0 else 0
                best_gw = df_history['points'].max() if len(df_history) > 0 else 0
                worst_gw = df_history['points'].min() if len(df_history) > 0 else 0
                
                # Transfer analysis
                total_transfers = df_history['event_transfers_cost'].sum() if len(df_history) > 0 else 0
                transfer_hits = len(df_history[df_history['event_transfers_cost'] > 0]) if len(df_history) > 0 else 0
                
                # Rank progression
                current_rank = manager['rank']
                rank_changes = df_history['overall_rank'].diff().fillna(0) if len(df_history) > 0 else []
                
                performance_data.append({
                    'Manager': manager['manager_name'],
                    'Player': manager['player_name'],
                    'Current_Rank': current_rank,
                    'Total_Points': total_points,
                    'Avg_Points_Per_GW': round(avg_points, 1),
                    'Consistency_Score': round(100 - consistency, 1),  # Higher is better
                    'Best_GW': int(best_gw),
                    'Worst_GW': int(worst_gw),
                    'Total_Transfer_Cost': int(total_transfers),
                    'Transfer_Hits_Taken': int(transfer_hits),
                    'Points_Per_Transfer_Hit': round(total_points / max(transfer_hits, 1), 1)
                })
            else:
                # Fallback for managers without history data
                performance_data.append({
                    'Manager': manager['manager_name'],
                    'Player': manager['player_name'],
                    'Current_Rank': manager['rank'],
                    'Total_Points': manager['total_points'],
                    'Avg_Points_Per_GW': 0,
                    'Consistency_Score': 0,
                    'Best_GW': 0,
                    'Worst_GW': 0,
                    'Total_Transfer_Cost': 0,
                    'Transfer_Hits_Taken': 0,
                    'Points_Per_Transfer_Hit': 0
                })
        
        return pd.DataFrame(performance_data).sort_values('Current_Rank')
    
    def get_differential_analysis(self, league_data: Dict) -> pd.DataFrame:
        """Analyze player ownership differentials within the league."""
        try:
            all_players = self.fpl_client.get_players_df()
        except Exception as e:
            self.logger.error(f"Error getting players data: {e}")
            return pd.DataFrame()
        
        # Get current teams for all managers
        manager_teams = []
        for manager in league_data['managers']:
            team_data = manager.get('current_team', {})
            if 'picks' in team_data:
                picks_df = pd.DataFrame(team_data['picks'])
                picks_df['manager_name'] = manager['manager_name']
                picks_df['manager_rank'] = manager['rank']
                manager_teams.append(picks_df)
        
        if not manager_teams:
            self.logger.warning("No team data found for differential analysis")
            return pd.DataFrame()
        
        # Combine all picks
        all_picks = pd.concat(manager_teams, ignore_index=True)
        
        # Calculate ownership within league
        league_ownership = all_picks.groupby('element').agg({
            'manager_name': 'count',
            'is_captain': 'sum',
            'is_vice_captain': 'sum'
        }).reset_index()
        
        league_ownership.columns = ['element', 'league_ownership', 'captain_count', 'vice_captain_count']
        league_ownership['ownership_percentage'] = (league_ownership['league_ownership'] / len(league_data['managers']) * 100)
        
        # Merge with player data
        differential_df = league_ownership.merge(
            all_players[['id', 'web_name', 'team_short', 'position', 'price', 'selected_by_percent', 'total_points']],
            left_on='element',
            right_on='id',
            how='left'
        )
        
        # Calculate differential score (low league ownership but high global ownership = good differential)
        differential_df['differential_score'] = (
            differential_df['selected_by_percent'] / differential_df['ownership_percentage'].clip(lower=1)
        )
        
        return differential_df.sort_values('differential_score', ascending=False)
    
    def create_league_dashboard(self, league_id: int, save_path: str = None):
        """Create comprehensive league dashboard with multiple visualizations."""
        # Get league data
        league_data = self.get_league_detailed_data(league_id)
        performance_df = self.analyze_league_performance(league_data)
        
        # Create subplots
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=[
                'League Standings', 'Points Progression',
                'Transfer Strategy Analysis', 'Consistency vs Performance',
                'Captain Choices', 'Top Differentials'
            ],
            specs=[
                [{"type": "bar"}, {"type": "scatter"}],
                [{"type": "bar"}, {"type": "scatter"}],
                [{"type": "bar"}, {"type": "table"}]
            ]
        )
        
        # 1. League Standings Bar Chart
        fig.add_trace(
            go.Bar(
                x=performance_df['Manager'],
                y=performance_df['Total_Points'],
                name='Total Points',
                marker_color='lightblue'
            ),
            row=1, col=1
        )
        
        # 2. Points Progression (need to implement with gameweek data)
        for manager in league_data['managers'][:5]:  # Top 5 for clarity
            history = manager.get('history', {})
            if 'current' in history and history['current']:
                gw_data = pd.DataFrame(history['current'])
                if not gw_data.empty:
                    fig.add_trace(
                        go.Scatter(
                            x=gw_data['event'],
                            y=gw_data['total_points'],
                            mode='lines+markers',
                            name=manager['manager_name']
                        ),
                        row=1, col=2
                    )
        
        # 3. Transfer Strategy
        fig.add_trace(
            go.Bar(
                x=performance_df['Manager'],
                y=performance_df['Transfer_Hits_Taken'],
                name='Transfer Hits',
                marker_color='red'
            ),
            row=2, col=1
        )
        
        # 4. Consistency vs Performance
        fig.add_trace(
            go.Scatter(
                x=performance_df['Consistency_Score'],
                y=performance_df['Total_Points'],
                mode='markers+text',
                text=performance_df['Manager'],
                textposition='top center',
                name='Manager Performance'
            ),
            row=2, col=2
        )
        
        # 5. Captain Choices Analysis
        try:
            differential_df = self.get_differential_analysis(league_data)
            if not differential_df.empty and 'captain_count' in differential_df.columns:
                top_captains = differential_df.nlargest(10, 'captain_count')
                fig.add_trace(
                    go.Bar(
                        x=top_captains['web_name'],
                        y=top_captains['captain_count'],
                        name='Captain Picks',
                        marker_color='gold'
                    ),
                    row=3, col=1
                )
                
                # 6. Top Differentials Table
                top_diffs = differential_df.nlargest(5, 'differential_score')[
                    ['web_name', 'ownership_percentage', 'selected_by_percent', 'differential_score']
                ].round(1)
                
                fig.add_trace(
                    go.Table(
                        header=dict(values=['Player', 'League Own%', 'Global Own%', 'Diff Score']),
                        cells=dict(values=[
                            top_diffs['web_name'],
                            top_diffs['ownership_percentage'],
                            top_diffs['selected_by_percent'],
                            top_diffs['differential_score']
                        ])
                    ),
                    row=3, col=2
                )
        except Exception as e:
            self.logger.error(f"Error creating differential analysis: {e}")
        
        # Update layout
        fig.update_layout(
            height=1200,
            title_text=f"Mini League Analytics Dashboard - {league_data['league_info']['name']}",
            showlegend=False
        )
        
        if save_path:
            fig.write_html(save_path)
            
        return fig
    
    def get_transfer_recommendations(self, league_data: Dict, your_manager_id: int) -> Dict:
        """Get personalized transfer recommendations based on league analysis."""
        try:
            differential_df = self.get_differential_analysis(league_data)
        except Exception as e:
            return {"error": f"Could not analyze differentials: {e}"}
        
        # Find your current team
        your_team = None
        for manager in league_data['managers']:
            if manager['manager_id'] == your_manager_id:
                your_team = manager['current_team']
                break
        
        if not your_team or 'picks' not in your_team:
            return {"error": "Could not find your team data"}
        
        your_picks = [pick['element'] for pick in your_team['picks']]
        
        if differential_df.empty:
            return {"error": "No differential data available"}
        
        # Find good differentials you don't own
        available_diffs = differential_df[
            ~differential_df['element'].isin(your_picks) &
            (differential_df['ownership_percentage'] < 30) &  # Low league ownership
            (differential_df['selected_by_percent'] > 10) &   # Decent global ownership
            (differential_df['total_points'] > 30)            # Good points
        ].head(10)
        
        # Find highly owned players you should consider
        must_haves = differential_df[
            ~differential_df['element'].isin(your_picks) &
            (differential_df['ownership_percentage'] > 70)    # Very high league ownership
        ].head(5)
        
        return {
            'differentials': available_diffs.to_dict('records') if not available_diffs.empty else [],
            'must_haves': must_haves.to_dict('records') if not must_haves.empty else [],
            'your_unique_players': differential_df[
                differential_df['element'].isin(your_picks) &
                (differential_df['ownership_percentage'] < 20)
            ].to_dict('records') if not differential_df.empty else []
        }

# Usage example and integration with your existing code
if __name__ == "__main__":
    # Import your existing FPL client
    try:
        from fpl_optimizer.api.fpl_client import FPLClient
        
        # Initialize clients
        fpl_client = FPLClient()
        league_analyzer = MiniLeagueAnalyzer(fpl_client)
        
        # Example usage
        league_id = 149533  # Your NBC Sports League ID from the image
        
        try:
            # Create comprehensive dashboard
            dashboard = league_analyzer.create_league_dashboard(
                league_id, 
                save_path="mini_league_dashboard.html"
            )
            
            # Get transfer recommendations (you'd need to find your manager ID)
            # recommendations = league_analyzer.get_transfer_recommendations(league_data, your_manager_id)
            
            print("Dashboard created successfully!")
            
        except Exception as e:
            print(f"Error: {e}")
    
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure you're running this from the correct directory with the fpl_optimizer module available.")