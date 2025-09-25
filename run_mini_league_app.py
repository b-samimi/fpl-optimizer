#!/usr/bin/env python3
"""
FPL Mini League Analytics Launcher

Run this script to start the Streamlit web application for mini league analysis.
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Launch the mini league analytics web app."""
    
    # Get the directory containing this script
    script_dir = Path(__file__).parent.absolute()
    
    # Add src to Python path
    src_dir = script_dir / "src"
    sys.path.insert(0, str(src_dir))
    
    # Path to the Streamlit app
    app_path = script_dir / "src" / "fpl_optimizer" / "web" / "streamlit_app.py"
    
    if not app_path.exists():
        print(f"Error: Streamlit app not found at {app_path}")
        sys.exit(1)
    
    # Launch Streamlit
    try:
        print("🚀 Starting FPL Mini League Analytics...")
        print("📊 The web app will open in your browser automatically.")
        print("🛑 Press Ctrl+C to stop the server.")
        print("-" * 50)
        
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            str(app_path),
            "--server.address", "localhost",
            "--server.port", "8501",
            "--browser.gatherUsageStats", "false"
        ])
        
    except KeyboardInterrupt:
        print("\n👋 Mini League Analytics stopped.")
    except Exception as e:
        print(f"❌ Error launching app: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()