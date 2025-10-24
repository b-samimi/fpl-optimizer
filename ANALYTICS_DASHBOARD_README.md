# FPL Analytics Dashboard

A comprehensive web-based analytics dashboard for Fantasy Premier League data analysis, inspired by your Jupyter notebook analyses.

## Features

### 1. Team Reliability Analysis
- **Defensive Metrics**: xGA per 90, shots faced, clean sheet rates
- **Offensive Metrics**: xG per 90, shots per 90, goal efficiency
- Visual charts showing best/worst defensive and offensive teams
- Complete data tables with all metrics

### 2. Differential Players
- Low ownership (<15%) players with high potential
- Scoring system combining form, points per 90, and xGI
- Identify mini-league advantage opportunities

### 3. Emerging FPL Assets
- Players gaining prominence before ownership rises
- Form-based analysis (4.5+ form, regular minutes)
- Get ahead of price rises and template picks

### 4. Non-Penalty xG (NPxG) Analysis
- Open-play goal-scoring threat analysis
- Shooting efficiency metrics
- Identify clinical finishers and underperformers

### 5. Top Players by Position
- Best performers for GKP, DEF, MID, FWD
- Form, points, and expected stats combined
- Easy position-by-position comparison

## How to Run

### Start the Analytics Dashboard

```bash
# Activate virtual environment
source fpl-env/bin/activate

# Run the analytics app
python src/fpl_optimizer/web/analytics_app.py
```

The analytics dashboard will start on: **http://localhost:5002**

### Start the Transfer Review App (Separate)

```bash
# In another terminal
source fpl-env/bin/activate
python src/fpl_optimizer/web/transfer_app.py
```

Transfer app runs on: **http://localhost:5001**

## Usage

1. **Open Browser**: Navigate to `http://localhost:5002`

2. **Load Data**: Click "Load Analytics Data" on the Overview tab
   - This fetches all FPL data from the API
   - Auto-detects completed gameweeks
   - Loads all analysis modules

3. **Explore Tabs**:
   - **Overview**: Dashboard introduction and data loading
   - **Team Reliability**: Defensive and offensive team metrics
   - **Differentials**: Low-ownership high-potential players
   - **Emerging Players**: Rising stars to target early
   - **NPxG Analysis**: Open-play goal threat analysis
   - **Top Players**: Best performers by position

## Analysis Details

### Team Reliability Metrics

**Defensive Reliability**:
- xGA per 90: Expected goals against (lower = better defense)
- Shots Faced per 90: Defensive pressure indicator
- Clean Sheet Rate: Percentage of games with no goals conceded
- Defensive Efficiency: Goals conceded vs expected

**Offensive Reliability**:
- xG per 90: Expected goals (higher = better attack)
- Shots per 90: Shot volume indicator
- Goals per 90: Actual scoring rate
- Offensive Efficiency: Goals vs expected

### Differential Players Scoring

Combines multiple factors:
- Points per 90 (40%)
- xGI per 90 (30%)
- Form score (20%)
- Low ownership bonus (10%)

Criteria:
- <15% ownership
- 4+ points per 90
- 3+ form score
- Regular minutes

### Emerging Players Scoring

Identifies breakout candidates:
- 4.5+ form (35%)
- Points per 90 (25%)
- Minutes per GW (25%)
- Low ownership bonus (10%)
- xGI contribution (5%)

Criteria:
- <25% ownership
- 60+ minutes per GW average
- 20+ total points
- 3.5+ points per 90

### NPxG Analysis

Non-penalty expected goals metrics:
- **NPxG per 90**: Open-play goal threat
- **Shooting Efficiency**: Actual goals vs expected
- **Conversion Rate**: Percentage of xG converted

Excludes penalties to focus on sustainable open-play scoring.

## Data Source

All data is fetched live from the official FPL API:
- Updated automatically each gameweek
- Includes all player and team statistics
- xG, xA, and expected stats included

