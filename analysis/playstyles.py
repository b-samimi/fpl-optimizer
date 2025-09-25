import pandas as pd
import numpy as np
import requests
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

class FPLPlaystyleAnalyzer:
    """
    Analyze player playstyles using FPL API data.
    Creates metrics to understand defensive actions, passing patterns, and playing styles.
    """
    
    def __init__(self):
        self.base_url = "https://fantasy.premierleague.com/api/"
        
    def fetch_comprehensive_data(self):
        """Fetch all available FPL data for playstyle analysis."""
        print("Fetching comprehensive FPL data...")
        
        # Get bootstrap data
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
        
        # Convert relevant columns to numeric
        numeric_cols = [
            'minutes', 'goals_scored', 'assists', 'clean_sheets', 'goals_conceded',
            'own_goals', 'penalties_saved', 'penalties_missed', 'yellow_cards', 
            'red_cards', 'saves', 'bonus', 'bps', 'influence', 'creativity', 
            'threat', 'ict_index', 'starts', 'expected_goals', 'expected_assists',
            'expected_goal_involvements', 'expected_goals_conceded'
        ]
        
        for col in numeric_cols:
            if col in players_df.columns:
                players_df[col] = pd.to_numeric(players_df[col], errors='coerce').fillna(0)
        
        return players_df
    
    def calculate_playstyle_metrics(self, players_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate advanced playstyle metrics from available FPL data."""
        print("Calculating playstyle metrics...")
        
        df = players_df.copy()
        
        # Filter players with meaningful minutes (at least 90 minutes total)
        df = df[df['minutes'] >= 90].copy()
        
        # Basic per-90 metrics
        df['minutes_per_90'] = df['minutes'] / 90
        df['goals_per_90'] = df['goals_scored'] / df['minutes_per_90']
        df['assists_per_90'] = df['assists'] / df['minutes_per_90']
        df['expected_goals_per_90'] = df['expected_goals'] / df['minutes_per_90']
        df['expected_assists_per_90'] = df['expected_assists'] / df['minutes_per_90']
        
        # Defensive metrics approximation
        # Using available data to infer defensive actions
        df['defensive_actions_per_90'] = np.where(
            df['position'].isin(['DEF', 'MID']),
            # Estimate defensive actions from clean sheets, cards, and BPS for defensive players
            (df['clean_sheets'] * 2 + df['yellow_cards'] * 3 + df['bps'] * 0.1) / df['minutes_per_90'],
            df['yellow_cards'] / df['minutes_per_90']  # For attackers, mainly cards
        )
        
        # Creativity and attacking intent
        df['creativity_per_90'] = df['creativity'] / df['minutes_per_90']
        df['threat_per_90'] = df['threat'] / df['minutes_per_90']
        df['influence_per_90'] = df['influence'] / df['minutes_per_90']
        
        # Shot conversion and efficiency
        df['shot_conversion'] = np.where(
            df['expected_goals'] > 0,
            df['goals_scored'] / df['expected_goals'],
            0
        )
        
        df['assist_efficiency'] = np.where(
            df['expected_assists'] > 0,
            df['assists'] / df['expected_assists'],
            0
        )
        
        # Passing approximation using creativity and assists
        # Higher creativity suggests more passes/key passes
        df['estimated_passes_per_90'] = (
            df['creativity_per_90'] * 0.5 + 
            df['assists_per_90'] * 10 + 
            df['expected_assists_per_90'] * 8
        )
        
        # Passes per defensive action (playstyle indicator)
        df['passes_per_defensive_action'] = np.where(
            df['defensive_actions_per_90'] > 0,
            df['estimated_passes_per_90'] / df['defensive_actions_per_90'],
            df['estimated_passes_per_90']  # If no defensive actions, just passes
        )
        
        # Discipline and aggression
        df['cards_per_90'] = (df['yellow_cards'] + df['red_cards'] * 2) / df['minutes_per_90']
        
        # Goal involvement rate
        df['goal_involvement_per_90'] = (df['goals_per_90'] + df['assists_per_90'])
        
        # Bonus point rate (indicates all-around performance)
        df['bonus_per_90'] = df['bonus'] / df['minutes_per_90']
        
        # Expected vs actual performance
        df['xg_overperformance'] = df['goals_scored'] - df['expected_goals']
        df['xa_overperformance'] = df['assists'] - df['expected_assists']
        
        # Position-specific metrics
        df['gk_save_rate'] = np.where(
            df['position'] == 'GK',
            df['saves'] / df['minutes_per_90'],
            0
        )
        
        df['defender_attacking_threat'] = np.where(
            df['position'] == 'DEF',
            (df['goals_per_90'] * 6 + df['assists_per_90'] * 3 + df['expected_goals_per_90'] * 4),
            0
        )
        
        # Style indicators
        df['explosive_potential'] = df['bps'] * df['bonus_per_90']  # High BPS + bonus = explosive games
        df['consistency_score'] = np.where(
            df['starts'] > 0,
            df['bonus'] / df['starts'],  # Consistent bonus point earning
            0
        )
        
        return df
    
    def categorize_playstyles(self, df: pd.DataFrame) -> pd.DataFrame:
        """Categorize players into playstyle archetypes."""
        print("Categorizing playstyles...")
        
        # Position-specific playstyle categorization
        df['playstyle'] = 'Unknown'
        
        # Goalkeepers
        gk_mask = df['position'] == 'GK'
        df.loc[gk_mask & (df['gk_save_rate'] > df[gk_mask]['gk_save_rate'].quantile(0.7)), 'playstyle'] = 'Shot Stopper'
        df.loc[gk_mask & (df['clean_sheets'] > df[gk_mask]['clean_sheets'].quantile(0.7)), 'playstyle'] = 'Clean Sheet Specialist'
        df.loc[gk_mask & (df['playstyle'] == 'Unknown'), 'playstyle'] = 'Balanced Keeper'
        
        # Defenders
        def_mask = df['position'] == 'DEF'
        df.loc[def_mask & (df['defender_attacking_threat'] > df[def_mask]['defender_attacking_threat'].quantile(0.8)), 'playstyle'] = 'Attacking Defender'
        df.loc[def_mask & (df['clean_sheets'] > df[def_mask]['clean_sheets'].quantile(0.7)) & (df['playstyle'] == 'Unknown'), 'playstyle'] = 'Defensive Wall'
        df.loc[def_mask & (df['cards_per_90'] > df[def_mask]['cards_per_90'].quantile(0.8)), 'playstyle'] = 'Aggressive Defender'
        df.loc[def_mask & (df['playstyle'] == 'Unknown'), 'playstyle'] = 'Balanced Defender'
        
        # Midfielders
        mid_mask = df['position'] == 'MID'
        df.loc[mid_mask & (df['goals_per_90'] > df[mid_mask]['goals_per_90'].quantile(0.8)), 'playstyle'] = 'Goal-Scoring Midfielder'
        df.loc[mid_mask & (df['assists_per_90'] > df[mid_mask]['assists_per_90'].quantile(0.8)), 'playstyle'] = 'Creative Playmaker'
        df.loc[mid_mask & (df['passes_per_defensive_action'] > df[mid_mask]['passes_per_defensive_action'].quantile(0.8)), 'playstyle'] = 'Deep-Lying Playmaker'
        df.loc[mid_mask & (df['defensive_actions_per_90'] > df[mid_mask]['defensive_actions_per_90'].quantile(0.8)), 'playstyle'] = 'Defensive Midfielder'
        df.loc[mid_mask & (df['playstyle'] == 'Unknown'), 'playstyle'] = 'Box-to-Box Midfielder'
        
        # Forwards
        fwd_mask = df['position'] == 'FWD'
        df.loc[fwd_mask & (df['goals_per_90'] > df[fwd_mask]['goals_per_90'].quantile(0.8)), 'playstyle'] = 'Clinical Finisher'
        df.loc[fwd_mask & (df['assists_per_90'] > df[fwd_mask]['assists_per_90'].quantile(0.7)), 'playstyle'] = 'Creative Forward'
        df.loc[fwd_mask & (df['shot_conversion'] > df[fwd_mask]['shot_conversion'].quantile(0.8)), 'playstyle'] = 'Lethal Striker'
        df.loc[fwd_mask & (df['playstyle'] == 'Unknown'), 'playstyle'] = 'All-Round Forward'
        
        return df
    
    def analyze_player_clusters(self, df: pd.DataFrame) -> Dict:
        """Perform simple clustering analysis to identify similar playing styles."""
        print("Performing simplified cluster analysis...")
        
        # Simple statistical clustering without sklearn
        cluster_results = {}
        
        for position in ['GK', 'DEF', 'MID', 'FWD']:
            pos_df = df[df['position'] == position].copy()
            
            if len(pos_df) < 5:  # Need minimum players
                continue
            
            # Select relevant features based on position
            if position == 'GK':
                features = ['gk_save_rate', 'clean_sheets', 'goals_conceded', 'bonus_per_90']
            elif position == 'DEF':
                features = ['clean_sheets', 'defender_attacking_threat', 'cards_per_90', 'defensive_actions_per_90']
            elif position == 'MID':
                features = ['goals_per_90', 'assists_per_90', 'creativity_per_90', 'defensive_actions_per_90', 'passes_per_defensive_action']
            else:  # FWD
                features = ['goals_per_90', 'assists_per_90', 'shot_conversion', 'threat_per_90']
            
            # Filter features that exist and have variance
            available_features = []
            for feature in features:
                if feature in pos_df.columns and pos_df[feature].var() > 0:
                    available_features.append(feature)
            
            if len(available_features) < 2:
                continue
            
            # Simple percentile-based clustering
            cluster_analysis = {}
            
            # Create 3 clusters based on primary metric
            primary_metric = available_features[0]
            pos_df_sorted = pos_df.sort_values(primary_metric, ascending=False)
            
            cluster_size = len(pos_df_sorted) // 3
            
            # High performers
            high_cluster = pos_df_sorted.iloc[:cluster_size]
            high_cluster['cluster'] = 0
            
            # Mid performers  
            mid_cluster = pos_df_sorted.iloc[cluster_size:2*cluster_size]
            mid_cluster['cluster'] = 1
            
            # Low performers
            low_cluster = pos_df_sorted.iloc[2*cluster_size:]
            low_cluster['cluster'] = 2
            
            # Combine clusters
            clustered_df = pd.concat([high_cluster, mid_cluster, low_cluster])
            
            # Analyze each cluster
            for cluster_id in range(3):
                cluster_players = clustered_df[clustered_df['cluster'] == cluster_id]
                cluster_names = ['High', 'Medium', 'Low']
                
                cluster_analysis[f'cluster_{cluster_id}'] = {
                    'name': f'{cluster_names[cluster_id]} {primary_metric.replace("_", " ").title()}',
                    'player_count': len(cluster_players),
                    'avg_metrics': cluster_players[available_features].mean().to_dict(),
                    'representative_players': cluster_players.nlargest(3, 'total_points')[['web_name', 'team_name']].values.tolist()
                }
            
            cluster_results[position] = {
                'features_used': available_features,
                'clusters': cluster_analysis,
                'primary_metric': primary_metric
            }
        
        return cluster_results
    
    def generate_player_reports(self, df: pd.DataFrame, top_n: int = 5) -> Dict:
        """Generate detailed playstyle reports for top players in each position."""
        print("Generating player reports...")
        
        reports = {}
        
        for position in ['GK', 'DEF', 'MID', 'FWD']:
            pos_df = df[df['position'] == position].copy()
            
            if len(pos_df) == 0:
                continue
            
            # Get top players by total points
            top_players = pos_df.nlargest(top_n, 'total_points')
            
            position_reports = []
            for _, player in top_players.iterrows():
                report = {
                    'name': player['web_name'],
                    'team': player['team_name'],
                    'price': player['price'],
                    'playstyle': player['playstyle'],
                    'total_points': player['total_points'],
                    'minutes': player['minutes']
                }
                
                # Position-specific metrics
                if position == 'GK':
                    report['key_metrics'] = {
                        'save_rate_per_90': round(player['gk_save_rate'], 2),
                        'clean_sheets': player['clean_sheets'],
                        'goals_conceded': player['goals_conceded']
                    }
                elif position == 'DEF':
                    report['key_metrics'] = {
                        'clean_sheets': player['clean_sheets'],
                        'attacking_threat': round(player['defender_attacking_threat'], 2),
                        'goals_assists': f"{player['goals_scored']}G {player['assists']}A",
                        'cards_per_90': round(player['cards_per_90'], 2)
                    }
                elif position == 'MID':
                    report['key_metrics'] = {
                        'goals_per_90': round(player['goals_per_90'], 2),
                        'assists_per_90': round(player['assists_per_90'], 2),
                        'creativity_per_90': round(player['creativity_per_90'], 2),
                        'passes_per_def_action': round(player['passes_per_defensive_action'], 2)
                    }
                else:  # FWD
                    report['key_metrics'] = {
                        'goals_per_90': round(player['goals_per_90'], 2),
                        'assists_per_90': round(player['assists_per_90'], 2),
                        'shot_conversion': round(player['shot_conversion'], 2),
                        'xg_overperformance': round(player['xg_overperformance'], 2)
                    }
                
                # Universal metrics
                report['performance_indicators'] = {
                    'form': player['form'],
                    'consistency_score': round(player['consistency_score'], 2),
                    'explosive_potential': round(player['explosive_potential'], 2)
                }
                
                position_reports.append(report)
            
            reports[position] = position_reports
        
        return reports
    
    def display_playstyle_analysis(self, df: pd.DataFrame, cluster_results: Dict, player_reports: Dict):
        """Display comprehensive playstyle analysis."""
        
        print("\n" + "="*100)
        print("FPL PLAYER PLAYSTYLE ANALYSIS")
        print("="*100)
        
        # Playstyle distribution
        print("\nPLAYSTYLE DISTRIBUTION BY POSITION:")
        print("-" * 60)
        
        for position in ['GK', 'DEF', 'MID', 'FWD']:
            pos_df = df[df['position'] == position]
            if len(pos_df) == 0:
                continue
                
            print(f"\n{position}:")
            style_counts = pos_df['playstyle'].value_counts()
            for style, count in style_counts.items():
                percentage = (count / len(pos_df)) * 100
                print(f"  {style}: {count} players ({percentage:.1f}%)")
        
        # Cluster analysis results
        print(f"\n\nCLUSTER ANALYSIS RESULTS:")
        print("-" * 60)
        
        for position, analysis in cluster_results.items():
            print(f"\n{position} - Identified {len(analysis['clusters'])} distinct playing styles:")
            
            for cluster_name, cluster_data in analysis['clusters'].items():
                cluster_id = cluster_name.split('_')[1]
                print(f"\n  Style {cluster_id} ({cluster_data['player_count']} players):")
                
                # Show representative players
                rep_players = cluster_data['representative_players']
                player_names = [f"{p[0]} ({p[1]})" for p in rep_players]
                print(f"    Representative: {', '.join(player_names[:2])}")
                
                # Show key characteristics
                metrics = cluster_data['avg_metrics']
                key_metrics = list(metrics.items())[:3]  # Show top 3 metrics
                print(f"    Characteristics: ", end="")
                for i, (metric, value) in enumerate(key_metrics):
                    if i > 0:
                        print(", ", end="")
                    print(f"{metric.replace('_', ' ').title()}: {value:.2f}", end="")
                print()
        
        # Player reports
        print(f"\n\nTOP PLAYER PLAYSTYLE PROFILES:")
        print("-" * 60)
        
        for position, reports in player_reports.items():
            print(f"\n{position} - TOP PERFORMERS:")
            
            for i, report in enumerate(reports, 1):
                print(f"\n  {i}. {report['name']} ({report['team']}) - £{report['price']}m")
                print(f"     Playstyle: {report['playstyle']}")
                print(f"     Total Points: {report['total_points']} | Minutes: {report['minutes']}")
                
                # Key metrics
                print(f"     Key Metrics: ", end="")
                metrics_str = []
                for metric, value in report['key_metrics'].items():
                    if isinstance(value, (int, float)):
                        metrics_str.append(f"{metric.replace('_', ' ').title()}: {value}")
                    else:
                        metrics_str.append(f"{metric.replace('_', ' ').title()}: {value}")
                print(" | ".join(metrics_str))
                
                # Performance indicators
                perf = report['performance_indicators']
                print(f"     Performance: Form {perf['form']} | Consistency {perf['consistency_score']} | Explosiveness {perf['explosive_potential']}")
        
        # Key insights
        print(f"\n\nKEY PLAYSTYLE INSIGHTS:")
        print("-" * 60)
        
        # Find most creative players
        creative_mids = df[(df['position'] == 'MID') & (df['playstyle'] == 'Creative Playmaker')]
        if len(creative_mids) > 0:
            top_creative = creative_mids.loc[creative_mids['creativity_per_90'].idxmax()]
            print(f"\nMost Creative: {top_creative['web_name']} ({top_creative['team_name']})")
            print(f"  Creativity/90: {top_creative['creativity_per_90']:.2f} | Assists/90: {top_creative['assists_per_90']:.2f}")
        
        # Find most attacking defenders
        att_defs = df[(df['position'] == 'DEF') & (df['playstyle'] == 'Attacking Defender')]
        if len(att_defs) > 0:
            top_att_def = att_defs.loc[att_defs['defender_attacking_threat'].idxmax()]
            print(f"\nMost Attacking Defender: {top_att_def['web_name']} ({top_att_def['team_name']})")
            print(f"  Attack Threat: {top_att_def['defender_attacking_threat']:.2f} | Goals+Assists: {top_att_def['goals_scored']+top_att_def['assists']}")
        
        # Find most clinical finishers
        clinical_fwds = df[(df['position'] == 'FWD') & (df['shot_conversion'] > 0)]
        if len(clinical_fwds) > 0:
            top_clinical = clinical_fwds.loc[clinical_fwds['shot_conversion'].idxmax()]
            print(f"\nMost Clinical Finisher: {top_clinical['web_name']} ({top_clinical['team_name']})")
            print(f"  Shot Conversion: {top_clinical['shot_conversion']:.2f} | xG Overperformance: {top_clinical['xg_overperformance']:.2f}")
        
        print(f"\n\nMETHODOLOGY NOTES:")
        print("-" * 60)
        print("• Defensive Actions: Estimated from clean sheets, cards, and BPS")
        print("• Passing Metrics: Derived from creativity, assists, and expected stats")
        print("• Playstyles: Algorithmic categorization based on performance patterns")
        print("• Clusters: K-means clustering on position-relevant metrics")
        print("="*100)
    
    def run_full_analysis(self):
        """Run the complete playstyle analysis."""
        print("Starting FPL Player Playstyle Analysis...")
        
        # Fetch and process data
        players_df = self.fetch_comprehensive_data()
        
        # Calculate playstyle metrics
        analyzed_df = self.calculate_playstyle_metrics(players_df)
        
        # Categorize playstyles
        categorized_df = self.categorize_playstyles(analyzed_df)
        
        # Perform cluster analysis
        cluster_results = self.analyze_player_clusters(categorized_df)
        
        # Generate player reports
        player_reports = self.generate_player_reports(categorized_df)
        
        # Display results
        self.display_playstyle_analysis(categorized_df, cluster_results, player_reports)
        
        return {
            'processed_data': categorized_df,
            'cluster_results': cluster_results,
            'player_reports': player_reports
        }

# Usage
if __name__ == "__main__":
    analyzer = FPLPlaystyleAnalyzer()
    results = analyzer.run_full_analysis()
    
    print("\n" + "="*50)
    print("Analysis complete!")
    print("Key derived metrics created:")
    print("• Passes per defensive action")
    print("• Shot conversion rates")
    print("• Defensive action frequency")
    print("• Creativity and threat per 90")
    print("• Playstyle categorization")
    print("• Player clustering by similarity")
    print("="*50)