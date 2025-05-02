#!/usr/bin/env python3
"""
Extract Product Information from Route4Me

This script demonstrates extracting product information from Route4Me routes
to verify that we can correctly identify and process product data.
"""

import os
import sys
import json
from datetime import datetime, timedelta
import requests
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

def fetch_route(session, route_id):
    """Fetch a specific route by ID"""
    url = "https://api.route4me.com/api.v4/route.php"
    params = {
        "api_key": ROUTE4ME_API_KEY,
        "route_id": route_id
    }
    
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching route: {e}")
        return None

def fetch_routes(session, limit=5):
    """Fetch recent routes"""
    url = "https://api.route4me.com/api.v4/route.php"
    params = {
        "api_key": ROUTE4ME_API_KEY,
        "limit": limit
    }
    
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        routes = response.json()
        
        if isinstance(routes, list):
            return [r.get("route_id") for r in routes if r.get("route_id")]
        else:
            print("Unexpected response format")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching routes: {e}")
        return []

def extract_products_from_route(route):
    """Extract product information from a route"""
    if not route:
        return None
    
    route_id = route.get("route_id", "unknown")
    route_name = route.get("name", f"Route {route_id}")
    
    print(f"\nProcessing Route: {route_name} (ID: {route_id})")
    
    # Initialize product data
    products_by_day = {}
    all_products = {}
    
    # Format creation date
    created_timestamp = route.get("created_timestamp")
    if created_timestamp and isinstance(created_timestamp, (int, float)):
        try:
            created_date = datetime.fromtimestamp(created_timestamp).strftime("%Y-%m-%d")
        except (ValueError, TypeError, OverflowError):
            created_date = "unknown"
    else:
        created_date = "unknown"
    
    print(f"Route date: {created_date}")
    
    # Initialize tracking for this day
    if created_date not in products_by_day:
        products_by_day[created_date] = {}
    
    # Process each address
    addresses = route.get("addresses", [])
    addresses_with_products = 0
    
    print(f"Processing {len(addresses)} addresses...")
    
    for addr_idx, addr in enumerate(addresses):
        # Skip depot addresses
        if addr.get("is_depot", False):
            continue
        
        # Check for custom fields
        if "custom_fields" in addr and isinstance(addr["custom_fields"], dict):
            custom_fields = addr["custom_fields"]
            
            # Look for product fields
            product_fields = {k: v for k, v in custom_fields.items() if k.startswith("product_")}
            if product_fields:
                addresses_with_products += 1
                print(f"\nAddress {addr_idx+1} has {len(product_fields)} product fields")
                
                # Extract product information
                for i in range(1, 10):  # Check for up to 9 products
                    price_field = f"product_{i}_price"
                    quantity_field = f"product_{i}_quantity"
                    name_field = f"product_{i}_name"
                    
                    if price_field in custom_fields and custom_fields[price_field]:
                        try:
                            price = float(custom_fields[price_field])
                            quantity = 1  # Default quantity
                            
                            # Get quantity if available
                            if quantity_field in custom_fields and custom_fields[quantity_field]:
                                try:
                                    quantity = int(custom_fields[quantity_field])
                                except (ValueError, TypeError):
                                    pass
                            
                            # Get product name if available
                            product_name = None
                            if name_field in custom_fields and custom_fields[name_field]:
                                product_name = str(custom_fields[name_field])
                            else:
                                # Use generic name if not available
                                product_name = f"Product {i}"
                                
                            # Track products sold
                            if product_name:
                                print(f"  Found product: {product_name}, price: {price}, quantity: {quantity}")
                                
                                # Track by day
                                if product_name not in products_by_day[created_date]:
                                    products_by_day[created_date][product_name] = {
                                        "quantity": 0,
                                        "value": 0.0
                                    }
                                products_by_day[created_date][product_name]["quantity"] += quantity
                                products_by_day[created_date][product_name]["value"] += price * quantity
                                
                                # Track overall
                                if product_name not in all_products:
                                    all_products[product_name] = {
                                        "quantity": 0,
                                        "value": 0.0
                                    }
                                all_products[product_name]["quantity"] += quantity
                                all_products[product_name]["value"] += price * quantity
                        except (ValueError, TypeError) as e:
                            print(f"  Error processing product {i}: {e}")
    
    print(f"\nFound {addresses_with_products} addresses with product fields")
    
    # Process top products for each day
    top_products_by_day = {}
    for day, products in products_by_day.items():
        # Sort products by value in descending order and take top 5
        sorted_products = sorted(products.items(), key=lambda x: x[1]["value"], reverse=True)[:5]
        top_products_by_day[day] = [
            {
                "name": name,
                "quantity": data["quantity"],
                "value": data["value"]
            }
            for name, data in sorted_products
        ]
    
    # Process top 5 products overall
    sorted_all_products = sorted(all_products.items(), key=lambda x: x[1]["value"], reverse=True)[:5]
    top_products_overall = [
        {
            "name": name,
            "quantity": data["quantity"],
            "value": data["value"]
        }
        for name, data in sorted_all_products
    ]
    
    # Print results
    print("\nProducts by day:")
    for day, products in top_products_by_day.items():
        print(f"\n{day} Top Products:")
        for idx, product in enumerate(products, 1):
            print(f"  {idx}. {product['name']}: {product['quantity']} units, ${product['value']:.2f}")
    
    print("\nTop Products Overall:")
    for idx, product in enumerate(top_products_overall, 1):
        print(f"  {idx}. {product['name']}: {product['quantity']} units, ${product['value']:.2f}")
    
    # Return the results
    return {
        "top_products_by_day": top_products_by_day,
        "top_products_overall": top_products_overall
    }

