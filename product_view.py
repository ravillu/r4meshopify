#!/usr/bin/env python3
"""
Product View Utility

Extracts product information from route data and aggregates it for reporting.
"""

import json
import re
from collections import defaultdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def extract_products_from_address(address):
    """Extract product information from an address
    
    Args:
        address: Address data with custom_fields
        
    Returns:
        List of product dictionaries
    """
    products = []
    
    # Skip addresses without custom fields
    if "custom_fields" not in address or not isinstance(address["custom_fields"], dict):
        return products
        
    custom_fields = address["custom_fields"]
    
    # Check for 'items' field which contains a summary (e.g., "1x Cod, 1x Salmon")
    if "items" in custom_fields and custom_fields["items"]:
        items_text = custom_fields["items"]
        
        # Extract products from items text using regex
        # Pattern matches formats like "2x Cod", "1x Salmon, Sushi-Grade"
        item_pattern = r'(\d+)x\s+([\w\s\(\)\-\,\.\/]+?)(?=\s*,\s*\d+x|\s*$)'
        matches = re.findall(item_pattern, items_text)
        
        for match in matches:
            try:
                quantity = int(match[0])
                product_name = match[1].strip()
                
                # Create a product entry for each item
                products.append({
                    "name": product_name,
                    "title": product_name,
                    "variant": "",
                    "sku": "",
                    "vendor": "",
                    "quantity": quantity,
                    "price": 0.0,  # We don't have price in the items field
                    "total_value": 0.0,
                    "is_summary": False,
                    "from_items_field": True  # Mark this as coming from items field
                })
            except (ValueError, IndexError):
                # Skip if we can't parse the quantity
                pass
    
    # Look for detailed product information (product_1_name, product_1_price, etc.)
    for i in range(1, 20):  # Check up to 19 products (increased from 9)
        name_field = f"product_{i}_name"
        price_field = f"product_{i}_price"
        quantity_field = f"product_{i}_quantity"
        title_field = f"product_{i}_title"
        variant_field = f"product_{i}_variant_title"
        sku_field = f"product_{i}_sku"
        vendor_field = f"product_{i}_vendor"
        
        # Skip if no product name is found
        if name_field not in custom_fields or not custom_fields[name_field]:
            continue
            
        # Extract product details
        product_name = custom_fields[name_field]
        
        # Skip tips when counting products
        if "tip" in product_name.lower() and "tip" == product_name.lower():
            continue
            
        # Get price (default to 0.0 if missing or invalid)
        product_price = 0.0
        if price_field in custom_fields and custom_fields[price_field]:
            try:
                product_price = float(custom_fields[price_field])
            except (ValueError, TypeError):
                pass
                
        # Get quantity (default to 1 if missing or invalid)
        product_quantity = 1
        if quantity_field in custom_fields and custom_fields[quantity_field]:
            try:
                product_quantity = int(custom_fields[quantity_field])
            except (ValueError, TypeError):
                pass
                
        # Get additional product details if available
        product_title = custom_fields.get(title_field, product_name)
        product_variant = custom_fields.get(variant_field, "")
        product_sku = custom_fields.get(sku_field, "")
        product_vendor = custom_fields.get(vendor_field, "")
        
        # Create product dictionary
        product = {
            "name": product_name,
            "title": product_title,
            "variant": product_variant,
            "sku": product_sku,
            "vendor": product_vendor,
            "quantity": product_quantity,
            "price": product_price,
            "total_value": product_price * product_quantity,
            "is_summary": False,
            "from_items_field": False
        }
        
        products.append(product)
    
    return products

def normalize_product_name(name):
    """Normalize a product name for consistent aggregation
    
    Args:
        name: Product name
        
    Returns:
        Normalized name
    """
    # Convert to lowercase
    name = name.lower()
    
    # Map common variants to a standard name
    name_mapping = {
        "salmon, sushi-grade": "salmon, sushi-grade",
        "salmon sushi-grade": "salmon, sushi-grade",
        "sushi-grade salmon": "salmon, sushi-grade",
        "salmon": "salmon, sushi-grade",  # Assume all salmon is sushi-grade unless specified
    }
    
    # Apply mappings
    for pattern, replacement in name_mapping.items():
        if pattern in name:
            return replacement
    
    return name