## Visualizations

Uses **Plotly.js** for interactive charts:
- Hover for detailed information
- Zoom and pan capabilities
- Responsive design
- Export chart images

## Tips for Using the Dashboard

### Before Each Gameweek

1. Load the latest data
2. Check Team Reliability for fixture analysis
3. Review Differentials for unique picks
4. Monitor Emerging Players for early moves

### For Wildcards

1. Analyze Team Reliability for next 5-8 GWs
2. Use NPxG Analysis for sustainable scorers
3. Check Differential& for template avoidance
4. Review Top Players by Position for premium picks

### For Transfers

1. Check player's team reliability metrics
2. Compare with Differentials for value picks
3. Use NPxG to identify goal threats
4. Monitor Emerging Players for early moves

## Technical Architecture

### Backend (Python/Flask)
- `analytics_app.py`: Flask server with REST API
- Endpoints for each analysis type
- Auto-gameweek detection
- Data caching and processing

### Frontend (HTML/JS/CSS)
- `analytics.html`: Main dashboard template
- `analytics.js`: Data fetching and visualization
- Plotly.js for interactive charts
- Tab-based navigation

### Shared Components
- FPL API client for data fetching
- Pandas for data processing
- NumPy for calculations

## API Endpoints

The dashboard provides these REST API endpoints:

- `GET /` - Main dashboard page
- `GET /api/init` - Initialize and load FPL data
- `GET /api/team_reliability` - Team defensive/offensive metrics
- `GET /api/differentials` - Low-ownership high-potential players
- `GET /api/emerging_players` - Rising FPL assets
- `GET /api/npxg_analysis` - Non-penalty xG analysis
- `GET /api/top_players` - Top performers by position

## Comparison with Jupyter Notebooks

The dashboard implements the same analyses from your notebooks:

| Notebook Analysis | Dashboard Feature |
|-------------------|-------------------|
| Team Reliability Analyzer | Team Reliability tab |
| Enhanced FPL Analyzer (Differentials) | Differentials tab |
| Emerging Players Analysis | Emerging Players tab |
| NPxG Shooting Analyzer | NPxG Analysis tab |
| Wildcard Optimizer | Top Players tab |

**Advantages of Web Dashboard**:
- No code execution needed
- Interactive visualizations
- Easy to share and access
- Auto-updates with latest data
- Mobile-friendly interface

## Troubleshooting

### Port Already in Use

If port 5002 is in use:
```bash
# Kill existing process
lsof -ti:5002 | xargs kill -9

# Or change port in analytics_app.py (last line)
app.run(debug=True, host='0.0.0.0', port=5003)
```

### Data Not Loading

- Check internet connection (needs FPL API access)
- Verify virtual environment is activated
- Check console for error messages
- Try refreshing the page

### Charts Not Displaying

- Ensure Plotly.js CDN is accessible
- Check browser console for JavaScript errors
- Try clearing browser cache

## Future Enhancements

Potential features to add:
- Fixture difficulty visualization
- Price change predictions
- Historical performance charts
- Head-to-head comparisons
- Export analysis reports
- Custom player watchlists
- Email alerts for recommendations

## File Structure

```
src/fpl_optimizer/web/
├── analytics_app.py              # Flask backend for analytics
├── transfer_app.py               # Flask backend for transfers
├── templates/
│   ├── analytics.html            # Analytics dashboard
│   └── transfer_review.html      # Transfer review page
└── static/
    ├── css/
    │   └── style.css             # Shared styles
    └── js/
        ├── analytics.js          # Analytics dashboard JS
        └── app.js                # Transfer review JS
```

## Credits

Based on FPL analysis methodologies from:
- Team reliability metrics (xGA, xG per 90)
- Differential player identification
- Emerging asset analysis
- NPxG shooting efficiency
- Value analysis frameworks

---

**Enjoy making data-driven FPL decisions!**

For questions or issues, check the console logs or review the Flask server output.
