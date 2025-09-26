import sys
from pathlib import Path

# Add the project root to Python path
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent  # Go up to project root
sys.path.insert(0, str(project_root / "src"))

# Streamlit and data analysis imports
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging

# Import FPL optimizer modules
from fpl_optimizer.api.fpl_client import FPLClient
from fpl_optimizer.analysis.mini_league_analyzer import MiniLeagueAnalyzer

# Streamlit page configuration
st.set_page_config(
    page_title="FPL Mini League Analytics",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
.main-header {
    font-size: 2.5rem;
    color: #37003c;
    text-align: center;
    margin-bottom: 2rem;
    font-weight: bold;
}
.metric-card {
    background-color: #f0f2f6;
    padding: 1rem;
    border-radius: 0.5rem;
    border-left: 4px solid #37003c;
}
.stMetric > label {
    color: #37003c !important;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_league_data(league_id):
    """Load and cache league data."""
    try:
        fpl_client = FPLClient()
        analyzer = MiniLeagueAnalyzer(fpl_client)
        return analyzer.get_league_detailed_data(league_id)
    except Exception as e:
        st.error(f"Error loading league data: {e}")
        return None

@st.cache_data(ttl=300)
def analyze_league_performance(league_data):
    """Analyze and cache league performance data."""
    if league_data is None:
        return None
    try:
        fpl_client = FPLClient()
        analyzer = MiniLeagueAnalyzer(fpl_client)
        return analyzer.analyze_league_performance(league_data)
    except Exception as e:
        st.error(f"Error analyzing performance: {e}")
        return None

@st.cache_data(ttl=300)
def get_differential_analysis(league_data):
    """Get and cache differential analysis."""
    if league_data is None:
        return None
    try:
        fpl_client = FPLClient()
        analyzer = MiniLeagueAnalyzer(fpl_client)
        return analyzer.analyze_differentials(league_data)
    except Exception as e:
        st.error(f"Error with differential analysis: {e}")
        return None

def main():
    """Main Streamlit application."""
    
    # Main header
    st.markdown('<h1 class="main-header">⚽ FPL Mini League Analytics</h1>', unsafe_allow_html=True)
    
    # Sidebar for league selection
    st.sidebar.header("🎯 League Selection")
    
    # Default league IDs (you can modify these)
    default_leagues = {
        "NBC Sports League": 149533,
        "@OfficialFPL on X": 31725,
        "Banterville Pop.6": 4
    }
    
    # League selection
    selected_league_name = st.sidebar.selectbox(
        "Choose a league:",
        ["Custom"] + list(default_leagues.keys())
    )
    
    if selected_league_name == "Custom":
        league_id = st.sidebar.number_input(
            "Enter League ID:",
            min_value=1,
            value=149533,
            help="Find your league ID in the URL of your mini league page"
        )
    else:
        league_id = default_leagues[selected_league_name]
        st.sidebar.write(f"League ID: {league_id}")
    
    # Analysis button
    if st.sidebar.button("🔍 Analyze League", type="primary"):
        with st.spinner("Loading league data..."):
            league_data = load_league_data(league_id)
            
            if league_data is None:
                st.error("Failed to load league data. Please check the league ID and try again.")
                return
            
            # Store in session state
            st.session_state.league_data = league_data
            st.session_state.league_id = league_id
    
    # Display analysis if data is available
    if hasattr(st.session_state, 'league_data') and st.session_state.league_data:
        league_data = st.session_state.league_data
        
        # League header
        league_info = league_data.get('league_info', {})
        st.header(f"📊 {league_info.get('name', 'Unknown League')}")
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Managers", len(league_data.get('managers', [])))
        
        with col2:
            st.metric("League Type", league_info.get('league_type', 'Unknown'))
        
        with col3:
            if league_data.get('managers'):
                avg_points = np.mean([m.get('summary', {}).get('total_points', 0) for m in league_data['managers']])
                st.metric("Average Points", f"{avg_points:.0f}")
        
        with col4:
            st.metric("Created", league_info.get('created', 'Unknown'))
        
        # Tabs for different analyses
        tab1, tab2, tab3, tab4 = st.tabs(["📈 Performance", "🎯 Differentials", "📊 Standings", "🔄 Transfers"])
        
        with tab1:
            st.subheader("League Performance Analysis")
            
            with st.spinner("Analyzing performance..."):
                performance_df = analyze_league_performance(league_data)
                
                if performance_df is not None and not performance_df.empty:
                    # Performance chart
                    fig = px.bar(
                        performance_df.head(10),
                        x='Manager',
                        y='Total_Points',
                        title="Top 10 Managers by Total Points",
                        color='Total_Points',
                        color_continuous_scale='viridis'
                    )
                    fig.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Performance table
                    st.dataframe(performance_df, use_container_width=True)
                else:
                    st.warning("No performance data available")
        
        with tab2:
            st.subheader("Differential Analysis")
            
            with st.spinner("Analyzing differentials..."):
                differential_data = get_differential_analysis(league_data)
                
                if differential_data is not None:
                    st.write("Player ownership and differential opportunities")
                    # Add your differential visualization here
                else:
                    st.warning("No differential data available")
        
        with tab3:
            st.subheader("Current Standings")
            
            if league_data.get('standings'):
                standings_df = pd.DataFrame(league_data['standings'])
                st.dataframe(standings_df, use_container_width=True)
            else:
                st.warning("No standings data available")
        
        with tab4:
            st.subheader("Transfer Analysis")
            st.info("Transfer analysis coming soon...")
    
    else:
        # Welcome message
        st.info("👈 Select a league from the sidebar to get started!")
        
        st.markdown("""
        ## Welcome to FPL Mini League Analytics! 🎉
        
        This tool helps you analyze your Fantasy Premier League mini leagues with:
        
        - 📊 **Performance Analysis**: Track manager performance and trends
        - 🎯 **Differential Analysis**: Find players that can help you climb the rankings  
        - 📈 **Transfer Insights**: Analyze transfer patterns and efficiency
        - 🏆 **Head-to-Head Comparisons**: Compare strategies with other managers
        
        ### How to get started:
        1. Find your mini league ID (from your league URL)
        2. Select it from the sidebar or enter a custom ID
        3. Click "Analyze League" to see detailed insights
        
        ### Finding your League ID:
        Go to your mini league page and look at the URL:
        `fantasy.premierleague.com/leagues/XXXXXX/standings/c`
        
        The `XXXXXX` number is your league ID.
        """)

if __name__ == "__main__":
    main()