#!/usr/bin/env python3
"""
Script to fetch all Shopify orders and create a mapping from order numbers to internal Shopify IDs.
This is useful for debugging the Route4Me-Shopify integration.
"""

import os
import sys
import json
import requests
import certifi
import urllib3
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials from environment
SHOPIFY_TOKEN = os.environ.get("SHOPIFY_TOKEN")
SHOPIFY_STORE_URL = os.environ.get("SHOPIFY_STORE_URL")

# Disable SSL verification warning if needed
VERIFY_SSL = os.environ.get('SHOPIFY_VERIFY_SSL', 'True').lower() not in ('false', '0', 'no')
if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print("WARNING: SSL verification disabled - NOT SECURE FOR PRODUCTION")

def fetch_shopify_orders(days_back=30, batch_size=250, max_pages=5):
    """Fetch all Shopify orders from the specified timeframe
    
    Args:
        days_back: Number of days to look back for orders
        batch_size: Number of orders to fetch per API call
        max_pages: Maximum number of pages to fetch to avoid excessive API calls
    """
    print(f"Fetching Shopify orders from the last {days_back} days (max {max_pages} pages)...")
    
    # Create a session
    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    })
    
    # Set SSL verification
    if VERIFY_SSL:
        session.verify = certifi.where()
        print(f"Using certificate bundle: {certifi.where()}")
    else:
        session.verify = False
        print("SSL verification disabled")
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    start_iso = start_date.isoformat()
    end_iso = end_date.isoformat()
    
    # Fetch orders
    all_orders = []
    page_info = None
    page_count = 0
    
    # First request with date filters
    url = f"https://{SHOPIFY_STORE_URL}/admin/api/2024-04/orders.json"
    params = {
        "status": "any",
        "limit": batch_size,
        "created_at_min": start_iso,
        "fields": "id,order_number,name,total_price,created_at"
    }
    
    while True:
        # Check if we've reached the maximum number of pages
        if max_pages and page_count >= max_pages:
            print(f"Reached maximum number of pages ({max_pages})")
            break
            
        try:
            # For subsequent requests, only use page_info
            if page_info:
                params = {
                    "limit": batch_size,
                    "page_info": page_info
                }
            
            # Make request
            page_count += 1
            print(f"Fetching orders batch {page_count}/{max_pages or '∞'} (page_info: {page_info is not None})...")
            response = session.get(url, params=params)
            response.raise_for_status()
            
            # Parse response
            orders_batch = response.json().get("orders", [])
            all_orders.extend(orders_batch)
            print(f"Fetched {len(orders_batch)} orders in this batch")
            
            # Check for pagination
            link_header = response.headers.get("Link", "")
            if "rel=\"next\"" in link_header and len(orders_batch) >= 1:
                import re
                page_info_match = re.search(r"page_info=([^&>]+)", link_header)
                if page_info_match:
                    page_info = page_info_match.group(1)
                    continue
            
            # No more pages
            break
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching orders: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            break
    
    print(f"Successfully fetched {len(all_orders)} orders in total")
    return all_orders

def build_order_mapping(orders):
    """Build mapping from order numbers and names to internal Shopify IDs"""
    mappings = {}
    
    for order in orders:
        # Map order_number to ID
        if "order_number" in order and "id" in order:
            order_number = str(order["order_number"])
            shopify_id = str(order["id"])
            mappings[order_number] = shopify_id
            
        # Map name (like "#1001") to ID
        if "name" in order and "id" in order:
            name = order["name"]
            shopify_id = str(order["id"])
            mappings[name] = shopify_id
            
            # Also map without the # prefix
            if name.startswith("#"):
                mappings[name[1:]] = shopify_id
    
    return mappings

def main():
    """Main function"""
    # Check credentials
    if not SHOPIFY_TOKEN or not SHOPIFY_STORE_URL:
        print("ERROR: Missing SHOPIFY_TOKEN or SHOPIFY_STORE_URL environment variables")
        sys.exit(1)
    
    # Fetch orders from the last 30 days, with a maximum of 5 pages
    orders = fetch_shopify_orders(days_back=30, max_pages=5)
    
    # Build mappings
    mappings = build_order_mapping(orders)
    
    # Print summary
    print(f"\nFound {len(mappings)} unique order number/name to ID mappings")
    
    # Save mappings to file
    with open("shopify_order_mappings.json", "w") as f:
        json.dump(mappings, f, indent=2)
    
    print(f"Saved mappings to shopify_order_mappings.json")
    
    # Print a sample of mappings
    print("\nSample mappings (order_number/name → Shopify ID):")
    sample_count = min(5, len(mappings))
    for i, (key, value) in enumerate(list(mappings.items())[:sample_count]):
        print(f"  {key} → {value}")

if __name__ == "__main__":
    main() 