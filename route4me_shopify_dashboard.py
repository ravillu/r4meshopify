#!/usr/bin/env python3
"""
Route4Me - Shopify Dashboard
----------------------------
Fetches routes from Route4Me, gets associated Shopify orders and calculates total value per route.
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set, Any, Union
import requests
import certifi
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
import urllib.parse

# Determine if we should verify SSL
# Setting this to False is only for development/debugging and should never be used in production
VERIFY_SSL = os.environ.get('SHOPIFY_VERIFY_SSL', 'True').lower() not in ('false', '0', 'no')

# Get the path to the certifi certificate bundle
CERT_BUNDLE = certifi.where()

# Only disable SSL warnings if we're intentionally not verifying
if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    # DEVELOPMENT ONLY: Set the environment variable to make all requests disable verification
    os.environ['PYTHONHTTPSVERIFY'] = '0'
    # Show a warning
    print("WARNING: SSL verification disabled - NOT SECURE FOR PRODUCTION")

# Setup logger at the module level so it's available when imported
logger = logging.getLogger(__name__)

# Configure logging immediately
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Try to load the .env file if dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Create a global Shopify session with proper certificate verification
# Get credentials from environment (or use empty strings as placeholders)
SHOPIFY_TOKEN = os.environ.get("SHOPIFY_TOKEN", "")
SHOPIFY_STORE_URL = os.environ.get("SHOPIFY_STORE_URL", "")

# Create the session
SHOPIFY = requests.Session()
SHOPIFY.headers.update({
    "X-Shopify-Access-Token": SHOPIFY_TOKEN,
    "Accept": "application/json",
    "Content-Type": "application/json"
})

# Configure SSL verification based on the environment variable and certifi bundle
SHOPIFY.verify = CERT_BUNDLE if VERIFY_SSL else False

# Add retry with reduced backoff
retry = Retry(total=2, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504])
SHOPIFY.mount("https://", HTTPAdapter(max_retries=retry))

# Log state for debugging
if not VERIFY_SSL:
    logger.warning("SSL verification disabled for Shopify API calls - NOT SECURE FOR PRODUCTION")
logger.info(f"SHOPIFY.verify = {SHOPIFY.verify}")
logger.info(f"Using certifi bundle: {CERT_BUNDLE}")
logger.info(f"Certifi version: {certifi.__version__}")
logger.info(f"REQUESTS_CA_BUNDLE = {os.environ.get('REQUESTS_CA_BUNDLE', 'Not set')}")
logger.info(f"PYTHONHTTPSVERIFY = {os.environ.get('PYTHONHTTPSVERIFY', 'Not set')}")

def redact_url(url):
    """Redact sensitive information from URLs before logging
    
    Args:
        url: URL string that may contain sensitive information
        
    Returns:
        URL with sensitive information redacted
    """
    if not url or not isinstance(url, str):
        return url
        
    try:
        # Parse the URL
        parsed = urllib.parse.urlparse(url)
        
        # Check for query parameters
        if parsed.query:
            query_params = urllib.parse.parse_qs(parsed.query)
            
            # List of parameters to redact (case-insensitive)
            sensitive_params = ['token', 'api_key', 'key', 'password', 'secret', 'access_token']
            
            # Redact sensitive parameters
            for param in list(query_params.keys()):
                if any(sensitive in param.lower() for sensitive in sensitive_params):
                    query_params[param] = ['[REDACTED]']
            
            # Rebuild the query string
            safe_query = urllib.parse.urlencode(query_params, doseq=True)
            
            # Rebuild the URL
            safe_url = urllib.parse.urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                safe_query,
                parsed.fragment
            ))
            
            return safe_url
        
        return url
        
    except Exception:
        # If anything goes wrong, just return the original URL
        return url

# Configure custom handler for logging with URL redaction
class RedactingSafeHandler(logging.Handler):
    """Logging handler that redacts sensitive information from log messages"""
    
    def __init__(self, base_handler):
        super().__init__(base_handler.level)
        self.base_handler = base_handler
        
    def emit(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            # Look for URL patterns and redact sensitive parts
            url_pattern = r'https?://[^\s]+'
            
            def redact_urls_in_match(match):
                url = match.group(0)
                return redact_url(url)
            
            record.msg = re.sub(url_pattern, redact_urls_in_match, record.msg)
            
        self.base_handler.emit(record)

# Apply redacting handler to existing handlers
def apply_log_redaction():
    """Apply URL redaction to all logging handlers"""
    root_logger = logging.getLogger()
    
    # Replace existing handlers with redacting versions
    original_handlers = root_logger.handlers.copy()
    root_logger.handlers = []
    
    for handler in original_handlers:
        root_logger.addHandler(RedactingSafeHandler(handler))
        
# Apply redaction
apply_log_redaction()

def setup_logging():
    """Configure logging based on LOG_LEVEL environment variable"""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger(__name__)
    
    # Warn if potentially problematic environment variables are set
    if os.environ.get('PYTHONHTTPSVERIFY', '1') == '0':
        logger.warning("PYTHONHTTPSVERIFY=0 is set, but will be ignored since we're using certifi. Consider removing this environment variable.")
    
    # Log SSL verification status
    logger.info(f"SSL verification for requests: {'Enabled' if VERIFY_SSL else 'Disabled'}")
    logger.info(f"Using certifi bundle: {CERT_BUNDLE} (version {certifi.__version__})")
    
    return logger


def create_session_with_retry():
    """Create a requests session with retry capability"""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    
    # Apply the same verification settings as the Shopify session
    session.verify = CERT_BUNDLE if VERIFY_SSL else False
    
    return session


def fetch_route4me_routes(session, api_key, start_date, end_date):
    """Fetch all routes from Route4Me within the given date range"""
    logger.info(f"Fetching Route4Me routes from {start_date} to {end_date}")
    
    route_summaries = []
    offset = 0
    limit = 100  # Fetch fewer routes at a time to avoid timeouts
    
    # Step 1: Get the list of route summaries (without addresses)
    while True:
        url = "https://api.route4me.com/api.v4/route.php"
        params = {
            "api_key": api_key,
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
            "offset": offset
        }
        
        try:
            logger.debug(f"Requesting route summaries with offset {offset}, limit {limit}")
            response = session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # v4 API returns a direct array of routes
            if isinstance(data, list):
                new_routes = data
                route_summaries.extend(new_routes)
                logger.debug(f"Fetched {len(new_routes)} route summaries")
                
                # If we received fewer than the limit, we're done
                if len(new_routes) < limit:
                    break
                    
                # Otherwise, increment the offset for the next page
                offset += limit
            else:
                logger.warning("Unexpected response format from Route4Me API")
                logger.debug(f"Response: {data}")
                break
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Route4Me routes: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            raise
    
    logger.info(f"Fetched a total of {len(route_summaries)} route summaries")
    
    # Step 2: Get full details for each route (including addresses with order IDs)
    detailed_routes = []
    
    for route_summary in route_summaries:
        route_id = route_summary.get("route_id")
        if not route_id:
            logger.warning("Route summary missing route_id, skipping")
            continue
            
        try:
            # Fetch detailed route info with addresses
            url = "https://api.route4me.com/api.v4/route.php"
            params = {
                "api_key": api_key,
                "route_id": route_id
            }
            
            logger.debug(f"Fetching detailed info for route {route_id}")
            response = session.get(url, params=params, timeout=30)
            response.raise_for_status()
            route_detail = response.json()
            
            if isinstance(route_detail, dict):
                detailed_routes.append(route_detail)
            else:
                logger.warning(f"Unexpected response format for route detail {route_id}")
                
            # Add a small delay to avoid hitting rate limits
            time.sleep(0.2)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching detailed info for route {route_id}: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            # Continue with other routes even if this one fails
            continue
    
    logger.info(f"Fetched details for {len(detailed_routes)} routes")
    return detailed_routes


def extract_order_ids_from_route(route):
    """Extract unique Shopify order IDs from a route"""
    order_ids = set()
    
    # Check if addresses exist in the route
    if "addresses" not in route or not route["addresses"]:
        logger.warning(f"No addresses found in route {route.get('route_id', 'unknown')}")
        return order_ids
    
    for address in route["addresses"]:
        order_id = None
        
        # Method 1: Check custom_fields object
        if "custom_fields" in address and isinstance(address["custom_fields"], dict):
            custom_fields = address["custom_fields"]
            # Try various possible field names for order ID
            for field_name in ["order_id", "order_uuid", "shopify_order_id", "id", "orderId"]:
                if field_name in custom_fields and custom_fields[field_name]:
                    order_id = custom_fields[field_name]
                    order_ids.add(str(order_id))
                    logger.debug(f"Found order ID {order_id} in custom_fields.{field_name}")
                    break
        
        # Method 2: Check for order information directly in the address
        if not order_id:
            for field_name in ["order_id", "order_uuid", "shopify_order_id", "id", "orderId"]:
                if field_name in address and address[field_name]:
                    order_id = address[field_name]
                    order_ids.add(str(order_id))
                    logger.debug(f"Found order ID {order_id} in address.{field_name}")
                    break
        
        # Method 3: Check order_inventory data
        if not order_id and "order_inventory" in address and address["order_inventory"]:
            inventory = address["order_inventory"]
            if isinstance(inventory, dict):
                for field_name in ["order_id", "id", "shopify_id"]:
                    if field_name in inventory and inventory[field_name]:
                        order_id = inventory[field_name]
                        order_ids.add(str(order_id))
                        logger.debug(f"Found order ID {order_id} in order_inventory.{field_name}")
                        break
        
        # Method 4: Check order_custom_data
        if not order_id and "order_custom_data" in address and address["order_custom_data"]:
            custom_data = address["order_custom_data"]
            if isinstance(custom_data, dict):
                for field_name in ["order_id", "id", "shopify_id", "shopify_order_id"]:
                    if field_name in custom_data and custom_data[field_name]:
                        order_id = custom_data[field_name]
                        order_ids.add(str(order_id))
                        logger.debug(f"Found order ID {order_id} in order_custom_data.{field_name}")
                        break
        
        # Method 5: Look for notes containing order ID pattern
        if not order_id and "notes" in address and address["notes"]:
            notes = address["notes"]
            if isinstance(notes, str):
                # Look for common order ID patterns in notes
                # Match #1234567890, Order: 1234567890, Order #1234567890, etc.
                order_patterns = [
                    r'#(\d+)',
                    r'[Oo]rder[:\s#]*(\d+)',
                    r'[Oo]rder[:\s#]*([A-Za-z0-9]+)'
                ]
                for pattern in order_patterns:
                    match = re.search(pattern, notes)
                    if match:
                        order_id = match.group(1)
                        order_ids.add(str(order_id))
                        logger.debug(f"Found order ID {order_id} in notes using pattern {pattern}")
                        break
    
    if not order_ids:
        logger.warning(f"Could not find any order IDs in route {route.get('route_id', 'unknown')}")
    else:
        logger.info(f"Found {len(order_ids)} unique order IDs in route {route.get('route_id', 'unknown')}")
    
    return order_ids


def shopify_id_for(store_url, order_number):
    """Translate a Shopify order_number to the internal id used by the API"""
    logger.debug(f"Looking up Shopify ID for order number: {order_number}")
    
    url = f"https://{store_url}/admin/api/2024-04/orders.json"
    params = {"status": "any", "order_number": order_number}
    
    try:
        # Use the session's configured verification (which uses certifi)
        response = SHOPIFY.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json().get("orders", [])
        
        if data:
            shopify_id = data[0].get("id")
            logger.debug(f"Found Shopify ID {shopify_id} for order number {order_number}")
            return shopify_id
        else:
            logger.warning(f"No order found for order number {order_number}")
            return None
            
    except requests.exceptions.HTTPError as e:
        logger.error(f"Shopify API error looking up order number {order_number}: {e.response.status_code}, {e.response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error looking up order number {order_number}: {e}")
    
    return None


def fetch_shopify_order(store_url, order_id):
    """Fetch a single Shopify order by ID"""
    # First, translate order number to Shopify internal ID if needed
    if str(order_id).isdigit() and len(str(order_id)) <= 10:
        # This looks like an order_number rather than a Shopify ID
        shopify_id = shopify_id_for(store_url, order_id)
        if not shopify_id:
            logger.warning(f"Order {order_id} not found in Shopify")
            return None
        logger.debug(f"Translated order number {order_id} to Shopify ID {shopify_id}")
        order_id = shopify_id
    
    # Use the latest stable API version (2024-04)
    url = f"https://{store_url}/admin/api/2024-04/orders/{order_id}.json"
    
    try:
        # Use the session's configured verification (which uses certifi)
        response = SHOPIFY.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"Shopify {e.response.status_code} for order {order_id}: {e.response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error for order {order_id}: {e}")
    return None


def fetch_shopify_orders_in_timeframe(store_url, start_date, end_date, batch_size=250):
    """Fetch all Shopify orders within a given timeframe in batches
    
    Args:
        store_url: Shopify store URL
        start_date: Start date string in YYYY-MM-DD format
        end_date: End date string in YYYY-MM-DD format
        batch_size: Maximum number of orders to fetch in one request
        
    Returns:
        List of orders from Shopify
    """
    logger.info(f"Fetching all Shopify orders from {start_date} to {end_date}")
    
    # Convert string dates to ISO format for Shopify API
    # Add buffer days to ensure we catch any orders that might be in the routes
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=14)
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=7)
        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()
    except ValueError:
        logger.error(f"Invalid date format. Expected YYYY-MM-DD, got {start_date} and {end_date}")
        # Use a larger window if parsing fails
        start_iso = (datetime.now() - timedelta(days=90)).isoformat()
        end_iso = datetime.now().isoformat()
    
    all_orders = []
    page_info = None
    
    while True:
        # Use the orders endpoint with created_at filters and pagination
        url = f"https://{store_url}/admin/api/2024-04/orders.json"
        params = {
            "status": "any",
            "limit": batch_size,
            "processed_at_min": start_iso,
            "processed_at_max": end_iso,
            "fields": "id,order_number,name,total_price,processed_at"
        }
        
        # Add pagination parameter if we have it
        if page_info:
            params["page_info"] = page_info
        
        try:
            logger.debug(f"Fetching batch of orders from Shopify (page_info: {page_info is not None})")
            # Use the session's configured verification (which uses certifi)
            response = SHOPIFY.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            # Extract orders from response
            orders_batch = response.json().get("orders", [])
            all_orders.extend(orders_batch)
            logger.debug(f"Fetched {len(orders_batch)} orders in this batch")
            
            # Check for pagination link in headers
            link_header = response.headers.get("Link", "")
            if "rel=\"next\"" in link_header and len(orders_batch) >= batch_size:
                # Extract page_info from the Link header
                import re
                page_info_match = re.search(r"page_info=([^&>]+)", link_header)
                if page_info_match:
                    page_info = page_info_match.group(1)
                    # Short delay before next request
                    time.sleep(0.5)
                    continue
            
            # If we get here, there are no more pages
            break
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Shopify orders: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            break
            
    logger.info(f"Successfully fetched {len(all_orders)} orders from Shopify")
    return all_orders


def build_order_number_to_id_map(orders):
    """Build a mapping of order number/name to Shopify internal ID
    
    Args:
        orders: List of Shopify order objects
        
    Returns:
        Dictionary mapping {order_number: shopify_id} and {name: shopify_id}
    """
    num_to_id = {}
    for order in orders:
        # Map the order_number to ID
        if "order_number" in order and "id" in order:
            num_to_id[str(order["order_number"])] = str(order["id"])
        
        # Also map the name (like "#1001") to ID
        if "name" in order and "id" in order:
            # Store with and without the # prefix
            name = order["name"]
            num_to_id[name] = str(order["id"])
            # Remove the # prefix if present
            if name.startswith("#"):
                num_to_id[name[1:]] = str(order["id"])
    
    logger.info(f"Built mapping for {len(num_to_id)} order numbers/names to Shopify IDs")
    return num_to_id


def chunk_list(lst, chunk_size):
    """Split a list into chunks of specified size
    
    Args:
        lst: The list to split
        chunk_size: Maximum size of each chunk
        
    Returns:
        Generator yielding chunks of the list
    """
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def fetch_multiple_shopify_orders_efficiently(store_url, order_ids, order_map, batch_size=50):
    """Fetch multiple Shopify orders in an efficient way using ID mapping
    
    Args:
        store_url: Shopify store URL
        order_ids: List of order IDs or references from routes
        order_map: Dictionary mapping {order_number/name: shopify_id}
        batch_size: Maximum number of orders to fetch in one request
        
    Returns:
        Dictionary of {order_reference: order_data} for successfully fetched orders
    """
    if not order_ids:
        return {}
    
    # Convert all input to strings for consistency
    order_refs = [str(order_id) for order_id in order_ids]
    
    # Map input references to Shopify IDs where possible
    shopify_ids = []
    for ref in order_refs:
        if ref in order_map:
            # This reference has a mapping to a Shopify ID
            shopify_ids.append(order_map[ref])
        elif ref.isdigit() and len(ref) > 10:
            # This looks like a Shopify ID already
            shopify_ids.append(ref)
    
    # Log what we're doing
    logger.info(f"Found Shopify IDs for {len(shopify_ids)} out of {len(order_refs)} order references")
    
    # Process in batches of 50 to stay within API limits
    results = {}
    
    # Only proceed if we have IDs to fetch
    if not shopify_ids:
        logger.warning("No valid Shopify IDs to fetch")
        return results
    
    # Fetch IDs in chunks
    for chunk in chunk_list(shopify_ids, batch_size):
        ids_string = ",".join(chunk)
        logger.debug(f"Fetching chunk of {len(chunk)} orders by Shopify ID")
        
        url = f"https://{store_url}/admin/api/2024-04/orders.json"
        params = {"ids": ids_string, "status": "any"}
        
        try:
            # Use the session's configured verification (which uses certifi)
            response = SHOPIFY.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            # Process the fetched orders
            orders = response.json().get("orders", [])
            logger.debug(f"Successfully fetched {len(orders)} orders")
            
            # Build a mapping from ID to the fetched order data
            for order in orders:
                order_id = str(order["id"])
                
                # Store by Shopify ID
                results[order_id] = {"order": order}
                
                # Also store by order_number for direct reference
                if "order_number" in order:
                    order_number = str(order["order_number"])
                    results[order_number] = {"order": order}
                
                # And by name (the #1001 format)
                if "name" in order:
                    order_name = order["name"]
                    results[order_name] = {"order": order}
                    
                    # Also without the # prefix
                    if order_name.startswith("#"):
                        results[order_name[1:]] = {"order": order}
                        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching batch of orders: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
        
        # Add a delay to avoid rate limits
        time.sleep(0.5)
    
    logger.info(f"Successfully processed {len(results)} orders")
    return results


def process_routes(routes, session, store_url):
    """Process routes, fetch Shopify orders, and calculate totals"""
    results = []
    
    # Before processing individual routes, get all orders within the timeframe
    # This assumes the routes are all within a similar timeframe
    start_date = None
    end_date = None
    
    # Try to extract date range from routes
    for route in routes:
        if "schedule" in route and route["schedule"]:
            if "date" in route["schedule"]:
                route_date = route["schedule"]["date"]
                if not start_date or route_date < start_date:
                    start_date = route_date
                if not end_date or route_date > end_date:
                    end_date = route_date
    
    # Use default date range if we couldn't extract from routes
    if not start_date or not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        logger.info(f"Using default date range: {start_date} to {end_date}")
    
    # Fetch all Shopify orders within the timeframe (with buffer days)
    all_shopify_orders = fetch_shopify_orders_in_timeframe(store_url, start_date, end_date)
    
    # Build mapping of order numbers to IDs
    order_map = build_order_number_to_id_map(all_shopify_orders)
    
    # Extract all unique order IDs from routes
    all_order_ids = set()
    for route in routes:
        route_id = route.get("route_id", "unknown")
        order_ids = extract_order_ids_from_route(route)
        all_order_ids.update(order_ids)
    
    # Log what we found in routes
    logger.info(f"Found {len(all_order_ids)} unique order references across all routes")
    
    # Fetch all order data efficiently
    shopify_orders = fetch_multiple_shopify_orders_efficiently(store_url, all_order_ids, order_map)
    
    # Now process each route with the pre-fetched data
    for route in routes:
        route_id = route.get("route_id", "unknown")
        route_name = route.get("name", f"Route {route_id}")
        
        logger.info(f"Processing route: {route_name} (ID: {route_id})")
        
        order_ids = extract_order_ids_from_route(route)
        logger.debug(f"Found {len(order_ids)} unique order IDs in route")
        
        total_value = 0.0
        total_orders = len(order_ids)
        orders_with_value = 0
        
        for order_id in order_ids:
            order_data = None
            order_id_str = str(order_id)
            
            # Lookup the order in our pre-fetched data
            if order_id_str in shopify_orders:
                order_data = shopify_orders[order_id_str]
            
            # Handle the found order data
            if order_data and "order" in order_data:
                try:
                    order_value = float(order_data["order"].get("total_price", "0"))
                    if order_value > 0:
                        total_value += order_value
                        orders_with_value += 1
                        order_number = order_data["order"].get("order_number", "unknown")
                        shopify_id = order_data["order"].get("id", "unknown")
                        logger.debug(f"Order {order_id_str} (#{order_number}, ID: {shopify_id}): ${order_value:.2f}")
                    else:
                        logger.warning(f"Order {order_id_str} has zero/negative value: ${order_value:.2f}")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid price value for order {order_id_str}")
            else:
                logger.warning(f"No data found for order reference {order_id_str}")
        
        results.append({
            "route_id": route_id,
            "route_name": route_name,
            "total_order_value": total_value,
            "total_orders": total_orders,
            "orders_with_value": orders_with_value
        })
        
        logger.info(f"Route {route_name} total value: ${total_value:.2f} from {orders_with_value}/{total_orders} orders")
    
    return results


def output_results(results, output_format="csv"):
    """Output the results in the specified format"""
    if output_format.lower() == "json":
        print(json.dumps(results, indent=2))
    else:  # CSV is the default
        print("route_id,route_name,total_order_value,total_orders,orders_with_value")
        for route in results:
            print(f"{route['route_id']},{route['route_name']},{route['total_order_value']:.2f},{route['total_orders']},{route['orders_with_value']}")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Route4Me - Shopify Dashboard")
    
    parser.add_argument("--start-date", 
                        help="Start date in YYYY-MM-DD format (default: 7 days ago)")
    parser.add_argument("--end-date", 
                        help="End date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--format", choices=["csv", "json"], default="csv",
                        help="Output format (default: csv)")
    
    return parser.parse_args()


if __name__ == "__main__":
    logger = setup_logging()
    session = create_session_with_retry()
    args = parse_args()
    
    # Set default dates if not provided
    today = datetime.now()
    if not args.end_date:
        args.end_date = today.strftime("%Y-%m-%d")
    if not args.start_date:
        args.start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        
    # Get environment variables
    route4me_api_key = os.environ.get("ROUTE4ME_API_KEY")
    shopify_store_url = os.environ.get("SHOPIFY_STORE_URL")
    
    if not all([route4me_api_key, shopify_store_url]):
        logger.error("Missing required environment variables. Please set: "
                    "ROUTE4ME_API_KEY, SHOPIFY_STORE_URL, SHOPIFY_TOKEN")
        sys.exit(1)
    
    try:
        # Fetch routes from Route4Me
        routes = fetch_route4me_routes(session, route4me_api_key, args.start_date, args.end_date)
        
        # Process routes and get results
        results = process_routes(routes, session, shopify_store_url)
        
        # Output the results
        output_results(results, args.format)
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1) 