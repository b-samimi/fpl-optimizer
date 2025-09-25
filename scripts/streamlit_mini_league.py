import streamlit as st
import pandas as pd
import sys
import os

# Robust path handling for different project structures
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)  # Go up one level from scripts/

# Try different import strategies
def import_analyzer():
    """Try multiple import paths to find the analyzer module."""
    import_attempts = [
        # Method 1: Standard src structure
        lambda: __import_from_path(project_root, 'src.fpl_optimizer.analysis.mini_league_analyzer'),
        # Method 2: Direct from src folder
        lambda: __import_from_path(os.path.join(project_root, 'src'), 'fpl_optimizer.analysis.mini_league_analyzer'),
        # Method 3: If running from project root
        lambda: __import_from_path(script_dir, 'src.fpl_optimizer.analysis.mini_league_analyzer'),
        # Method 4: Relative import
        lambda: __import_from_path(os.path.join(script_dir, '..'), 'src.fpl_optimizer.analysis.mini_league_analyzer'),
    ]
    
    for attempt in import_attempts:
        try:
            return attempt()
        except ImportError:
            continue
    
    raise ImportError("Could not import MiniLeagueAnalyzer. Please check your project structure.")

def __import_from_path(path, module_name):
    """Helper to import from a specific path."""
    if path not in sys.path:
        sys.path.insert(0, path)
    
    module_parts = module_name.split('.')
    module = __import__(module_name)
    
    for part in module_parts[1:]:
        module = getattr(module, part)
    
    return module.MiniLeagueAnalyzer

# Try to import the analyzer
try:
    MiniLeagueAnalyzer = import_analyzer()
    import plotly.express as px
    IMPORT_SUCCESS = True
except ImportError as e:
    IMPORT_SUCCESS = False
    IMPORT_ERROR = str(e)

st.set_page_config(
    page_title="FPL Mini League Analyzer", 
    page_icon="⚽", 
    layout="wide"
)

st.title("⚽ FPL Mini League Analyzer")

if not IMPORT_SUCCESS:
    st.error(f"❌ Import Error: {IMPORT_ERROR}")
    st.markdown("""
    ## 🔧 Setup Instructions:
    
    **Your project structure should look like this:**
    ```
    fpl-optimizer/
    ├── scripts/
    │   └── streamlit_mini_league.py  (this file)
    └── src/
        └── fpl_optimizer/
            ├── __init__.py
            ├── api/
            │   ├── __init__.py
            │   └── fpl_client.py
            └── analysis/
                ├── __init__.py
                └── mini_league_analyzer.py
    ```
    
    **To fix this:**
    1. Make sure you have all the required files in the right places
    2. Run this from your project root directory: `streamlit run scripts/streamlit_mini_league.py`
    3. Or copy all files to match the structure above
    
    **Quick Fix - Create the missing files:**
    """)
    
    # Show code to create missing files
    with st.expander("📄 Click to see the missing files code"):
        st.code('''
# If you're missing the mini_league_analyzer.py, create it with this content:
# (This should be in: src/fpl_optimizer/analysis/mini_league_analyzer.py)

import pandas as pd
import requests

class MiniLeagueAnalyzer:
    def __init__(self, league_id):
        self.league_id = league_id
        self.base_url = "https://fantasy.premierleague.com/api/"
    
    def get_league_standings(self):
        """Get league standings - simplified version."""
        try:
            response = requests.get(f"{self.base_url}leagues-classic/{self.league_id}/standings/")
            response.raise_for_status()
            data = response.json()
            return pd.DataFrame(data['standings']['results'])
        except Exception as e:
            st.error(f"Error fetching league data: {e}")
            return pd.DataFrame()
    
    def get_comprehensive_insights(self):
        """Get basic insights."""
        standings = self.get_league_standings()
        
        if standings.empty:
            return {
                'standings': pd.DataFrame(),
                'transfer_activity': pd.DataFrame(),
                'monthly_performance': pd.DataFrame(),
                'league_stats': pd.DataFrame()
            }
        
        # Basic transfer analysis (simplified)
        transfer_analysis = standings.copy()
        transfer_analysis['estimated_transfer_cost'] = 0
        transfer_analysis['transfer_efficiency'] = standings['total']
        
        # Monthly performance (simplified)
        monthly_analysis = standings.copy()
        monthly_analysis['avg_points_per_gw'] = standings['total'] / 5
        monthly_analysis['projected_monthly'] = monthly_analysis['avg_points_per_gw'] * 4
        
        # League stats
        league_stats = pd.DataFrame({
            'Metric': ['Total Managers', 'Average Points', 'Points Leader', 'Last GW Average'],
            'Value': [
                len(standings),
                standings['total'].mean().round(2),
                standings['total'].max(),
                standings.get('event_total', [0]).mean() if 'event_total' in standings else 0
            ]
        })
        
        return {
            'standings': standings,
            'transfer_activity': transfer_analysis,
            'monthly_performance': monthly_analysis,
            'league_stats': league_stats
        }
        ''', language='python')
    
    st.stop()

