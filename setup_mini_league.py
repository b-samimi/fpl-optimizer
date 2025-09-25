#!/usr/bin/env python3
"""
Setup and test script for FPL Mini League Analytics

This script will:
1. Install required dependencies
2. Test the FPL API connection
3. Run a quick analysis of your main league
4. Provide next steps
"""

import subprocess
import sys
from pathlib import Path

def install_dependencies():
    """Install required dependencies."""
    print("📦 Installing dependencies...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "streamlit>=1.28.0", 
            "plotly>=5.17.0",
            "kaleido>=0.2.1"
        ])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing dependencies: {e}")
        return False

def test_fpl_connection():
    """Test FPL API connection and basic functionality."""
    print("\n🧪 Testing FPL API connection...")
    
    try:
        # Add src to path
        sys.path.insert(0, str(Path.cwd() / "src"))
        
        from fpl_optimizer.api.fpl_client import FPLClient
        from fpl_optimizer.analysis.mini_league_analyzer import MiniLeagueAnalyzer
        
        # Test basic API connection
        print("   • Connecting to FPL API...")
        fpl_client = FPLClient()
        players_df = fpl_client.get_players_df()
        print(f"   • Retrieved {len(players_df)} players ✅")
        
        # Test mini league analyzer
        print("   • Testing mini league analyzer...")
        analyzer = MiniLeagueAnalyzer(fpl_client)
        
        # Test with your main league
        main_league_id = 149533  # NBC Sports League
        print(f"   • Analyzing league {main_league_id}...")
        
        league_data = analyzer.get_league_detailed_data(main_league_id)
        print(f"   • Found {len(league_data['managers'])} managers in '{league_data['league_info']['name']}' ✅")
        
        # Quick performance analysis
        performance_df = analyzer.analyze_league_performance(league_data)
        leader = performance_df.iloc[0]
        
        print(f"   • League leader: {leader['Manager']} with {leader['Total_Points']} points ✅")
        
        print("\n🎉 All tests passed! Your mini league analytics is ready to use.")
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        print("💡 This might be due to FPL API rate limiting. Try again in a few minutes.")
        return False

def show_next_steps():
    """Show next steps for using the analytics."""
    print("\n🚀 Next Steps:")
    print("=" * 50)
    
    print("\n1️⃣  Launch Web App:")
    print("   python run_mini_league_app.py")
    print("   📊 Interactive dashboard will open in your browser")
    
    print("\n2️⃣  Use Jupyter Notebook:")
    print("   jupyter notebook notebooks/mini_league_analysis.ipynb")  
    print("   🔬 For detailed analysis and experimentation")
    
    print("\n3️⃣  Your League IDs:")
    print("   • NBC Sports League: 149533")
    print("   • @OfficialFPL on X: 31725") 
    print("   • Banterville Pop.6: 4")
    
    print("\n4️⃣  Key Features Available:")
    print("   🏆 League standings and rankings")
    print("   📈 Performance trend analysis")
    print("   🎯 Differential player identification")  
    print("   🔄 Transfer strategy insights")
    print("   ⚖️  Head-to-head manager comparison")
    
    print("\n5️⃣  Strategic Applications:")
    print("   • Find differentials to climb rankings")
    print("   • Analyze transfer efficiency of competitors")
    print("   • Identify must-have players you're missing")
    print("   • Track captain choice patterns")
    
    print("\n📚 Documentation:")
    print("   Read MINI_LEAGUE_README.md for detailed usage guide")

def main():
    """Main setup and test routine."""
    print("🏆 FPL Mini League Analytics Setup")
    print("=" * 40)
    
    # Install dependencies
    if not install_dependencies():
        print("❌ Setup failed during dependency installation")
        return False
    
    # Test connection and functionality
    if not test_fpl_connection():
        print("⚠️  Setup completed but testing failed")
        print("💡 You can still try running the applications manually")
        show_next_steps()
        return False
    
    # Show next steps
    show_next_steps()
    return True

if __name__ == "__main__":
    main()