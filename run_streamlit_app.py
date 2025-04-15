#!/usr/bin/env python
"""
Wrapper script to run the Streamlit face matching app.
This ensures the app module is properly imported.
"""
import os
import sys

# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath("."))

# Now run the Streamlit app
if __name__ == "__main__":
    import streamlit.web.cli as stcli
    
    # Get the path to the app
    app_path = "app/ui/face_matching_app.py"
    
    # Run the app
    sys.argv = ["streamlit", "run", app_path]
    stcli.main() 