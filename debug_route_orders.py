#!/usr/bin/env python3
"""
Debug Route Orders

This script examines a specific Route4Me route to identify why some orders 
might not have values associated with them.
"""

import os
import sys
import json
from datetime import datetime
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials
ROUTE4ME_API_KEY = os.environ.get("ROUTE4ME_API_KEY")

def fetch_route_detail(route_id):
    """Fetch a specific route by ID"""
    print(f"Fetching detailed data for route {route_id}...")
    
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

def analyze_route_addresses(route):
    """Analyze addresses in a route to check for order values"""
    if not route:
        print("No route data to analyze")
        return
    
    # Get basic route info
    route_id = route.get("route_id", "unknown")
    route_name = route.get("name", f"Route {route_id}")
    
    print(f"\nAnalyzing Route: {route_name}")
    print(f"Route ID: {route_id}")
    
    # Get addresses
    addresses = route.get("addresses", [])
    print(f"Total Addresses: {len(addresses)}")
    
    # Count non-depot addresses
    non_depot_addresses = [addr for addr in addresses if not addr.get("is_depot", False)]
    print(f"Delivery Addresses: {len(non_depot_addresses)}")
    
    # Track stats
    addresses_with_custom_fields = 0
    addresses_with_order_refs = 0
    addresses_with_price = 0
    missing_subtotal_price = 0
    missing_total_price = 0
    total_value = 0.0
    
    # Analyze each address
    print("\nADDRESS BREAKDOWN:")
    print("------------------")
    
    for i, addr in enumerate(non_depot_addresses):
        addr_line = addr.get("address", "No address")
        print(f"\nAddress {i+1}: {addr_line}")
        
        if "custom_fields" not in addr or not isinstance(addr["custom_fields"], dict):
            print("  ❌ Missing custom_fields")
            continue
            
        addresses_with_custom_fields += 1
        custom_fields = addr["custom_fields"]
        
        # Check for order reference fields
        order_refs = {}
        for field_name in ["order_id", "id", "name", "order_uuid"]:
            if field_name in custom_fields and custom_fields[field_name]:
                order_refs[field_name] = custom_fields[field_name]
        
        if order_refs:
            addresses_with_order_refs += 1
            print(f"  ✓ Found order references: {json.dumps(order_refs)}")
        else:
            print("  ❌ No order references found")
            continue
        
        # Check for price fields
        has_price = False
        
        if "subtotal_price" in custom_fields and custom_fields["subtotal_price"]:
            try:
                subtotal = float(custom_fields["subtotal_price"])
                print(f"  ✓ Subtotal Price: ${subtotal:.2f}")
                total_value += subtotal
                addresses_with_price += 1
                has_price = True
            except (ValueError, TypeError):
                print(f"  ❌ Invalid subtotal_price: {custom_fields['subtotal_price']}")
        else:
            missing_subtotal_price += 1
            
        if not has_price and "total_price" in custom_fields and custom_fields["total_price"]:
            try:
                total = float(custom_fields["total_price"])
                print(f"  ✓ Total Price: ${total:.2f}")
                total_value += total
                addresses_with_price += 1
                has_price = True
            except (ValueError, TypeError):
                print(f"  ❌ Invalid total_price: {custom_fields['total_price']}")
        elif not has_price:
            missing_total_price += 1
            
        if not has_price:
            # Print a few key fields to help debug
            print("  ❌ No price information found")
            key_fields = ["created_at", "financial_status", "tags", "email"]
            debug_info = {k: v for k, v in custom_fields.items() if k in key_fields and v}
            if debug_info:
                print(f"  ℹ️ Debug info: {json.dumps(debug_info)}")
    
    # Print summary
    print("\nSUMMARY:")
    print("--------")
    print(f"Total delivery addresses: {len(non_depot_addresses)}")
    print(f"Addresses with custom fields: {addresses_with_custom_fields}")
    print(f"Addresses with order references: {addresses_with_order_refs}")
    print(f"Addresses with price information: {addresses_with_price}")
    print(f"Addresses missing subtotal_price: {missing_subtotal_price}")
    print(f"Addresses missing total_price: {missing_total_price}")
    print(f"Total route value: ${total_value:.2f}")
    
    if addresses_with_order_refs > 0:
        success_rate = (addresses_with_price / addresses_with_order_refs) * 100
        print(f"Success rate: {success_rate:.1f}%")
    
    return total_value

def main():
    """Main function"""
    # Check for required environment variables
    if not ROUTE4ME_API_KEY:
        print("ERROR: Missing ROUTE4ME_API_KEY environment variable")
        sys.exit(1)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Route Order Analysis')
    parser.add_argument('route_id', help='Route ID to analyze')
    parser.add_argument('--output', help='Output file for detailed results')
    args = parser.parse_args()
    
    # Fetch and analyze route
    route = fetch_route_detail(args.route_id)
    
    if not route:
        print("Failed to fetch route data")
        sys.exit(1)
    
    # Analyze addresses
    total_value = analyze_route_addresses(route)
    
    # Save full route data if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(route, f, indent=2)
        print(f"\nSaved full route data to {args.output}")

if __name__ == "__main__":
    main() 