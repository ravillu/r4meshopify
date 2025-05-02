#!/usr/bin/env python3
"""
Debug script to dump a complete Route4Me route to JSON
for detailed analysis of product data
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials
ROUTE4ME_API_KEY = os.environ.get("ROUTE4ME_API_KEY")

def fetch_route(route_id):
    """Fetch a specific route by ID"""
    url = "https://api.route4me.com/api.v4/route.php"
    params = {
        "api_key": ROUTE4ME_API_KEY,
        "route_id": route_id
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching route: {e}")
        return None

def save_route_to_json(route_id, filename=None):
    """Save a route to a JSON file for analysis"""
    # Get the route data
    route_data = fetch_route(route_id)
    
    if not route_data:
        print("Failed to fetch route data")
        return
    
    # Default filename if not provided
    if not filename:
        filename = f"route_{route_id}.json"
    
    # Save to file
    with open(filename, 'w') as f:
        json.dump(route_data, f, indent=2)
    
    print(f"Saved route data to {filename}")
    
    # Extract and save product fields
    product_data = {}
    address_count = 0
    address_with_products = 0
    
    for addr in route_data.get("addresses", []):
        if addr.get("is_depot", False):
            continue
            
        address_count += 1
        if "custom_fields" in addr and isinstance(addr["custom_fields"], dict):
            custom_fields = addr["custom_fields"]
            
            # Look for product fields
            product_keys = [k for k in custom_fields.keys() if k.startswith("product_")]
            if product_keys:
                address_with_products += 1
                
                # Group by product number
                for i in range(1, 10):
                    prefix = f"product_{i}_"
                    product_fields = {k[len(prefix):]: v for k, v in custom_fields.items() 
                                    if k.startswith(prefix)}
                    
                    if product_fields:
                        if i not in product_data:
                            product_data[i] = []
                        product_data[i].append(product_fields)
    
    # Save product data to separate file
    product_filename = f"products_{route_id}.json"
    with open(product_filename, 'w') as f:
        json.dump(product_data, f, indent=2)
    
    print(f"Saved product data to {product_filename}")
    print(f"Found {address_with_products}/{address_count} addresses with product data")
    
def main():
    """Main function"""
    # Check for required environment variables
    if not ROUTE4ME_API_KEY:
        print("ERROR: Missing ROUTE4ME_API_KEY environment variable")
        sys.exit(1)
    
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python debug_products.py ROUTE_ID [OUTPUT_FILE]")
        sys.exit(1)
    
    route_id = sys.argv[1]
    filename = sys.argv[2] if len(sys.argv) > 2 else None
    
    save_route_to_json(route_id, filename)

if __name__ == "__main__":
    main() 