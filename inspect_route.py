#!/usr/bin/env python3
"""
Script to inspect a Route4Me route in detail.
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
    """Fetch a single route by ID"""
    print(f"Fetching route {route_id}...")
    
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
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return None

def main():
    """Main function"""
    # Check for required environment variables
    if not ROUTE4ME_API_KEY:
        print("ERROR: Missing ROUTE4ME_API_KEY environment variable")
        sys.exit(1)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Inspect a Route4Me route')
    parser.add_argument('route_id', help='Route ID to inspect')
    parser.add_argument('--output', help='Output file for the route JSON')
    args = parser.parse_args()
    
    # Fetch the route
    route = fetch_route(args.route_id)
    
    if not route:
        print("Failed to fetch route")
        sys.exit(1)
    
    # Print summary
    print("\nROUTE SUMMARY")
    print("=============")
    print(f"ID: {route.get('route_id', 'unknown')}")
    print(f"Name: {route.get('name', 'unnamed')}")
    print(f"Created: {route.get('created_timestamp', 'unknown')}")
    print(f"Status: {route.get('status', 'unknown')}")
    
    # Print addresses
    addresses = route.get("addresses", [])
    print(f"\nAddresses: {len(addresses)}")
    
    if addresses:
        for i, addr in enumerate(addresses):
            print(f"\nAddress {i+1}:")
            print(f"  Address: {addr.get('address', 'No address')}")
            print(f"  Is Depot: {addr.get('is_depot', False)}")
            
            # Print custom fields if any
            if "custom_fields" in addr and addr["custom_fields"]:
                print(f"  Custom Fields: {json.dumps(addr['custom_fields'], indent=2)}")
            
            # Print notes if any
            if "notes" in addr and addr["notes"]:
                print(f"  Notes: {addr['notes']}")
    else:
        print("No addresses found in the route!")
        
        # Check for route_destination_id
        if "route_destination_id" in route:
            print(f"\nRoute has route_destination_id: {route['route_destination_id']}")
            print("This suggests the route might be using a different endpoint for addresses.")
        
        # Check for optimization_problem_id
        if "optimization_problem_id" in route:
            print(f"\nRoute has optimization_problem_id: {route['optimization_problem_id']}")
            print("The addresses might be associated with the optimization problem instead.")
    
    # Print full route to file if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(route, f, indent=2)
        print(f"\nRoute saved to {args.output}")

if __name__ == "__main__":
    main() 