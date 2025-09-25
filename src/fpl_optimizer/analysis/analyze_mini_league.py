#!/usr/bin/env python3
"""
Quick Mini League Analysis Script

Usage: python analyze_mini_league.py [LEAGUE_ID]

This script will analyze your FPL mini league and provide:
- Transfer activity analysis
- Top movers identification  
- Monthly performance metrics
- Comprehensive league insights
"""

import sys
import os

# Add the project root to the path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.fpl_optimizer.analysis.mini_league_analyzer import quick_league_analysis
import pandas as pd

def main():
    # You can either pass league_id as argument or set it here
    if len(sys.argv) > 1:
        league_id = int(sys.argv[1])
    else:
        # From your screenshot, I can see you're in several leagues
        # You'll need to replace this with your actual mini league ID
        league_id = input("Enter your mini league ID: ")
        league_id = int(league_id)
    
    print(f"\n🔍 Analyzing Mini League {league_id}...")
    print("=" * 50)
    
    # Run the analysis
    result = quick_league_analysis(league_id)
    
    if not result['success']:
        print(f"❌ Error: {result['error']}")
        return
    
    insights = result['insights']
    
    # Display key insights
    print("\n📊 LEAGUE OVERVIEW")
    print("-" * 20)
    print(insights['league_stats'].to_string(index=False))
    
    print("\n🔄 TOP TRANSFER ACTIVITY")
    print("-" * 25)
    print(insights['transfer_activity'].head(10).to_string(index=False))
    
    print("\n📈 TOP RECENT MOVERS")
    print("-" * 20)
    if 'last_gw' in insights['top_movers']:
        print(insights['top_movers']['last_gw'].head().to_string(index=False))
    
    print("\n📅 MONTHLY PERFORMANCE PROJECTIONS")
    print("-" * 35)
    monthly_top = insights['monthly_performance'].nlargest(10, 'projected_monthly')
    print(monthly_top.to_string(index=False))
    
    print("\n📋 CURRENT STANDINGS (Top 10)")
    print("-" * 30)
    standings_display = insights['standings'][['rank', 'player_name', 'total', 'event_total']].head(10)
    print(standings_display.to_string(index=False))
    
    # Full report
    print("\n" + "="*60)
    print("📄 DETAILED REPORT")
    print("="*60)
    print(result['report'])
    
    # Save to file
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M")
    filename = f"mini_league_{league_id}_analysis_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write(result['report'])
        f.write("\n\n" + "="*60 + "\n")
        f.write("RAW DATA TABLES\n")
        f.write("="*60 + "\n\n")
        
        f.write("STANDINGS:\n")
        f.write(insights['standings'].to_string())
        f.write("\n\nTRANSFER ACTIVITY:\n")
        f.write(insights['transfer_activity'].to_string())
        f.write("\n\nMONTHLY PERFORMANCE:\n")
        f.write(insights['monthly_performance'].to_string())
    
    print(f"\n💾 Full analysis saved to: {filename}")
    
    # Ask if user wants to see visualizations
    show_viz = input("\nWould you like to generate visualizations? (y/n): ")
    if show_viz.lower() == 'y':
        try:
            plots = result['analyzer'].create_league_dashboard()
            
            # Save plots as HTML
            for plot_name, fig in plots.items():
                html_file = f"mini_league_{league_id}_{plot_name}_{timestamp}.html"
                fig.write_html(html_file)
                print(f"📊 Saved {plot_name} to {html_file}")
            
            print("\n✅ All visualizations saved as HTML files!")
            
        except Exception as e:
            print(f"❌ Error generating visualizations: {e}")
    
    print("\n🎯 QUICK INSIGHTS:")
    print("- Check transfer efficiency to see who's making smart moves")
    print("- Look at recent movers to identify momentum shifts") 
    print("- Use monthly projections to spot consistent performers")
    print("- Monitor the points gap for comeback opportunities")

if __name__ == "__main__":
    main()