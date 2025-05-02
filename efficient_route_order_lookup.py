#!/usr/bin/env python3
"""
Efficient Route-Order Lookup

This script:
1. Fetches routes for a specific date range
2. Extracts order references from those routes
3. Looks up only those specific orders from Shopify
4. Builds a mapping for the dashboard to use

This approach minimizes API calls and respects Shopify's rate limits.
"""

import os
import sys
import json
import time
import re
from datetime import datetime, timedelta
import requests
import certifi
import urllib3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials
ROUTE4ME_API_KEY = os.environ.get("ROUTE4ME_API_KEY")
SHOPIFY_TOKEN = os.environ.get("SHOPIFY_TOKEN")
SHOPIFY_STORE_URL = os.environ.get("SHOPIFY_STORE_URL")

# SSL verification setting (prefer secure connections in production)
VERIFY_SSL = os.environ.get('SHOPIFY_VERIFY_SSL', 'True').lower() not in ('false', '0', 'no')
if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print("WARNING: SSL verification disabled - NOT SECURE FOR PRODUCTION")

def create_route4me_session():
    """Create a requests session for Route4Me API"""
    session = requests.Session()
    return session

def create_shopify_session():
    """Create a requests session for Shopify API"""
    session = requests.Session()
    
    # Set headers for Shopify API
    session.headers.update({
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    })
    
    # Configure SSL verification
    if VERIFY_SSL:
        session.verify = certifi.where()
        print(f"Using certificate bundle: {certifi.where()}")
    else:
        session.verify = False
        print("SSL verification disabled")
    
    return session

