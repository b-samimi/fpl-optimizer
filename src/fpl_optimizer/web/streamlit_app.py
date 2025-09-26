import sys
import os
from pathlib import Path

# Add the project root to Python path - multiple approaches for robustness
current_file = Path(__file__).resolve()

# Method 1: Go up from web/ -> fpl_optimizer/ -> src/ -> project_root/
project_root = current_file.parent.parent.parent.parent
src_path = project_root / "src"

# Method 2: Alternative path calculation
alt_src_path = current_file.parent.parent.parent

# Method 3: Direct relative path
direct_src = Path(__file__).parent.parent.parent

# Try to add the correct src path
for potential_src in [src_path, alt_src_path, direct_src]:
    if potential_src.exists() and (potential_src / "fpl_optimizer").exists():
        sys.path.insert(0, str(potential_src))
        break
else:
    # Fallback: Add current directory structure
    sys.path.insert(0, str(current_file.parent.parent.parent))
    sys.path.insert(0, str(project_root / "src"))
    sys.path.insert(0, str(Path.cwd() / "src"))

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

# Enhanced CSS for better readability and transfer monitoring
st.markdown("""
<style>
/* Fix text readability */
.main-header {
    font-size: 2.5rem;
    color: #00ff87;  /* Bright green for better contrast */
    text-align: center;
    margin-bottom: 2rem;
    font-weight: bold;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
}

/* Improve metric text visibility */
.stMetric > div[data-testid="metric-container"] > div {
    color: #ffffff !important;
}

.stMetric label {
    color: #00ff87 !important;
    font-weight: bold !important;
    font-size: 1.1rem !important;
}

/* Improve general text readability */
.stMarkdown, .stText {
    color: #ffffff !important;
}

/* Tab text visibility */
.stTabs [data-baseweb="tab"] {
    color: #ffffff !important;
}

.stTabs [aria-selected="true"] {
    color: #00ff87 !important;
    border-bottom-color: #00ff87 !important;
}

/* Table text readability */
.stDataFrame {
    background-color: rgba(0, 0, 0, 0.3);
}

/* Better contrast for headers */
h1, h2, h3, h4, h5, h6 {
    color: #00ff87 !important;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.7);
}

/* Sidebar improvements */
.css-1d391kg {
    background-color: rgba(0, 0, 0, 0.2);
}

/* Transfer monitoring highlight */
.transfer-highlight {
    background: linear-gradient(45deg, #ff6b6b, #feca57);
    padding: 10px;
    border-radius: 8px;
    margin: 10px 0;
    border-left: 4px solid #ff6b6b;
}

.player-behavior-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
    color: white;
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
}

/* Select box text */
.stSelectbox > div > div {
    color: #ffffff !important;
}

/* Button styling */
.stButton > button {
    background-color: #00ff87;
    color: #000000;
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

@st.cache_data(ttl=300)
def analyze_weekly_transfer_behavior(league_data):
    """Analyze week-over-week transfer patterns and behavior."""
    transfer_behavior = []
    
    for manager in league_data['managers']:
        history = manager.get('history', {})
        current_gw_history = history.get('current', [])
        
        if current_gw_history:
            df_history = pd.DataFrame(current_gw_history)
            
            # Calculate week-over-week metrics
            df_history['points_change'] = df_history['points'].diff()
            df_history['rank_change'] = -df_history['overall_rank'].diff()  # Negative because lower rank is better
            df_history['transfers_this_week'] = df_history['event_transfers']
            df_history['players_changed'] = df_history['event_transfers']  # Actual player changes
            df_history['penalty_hits'] = (df_history['event_transfers'] - 1).clip(lower=0)  # Point penalties taken
            df_history['points_lost_penalties'] = df_history['penalty_hits'] * 4
            
            # Recent behavior (last 5 gameweeks)
            recent_weeks = df_history.tail(5)
            
            # Calculate behavioral patterns
            avg_weekly_transfers = recent_weeks['transfers_this_week'].mean()
            penalty_frequency = (recent_weeks['penalty_hits'] > 0).sum() / len(recent_weeks)
            points_volatility = recent_weeks['points'].std()
            rank_momentum = recent_weeks['rank_change'].sum()
            
            # Transfer success rate (positive points change after taking penalties)
            penalty_weeks = recent_weeks[recent_weeks['penalty_hits'] > 0]
            if len(penalty_weeks) > 0:
                transfer_success_rate = (penalty_weeks['points_change'] > penalty_weeks['points_lost_penalties']).mean()
            else:
                transfer_success_rate = 0
            
            # Recent 3 weeks trend
            last_3_weeks = df_history.tail(3)
            recent_transfer_trend = "Increasing" if last_3_weeks['transfers_this_week'].is_monotonic_increasing else \
                                  "Decreasing" if last_3_weeks['transfers_this_week'].is_monotonic_decreasing else "Stable"
            
            transfer_behavior.append({
                'Manager': manager['manager_name'],
                'Current_Rank': manager['rank'],
                'Avg_Weekly_Transfers': round(avg_weekly_transfers, 1),
                'Penalty_Frequency_Pct': round(penalty_frequency * 100, 1),
                'Points_Volatility': round(points_volatility, 1),
                'Rank_Momentum': int(rank_momentum),
                'Transfer_Success_Rate': round(transfer_success_rate * 100, 1),
                'Recent_Transfer_Trend': recent_transfer_trend,
                'Last_GW_Transfers': int(df_history.iloc[-1]['transfers_this_week']) if len(df_history) > 0 else 0,
                'Last_GW_Penalties': int(df_history.iloc[-1]['penalty_hits']) if len(df_history) > 0 else 0,
                'Last_GW_Points': int(df_history.iloc[-1]['points']) if len(df_history) > 0 else 0
            })
    
    return pd.DataFrame(transfer_behavior)

def show_enhanced_transfer_analysis(league_data):
    """Show enhanced week-over-week transfer analysis."""
    st.header("🔄 Week-over-Week Transfer Monitoring")
    
    # Get transfer behavior data
    transfer_df = analyze_weekly_transfer_behavior(league_data)
    
    if transfer_df.empty:
        st.warning("No transfer data available")
        return
    
    # Current week highlights
    st.markdown('<div class="transfer-highlight">', unsafe_allow_html=True)
    st.subheader("🚨 This Week's Activity")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        active_managers = len(transfer_df[transfer_df['Last_GW_Transfers'] > 0])
        st.metric("Active Managers", f"{active_managers}/{len(transfer_df)}")
    
    with col2:
        total_penalties = transfer_df['Last_GW_Penalties'].sum()
        st.metric("Point Penalties Taken", total_penalties)
    
    with col3:
        most_transfers = transfer_df['Last_GW_Transfers'].max()
        most_active = transfer_df[transfer_df['Last_GW_Transfers'] == most_transfers]['Manager'].iloc[0] if most_transfers > 0 else "None"
        st.metric("Most Active", f"{most_active} ({most_transfers})")
    
    with col4:
        if len(transfer_df) > 0:
            highest_scorer = transfer_df.loc[transfer_df['Last_GW_Points'].idxmax()]
            st.metric("Top Scorer", f"{highest_scorer['Manager']} ({highest_scorer['Last_GW_Points']})")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Player behavior patterns
    st.subheader("🧠 Player Behavior Patterns")
    
    # Create behavior categories
    transfer_df['Behavior_Type'] = transfer_df.apply(lambda x: 
        "🔥 Aggressive" if x['Penalty_Frequency_Pct'] > 40 else
        "⚡ Active" if x['Avg_Weekly_Transfers'] > 1.5 else
        "🛡️ Conservative" if x['Penalty_Frequency_Pct'] < 10 else
        "📊 Balanced", axis=1)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Transfer frequency vs Success rate
        fig = px.scatter(
            transfer_df,
            x='Penalty_Frequency_Pct',
            y='Transfer_Success_Rate',
            size='Avg_Weekly_Transfers',
            color='Behavior_Type',
            hover_data=['Manager', 'Rank_Momentum'],
            title="Transfer Strategy Effectiveness",
            labels={
                'Penalty_Frequency_Pct': 'Penalty Frequency (% of weeks taking -4 point hits)',
                'Transfer_Success_Rate': 'Transfer Success Rate (% when penalties pay off)'
            }
        )
        fig.add_hline(y=50, line_dash="dash", line_color="white", annotation_text="50% Success Rate")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Rank momentum vs transfer activity
        fig = px.scatter(
            transfer_df,
            x='Avg_Weekly_Transfers',
            y='Rank_Momentum',
            color='Points_Volatility',
            size='Current_Rank',
            hover_data=['Manager'],
            title="Transfer Activity vs Rank Movement",
            labels={
                'Avg_Weekly_Transfers': 'Avg Weekly Transfers',
                'Rank_Momentum': 'Rank Improvement (Last 5 GWs)'
            },
            color_continuous_scale='RdYlGn'
        )
        fig.add_hline(y=0, line_dash="dash", line_color="white", annotation_text="No Change")
        st.plotly_chart(fig, use_container_width=True)
    
    # Player behavior cards
    st.subheader("👥 Individual Player Profiles")
    
    # Sort by current rank for display
    display_df = transfer_df.sort_values('Current_Rank')
    
    for i, (_, manager) in enumerate(display_df.head(6).iterrows()):  # Show top 6
        col = st.columns(3)[i % 3]
        
        with col:
            st.markdown(f'''
            <div class="player-behavior-card">
                <h4>{manager['Manager']} (#{manager['Current_Rank']})</h4>
                <p><strong>{manager['Behavior_Type']}</strong></p>
                <p>📊 Avg Transfers: {manager['Avg_Weekly_Transfers']}/week</p>
                <p>⚡ Penalty Rate: {manager['Penalty_Frequency_Pct']}%</p>
                <p>📈 Success Rate: {manager['Transfer_Success_Rate']}%</p>
                <p>🏃 Momentum: {manager['Rank_Momentum']:+d} ranks</p>
                <p>📋 Last Week: {manager['Last_GW_Transfers']} transfers, {manager['Last_GW_Points']} pts</p>
            </div>
            ''', unsafe_allow_html=True)
    
    # Detailed transfer behavior table
    st.subheader("📋 Detailed Transfer Behavior")
    
    # Format the dataframe for better display
    display_cols = [
        'Manager', 'Current_Rank', 'Behavior_Type', 'Avg_Weekly_Transfers',
        'Penalty_Frequency_Pct', 'Transfer_Success_Rate', 'Rank_Momentum',
        'Recent_Transfer_Trend', 'Last_GW_Transfers', 'Last_GW_Points'
    ]
    
    st.dataframe(
        transfer_df[display_cols].style.format({
            'Avg_Weekly_Transfers': '{:.1f}',
            'Penalty_Frequency_Pct': '{:.1f}%',
            'Transfer_Success_Rate': '{:.1f}%',
            'Rank_Momentum': '{:+d}'
        }),
        use_container_width=True
    )
    
    # Weekly transfer timeline
    st.subheader("📈 Weekly Transfer Activity Timeline")
    st.info("💡 **Chart Guide**: Line shows total transfers made each week. Marker size indicates point penalties taken (larger = more -4 point hits). Chips like Free Hit/Wildcard allow unlimited transfers without penalties.")
    
    # Create timeline chart for active managers
    fig = go.Figure()
    
    colors = px.colors.qualitative.Set3
    active_managers = league_data['managers'][:5]  # Top 5 for clarity
    
    for i, manager in enumerate(active_managers):
        history = manager.get('history', {})
        if 'current' in history and history['current']:
            gw_data = pd.DataFrame(history['current'])
            if not gw_data.empty:
                gw_data['penalty_hits'] = (gw_data['event_transfers'] - 1).clip(lower=0)
                
                fig.add_trace(go.Scatter(
                    x=gw_data['event'],
                    y=gw_data['event_transfers'],
                    mode='lines+markers',
                    name=manager['manager_name'],
                    line=dict(color=colors[i % len(colors)], width=2),
                    marker=dict(size=gw_data['penalty_hits'] * 4 + 6),  # Size based on penalties
                    hovertemplate=f"<b>{manager['manager_name']}</b><br>" +
                                "GW: %{x}<br>" +
                                "Players Changed: %{y}<br>" +
                                "Point Penalties: %{customdata}<br>" +
                                "<extra></extra>",
                    customdata=gw_data['penalty_hits']
                ))
    
    fig.update_layout(
        title="Weekly Transfer Activity (Line = transfers made, Marker size = point penalties taken)",
        xaxis_title="Gameweek",
        yaxis_title="Number of Transfers Made",
        height=400,
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)

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
            value=750563,
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
                avg_points = np.mean([m.get('total_points', 0) for m in league_data['managers']])
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
            # Enhanced transfer analysis
            show_enhanced_transfer_analysis(league_data)
    
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
        
        ### Finding your League ID:
        Go to your mini league page and look at the URL:
        `fantasy.premierleague.com/leagues/XXXXXX/standings/c`
        
        The `XXXXXX` number is your league ID.
        """)

if __name__ == "__main__":
    main()