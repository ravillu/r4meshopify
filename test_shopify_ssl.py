#!/usr/bin/env python3
"""
Test script to verify Shopify API SSL connection is working properly.
"""

import os
import sys
import json
import requests
import certifi
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_shopify_connection():
    """Test connection to Shopify API with proper SSL verification"""
    # Get credentials from environment
    shopify_token = os.environ.get("SHOPIFY_TOKEN")
    shopify_store_url = os.environ.get("SHOPIFY_STORE_URL")
    
    if not shopify_token or not shopify_store_url:
        print("ERROR: Missing required environment variables SHOPIFY_TOKEN or SHOPIFY_STORE_URL")
        sys.exit(1)
    
    # Create a session with proper certificate verification
    session = requests.Session()
    
    # Use certifi bundle for verification
    cert_path = certifi.where()
    session.verify = cert_path
    
    # Set headers for Shopify API
    session.headers.update({
        "X-Shopify-Access-Token": shopify_token,
        "Accept": "application/json",
        "Content-Type": "application/json"
    })
    
    # Print environment and configuration info
    print(f"Certifi version: {certifi.__version__}")
    print(f"Certifi bundle path: {cert_path}")
    print(f"Shopify store URL: {shopify_store_url}")
    print(f"Python version: {sys.version}")
    print(f"Requests verify: {session.verify}")
    
    # Test connection to Shopify API
    url = f"https://{shopify_store_url}/admin/api/2024-04/shop.json"
    
    try:
        print(f"\nTesting connection to Shopify API...")
        response = session.get(url, timeout=10)
        response.raise_for_status()
        
        shop_data = response.json().get("shop", {})
        print(f"\nSUCCESS! Connection to Shopify API established.")
        print(f"Shop name: {shop_data.get('name')}")
        print(f"Shop domain: {shop_data.get('domain')}")
        print(f"API response status: {response.status_code}")
        return True
        
    except requests.exceptions.SSLError as e:
        print("\nERROR: SSL Certificate verification failed:")
        print(f"  {e}")
        print("\nPossible solutions:")
        print("1. Run: pip install --upgrade certifi")
        print("2. Ensure you're not behind a proxy that's performing MITM SSL decryption")
        print("3. Check that your system time is correct")
        return False
        
    except requests.exceptions.RequestException as e:
        print(f"\nERROR: Failed to connect to Shopify API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Response: {e.response.text}")
        return False

if __name__ == "__main__":
    if test_shopify_connection():
        sys.exit(0)
    else:
        sys.exit(1) 