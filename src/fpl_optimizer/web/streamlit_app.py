import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os
from pathlib import Path

# Fix the Python path to find your modules
current_dir = Path(__file__).parent.absolute()
project_root = current_dir.parent.parent.parent  # Go up to project root
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))

try:
    # Import your existing modules
    from fpl_optimizer.api.fpl_client import FPLClient
    
    # Import the analyzer - try both locations
    try:
        from fpl_optimizer.analysis.mini_league_analyzer import MiniLeagueAnalyzer
    except ImportError:
        # Fallback to outputs directory
        outputs_dir = project_root / "outputs"
        if outputs_dir.exists():
            sys.path.insert(0, str(outputs_dir))
            from mini_league_analyzer import MiniLeagueAnalyzer
        else:
            st.error("Could not find mini_league_analyzer. Please check file locations.")
            st.stop()

except ImportError as e:
    st.error(f"Import error: {e}")
    st.error("Please check that you're running this from your project root directory.")
    st.stop()

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
        return analyzer.get_differential_analysis(league_data)
    except Exception as e:
        st.error(f"Error getting differential analysis: {e}")
        return None

def main():
    # Header
    st.markdown('<h1 class="main-header">⚽ FPL Mini League Analytics Dashboard</h1>', unsafe_allow_html=True)
    
    # Sidebar for league input and navigation
    with st.sidebar:
        st.header("🏆 League Configuration")
        
        # Default to your known league IDs
        league_options = {
            "NBC Sports League": 149533,
            "@OfficialFPL on X": 31725,
            "Banterville Pop.6": 4,
            "Custom League": None
        }
        
        selected_league = st.selectbox("Select League:", list(league_options.keys()))
        
        if selected_league == "Custom League":
            league_id = st.number_input("Enter League ID:", min_value=1, value=149533)
        else:
            league_id = league_options[selected_league]
            st.info(f"League ID: {league_id}")
        
        st.markdown("---")
        
        # Navigation
        analysis_type = st.radio(
            "Choose Analysis:",
            ["Overview", "Performance Analysis", "Differential Analysis", "Transfer Insights", "Team Comparison"]
        )
        
        st.markdown("---")
        st.markdown("### 📊 Your Current Stats")
        st.metric("Overall Rank", "4,529,338")
        st.metric("GW5 Points", "57")
        st.metric("Total Points", "258")
    
    # Load data
    if league_id:
        try:
            with st.spinner("Loading league data..."):
                league_data = load_league_data(league_id)
                if league_data is None:
                    st.error("Failed to load league data. Please try again.")
                    return
                
                performance_df = analyze_league_performance(league_data)
                if performance_df is None:
                    st.error("Failed to analyze performance data. Please try again.")
                    return
            
            # Main content based on selection
            if analysis_type == "Overview":
                show_overview(league_data, performance_df)
            elif analysis_type == "Performance Analysis":
                show_performance_analysis(league_data, performance_df)
            elif analysis_type == "Differential Analysis":
                show_differential_analysis(league_data)
            elif analysis_type == "Transfer Insights":
                show_transfer_insights(league_data, performance_df)
            elif analysis_type == "Team Comparison":
                show_team_comparison(league_data)
                
        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
            st.info("Please check the league ID and try again.")