def parse_date_arg(date_str):
    """Parse date string in YYYY-MM-DD format"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print(f"Invalid date format: {date_str}, expected YYYY-MM-DD")
        return None

def fetch_routes_for_daterange(session, api_key, start_date, end_date):
    """Fetch all routes for a specific date range"""
    print(f"Fetching Route4Me routes from {start_date} to {end_date}...")
    
    # Format dates for API
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # Step 1: Get all route IDs for the date range
    url = "https://api.route4me.com/api.v4/route.php"
    params = {
        "api_key": api_key,
        "start_date": start_str,
        "end_date": end_str,
        "limit": 100  # Fetch 100 routes at a time
    }
    
    route_ids = []
    offset = 0
    
    while True:
        try:
            # Update offset for pagination
            if offset > 0:
                params["offset"] = offset
            
            # Make API request
            response = session.get(url, params=params)
            response.raise_for_status()
            routes_batch = response.json()
            
            # Check response format
            if not isinstance(routes_batch, list):
                print(f"Unexpected response format from Route4Me API")
                break
                
            print(f"Fetched batch of {len(routes_batch)} route summaries")
            
            # Extract route IDs
            batch_ids = [route.get("route_id") for route in routes_batch if route.get("route_id")]
            route_ids.extend(batch_ids)
            
            # Check if we need to fetch more
            if len(routes_batch) < params["limit"]:
                break
                
            # Update offset for next batch
            offset += len(routes_batch)
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Route4Me routes: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            break
    
    print(f"Found {len(route_ids)} route IDs")
    
    # Step 2: Fetch detailed data for each route
    detailed_routes = []
    
    for i, route_id in enumerate(route_ids):
        print(f"Fetching detailed route {i+1}/{len(route_ids)}: {route_id}")
        
        url = "https://api.route4me.com/api.v4/route.php"
        params = {
            "api_key": api_key,
            "route_id": route_id
        }
        
        try:
            response = session.get(url, params=params)
            response.raise_for_status()
            route_detail = response.json()
            
            if isinstance(route_detail, dict) and "addresses" in route_detail:
                address_count = len(route_detail.get("addresses", []))
                print(f"  Route has {address_count} addresses")
                detailed_routes.append(route_detail)
            else:
                print(f"  Route has no addresses, skipping")
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching detailed route {route_id}: {e}")
    
    print(f"Successfully fetched {len(detailed_routes)} routes with addresses")
    return detailed_routes

def extract_order_references_from_routes(routes, debug=False):
    """Extract all order references from a list of routes"""
    all_references = set()
    routes_with_refs = {}
    
    print("Extracting order references from routes...")
    
    # Log some overall route info
    total_addresses = sum(len(route.get("addresses", [])) for route in routes)
    print(f"Routes contain {total_addresses} total addresses")
    
    for route in routes:
        route_id = route.get("route_id", "unknown")
        route_name = route.get("name", f"Route {route_id}")
        
        if debug:
            print(f"\nAnalyzing route: {route_name} (ID: {route_id})")
        
        # Skip routes without addresses
        if "addresses" not in route or not route["addresses"]:
            if debug:
                print(f"  No addresses found in route {route_id}")
            continue
            
        # Extract references from this route
        route_refs = set()
        
        # Log addresses in this route
        if debug:
            print(f"  Route contains {len(route['addresses'])} addresses")
            
        for i, address in enumerate(route["addresses"]):
            # Skip the depot/origin
            if address.get("is_depot"):
                if debug:
                    print(f"  Address {i+1}: Skipping depot")
                continue
            
            if debug:
                print(f"  Address {i+1} - {address.get('address', 'No address')}:")
                
            # Extract from custom_fields
            if "custom_fields" in address and isinstance(address["custom_fields"], dict):
                if debug:
                    print(f"    Custom fields: {json.dumps(address['custom_fields'])}")
                for field_name in ["order_id", "order_uuid", "shopify_order_id", "id", "orderId"]:
                    if field_name in address["custom_fields"] and address["custom_fields"][field_name]:
                        ref = str(address["custom_fields"][field_name])
                        route_refs.add(ref)
                        if debug:
                            print(f"    Found reference in custom_fields.{field_name}: {ref}")
                        # Also try without # prefix if present
                        if ref.startswith("#"):
                            route_refs.add(ref[1:])
            
            # Extract from direct address fields
            for field_name in ["order_id", "order_uuid", "shopify_order_id", "id", "orderId"]:
                if field_name in address and address[field_name]:
                    ref = str(address[field_name])
                    route_refs.add(ref)
                    if debug:
                        print(f"    Found reference in {field_name}: {ref}")
                    # Also try without # prefix if present
                    if ref.startswith("#"):
                        route_refs.add(ref[1:])
            
            # Check for any custom data
            if "order_custom_data" in address and address["order_custom_data"]:
                if debug:
                    print(f"    Order custom data: {json.dumps(address['order_custom_data'])}")
            
            # Extract from notes with regex patterns
            if "notes" in address and address["notes"]:
                notes = address["notes"]
                if isinstance(notes, str):
                    if debug:
                        print(f"    Notes: {notes}")
                    # Look for order ID patterns in notes
                    patterns = [
                        r'#(\d+)',
                        r'[Oo]rder[:\s#]*(\d+)',
                        r'[Oo]rder[:\s#]*([A-Za-z0-9]+)'
                    ]
                    for pattern in patterns:
                        matches = re.findall(pattern, notes)
                        for match in matches:
                            route_refs.add(match)
                            if debug:
                                print(f"    Found reference in notes using pattern {pattern}: {match}")
        
        # Update the overall collections
        if route_refs:
            all_references.update(route_refs)
            routes_with_refs[route_id] = route_refs
            if debug:
                print(f"  Found {len(route_refs)} references in route {route_id}: {sorted(route_refs)}")
        elif debug:
            print(f"  No order references found in route {route_id}")
    
    print(f"Found {len(all_references)} unique order references across {len(routes_with_refs)} routes")
    return all_references, routes_with_refs

def lookup_shopify_order_by_name(session, store_url, order_ref):
    """Look up a Shopify order by name/number"""
    # Try to handle both numeric-only references and those with # prefix
    query_ref = order_ref
    if order_ref.isdigit():
        # For numeric references, we might need to search by order_number
        query_ref = order_ref
    elif order_ref.startswith("#") and order_ref[1:].isdigit():
        # Handle #1234 format
        query_ref = order_ref
    
    url = f"https://{store_url}/admin/api/2024-04/orders.json"
    params = {
        "status": "any",
        "name": query_ref
    }
    
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        
        orders = response.json().get("orders", [])
        if orders:
            return orders[0]
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error looking up order {order_ref}: {e}")
        return None

def batch_lookup_shopify_orders(session, store_url, order_refs, batch_size=20):
    """Look up Shopify orders in batches to respect rate limits"""
    print(f"Looking up {len(order_refs)} Shopify orders in batches of {batch_size}...")
    
    # Process order references in groups
    order_mappings = {}
    remaining_refs = list(order_refs)
    
    # Initial progress info
    total_refs = len(remaining_refs)
    processed = 0
    found = 0
    
    # Process in batches
    while remaining_refs:
        # Take the next batch
        batch = remaining_refs[:batch_size]
        remaining_refs = remaining_refs[batch_size:]
        
        print(f"Processing batch of {len(batch)} orders ({processed}/{total_refs})...")
        
        # Process each reference
        for order_ref in batch:
            # Look up the order
            order = lookup_shopify_order_by_name(session, store_url, order_ref)
            
            # Update progress
            processed += 1
            
            # If found, add to mappings
            if order and "id" in order:
                shopify_id = str(order["id"])
                found += 1
                
                # Store mappings for the original reference
                order_mappings[order_ref] = shopify_id
                
                # Also store by order_number
                if "order_number" in order:
                    order_number = str(order["order_number"])
                    order_mappings[order_number] = shopify_id
                
                # Also store by name
                if "name" in order:
                    order_name = order["name"]
                    order_mappings[order_name] = shopify_id
                    
                    # And without # prefix
                    if order_name.startswith("#"):
                        order_mappings[order_name[1:]] = shopify_id
            
            # Print progress
            if processed % 10 == 0 or processed == total_refs:
                print(f"Processed {processed}/{total_refs} references, found {found} orders")
        
        # Add delay between batches to respect rate limits
        if remaining_refs:
            print("Pausing for 2 seconds to respect Shopify rate limits...")
            time.sleep(2)
    
    print(f"Successfully mapped {found} out of {total_refs} order references to Shopify IDs")
    return order_mappings

def save_mappings(mappings, routes_with_refs, filename="shopify_order_mappings.json"):
    """Save the mappings to a file"""
    # Create a more comprehensive mapping object
    output = {
        "order_to_id": mappings,
        "routes": {},
        "stats": {
            "total_routes": len(routes_with_refs),
            "total_references": sum(len(refs) for refs in routes_with_refs.values()),
            "mapped_references": sum(1 for route_id, refs in routes_with_refs.items() 
                                    for ref in refs if ref in mappings),
            "generated_at": datetime.now().isoformat()
        }
    }
    
    # Add route-specific information
    for route_id, refs in routes_with_refs.items():
        mapped_refs = {ref: mappings.get(ref) for ref in refs if ref in mappings}
        output["routes"][route_id] = {
            "references": list(refs),
            "mapped": mapped_refs,
            "success_rate": len(mapped_refs) / len(refs) if refs else 0
        }
    
    # Save to file
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"Saved mappings to {filename}")
    return output

def print_summary(stats):
    """Print a summary of the results"""
    print("\nSUMMARY")
    print("=======")
    print(f"Total routes with references: {stats['total_routes']}")
    print(f"Total order references found: {stats['total_references']}")
    
    mapped = stats['mapped_references']
    total = stats['total_references']
    success_rate = (mapped / total) * 100 if total > 0 else 0
    
    print(f"Successfully mapped references: {mapped} / {total} ({success_rate:.1f}%)")
    print(f"Generated at: {stats['generated_at']}")

def main():
    """Main function"""
    # Check for required environment variables
    if not all([ROUTE4ME_API_KEY, SHOPIFY_TOKEN, SHOPIFY_STORE_URL]):
        print("ERROR: Missing required environment variables")
        print("Make sure ROUTE4ME_API_KEY, SHOPIFY_TOKEN, and SHOPIFY_STORE_URL are set")
        sys.exit(1)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Efficient Route-Order Lookup')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    parser.add_argument('--days', type=int, default=7, help='Number of days to look back (default: 7)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    args = parser.parse_args()
    
    # Determine date range
    end_date = datetime.now()
    
    if args.end_date:
        parsed_end = parse_date_arg(args.end_date)
        if parsed_end:
            end_date = parsed_end
    
    if args.start_date:
        start_date = parse_date_arg(args.start_date)
        if not start_date:
            sys.exit(1)
    else:
        # Default to looking back args.days days
        start_date = end_date - timedelta(days=args.days)
    
    # Create API sessions
    r4m_session = create_route4me_session()
    shopify_session = create_shopify_session()
    
    # Execute the workflow
    # 1. Fetch routes for the date range
    routes = fetch_routes_for_daterange(r4m_session, ROUTE4ME_API_KEY, start_date, end_date)
    
    if not routes:
        print("No routes found for the specified date range")
        sys.exit(1)
    
    # 2. Extract order references
    order_refs, routes_with_refs = extract_order_references_from_routes(routes, debug=args.debug)
    
    if not order_refs:
        print("No order references found in the routes")
        sys.exit(1)
    
    # 3. Look up orders in Shopify
    mappings = batch_lookup_shopify_orders(shopify_session, SHOPIFY_STORE_URL, order_refs)
    
    # 4. Save and report results
    output = save_mappings(mappings, routes_with_refs)
    print_summary(output["stats"])
    
    # Print specific route success rates
    print("\nRoute success rates:")
    for route_id, route_data in output["routes"].items():
        success_rate = route_data["success_rate"] * 100
        refs_count = len(route_data["references"])
        mapped_count = len(route_data["mapped"])
        print(f"Route {route_id}: {mapped_count}/{refs_count} refs mapped ({success_rate:.1f}%)")

if __name__ == "__main__":
    main() 