st.markdown("Get comprehensive insights into your Fantasy Premier League mini league performance!")

# Sidebar for league selection
st.sidebar.header("League Configuration")
league_id = st.sidebar.number_input(
    "Enter your Mini League ID:", 
    min_value=1, 
    value=1, 
    help="You can find this in your FPL mini league URL"
)

if st.sidebar.button("🔍 Analyze League") or 'analyzer' not in st.session_state:
    with st.spinner(f"Analyzing league {league_id}..."):
        try:
            st.session_state.analyzer = MiniLeagueAnalyzer(league_id)
            st.session_state.insights = st.session_state.analyzer.get_comprehensive_insights()
            st.session_state.league_id = league_id
            st.success(f"✅ Successfully loaded league {league_id}!")
        except Exception as e:
            st.error(f"❌ Error loading league: {e}")
            st.stop()

if 'insights' in st.session_state:
    insights = st.session_state.insights
    
    # Check if we have data
    if insights['standings'].empty:
        st.error("❌ No data found for this league. Please check your league ID.")
        st.stop()
    
    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    
    standings = insights['standings']
    
    with col1:
        st.metric(
            "Total Managers", 
            len(standings)
        )
    
    with col2:
        st.metric(
            "Average Points", 
            f"{standings['total'].mean():.1f}"
        )
    
    with col3:
        st.metric(
            "Points Leader", 
            f"{standings['total'].max()}"
        )
    
    with col4:
        event_avg = standings.get('event_total', [0]).mean() if 'event_total' in standings else 0
        st.metric(
            "Last GW Average", 
            f"{event_avg:.1f}"
        )
    
    # Tabs for different analyses
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 League Overview", 
        "🔄 Transfer Analysis", 
        "📈 Top Movers", 
        "📅 Performance Trends",
        "📋 Detailed Data"
    ])
    
    with tab1:
        st.subheader("Current League Standings")
        
        # Interactive standings table
        display_cols = ['rank', 'player_name', 'total']
        if 'event_total' in standings.columns:
            display_cols.append('event_total')
        
        standings_display = standings[display_cols].copy()
        standings_display.columns = ['Rank', 'Manager', 'Total Points'] + (['Last GW'] if 'event_total' in standings.columns else [])
        
        st.dataframe(
            standings_display, 
            use_container_width=True,
            hide_index=True
        )
        
        # Points distribution chart
        col1, col2 = st.columns(2)
        
        with col1:
            fig_dist = px.histogram(
                standings, 
                x='total', 
                title='Points Distribution',
                nbins=15
            )
            st.plotly_chart(fig_dist, use_container_width=True)
        
        with col2:
            fig_rank = px.scatter(
                standings, 
                x='rank', 
                y='total',
                hover_name='player_name',
                title='Rank vs Total Points'
            )
            st.plotly_chart(fig_rank, use_container_width=True)
    
    with tab2:
        st.subheader("🔄 Transfer Activity Analysis")
        
        transfer_data = insights['transfer_activity']
        
        st.markdown("**Transfer Efficiency Rankings:**")
        st.markdown("*Higher efficiency = better points return per transfer cost*")
        
        # Color code the transfer efficiency
        if not transfer_data.empty:
            display_cols = ['player_name', 'rank', 'total']
            if 'transfer_efficiency' in transfer_data.columns:
                display_cols.append('transfer_efficiency')
            
            st.dataframe(
                transfer_data[display_cols],
                use_container_width=True,
                hide_index=True
            )
            
            # Transfer efficiency chart
            if 'transfer_efficiency' in transfer_data.columns:
                fig_transfers = px.bar(
                    transfer_data.head(10),
                    x='player_name',
                    y='transfer_efficiency',
                    title='Top 10 Transfer Efficiency Rankings',
                    color='transfer_efficiency',
                    color_continuous_scale='RdYlGn'
                )
                fig_transfers.update_xaxis(tickangle=45)
                st.plotly_chart(fig_transfers, use_container_width=True)
    
    with tab3:
        st.subheader("📈 League Movement Analysis")
        
        # Recent performance
        if 'event_total' in standings.columns:
            recent_top = standings.nlargest(10, 'event_total')
        else:
            recent_top = standings.head(10)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🔥 Top Performers**")
            display_cols = ['player_name', 'rank']
            if 'event_total' in standings.columns:
                display_cols.insert(1, 'event_total')
                
            recent_display = recent_top[display_cols].copy()
            column_names = ['Manager', 'Current Rank']
            if 'event_total' in standings.columns:
                column_names.insert(1, 'Last GW Points')
                
            recent_display.columns = column_names
            st.dataframe(recent_display, hide_index=True)
        
        with col2:
            if 'event_total' in standings.columns:
                fig_recent = px.bar(
                    recent_top,
                    x='event_total',
                    y='player_name',
                    orientation='h',
                    title='Last Gameweek Performance',
                    color='event_total',
                    color_continuous_scale='Blues'
                )
                st.plotly_chart(fig_recent, use_container_width=True)
            else:
                fig_recent = px.bar(
                    recent_top,
                    x='total',
                    y='player_name',
                    orientation='h',
                    title='Total Points Performance',
                    color='total',
                    color_continuous_scale='Blues'
                )
                st.plotly_chart(fig_recent, use_container_width=True)
        
        # Show bottom performers
        st.markdown("**📉 Bottom 5 - Need to Catch Up**")
        bottom_5 = standings.nsmallest(5, 'total')[['player_name', 'total', 'rank']]
        bottom_5.columns = ['Manager', 'Total Points', 'Rank']
        st.dataframe(bottom_5, hide_index=True)
    
    with tab4:
        st.subheader("📅 Performance Projections")
        
        monthly_data = insights['monthly_performance']
        
        if not monthly_data.empty and 'projected_monthly' in monthly_data.columns:
            # Monthly performance chart
            fig_monthly = px.bar(
                monthly_data.head(15),
                x='player_name',
                y='projected_monthly',
                title='Projected Monthly Performance',
                color='projected_monthly',
                color_continuous_scale='Greens'
            )
            fig_monthly.update_xaxis(tickangle=45)
            st.plotly_chart(fig_monthly, use_container_width=True)
            
            # Performance metrics table
            st.markdown("**Performance Metrics:**")
            display_cols = ['player_name', 'total', 'avg_points_per_gw', 'projected_monthly']
            monthly_display = monthly_data[display_cols].copy()
            monthly_display.columns = ['Manager', 'Total Points', 'Avg/GW', 'Projected Monthly']
            st.dataframe(monthly_display, use_container_width=True, hide_index=True)
        else:
            st.info("Performance projection data not available.")
    
    with tab5:
        st.subheader("📋 Raw Data & Export")
        
        # League statistics
        st.markdown("**League Statistics:**")
        if not insights['league_stats'].empty:
            st.dataframe(insights['league_stats'], hide_index=True)
        
        # Export options
        st.markdown("**📥 Export Data:**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            csv_standings = standings.to_csv(index=False)
            st.download_button(
                "Download Standings CSV",
                csv_standings,
                f"league_{st.session_state.league_id}_standings.csv",
                "text/csv"
            )
        
        with col2:
            if not insights['transfer_activity'].empty:
                csv_transfers = insights['transfer_activity'].to_csv(index=False)
                st.download_button(
                    "Download Transfer Analysis CSV",
                    csv_transfers,
                    f"league_{st.session_state.league_id}_transfers.csv",
                    "text/csv"
                )
        
        with col3:
            if not insights['monthly_performance'].empty:
                csv_monthly = insights['monthly_performance'].to_csv(index=False)
                st.download_button(
                    "Download Performance Data CSV",
                    csv_monthly,
                    f"league_{st.session_state.league_id}_performance.csv",
                    "text/csv"
                )
        
        # Raw data viewer
        if st.checkbox("Show Raw Data"):
            st.markdown("**Full Standings Data:**")
            st.dataframe(standings, use_container_width=True)

# Footer
st.markdown("---")
st.markdown(
    """
    **🎯 How to Use These Insights:**
    - **Transfer Analysis:** Identify who's making smart moves vs costly mistakes
    - **Top Movers:** Spot momentum shifts and rising managers  
    - **Performance Trends:** Find consistent performers vs volatile players
    - **League Stats:** Understand your league's competitive landscape
    
    *Note: Analysis uses publicly available FPL data. Some metrics are estimated based on available information.*
    """
)

if 'analyzer' not in st.session_state:
    st.info("👆 Enter your mini league ID in the sidebar to get started!")