def show_overview(league_data, performance_df):
    """Show league overview with key metrics."""
    st.header(f"🏆 {league_data['league_info']['name']}")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Managers", len(league_data['managers']))
    with col2:
        st.metric("League Leader", performance_df.iloc[0]['Manager'])
    with col3:
        st.metric("Highest Score", int(performance_df['Total_Points'].max()))
    with col4:
        avg_score = performance_df['Total_Points'].mean()
        st.metric("Average Score", f"{avg_score:.1f}")
    
    # Current standings
    st.subheader("📊 Current Standings")
    
    # Create standings chart
    fig = go.Figure()
    
    # Color code based on position
    colors = ['gold' if i == 0 else 'silver' if i == 1 else 'chocolate' if i == 2 else 'lightblue' 
              for i in range(len(performance_df))]
    
    fig.add_trace(go.Bar(
        x=performance_df['Manager'],
        y=performance_df['Total_Points'],
        marker_color=colors,
        text=performance_df['Total_Points'],
        textposition='outside'
    ))
    
    fig.update_layout(
        title="League Standings by Total Points",
        xaxis_title="Manager",
        yaxis_title="Total Points",
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed standings table
    st.subheader("📈 Detailed Standings")
    display_df = performance_df[['Current_Rank', 'Manager', 'Total_Points', 'Avg_Points_Per_GW', 'Best_GW']].copy()
    display_df.columns = ['Rank', 'Manager', 'Total Points', 'Avg/GW', 'Best GW']
    st.dataframe(display_df, use_container_width=True)

def show_performance_analysis(league_data, performance_df):
    """Show detailed performance analysis."""
    st.header("📊 Performance Analysis")
    
    # Performance metrics comparison
    col1, col2 = st.columns(2)
    
    with col1:
        # Consistency vs Points scatter
        fig = px.scatter(
            performance_df,
            x='Consistency_Score',
            y='Total_Points',
            hover_data=['Manager', 'Avg_Points_Per_GW'],
            title="Consistency vs Total Points",
            labels={'Consistency_Score': 'Consistency Score (Higher = More Consistent)'}
        )
        fig.add_annotation(
            x=performance_df['Consistency_Score'].mean(),
            y=performance_df['Total_Points'].max() * 0.95,
            text="High Consistency →",
            showarrow=True
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Transfer strategy analysis
        fig = px.bar(
            performance_df,
            x='Manager',
            y='Transfer_Hits_Taken',
            title="Transfer Hits Taken",
            color='Points_Per_Transfer_Hit',
            color_continuous_scale='RdYlGn'
        )
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)
    
    # Gameweek progression for top managers
    st.subheader("📈 Points Progress Over Time")
    
    # Create line chart for top 5 managers
    fig = go.Figure()
    
    colors = px.colors.qualitative.Set1
    for i, manager in enumerate(league_data['managers'][:5]):
        history = manager.get('history', {})
        if 'current' in history and history['current']:
            gw_data = pd.DataFrame(history['current'])
            if not gw_data.empty:
                fig.add_trace(go.Scatter(
                    x=gw_data['event'],
                    y=gw_data['total_points'],
                    mode='lines+markers',
                    name=manager['manager_name'],
                    line=dict(color=colors[i % len(colors)])
                ))
    
    fig.update_layout(
        title="Total Points Progression (Top 5)",
        xaxis_title="Gameweek",
        yaxis_title="Total Points",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

def show_differential_analysis(league_data):
    """Show player differential analysis."""
    st.header("🎯 Differential Analysis")
    
    with st.spinner("Analyzing player differentials..."):
        differential_df = get_differential_analysis(league_data)
    
    if differential_df is None or differential_df.empty:
        st.warning("Unable to load differential data. Please try again.")
        return
    
    # Top differentials
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔥 Best Differentials")
        st.caption("Players with high global ownership but low league ownership")
        
        top_diffs = differential_df[
            (differential_df['ownership_percentage'] < 50) & 
            (differential_df['selected_by_percent'] > 5)
        ].head(10)
        
        if not top_diffs.empty:
            fig = px.scatter(
                top_diffs,
                x='ownership_percentage',
                y='selected_by_percent',
                size='total_points',
                hover_data=['web_name', 'price'],
                title="League vs Global Ownership",
                labels={
                    'ownership_percentage': 'League Ownership %',
                    'selected_by_percent': 'Global Ownership %'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Display table
            display_cols = ['web_name', 'team_short', 'position', 'price', 'ownership_percentage', 'selected_by_percent', 'total_points']
            st.dataframe(
                top_diffs[display_cols].round(1),
                column_config={
                    'web_name': 'Player',
                    'team_short': 'Team',
                    'position': 'Pos',
                    'price': 'Price',
                    'ownership_percentage': 'League Own%',
                    'selected_by_percent': 'Global Own%',
                    'total_points': 'Points'
                },
                use_container_width=True
            )
    
    with col2:
        st.subheader("👥 Highly Owned Players")
        st.caption("Players owned by most managers in your league")
        
        popular_players = differential_df[differential_df['ownership_percentage'] > 50].head(10)
        
        if not popular_players.empty:
            fig = px.bar(
                popular_players,
                x='web_name',
                y='ownership_percentage',
                color='total_points',
                title="Most Popular Players in League",
                color_continuous_scale='Viridis'
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

def show_transfer_insights(league_data, performance_df):
    """Show transfer insights and recommendations."""
    st.header("🔄 Transfer Insights")
    
    # Transfer efficiency analysis
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Transfer Efficiency")
        
        fig = px.scatter(
            performance_df,
            x='Transfer_Hits_Taken',
            y='Points_Per_Transfer_Hit',
            size='Total_Points',
            hover_data=['Manager'],
            title="Transfer Strategy Efficiency"
        )
        
        # Add efficiency zones
        fig.add_hline(y=performance_df['Points_Per_Transfer_Hit'].mean(), 
                     line_dash="dash", line_color="red", 
                     annotation_text="Average Efficiency")
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Transfer Activity")
        
        fig = px.bar(
            performance_df.sort_values('Transfer_Hits_Taken'),
            x='Manager',
            y=['Transfer_Hits_Taken'],
            title="Total Transfer Hits by Manager"
        )
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)
    
    # Captain choices analysis
    st.subheader("⭐ Captain Choices Analysis")
    
    differential_df = get_differential_analysis(league_data)
    if differential_df is not None and not differential_df.empty and 'captain_count' in differential_df.columns:
        captain_choices = differential_df[differential_df['captain_count'] > 0].sort_values('captain_count', ascending=False).head(10)
        
        if not captain_choices.empty:
            fig = px.bar(
                captain_choices,
                x='web_name',
                y='captain_count',
                title="Most Popular Captain Choices",
                color='total_points',
                color_continuous_scale='RdYlGn'
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

def show_team_comparison(league_data):
    """Show detailed team comparison."""
    st.header("🏟️ Team Comparison")
    
    # Manager selection for comparison
    manager_names = [manager['manager_name'] for manager in league_data['managers']]
    
    col1, col2 = st.columns(2)
    
    with col1:
        manager1 = st.selectbox("Select First Manager:", manager_names, index=0)
    with col2:
        manager2 = st.selectbox("Select Second Manager:", manager_names, index=1 if len(manager_names) > 1 else 0)
    
    if manager1 and manager2 and manager1 != manager2:
        # Get team data for both managers
        team1_data = None
        team2_data = None
        
        for manager in league_data['managers']:
            if manager['manager_name'] == manager1:
                team1_data = manager
            elif manager['manager_name'] == manager2:
                team2_data = manager
        
        if team1_data and team2_data:
            # Performance comparison
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(f"📊 {manager1}")
                st.metric("Total Points", team1_data['total_points'])
                st.metric("Current Rank", team1_data['rank'])
                
                # Show gameweek performance
                if 'history' in team1_data and 'current' in team1_data['history']:
                    recent_gws = pd.DataFrame(team1_data['history']['current']).tail(5)
                    if not recent_gws.empty:
                        st.line_chart(recent_gws.set_index('event')['points'])
            
            with col2:
                st.subheader(f"📊 {manager2}")
                st.metric("Total Points", team2_data['total_points'])
                st.metric("Current Rank", team2_data['rank'])
                
                # Show gameweek performance
                if 'history' in team2_data and 'current' in team2_data['history']:
                    recent_gws = pd.DataFrame(team2_data['history']['current']).tail(5)
                    if not recent_gws.empty:
                        st.line_chart(recent_gws.set_index('event')['points'])
            
            # Head-to-head chart
            st.subheader("📈 Head-to-Head Comparison")
            
            if ('history' in team1_data and 'current' in team1_data['history'] and
                'history' in team2_data and 'current' in team2_data['history']):
                
                gw1_data = pd.DataFrame(team1_data['history']['current'])
                gw2_data = pd.DataFrame(team2_data['history']['current'])
                
                if not gw1_data.empty and not gw2_data.empty:
                    fig = go.Figure()
                    
                    fig.add_trace(go.Scatter(
                        x=gw1_data['event'],
                        y=gw1_data['total_points'],
                        mode='lines+markers',
                        name=manager1,
                        line=dict(color='blue')
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=gw2_data['event'],
                        y=gw2_data['total_points'],
                        mode='lines+markers',
                        name=manager2,
                        line=dict(color='red')
                    ))
                    
                    fig.update_layout(
                        title="Total Points Progression",
                        xaxis_title="Gameweek",
                        yaxis_title="Total Points"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()