def aggregate_products_by_route(routes):
    """
    Aggregate products by route and add product details to each route
    
    Args:
        routes (list): List of route dictionaries from Route4Me API
        
    Returns:
        list: Routes with product details
    """
    logger.info(f"Aggregating products from {len(routes)} routes")
    
    routes_with_products = []
    
    for route in routes:
        try:
            route_products = []
            
            # Skip routes with no addresses
            if not route.get('addresses'):
                continue
                
            route_id = route.get('route_id', 'unknown')
            route_name = route.get('name', f"Route {route_id}")
            
            # Process each address in the route
            for address in route.get('addresses', []):
                # Skip depot/start/end addresses
                if address.get('is_depot'):
                    continue
                    
                # Get custom data which contains Shopify order details
                custom_data = address.get('custom_fields', {})
                
                # First try to get products from line_items
                if custom_data and custom_data.get('line_items'):
                    # Process each line item (product)
                    for item in custom_data.get('line_items', []):
                        # Skip items without required fields
                        if not item.get('name') or not item.get('price'):
                            continue
                            
                        # Calculate price and quantity
                        try:
                            price = float(item.get('price', 0))
                            quantity = int(item.get('quantity', 1))
                            total_item_value = price * quantity
                            
                            # Create product entry
                            product = {
                                'name': item.get('name'),
                                'sku': item.get('sku', ''),
                                'price': price,
                                'quantity': quantity,
                                'total_value': total_item_value
                            }
                            
                            # Add to route products
                            route_products.append(product)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error processing product in route {route_id}: {str(e)}")
                            continue
                else:
                    # Fall back to extracting products from individual fields
                    address_products = extract_products_from_address(address)
                    if address_products:
                        route_products.extend(address_products)
            
            # Only include routes with products
            if route_products:
                route_with_products = {
                    'route_id': route_id,
                    'route_name': route_name,
                    'products': route_products,
                    'created_timestamp': route.get('created_timestamp'),
                    'scheduled_date': route.get('scheduled_date')
                }
                
                # Add total product value for the route
                route_with_products['total_product_value'] = sum(p['total_value'] for p in route_products)
                
                # Add route to list
                routes_with_products.append(route_with_products)
                
        except Exception as e:
            logger.error(f"Error processing route {route.get('route_id', 'unknown')}: {str(e)}")
            continue
    
    logger.info(f"Found {len(routes_with_products)} routes with products")
    return routes_with_products

def get_top_products(routes_with_products, top_n=20):
    """
    Get the top N products by total value across all routes
    
    Args:
        routes_with_products (list): Routes with product details
        top_n (int): Number of top products to return (default: 20)
        
    Returns:
        list: Top products with aggregated statistics
    """
    logger.info("Calculating top products")
    
    # Track product totals
    product_map = defaultdict(lambda: {
        'name': '',
        'sku': '',
        'quantity': 0,
        'total_value': 0.0,
        'found_in_routes': set()  # Track which routes this product appears in
    })
    
    # Aggregate products across all routes
    for route in routes_with_products:
        route_id = route.get('route_id')
        
        for product in route.get('products', []):
            product_name = product.get('name', '')
            if not product_name:
                continue
                
            # Use name as key, could use SKU if preferred
            product_map[product_name]['name'] = product_name
            product_map[product_name]['sku'] = product.get('sku', '')
            product_map[product_name]['quantity'] += product.get('quantity', 0)
            product_map[product_name]['total_value'] += product.get('total_value', 0.0)
            product_map[product_name]['found_in_routes'].add(route_id)
    
    # Convert to list for sorting
    products_list = []
    for name, data in product_map.items():
        if data['quantity'] > 0:
            # Convert set to count for serialization
            data['found_in_routes'] = len(data['found_in_routes'])
            
            # Calculate average price
            data['avg_price'] = data['total_value'] / data['quantity'] if data['quantity'] > 0 else 0
            
            products_list.append(data)
    
    # Sort by total value and take top N
    top_products = sorted(products_list, key=lambda x: x['total_value'], reverse=True)[:top_n]
    
    logger.info(f"Found {len(top_products)} top products")
    return top_products

def generate_product_report(routes, include_details=True):
    """Generate a comprehensive product report for routes
    
    Args:
        routes: List of route objects
        include_details: Whether to include detailed product breakdowns
        
    Returns:
        Report dictionary with product statistics
    """
    # Aggregate products by route
    routes_with_products = aggregate_products_by_route(routes)
    
    # Get top products overall (get all products)
    top_products = get_top_products(routes_with_products, top_n=100)
    
    # Calculate overall totals
    total_product_count = sum(len(route.get('products', [])) for route in routes_with_products)
    total_unique_items = len(top_products)
    total_value = sum(route.get('total_product_value', 0) for route in routes_with_products)
    
    # Build report
    report = {
        "summary": {
            "route_count": len(routes),
            "total_product_count": total_product_count,
            "total_unique_items": total_unique_items,
            "total_value": total_value,
            "generated_at": datetime.now().isoformat()
        },
        "top_products": top_products,
        "routes": []
    }
    
    # Include route details if requested
    if include_details:
        for route in routes_with_products:
            route_id = route.get('route_id')
            # Get route date
            route_info = next((r for r in routes if r.get("route_id") == route_id), {})
            route_date = None
            if "schedule" in route_info and route_info["schedule"]:
                if "date" in route_info["schedule"]:
                    route_date = route_info["schedule"]["date"]
            
            route_summary = {
                "route_id": route_id,
                "route_name": route.get('route_name'),
                "route_date": route_date,
                "product_count": len(route.get('products', [])),
                "unique_items": len(set(p.get('name') for p in route.get('products', []))),
                "total_value": route.get('total_product_value', 0)
            }
            
            # Get top products for this route
            if route.get('products'):
                route_top_products = sorted(
                    route.get('products', []),
                    key=lambda x: x.get('total_value', 0),
                    reverse=True
                )[:5]  # Show top 5 products per route
                route_summary["top_products"] = route_top_products
            
            report["routes"].append(route_summary)
    
    return report

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate product report from route data')
    parser.add_argument('input_file', help='JSON file containing route data')
    parser.add_argument('--output', help='Output file for the report (JSON format)')
    args = parser.parse_args()
    
    try:
        with open(args.input_file, 'r') as f:
            routes = json.load(f)
            
        # Handle both single route and array of routes
        if isinstance(routes, dict):
            routes = [routes]
            
        report = generate_product_report(routes)
        
        # Output to file or stdout
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
                print(f"Report saved to {args.output}")
        else:
            print(json.dumps(report, indent=2))
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1) 