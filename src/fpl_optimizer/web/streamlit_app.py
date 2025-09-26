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

@st.cache_data(ttl=300)
def analyze_monthly_performance(league_data, start_month=None, end_month=None):
    """Analyze performance by month with date range filtering."""
    monthly_data = []
    
    for manager in league_data['managers']:
        history = manager.get('history', {})
        current_gw_history = history.get('current', [])
        
        if current_gw_history:
            df_history = pd.DataFrame(current_gw_history)
            
            # Convert deadline_time to datetime if available, otherwise use event number
            if 'deadline_time' in df_history.columns:
                df_history['date'] = pd.to_datetime(df_history['deadline_time'])
                df_history['month'] = df_history['date'].dt.to_period('M')
            else:
                # Fallback: estimate months based on gameweek (assuming ~4 GWs per month)
                df_history['month'] = ((df_history['event'] - 1) // 4) + 1
                df_history['month_name'] = df_history['month'].apply(
                    lambda x: ['Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May'][x-1] if x <= 10 else f'Month{x}'
                )
            
            # Group by month
            if 'date' in df_history.columns:
                monthly_stats = df_history.groupby('month').agg({
                    'points': ['sum', 'mean', 'std', 'count'],
                    'event_transfers': 'sum',
                    'event_transfers_cost': 'sum',
                    'overall_rank': 'last'
                }).round(2)
                
                monthly_stats.columns = ['Total_Points', 'Avg_Points', 'Points_Std', 'Games_Played', 
                                       'Total_Transfers', 'Transfer_Cost', 'Final_Rank']
                
                for month, stats in monthly_stats.iterrows():
                    monthly_data.append({
                        'Manager': manager['manager_name'],
                        'Month': str(month),
                        'Total_Points': stats['Total_Points'],
                        'Avg_Points_Per_GW': stats['Avg_Points'],
                        'Consistency': 100 - stats['Points_Std'] if stats['Points_Std'] > 0 else 100,
                        'Games_Played': int(stats['Games_Played']),
                        'Total_Transfers': int(stats['Total_Transfers']),
                        'Transfer_Cost': int(stats['Transfer_Cost']),
                        'Final_Rank': int(stats['Final_Rank']),
                        'Points_Per_Game': round(stats['Total_Points'] / stats['Games_Played'], 1)
                    })
            else:
                # Fallback monthly grouping
                monthly_stats = df_history.groupby('month').agg({
                    'points': ['sum', 'mean', 'count'],
                    'event_transfers': 'sum'
                }).round(2)
                
                monthly_stats.columns = ['Total_Points', 'Avg_Points', 'Games_Played', 'Total_Transfers']
                
                for month, stats in monthly_stats.iterrows():
                    month_name = ['Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May'][month-1] if month <= 10 else f'Month{month}'
                    monthly_data.append({
                        'Manager': manager['manager_name'],
                        'Month': month_name,
                        'Total_Points': stats['Total_Points'],
                        'Avg_Points_Per_GW': stats['Avg_Points'],
                        'Games_Played': int(stats['Games_Played']),
                        'Total_Transfers': int(stats['Total_Transfers']),
                        'Points_Per_Game': round(stats['Total_Points'] / stats['Games_Played'], 1)
                    })
    
    return pd.DataFrame(monthly_data) if monthly_data else pd.DataFrame()

@st.cache_data(ttl=300)
def analyze_weekly_trends(league_data, weeks_back=8):
    """Analyze recent weekly trends and momentum."""
    weekly_trends = []
    
    for manager in league_data['managers']:
        history = manager.get('history', {})
        current_gw_history = history.get('current', [])
        
        if current_gw_history:
            df_history = pd.DataFrame(current_gw_history)
            
            # Get recent weeks
            recent_weeks = df_history.tail(weeks_back)
            
            if len(recent_weeks) > 0:
                # Calculate trends
                points_trend = recent_weeks['points'].rolling(window=3).mean().iloc[-1] if len(recent_weeks) >= 3 else recent_weeks['points'].mean()
                rank_change = recent_weeks['overall_rank'].iloc[0] - recent_weeks['overall_rank'].iloc[-1] if len(recent_weeks) > 1 else 0
                best_week = recent_weeks['points'].max()
                worst_week = recent_weeks['points'].min()
                
                # Form analysis (last 5 gameweeks)
                last_5 = recent_weeks.tail(5)
                form_points = last_5['points'].sum()
                form_avg = last_5['points'].mean()
                
                # Momentum calculation
                if len(recent_weeks) >= 4:
                    first_half = recent_weeks.head(len(recent_weeks)//2)['points'].mean()
                    second_half = recent_weeks.tail(len(recent_weeks)//2)['points'].mean()
                    momentum = second_half - first_half
                else:
                    momentum = 0
                
                weekly_trends.append({
                    'Manager': manager['manager_name'],
                    'Current_Rank': manager['rank'],
                    'Points_Trend_3GW': round(points_trend, 1),
                    'Rank_Change': int(rank_change),
                    'Best_Recent_Week': int(best_week),
                    'Worst_Recent_Week': int(worst_week),
                    'Form_Points_5GW': int(form_points),
                    'Form_Average': round(form_avg, 1),
                    'Momentum': round(momentum, 1),
                    'Trending': 'Up' if momentum > 2 else 'Down' if momentum < -2 else 'Stable'
                })
    
    return pd.DataFrame(weekly_trends) if weekly_trends else pd.DataFrame()

@st.cache_data(ttl=300)
def get_gameweek_comparison(league_data, selected_gameweeks):
    """Compare specific gameweeks performance."""
    comparison_data = []
    
    for manager in league_data['managers']:
        history = manager.get('history', {})
        current_gw_history = history.get('current', [])
        
        if current_gw_history:
            df_history = pd.DataFrame(current_gw_history)
            
            for gw in selected_gameweeks:
                gw_data = df_history[df_history['event'] == gw]
                if not gw_data.empty:
                    gw_info = gw_data.iloc[0]
                    comparison_data.append({
                        'Manager': manager['manager_name'],
                        'Gameweek': f"GW{gw}",
                        'Points': gw_info['points'],
                        'Rank': gw_info['overall_rank'],
                        'Transfers': gw_info['event_transfers'],
                        'Transfer_Cost': gw_info.get('event_transfers_cost', 0)
                    })
    
    return pd.DataFrame(comparison_data) if comparison_data else pd.DataFrame()

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

def show_monthly_weekly_analysis(league_data):
    """Show comprehensive monthly and weekly analysis."""
    st.header("📅 Monthly & Weekly Performance Analysis")
    
    # Analysis type selector
    analysis_type = st.selectbox(
        "Choose Analysis Type:",
        ["Monthly Performance", "Weekly Trends", "Gameweek Comparison", "Custom Date Range"]
    )
    
    if analysis_type == "Monthly Performance":
        st.subheader("📊 Monthly Performance Breakdown")
        
        with st.spinner("Analyzing monthly performance..."):
            monthly_df = analyze_monthly_performance(league_data)
        
        if not monthly_df.empty:
            # Monthly performance overview
            col1, col2 = st.columns(2)
            
            with col1:
                # Points by month chart
                avg_monthly = monthly_df.groupby('Month')['Total_Points'].mean().reset_index()
                fig = px.bar(
                    avg_monthly,
                    x='Month',
                    y='Total_Points',
                    title="Average Points by Month",
                    color='Total_Points',
                    color_continuous_scale='viridis'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Consistency by month
                if 'Consistency' in monthly_df.columns:
                    consistency_monthly = monthly_df.groupby('Month')['Consistency'].mean().reset_index()
                    fig = px.line(
                        consistency_monthly,
                        x='Month',
                        y='Consistency',
                        title="Consistency Trends by Month",
                        markers=True
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    # Alternative chart if consistency not available
                    avg_ppg = monthly_df.groupby('Month')['Points_Per_Game'].mean().reset_index()
                    fig = px.line(
                        avg_ppg,
                        x='Month',
                        y='Points_Per_Game',
                        title="Points Per Game by Month",
                        markers=True
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            # Top performers by month
            st.subheader("🏆 Top Performers by Month")
            
            months = monthly_df['Month'].unique()
            selected_month = st.selectbox("Select Month:", months)
            
            month_data = monthly_df[monthly_df['Month'] == selected_month].sort_values('Total_Points', ascending=False)
            
            if not month_data.empty:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Month Leader", month_data.iloc[0]['Manager'])
                    st.metric("Points", int(month_data.iloc[0]['Total_Points']))
                
                with col2:
                    if 'Consistency' in month_data.columns:
                        st.metric("Most Consistent", month_data.sort_values('Consistency', ascending=False).iloc[0]['Manager'])
                        st.metric("Consistency Score", f"{month_data['Consistency'].max():.1f}")
                    else:
                        st.metric("Best PPG", month_data.sort_values('Points_Per_Game', ascending=False).iloc[0]['Manager'])
                        st.metric("Points Per Game", f"{month_data['Points_Per_Game'].max():.1f}")
                
                with col3:
                    if 'Total_Transfers' in month_data.columns:
                        st.metric("Most Active", month_data.sort_values('Total_Transfers', ascending=False).iloc[0]['Manager'])
                        st.metric("Transfers Made", int(month_data['Total_Transfers'].max()))
                    else:
                        st.metric("Games Played", int(month_data['Games_Played'].max()))
                
                # Monthly leaderboard
                st.dataframe(month_data, use_container_width=True)
        else:
            st.warning("No monthly data available")
    
    elif analysis_type == "Weekly Trends":
        st.subheader("📈 Recent Weekly Trends & Momentum")
        
        weeks_back = st.slider("Analyze last N weeks:", 4, 15, 8)
        
        with st.spinner("Analyzing weekly trends..."):
            trends_df = analyze_weekly_trends(league_data, weeks_back)
        
        if not trends_df.empty:
            # Momentum analysis
            col1, col2 = st.columns(2)
            
            with col1:
                # Form vs Current Rank
                fig = px.scatter(
                    trends_df,
                    x='Current_Rank',
                    y='Form_Average',
                    size='Form_Points_5GW',
                    color='Trending',
                    hover_data=['Manager'],
                    title="Current Form vs League Position",
                    color_discrete_map={'Up': 'green', 'Down': 'red', 'Stable': 'blue'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Rank movement
                fig = px.bar(
                    trends_df.sort_values('Rank_Change', ascending=False),
                    x='Manager',
                    y='Rank_Change',
                    title="Rank Movement (Recent Period)",
                    color='Rank_Change',
                    color_continuous_scale='RdYlGn'
                )
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)
            
            # Trending managers
            st.subheader("🔥 Trending Managers")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**📈 Trending Up**")
                trending_up = trends_df[trends_df['Trending'] == 'Up'].sort_values('Momentum', ascending=False)
                if not trending_up.empty:
                    for _, manager in trending_up.head(3).iterrows():
                        st.write(f"🟢 {manager['Manager']} (+{manager['Momentum']:.1f})")
                else:
                    st.write("No managers trending up")
            
            with col2:
                st.write("**📉 Trending Down**")
                trending_down = trends_df[trends_df['Trending'] == 'Down'].sort_values('Momentum')
                if not trending_down.empty:
                    for _, manager in trending_down.head(3).iterrows():
                        st.write(f"🔴 {manager['Manager']} ({manager['Momentum']:.1f})")
                else:
                    st.write("No managers trending down")
            
            with col3:
                st.write("**⚖️ Best Form**")
                best_form = trends_df.sort_values('Form_Average', ascending=False)
                for _, manager in best_form.head(3).iterrows():
                    st.write(f"⭐ {manager['Manager']} ({manager['Form_Average']:.1f}/GW)")
            
            # Detailed trends table
            st.subheader("📋 Detailed Weekly Analysis")
            st.dataframe(trends_df, use_container_width=True)
        else:
            st.warning("No weekly trend data available")
    
    elif analysis_type == "Gameweek Comparison":
        st.subheader("⚡ Gameweek Head-to-Head Comparison")
        
        # Get available gameweeks
        sample_manager = league_data['managers'][0] if league_data['managers'] else None
        if sample_manager and 'history' in sample_manager and 'current' in sample_manager['history']:
            available_gws = [gw['event'] for gw in sample_manager['history']['current']]
            
            col1, col2 = st.columns(2)
            with col1:
                gw1 = st.selectbox("Select first gameweek:", available_gws, index=0 if available_gws else 0)
            with col2:
                gw2 = st.selectbox("Select second gameweek:", available_gws, index=min(1, len(available_gws)-1))
            
            if st.button("Compare Gameweeks"):
                comparison_df = get_gameweek_comparison(league_data, [gw1, gw2])
                
                if not comparison_df.empty:
                    # Create side-by-side comparison
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**GW{gw1} Performance**")
                        gw1_data = comparison_df[comparison_df['Gameweek'] == f'GW{gw1}'].sort_values('Points', ascending=False)
                        st.dataframe(gw1_data, use_container_width=True)
                    
                    with col2:
                        st.write(f"**GW{gw2} Performance**")
                        gw2_data = comparison_df[comparison_df['Gameweek'] == f'GW{gw2}'].sort_values('Points', ascending=False)
                        st.dataframe(gw2_data, use_container_width=True)
                    
                    # Points comparison chart
                    fig = px.bar(
                        comparison_df,
                        x='Manager',
                        y='Points',
                        color='Gameweek',
                        title=f"Points Comparison: GW{gw1} vs GW{gw2}",
                        barmode='group'
                    )
                    fig.update_xaxes(tickangle=45)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("No comparison data available for selected gameweeks")
        else:
            st.warning("No gameweek data available for comparison")
    
    elif analysis_type == "Custom Date Range":
        st.subheader("🗓️ Custom Date Range Analysis")
        st.info("Feature coming soon - will allow filtering by specific date ranges and custom metrics!")

def main():
    """Main Streamlit application."""
    
    # Main header
    st.markdown('<h1 class="main-header">⚽ FPL Mini League Analytics</h1>', unsafe_allow_html=True)
    
    # Sidebar for league selection
    st.sidebar.header("🎯 League Selection")
    
    # Default league IDs (you can modify these)
    default_leagues = {
        "Banterville Pop.7": 750563
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
        tab1, tab2, tab3 = st.tabs(["📈 Performance", "📅 Monthly/Weekly", "🔄 Transfers"])
        
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
            show_monthly_weekly_analysis(league_data)
        
        with tab3:
            # Enhanced transfer analysis
            show_enhanced_transfer_analysis(league_data)
    
    else:
        # Welcome message
        st.info("👈 Select a league from the sidebar to get started!")
        
        st.markdown("""
        ## Welcome to FPL Mini League Analytics! 🎉
        
        This tool helps you analyze your Fantasy Premier League mini leagues with:
        
        - 📊 **Performance Analysis**: Track manager performance and trends
        - 📅 **Monthly/Weekly Analysis**: Understand performance patterns over time
        - 🔄 **Transfer Insights**: Analyze transfer patterns and efficiency
        
        ### Finding your League ID:
        Go to your mini league page and look at the URL:
        `fantasy.premierleague.com/leagues/XXXXXX/standings/c`
        
        The `XXXXXX` number is your league ID.
        """)

if __name__ == "__main__":
    main()