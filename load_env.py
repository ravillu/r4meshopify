#!/usr/bin/env python3
"""
Helper script to load environment variables from .env file
"""

import os
import sys


def load_env(env_file='.env'):
    """Load environment variables from a .env file"""
    if not os.path.exists(env_file):
        print(f"Error: {env_file} file not found.")
        print(f"Please copy .env.example to {env_file} and update the values.")
        return False
    
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Parse key-value pairs
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
    
    # Verify required variables
    required_vars = ['ROUTE4ME_API_KEY', 'SHOPIFY_STORE_URL', 'SHOPIFY_TOKEN']
    missing = [var for var in required_vars if not os.environ.get(var)]
    
    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        return False
    
    return True


if __name__ == "__main__":
    # This can be used as a standalone script to verify environment variables
    env_file = '.env'
    if len(sys.argv) > 1:
        env_file = sys.argv[1]
    
    if load_env(env_file):
        print("Environment variables loaded successfully!")
        print("\nAvailable variables:")
        for key in ['ROUTE4ME_API_KEY', 'SHOPIFY_STORE_URL', 'SHOPIFY_TOKEN', 'LOG_LEVEL']:
            value = os.environ.get(key, 'Not set')
            # Mask sensitive data
            if key in ['ROUTE4ME_API_KEY', 'SHOPIFY_TOKEN'] and value != 'Not set':
                value = value[:4] + '****' + value[-4:]
            print(f"  {key}: {value}")
    else:
        sys.exit(1) 