import os
import sys

# Ensure Vercel serverless environment flag
os.environ['VERCEL'] = '1'

# Add the parking_app directory to sys.path so modules and models can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
app_dir = os.path.join(root_dir, '24f1002035', 'parking_app_24F1002035')

if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from app import app

# Expose for Vercel WSGI runner
app = app
