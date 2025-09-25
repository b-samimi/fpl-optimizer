import streamlit as st
import pandas as pd
import sys
import os

# Add the project root to the path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.fpl_optimizer.analysis.mini_league_analyzer import MiniLeagueAnalyzer
import plotly.express as px

st.set_page_config(
    page_title="FPL Mini League Analyzer", 
    page_icon="⚽", 
    layout="wide"
)

st.title("⚽ FPL Mini League Analyzer")
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
        st.metric(
            "Last GW Average", 
            f"{standings['event_total'].mean():.1f}"
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
        standings_display = standings[['rank', 'player_name', 'total', 'event_total']].copy()
        standings_display.columns = ['Rank', 'Manager', 'Total Points', 'Last GW']
        
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
        st.dataframe(
            transfer_data,
            use_container_width=True,
            hide_index=True
        )
        
        # Transfer efficiency chart
        if len(transfer_data) > 0:
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
        recent_top = standings.nlargest(10, 'event_total')
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🔥 Last Gameweek Top Performers**")
            recent_display = recent_top[['player_name', 'event_total', 'rank']].copy()
            recent_display.columns = ['Manager', 'Last GW Points', 'Current Rank']
            st.dataframe(recent_display, hide_index=True)
        
        with col2:
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
        
        # Show top and bottom performers
        st.markdown("**📉 Bottom 5 - Need to Catch Up**")
        bottom_5 = standings.nsmallest(5, 'total')[['player_name', 'total', 'rank']]
        bottom_5.columns = ['Manager', 'Total Points', 'Rank']
        st.dataframe(bottom_5, hide_index=True)
    
    with tab4:
        st.subheader("📅 Performance Projections")
        
        monthly_data = insights['monthly_performance']
        
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
        monthly_display = monthly_data[['player_name', 'total', 'avg_points_per_gw', 'projected_monthly']].copy()
        monthly_display.columns = ['Manager', 'Total Points', 'Avg/GW', 'Projected Monthly']
        st.dataframe(monthly_display, use_container_width=True, hide_index=True)
    
    with tab5:
        st.subheader("📋 Raw Data & Export")
        
        # League statistics
        st.markdown("**League Statistics:**")
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
            csv_transfers = transfer_data.to_csv(index=False)
            st.download_button(
                "Download Transfer Analysis CSV",
                csv_transfers,
                f"league_{st.session_state.league_id}_transfers.csv",
                "text/csv"
            )
        
        with col3:
            csv_monthly = monthly_data.to_csv(index=False)
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