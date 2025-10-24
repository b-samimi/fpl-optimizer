# FPL Transfer Review Web App - User Guide

## Overview
A locally-run web application for reviewing FPL player data, analyzing your team, and making informed transfer decisions. Built with Flask backend and modern JavaScript frontend.

## Features

### 1. Team Analysis
- Load your FPL team using your Manager ID
- View detailed stats for all your players
- Identify players with issues (injuries, poor form, suspensions)
- Get automatic transfer recommendations with priority levels

### 2. Transfer Recommendations
- Automatically identifies problematic players
- Shows issues: injuries, poor form, lack of minutes, suspensions
- Prioritizes recommendations (HIGH/MEDIUM/LOW)
- Find replacement suggestions with similar pricing

### 3. Player Search
- Search by player name or team
- Filter by position (GKP, DEF, MID, FWD)
- Sort by: Best Value, Total Points, Form, PPG, Ownership %
- View detailed player statistics

### 4. Top Players
- View top performers by category:
  - Best Value Score
  - Total Points
  - In Form
  - Points Per Game
- Filter by position
- Quick player comparisons

### 5. Player Details
- Complete player statistics
- Form analysis
- Goals, assists, clean sheets
- Injury/availability status
- Value score (comprehensive metric)

## How to Run

### Start the Application

```bash
# Activate virtual environment
source fpl-env/bin/activate

# Run the Flask app
python src/fpl_optimizer/web/transfer_app.py
```

The app will start on **http://localhost:5001**

### Access the Application

Open your web browser and go to:
```
http://localhost:5001
```

## How to Use

### 1. Load Your Team

1. Enter your FPL Manager ID in the input field
   - Find your ID in your FPL profile URL: `fantasy.premierleague.com/entry/YOUR_ID`
   - Example: If the URL is `fantasy.premierleague.com/entry/3692302`, your ID is `3692302`

2. Click "Load My Team"

3. The app will display:
   - Team statistics (value, points, form)
   - All your players grouped by position
   - Players with issues highlighted in red
   - Transfer recommendations

### 2. Review Transfer Recommendations

The app automatically analyzes your team and shows:

- **HIGH Priority**: Injured/suspended players, players with no minutes
- **MEDIUM Priority**: Poor form, fitness doubts
- **LOW Priority**: Minor concerns

For each recommendation:
- Click "Find Replacements" to see suitable alternatives
- Replacements are scored based on form, points, and value

### 3. Search for Players

Use the search section to find new players:

1. Enter player name or team name
2. Select position filter (optional)
3. Choose sorting criteria
4. Click "Search"

Click "View Details" on any player to see complete statistics.

### 4. Explore Top Players

1. Select category (Value Score, Total Points, Form, PPG)
2. Optionally filter by position
3. Click "Load Top Players"
4. View the top 10 players in that category

## Key Metrics Explained

### Value Score
Composite metric calculated as:
```
(Points Per Game × 10) + (Form × 5) - Price
```
Higher is better. Helps identify the best value players.

### Form
Average points in the last few gameweeks. Shows current performance trend.

### Points Per Game (PPG)
Total points divided by games played. Better than total points for comparing players who've played different numbers of games.

### Ownership %
Percentage of FPL managers who own this player. Useful for differential picks.

## Position Filters

Click position buttons to filter your team view:
- **All**: Show all players
- **Goalkeepers**: GKP only
- **Defenders**: DEF only
- **Midfielders**: MID only
- **Forwards**: FWD only

## Understanding Player Issues

### Injury Concern
- Shows chance of playing percentage
- Red badge for <50% chance
- Orange badge for 50-75% chance

### Poor Form
- Form score below 2.0
- Indicates recent poor performance

### No Minutes
- Player hasn't played any minutes
- May indicate loss of starting position

### Status Issues
- **i**: Injured
- **d**: Doubtful
- **s**: Suspended
- **u**: Unavailable
- **a**: Available (good!)

## Tips for Using the App

1. **Before Each Gameweek**:
   - Load your team
   - Review transfer recommendations
   - Check HIGH priority issues first

2. **Finding Replacements**:
   - Use the "Find Replacements" button for problematic players
   - Consider ownership % for differential options
   - Check upcoming fixtures (not shown in app yet, check FPL site)

3. **Exploring Options**:
   - Use "Top Players" by position to find top performers
   - Search for specific players or teams
   - Sort by "Best Value" to find bargains

4. **Making Transfers**:
   - Compare replacement statistics with your current player
   - Consider form over total points for in-form players
   - Balance value with consistency (PPG)

## Data Source

All data is fetched live from the official FPL API:
- Player statistics
- Team information
- Current gameweek data
- Injury/availability status

Data is automatically loaded when the app starts and can be refreshed by restarting the app.

## Troubleshooting

### App won't start
- Make sure virtual environment is activated
- Check Flask and flask-cors are installed: `pip install flask flask-cors`
- Verify port 5001 is not in use

### Team won't load
- Verify your Manager ID is correct
- Check internet connection (app needs to access FPL API)
- Make sure you have an active FPL team for the current season

### No data showing
- FPL API might be temporarily unavailable
- Try refreshing the page
- Restart the Flask app

## Future Enhancements

Potential features to add:
- Fixture difficulty visualization
- Price change predictions
- Historical performance charts
- Head-to-head player comparisons
- Save favorite players
- Export transfer shortlist

## Technical Details

- **Backend**: Flask (Python)
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Data Source**: Official FPL API
- **Charts**: Chart.js (currently included but not fully utilized)
- **Styling**: Custom CSS with FPL color scheme

## Files Structure

```
src/fpl_optimizer/web/
├── transfer_app.py          # Flask backend
├── templates/
│   └── transfer_review.html # HTML template
├── static/
│   ├── css/
│   │   └── style.css        # Styling
│   └── js/
│       └── app.js           # Frontend logic
```

## API Endpoints

The app provides these API endpoints:

- `POST /api/init` - Initialize FPL data
- `GET /api/team/<manager_id>` - Get team data
- `GET /api/replacements/<player_id>` - Get replacement suggestions
- `GET /api/players/search` - Search players
- `GET /api/player/<player_id>` - Get player details
- `GET /api/top_players` - Get top players by category

---

Enjoy making informed FPL transfer decisions!
