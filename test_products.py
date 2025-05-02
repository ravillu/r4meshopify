#!/usr/bin/env python3
"""
Test script to check for product fields in Route4Me API responses
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key
ROUTE4ME_API_KEY = os.environ.get("ROUTE4ME_API_KEY")
if not ROUTE4ME_API_KEY:
    print("ERROR: Missing ROUTE4ME_API_KEY environment variable")
    sys.exit(1)

def create_session():
    """Create a requests session"""
    return requests.Session()

def fetch_routes(session, days=7, limit=10):
    """Fetch routes from the last N days"""
    print(f"Fetching up to {limit} routes from the last {days} days...")
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Format dates for API
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    url = "https://api.route4me.com/api.v4/route.php"
    params = {
        "api_key": ROUTE4ME_API_KEY,
        "start_date": start_str,
        "end_date": end_str,
        "limit": limit
    }
    
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        routes = response.json()
        
        if isinstance(routes, list):
            print(f"Successfully fetched {len(routes)} routes")
            return [r.get("route_id") for r in routes if r.get("route_id")]
        else:
            print("Unexpected response format")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching routes: {e}")
        return []

def examine_route(route_id):
    """Examine a route for product fields in custom_fields"""
    session = create_session()
    url = "https://api.route4me.com/api.v4/route.php"
    
    # Get detailed route info
    params = {
        "api_key": ROUTE4ME_API_KEY,
        "route_id": route_id
    }
    
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        route = response.json()
        
        # Extract custom fields from non-depot addresses
        all_product_fields = set()
        address_count = 0
        product_count = 0
        
        for addr in route.get("addresses", []):
            if addr.get("is_depot", False):
                continue
                
            address_count += 1
            if "custom_fields" in addr and isinstance(addr["custom_fields"], dict):
                custom_fields = addr["custom_fields"]
                
                # Look for product fields
                product_keys = [k for k in custom_fields.keys() if k.startswith("product_")]
                if product_keys:
                    product_count += 1
                    all_product_fields.update(product_keys)
        
        # Return summary
        route_name = route.get("name", route_id)
        return {
            "route_id": route_id,
            "route_name": route_name,
            "address_count": address_count,
            "product_address_count": product_count,
            "product_field_count": len(all_product_fields),
            "has_products": product_count > 0
        }
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching route details for {route_id}: {e}")
        return {
            "route_id": route_id,
            "error": str(e),
            "has_products": False
        }

def analyze_multiple_routes():
    """Analyze multiple routes for product data"""
    session = create_session()
    
    # Get route IDs
    route_ids = fetch_routes(session, days=30, limit=20)
    
    if not route_ids:
        print("No routes found to analyze")
        sys.exit(1)
    
    # Check each route
    print(f"\nAnalyzing {len(route_ids)} routes for product data...\n")
    
    routes_with_products = 0
    addresses_with_products = 0
    total_addresses = 0
    
    results = []
    
    for i, route_id in enumerate(route_ids):
        print(f"Checking route {i+1}/{len(route_ids)}: {route_id}")
        route_data = examine_route(route_id)
        results.append(route_data)
        
        if route_data.get("has_products"):
            routes_with_products += 1
            addresses_with_products += route_data.get("product_address_count", 0)
        
        total_addresses += route_data.get("address_count", 0)
    
    # Print summary
    print("\n" + "="*50)
    print("SUMMARY OF PRODUCT DATA IN ROUTES")
    print("="*50)
    print(f"Total routes analyzed: {len(route_ids)}")
    print(f"Routes with product data: {routes_with_products} ({routes_with_products/len(route_ids)*100:.1f}%)")
    print(f"Total addresses: {total_addresses}")
    print(f"Addresses with product data: {addresses_with_products} ({addresses_with_products/total_addresses*100 if total_addresses else 0:.1f}%)")
    
    # Print individual route results
    print("\nDETAILED RESULTS:")
    print("-"*50)
    for route in results:
        status = "✓" if route.get("has_products") else "✗"
        name = route.get("route_name", route.get("route_id"))
        if route.get("has_products"):
            print(f"{status} {name}: {route.get('product_address_count')}/{route.get('address_count')} addresses have products")
        else:
            if "error" in route:
                print(f"{status} {route.get('route_id')}: Error - {route.get('error')}")
            else:
                print(f"{status} {name}: No products (checked {route.get('address_count')} addresses)")

def examine_single_route(route_id=None):
    """Examine a single route in detail"""
    session = create_session()
    url = "https://api.route4me.com/api.v4/route.php"
    
    # Get a route ID if not provided
    if not route_id:
        print("Fetching a sample route...")
        params = {
            "api_key": ROUTE4ME_API_KEY,
            "limit": 1  # Just need one route
        }
        
        try:
            response = session.get(url, params=params)
            response.raise_for_status()
            routes = response.json()
            
            if isinstance(routes, list) and len(routes) > 0:
                route_id = routes[0].get("route_id")
                print(f"Using route ID: {route_id}")
            else:
                print("No routes found!")
                sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching routes: {e}")
            sys.exit(1)
    
    # Get detailed route info
    print(f"Fetching detailed info for route {route_id}...")
    params = {
        "api_key": ROUTE4ME_API_KEY,
        "route_id": route_id
    }
    
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        route = response.json()
        
        # Extract custom fields from non-depot addresses
        all_custom_fields = []
        all_product_fields = set()
        address_count = 0
        product_count = 0
        
        for addr in route.get("addresses", []):
            if addr.get("is_depot", False):
                continue
                
            address_count += 1
            if "custom_fields" in addr and isinstance(addr["custom_fields"], dict):
                custom_fields = addr["custom_fields"]
                all_custom_fields.append(custom_fields)
                
                # Look for product fields
                product_keys = [k for k in custom_fields.keys() if k.startswith("product_")]
                if product_keys:
                    product_count += 1
                    print(f"\nFound {len(product_keys)} product fields in address {address_count}:")
                    
                    # Print ALL custom fields for this address to see context
                    print(f"\nALL CUSTOM FIELDS for address {address_count}:")
                    for key, value in custom_fields.items():
                        print(f"  {key}: {value}")
                    
                    print(f"\nPRODUCT FIELDS ONLY for address {address_count}:")
                    for key in sorted(product_keys):
                        all_product_fields.add(key)
                        value = custom_fields[key]
                        print(f"  {key}: {value}")
        
        # Print summary
        print("\nSUMMARY:")
        print(f"Route has {address_count} non-depot addresses")
        print(f"Found {product_count} addresses with product fields")
        
        if all_product_fields:
            print("\nAll product field types found:")
            for field in sorted(all_product_fields):
                print(f"  {field}")
                
            # Print examples of addresses with products
            print("\nDetailed product examples:")
            for i, custom_fields in enumerate(all_custom_fields):
                product_keys = [k for k in custom_fields.keys() if k.startswith("product_")]
                if product_keys:
                    print(f"\nAddress {i+1} product data:")
                    products = {}
                    
                    # Group by product
                    for i in range(1, 10):
                        name_key = f"product_{i}_name"
                        price_key = f"product_{i}_price"
                        quantity_key = f"product_{i}_quantity"
                        
                        if name_key in custom_fields or price_key in custom_fields:
                            product = {
                                "name": custom_fields.get(name_key, f"Product {i}"),
                                "price": custom_fields.get(price_key, "0"),
                                "quantity": custom_fields.get(quantity_key, "1")
                            }
                            
                            try:
                                price = float(product["price"])
                                quantity = int(product["quantity"])
                                product["total"] = price * quantity
                            except (ValueError, TypeError):
                                product["total"] = "error"
                                
                            products[i] = product
                    
                    # Output product info
                    for i, product in products.items():
                        print(f"  Product {i}:")
                        print(f"    Name: {product['name']}")
                        print(f"    Price: ${product['price']}")
                        print(f"    Quantity: {product['quantity']}")
                        if product["total"] != "error":
                            print(f"    Total: ${product['total']}")
        else:
            print("\nNo product fields found in this route!")
            
            # Print an example of custom fields
            if all_custom_fields:
                print("\nExample of available custom fields:")
                example = all_custom_fields[0]
                for key, value in example.items():
                    print(f"  {key}: {value}")
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching route details: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--multi":
            analyze_multiple_routes()
        else:
            # Assume it's a route ID
            examine_single_route(sys.argv[1])
    else:
        # Default to examining a single random route
        examine_single_route() 