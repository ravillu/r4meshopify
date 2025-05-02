#!/bin/bash
# Simple runner script for Route4Me - Shopify Dashboard

# Make scripts executable if they aren't already
chmod +x route4me_shopify_dashboard.py
chmod +x load_env.py

# Check if .env file exists, create from example if it doesn't
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "Creating .env file from .env.example..."
        cp .env.example .env
        echo "Please review and update the values in .env before running again."
        exit 1
    else
        echo "Error: No .env or .env.example file found."
        exit 1
    fi
fi

# Pass all arguments to the script
./route4me_shopify_dashboard.py "$@" 