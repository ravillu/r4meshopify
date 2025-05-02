#!/usr/bin/env python3
"""
Examine Route Data

This script loads and examines route data in more detail to find additional price information.
"""

import json
import sys
from pprint import pprint

def analyze_address_fields(addr, address_index, verbose=False):
    """Analyze custom fields in an address to find price-related information"""
    address_line = addr.get("address", "No address")
    print(f"\nAnalyzing Address {address_index}: {address_line}")
    
    # Check if address has custom fields
    if "custom_fields" not in addr or not isinstance(addr["custom_fields"], dict):
        print("  No custom_fields found")
        return None
    
    custom_fields = addr["custom_fields"]
    
    # Find order references
    order_refs = {}
    for field_name in ["order_id", "id", "name", "order_uuid"]:
        if field_name in custom_fields and custom_fields[field_name]:
            order_refs[field_name] = custom_fields[field_name]
    
    if order_refs:
        print(f"  Order References: {', '.join(f'{k}={v}' for k, v in order_refs.items())}")
    else:
        print("  No order references found")
        return None
    
    # Look for direct price fields
    price_info = {}
    price_found = False
    for field_name in ["subtotal_price", "total_price"]:
        if field_name in custom_fields and custom_fields[field_name]:
            try:
                price = float(custom_fields[field_name])
                price_info[field_name] = price
                price_found = True
            except (ValueError, TypeError):
                print(f"  Invalid {field_name}: {custom_fields[field_name]}")
    
    if price_found:
        print(f"  Direct Price Info: {', '.join(f'{k}=${v:.2f}' for k, v in price_info.items())}")
    else:
        print("  No direct price information found, searching for alternatives...")
    
    # Look for alternative price-related fields
    alt_price_fields = ["current_total_price", "product_1_price", "product_2_price", "product_3_price"]
    alt_price_info = {}
    
    for field_name in alt_price_fields:
        if field_name in custom_fields and custom_fields[field_name]:
            try:
                price = float(custom_fields[field_name])
                alt_price_info[field_name] = price
            except (ValueError, TypeError):
                if verbose:
                    print(f"  Invalid {field_name}: {custom_fields[field_name]}")
    
    if alt_price_info:
        print(f"  Alternative Price Info: {', '.join(f'{k}=${v:.2f}' for k, v in alt_price_info.items())}")
        
        # Check note_attributes for price info
        if 'note_attributes' in custom_fields and custom_fields['note_attributes']:
            try:
                note_attributes_str = str(custom_fields['note_attributes'])
                if 'current_total_price' in note_attributes_str:
                    print(f"  Note attributes contain price information: {note_attributes_str}")
                    # Try to parse note_attributes
                    if note_attributes_str.startswith('[') and note_attributes_str.endswith(']'):
                        try:
                            # Replace single quotes with double quotes for JSON parsing
                            json_str = note_attributes_str.replace("'", '"')
                            attributes = json.loads(json_str)
                            for attr in attributes:
                                if isinstance(attr, dict) and 'name' in attr and 'value' in attr:
                                    if attr['name'] == 'current_total_price':
                                        try:
                                            price = float(attr['value'])
                                            alt_price_info['current_total_price'] = price
                                            print(f"  Extracted from note_attributes: current_total_price=${price:.2f}")
                                        except (ValueError, TypeError):
                                            pass
                        except json.JSONDecodeError:
                            pass
            except:
                pass
    
    # If no price info found at all, look for product information to calculate total
    if not price_found and not alt_price_info:
        print("  Searching for product information...")
        product_count = 0
        product_total = 0.0
        
        for i in range(1, 10):  # Check for up to 9 products
            price_field = f"product_{i}_price"
            quantity_field = f"product_{i}_quantity"
            
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
                    
                    product_value = price * quantity
                    product_count += 1
                    product_total += product_value
                    
                    print(f"  Product {i}: ${price:.2f} x {quantity} = ${product_value:.2f}")
                except (ValueError, TypeError):
                    pass
        
        if product_count > 0:
            print(f"  Calculated from products: total=${product_total:.2f} (from {product_count} products)")
            alt_price_info['calculated_total'] = product_total
    
    # Combine all price information
    all_price_info = {**price_info, **alt_price_info}
    
    # If verbose, print all custom fields
    if verbose and not all_price_info:
        print("\nAll custom fields:")
        for k, v in sorted(custom_fields.items()):
            print(f"  {k}: {v}")
    
    return all_price_info

def main():
    """Main function"""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Examine Route Data')
    parser.add_argument('input_file', help='Input route data JSON file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show verbose output')
    args = parser.parse_args()
    
    # Load data
    try:
        with open(args.input_file, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading file: {e}")
        sys.exit(1)
    
    # Check if this is route data
    if not isinstance(data, dict) or 'addresses' not in data or not isinstance(data['addresses'], list):
        print("Input file does not contain valid route data")
        sys.exit(1)
    
    # Print route info
    route_id = data.get('route_id', 'unknown')
    route_name = data.get('name', f'Route {route_id}')
    print(f"Route: {route_name}")
    print(f"Route ID: {route_id}")
    
    # Analyze addresses
    addresses = data.get('addresses', [])
    print(f"Total addresses: {len(addresses)}")
    
    # Get non-depot addresses
    non_depot_addresses = [addr for addr in addresses if not addr.get('is_depot', False)]
    print(f"Delivery addresses: {len(non_depot_addresses)}")
    
    # Analyze each address
    total_value = 0.0
    addresses_with_price = 0
    found_price_fields = set()
    alternate_prices = 0
    calculated_prices = 0
    
    for i, addr in enumerate(non_depot_addresses):
        price_info = analyze_address_fields(addr, i+1, verbose=args.verbose)
        
        if price_info:
            addresses_with_price += 1
            
            # Determine best price to use
            if 'subtotal_price' in price_info:
                price = price_info['subtotal_price']
                total_value += price
                found_price_fields.add('subtotal_price')
            elif 'total_price' in price_info:
                price = price_info['total_price']
                total_value += price
                found_price_fields.add('total_price')
            elif 'current_total_price' in price_info:
                price = price_info['current_total_price']
                total_value += price
                found_price_fields.add('current_total_price')
                alternate_prices += 1
            elif 'calculated_total' in price_info:
                price = price_info['calculated_total']
                total_value += price
                found_price_fields.add('calculated_total')
                calculated_prices += 1
            else:
                # Use first available price field
                field_name = next(iter(price_info.keys()))
                price = price_info[field_name]
                total_value += price
                found_price_fields.add(field_name)
                alternate_prices += 1
    
    # Print summary
    print("\nSUMMARY:")
    print(f"Total delivery addresses: {len(non_depot_addresses)}")
    print(f"Addresses with price information: {addresses_with_price}")
    print(f"Total route value: ${total_value:.2f}")
    print(f"Price fields used: {', '.join(found_price_fields)}")
    
    if alternate_prices > 0:
        print(f"  Including {alternate_prices} addresses using alternative price fields")
    if calculated_prices > 0:
        print(f"  Including {calculated_prices} addresses using calculated product totals")
    
    if len(non_depot_addresses) > 0:
        success_rate = (addresses_with_price / len(non_depot_addresses)) * 100
        print(f"Success rate: {success_rate:.1f}%")

if __name__ == "__main__":
    main() 