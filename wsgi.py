#!/usr/bin/python3
"""
WSGI Entry Point for Web Content Scraper
This file is used by Gunicorn to serve the Flask application in production.
"""

import sys
import os

# Add the project directory to the Python path
sys.path.insert(0, '/var/www/web-scraper/')

from app import app as application

if __name__ == "__main__":
    application.run()