def extract_products_from_multiple_routes(route_ids):
    """Extract product information from multiple routes"""
    session = create_session()
    
    # Initialize aggregated product data
    all_products_combined = {}
    top_products_by_day_combined = {}
    
    for i, route_id in enumerate(route_ids):
        print(f"\nProcessing route {i+1}/{len(route_ids)}: {route_id}")
        
        # Fetch route
        route = fetch_route(session, route_id)
        if not route:
            print(f"Failed to fetch route {route_id}")
            continue
        
        # Extract products
        result = extract_products_from_route(route)
        if not result:
            continue
        
        # Merge top products by day
        for day, products in result["top_products_by_day"].items():
            if day not in top_products_by_day_combined:
                top_products_by_day_combined[day] = {}
            
            for product in products:
                name = product["name"]
                quantity = product["quantity"]
                value = product["value"]
                
                if name not in top_products_by_day_combined[day]:
                    top_products_by_day_combined[day][name] = {
                        "quantity": 0,
                        "value": 0.0
                    }
                
                top_products_by_day_combined[day][name]["quantity"] += quantity
                top_products_by_day_combined[day][name]["value"] += value
        
        # Merge overall products
        for product in result["top_products_overall"]:
            name = product["name"]
            quantity = product["quantity"]
            value = product["value"]
            
            if name not in all_products_combined:
                all_products_combined[name] = {
                    "quantity": 0,
                    "value": 0.0
                }
            
            all_products_combined[name]["quantity"] += quantity
            all_products_combined[name]["value"] += value
    
    # Process final top products by day
    final_top_products_by_day = {}
    for day, products in top_products_by_day_combined.items():
        # Sort products by value in descending order and take top 5
        sorted_products = sorted(products.items(), key=lambda x: x[1]["value"], reverse=True)[:5]
        final_top_products_by_day[day] = [
            {
                "name": name,
                "quantity": data["quantity"],
                "value": data["value"]
            }
            for name, data in sorted_products
        ]
    
    # Process final top 5 products overall
    sorted_all_products = sorted(all_products_combined.items(), key=lambda x: x[1]["value"], reverse=True)[:5]
    final_top_products_overall = [
        {
            "name": name,
            "quantity": data["quantity"],
            "value": data["value"]
        }
        for name, data in sorted_all_products
    ]
    
    # Print final results
    print("\n" + "="*50)
    print("COMBINED RESULTS FROM ALL ROUTES")
    print("="*50)
    
    print("\nProducts by day:")
    for day, products in final_top_products_by_day.items():
        print(f"\n{day} Top Products:")
        for idx, product in enumerate(products, 1):
            print(f"  {idx}. {product['name']}: {product['quantity']} units, ${product['value']:.2f}")
    
    print("\nTop Products Overall:")
    for idx, product in enumerate(final_top_products_overall, 1):
        print(f"  {idx}. {product['name']}: {product['quantity']} units, ${product['value']:.2f}")

def main():
    """Main function"""
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python extract_products.py ROUTE_ID")
        print("       python extract_products.py --multi [NUMBER_OF_ROUTES]")
        sys.exit(1)
    
    if sys.argv[1] == "--multi":
        # Process multiple routes
        limit = 5  # Default
        if len(sys.argv) > 2:
            try:
                limit = int(sys.argv[2])
            except ValueError:
                print(f"Invalid number of routes: {sys.argv[2]}")
                sys.exit(1)
        
        # Fetch routes
        session = create_session()
        route_ids = fetch_routes(session, limit)
        
        if not route_ids:
            print("No routes found")
            sys.exit(1)
        
        print(f"Found {len(route_ids)} routes to process")
        extract_products_from_multiple_routes(route_ids)
    else:
        # Process a single route
        route_id = sys.argv[1]
        
        # Create session and fetch route
        session = create_session()
        route = fetch_route(session, route_id)
        
        if not route:
            print(f"Failed to fetch route {route_id}")
            sys.exit(1)
        
        # Extract products
        extract_products_from_route(route)

if __name__ == "__main__":
    main() 