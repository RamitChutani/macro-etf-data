#!/usr/bin/env python3
"""
Auto-refresh dashboard viewer - watches the Excel file and displays it live.
Run this in a separate terminal while editing build_excel_dashboard_mvp.py.
"""

import subprocess
import time
import os
from pathlib import Path

OUTPUT_XLSX = "data/outputs/etf_gdp_dashboard_mvp.xlsx"

def main():
    print(f"🔍 Watching {OUTPUT_XLSX} for changes...")
    print("Press Ctrl+C to stop\n")
    
    last_modified = None
    
    while True:
        try:
            if os.path.exists(OUTPUT_XLSX):
                current_modified = os.path.getmtime(OUTPUT_XLSX)
                
                if last_modified is None:
                    print(f"✅ Found dashboard: {OUTPUT_XLSX}")
                    print(f"   Last modified: {time.ctime(current_modified)}")
                    last_modified = current_modified
                elif current_modified != last_modified:
                    print(f"\n🔄 Dashboard updated! (New: {time.ctime(current_modified)})")
                    print("   Re-run pipeline or refresh your Excel viewer to see changes.\n")
                    last_modified = current_modified
            
            time.sleep(2)
            
        except KeyboardInterrupt:
            print("\n👋 Stopping watcher.")
            break

if __name__ == "__main__":
    main()
