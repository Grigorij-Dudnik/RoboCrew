import sys
import os
from streamlit.web import cli as stcli

def main():
    curr_path = os.path.dirname(__file__)
    file_path = os.path.join(curr_path, "app.py")
    
    sys.argv = ["streamlit", "run", file_path]
    sys.exit(stcli.main())