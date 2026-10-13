import os
import sys

# Set serverless environment flag
os.environ['VERCEL'] = '1'

# Add the project root directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app

# Expose WSGI app for Vercel
handler = app
