
# Create a test file
import requests
import pandas as pd
import json
from datetime import datetime

print(" Testing FPL API Connection...")
print("=" * 50)

# Test 1: Basic API connection
try:
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    print(f"📡 Connecting to: {url}")
    
    response = requests.get(url, timeout=10)
    
    if response.status_code == 200:
        print("✅ FPL API connection successful!")
        
        # Parse the data
        data = response.json()
        
        # Show what data we got
        print(f"📊 Data keys available: {list(data.keys())}")
        
        # Test 2: Get player information
        players = data['elements']
        print(f"👥 Found {len(players)} players")
        
        # Test 3: Get team information  
        teams = data['teams']
        print(f"⚽ Found {len(teams)} teams")
        
        # Test 4: Show some sample player data
        print("\n🌟 Top 5 most expensive players:")
        players_df = pd.DataFrame(players)
        
        # Convert price (comes as integers, divide by 10 for actual price)
        players_df['price'] = players_df['now_cost'] / 10.0
        
        # Get top 5 most expensive players
        top_players = players_df.nlargest(5, 'now_cost')[['web_name', 'team', 'price', 'total_points']]
        
        for _, player in top_players.iterrows():
            print(f"  💰 {player['web_name']}: £{player['price']}m - {player['total_points']} points")
        
        # Test 5: Current gameweek info
        events = data['events']
        current_gw = next((event for event in events if event['is_current']), None)
        if current_gw:
            print(f"\n📅 Current Gameweek: {current_gw['id']} - {current_gw['name']}")
        
        print(f"\n🎯 Test completed successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    else:
        print(f"❌ Error: API returned status code {response.status_code}")
        
except requests.exceptions.RequestException as e:
    print(f"❌ Network error: {e}")
except json.JSONDecodeError as e:
    print(f"❌ JSON parsing error: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")

print("=" * 50)
print("🏁 FPL API test complete!")
