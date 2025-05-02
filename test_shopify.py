#!/usr/bin/env python3
"""
Test script for Shopify API connectivity
"""

import os
import sys
import requests
import urllib3
import json
from dotenv import load_dotenv

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables
load_dotenv()

def test_shopify_connection():
    """Test connection to Shopify API and display results"""
    
    # Get credentials
    token = os.environ.get("SHOPIFY_TOKEN", "")
    store_url = os.environ.get("SHOPIFY_STORE_URL", "")
    
    if not token or not store_url:
        print("ERROR: Missing SHOPIFY_TOKEN or SHOPIFY_STORE_URL environment variables")
        return False
    
    print(f"Testing connection to {store_url} with token {token[:4]}...{token[-4:]}")
    
    # Create session
    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": token,
        "Accept": "application/json"
    })
    
    # Test with verification
    url = f"https://{store_url}/admin/api/2024-04/shop.json"
    
    print("\n1. Testing with SSL verification enabled:")
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"SUCCESS! Connected to {data['shop']['name']}")
        print(f"Response: {json.dumps(data, indent=2)[:200]}...")
        return True
    except Exception as e:
        print(f"FAILED with error: {e}")
    
    # Test without verification
    print("\n2. Testing with SSL verification disabled:")
    try:
        response = session.get(url, verify=False, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"SUCCESS! Connected to {data['shop']['name']}")
        print(f"Response: {json.dumps(data, indent=2)[:200]}...")
        return True
    except Exception as e:
        print(f"FAILED with error: {e}")
    
    # Test specific order if request succeeds
    print("\n3. Testing specific order retrieval (with SSL verification disabled):")
    order_id = "82899055"  # Using one of the order IDs from your logs
    url = f"https://{store_url}/admin/api/2024-04/orders/{order_id}.json"
    
    try:
        response = session.get(url, verify=False, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"SUCCESS! Retrieved order {order_id}")
        print(f"Order total: ${data['order']['total_price']}")
        return True
    except Exception as e:
        print(f"FAILED with error: {e}")
    
    return False

if __name__ == "__main__":
    print("Shopify API Connection Test")
    print("==========================")
    
    print("\nEnvironment:")
    print(f"PYTHONHTTPSVERIFY: {os.environ.get('PYTHONHTTPSVERIFY', 'Not set')}")
    print(f"REQUESTS_CA_BUNDLE: {os.environ.get('REQUESTS_CA_BUNDLE', 'Not set')}")
    
    # Override for this test
    os.environ['PYTHONHTTPSVERIFY'] = '0'
    print("Setting PYTHONHTTPSVERIFY=0 for this test")
    
    # Run the test
    success = test_shopify_connection()
    
    if success:
        print("\nTest PASSED!")
        sys.exit(0)
    else:
        print("\nTest FAILED. Please check your credentials and connection.")
        sys.exit(1) 