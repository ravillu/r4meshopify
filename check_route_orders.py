#!/usr/bin/env python3
"""
Script to check if Route4Me order references match with our Shopify ID mappings.
"""

import os
import sys
import json
import time
import requests
import urllib3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials
ROUTE4ME_API_KEY = os.environ.get("ROUTE4ME_API_KEY")
SHOPIFY_TOKEN = os.environ.get("SHOPIFY_TOKEN")
SHOPIFY_STORE_URL = os.environ.get("SHOPIFY_STORE_URL")

# Disable SSL verification warning if needed
VERIFY_SSL = os.environ.get('SHOPIFY_VERIFY_SSL', 'True').lower() not in ('false', '0', 'no')
if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print("WARNING: SSL verification disabled - NOT SECURE FOR PRODUCTION")

def create_session():
    """Create a requests session with retry capability"""
    session = requests.Session()
    session.verify = VERIFY_SSL
    return session

def fetch_recent_routes(session, api_key, days=3, limit=10):
    """Fetch recent routes from Route4Me"""
    print(f"Fetching {limit} most recent Route4Me routes...")
    
    # Calculate date range
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    url = "https://api.route4me.com/api.v4/route.php"
    params = {
        "api_key": api_key,
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit
    }
    
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        routes = response.json()
        
        if isinstance(routes, list):
            print(f"Successfully fetched {len(routes)} routes")
            return routes
        else:
            print(f"Unexpected response format from Route4Me API")
            return []
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Route4Me routes: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return []

def extract_order_ids_from_route(route):
    """Extract order references from a route"""
    import re
    
    order_ids = set()
    
    # Check if addresses exist in the route
    if "addresses" not in route or not route["addresses"]:
        print(f"No addresses found in route {route.get('route_id', 'unknown')}")
        return order_ids
    
    for address in route["addresses"]:
        # Check various fields that might contain order references
        fields_to_check = []
        
        # Custom fields
        if "custom_fields" in address and isinstance(address["custom_fields"], dict):
            for field_name, value in address["custom_fields"].items():
                if value:
                    fields_to_check.append((f"custom_fields.{field_name}", value))
        
        # Direct address fields
        for field_name in ["order_id", "order_uuid", "shopify_order_id", "id", "orderId"]:
            if field_name in address and address[field_name]:
                fields_to_check.append((field_name, address[field_name]))
        
        # Order inventory
        if "order_inventory" in address and isinstance(address["order_inventory"], dict):
            for field_name, value in address["order_inventory"].items():
                if value:
                    fields_to_check.append((f"order_inventory.{field_name}", value))
        
        # Order custom data
        if "order_custom_data" in address and isinstance(address["order_custom_data"], dict):
            for field_name, value in address["order_custom_data"].items():
                if value:
                    fields_to_check.append((f"order_custom_data.{field_name}", value))
        
        # Notes
        if "notes" in address and address["notes"]:
            notes = address["notes"]
            if isinstance(notes, str):
                fields_to_check.append(("notes", notes))
                
                # Extract potential order references from notes
                patterns = [
                    r'#(\d+)',
                    r'[Oo]rder[:\s#]*(\d+)',
                    r'[Oo]rder[:\s#]*([A-Za-z0-9]+)'
                ]
                for pattern in patterns:
                    matches = re.findall(pattern, notes)
                    for match in matches:
                        fields_to_check.append((f"notes[{pattern}]", match))
        
        # Add all potential order references to the set
        for field_name, value in fields_to_check:
            if value:
                order_ids.add((field_name, str(value)))
    
    return order_ids

def load_shopify_mappings(filename="shopify_order_mappings.json"):
    """Load Shopify order mappings from file"""
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading Shopify mappings: {e}")
        return {}

def main():
    """Main function"""
    # Check credentials
    if not all([ROUTE4ME_API_KEY, SHOPIFY_TOKEN, SHOPIFY_STORE_URL]):
        print("ERROR: Missing required environment variables")
        sys.exit(1)
    
    # Create session
    session = create_session()
    
    # Load Shopify mappings
    shopify_mappings = load_shopify_mappings()
    print(f"Loaded {len(shopify_mappings)} Shopify order mappings")
    
    # Fetch recent routes
    routes = fetch_recent_routes(session, ROUTE4ME_API_KEY, days=7, limit=5)
    
    # Track statistics
    total_refs = 0
    matched_refs = 0
    
    # Process each route
    print("\nChecking routes for matching order references...")
    for i, route in enumerate(routes):
        route_id = route.get("route_id", "unknown")
        route_name = route.get("name", f"Route {route_id}")
        
        print(f"\nRoute {i+1}: {route_name} (ID: {route_id})")
        
        # Extract order references
        order_refs = extract_order_ids_from_route(route)
        if not order_refs:
            print("  No order references found")
            continue
        
        print(f"  Found {len(order_refs)} potential order references")
        total_refs += len(order_refs)
        
        # Check against Shopify mappings
        matches = []
        for field, ref in order_refs:
            # Check the reference itself
            if ref in shopify_mappings:
                matches.append((field, ref, shopify_mappings[ref]))
                continue
                
            # Try with a # prefix
            if ref.isdigit() and f"#{ref}" in shopify_mappings:
                matches.append((field, ref, shopify_mappings[f"#{ref}"]))
                continue
        
        matched_refs += len(matches)
        
        # Print matches
        if matches:
            print(f"  Found {len(matches)} matches with Shopify orders:")
            for field, ref, shopify_id in matches:
                print(f"    - {field}: {ref} → Shopify ID: {shopify_id}")
        else:
            print("  No matches found with Shopify orders")
    
    # Print summary
    print("\nSummary:")
    print(f"  Total routes checked: {len(routes)}")
    print(f"  Total order references found: {total_refs}")
    print(f"  Matches with Shopify orders: {matched_refs}")
    if total_refs > 0:
        match_rate = (matched_refs / total_refs) * 100
        print(f"  Match rate: {match_rate:.1f}%")
    
if __name__ == "__main__":
    main() 