#!/bin/bash

echo "🔧 Setting up FPL Mini League Analyzer..."
echo "========================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

# Install required packages
echo "📦 Installing required packages..."
pip install pandas requests plotly streamlit numpy python-dotenv

echo ""
echo "✅ Setup complete! Here's how to use your mini league analyzer:"
echo ""
echo "🔍 METHOD 1: Command Line Analysis"
echo "   python analyze_mini_league.py [LEAGUE_ID]"
echo ""
echo "🌐 METHOD 2: Interactive Web App"  
echo "   streamlit run streamlit_mini_league.py"
echo ""
echo "📚 To find your league ID:"
echo "   1. Go to your FPL mini league page"
echo "   2. Look at the URL: fantasy.premierleague.com/leagues/XXXXXX/standings/c"
echo "   3. The XXXXXX number is your league ID"
echo ""
echo "🎯 Features you'll get:"
echo "   ✓ Transfer activity analysis"
echo "   ✓ Top movers identification"
echo "   ✓ Monthly performance projections"
echo "   ✓ League standings & statistics"
echo "   ✓ Interactive visualizations"
echo "   ✓ Data export capabilities"
echo ""
echo "Happy analyzing! ⚽"