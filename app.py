#!/usr/bin/env python3
"""
Web UI for Route4Me - Shopify Dashboard
"""

import os
import io
import csv
import json
import sys
import traceback
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, Response, session
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import DateField, SelectField, SubmitField
from wtforms.validators import DataRequired

# Import dotenv for environment variable loading
try:
    from dotenv import load_dotenv
    # Load environment variables from .env file
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Environment variables need to be set manually.")

# Import from the more efficient direct calculation module
from calculate_route_values import (
    create_session, fetch_routes_for_daterange, calculate_route_values
)

# POS functionality has been removed as requested

# Initialize Flask app
app = Flask(__name__)

# Simple session configuration
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(24).hex())

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Check if we're in debug mode
DEBUG_MODE = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

# Configure logging directly instead of using the imported function
logging_level = logging.DEBUG if DEBUG_MODE else logging.INFO
logging.basicConfig(
    level=logging_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
app_logger = logging.getLogger(__name__)

# Create form for date selection
class DateRangeForm(FlaskForm):
    start_date = DateField('Start Date', validators=[DataRequired()], 
                         default=datetime.now() - timedelta(days=7))
    end_date = DateField('End Date', validators=[DataRequired()],
                       default=datetime.now())
    output_format = SelectField('Output Format', 
                              choices=[('csv', 'CSV'), ('json', 'JSON'), ('html', 'Table')],
                              default='html')
    submit = SubmitField('Generate Report')


def get_preset_dates(preset_type):
    """Generate date ranges for preset reports"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    start_date = ""
    end_date = ""
    
    if preset_type == 'today':
        start_date = today.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    elif preset_type == 'yesterday':
        yesterday = today - timedelta(days=1)
        start_date = yesterday.strftime('%Y-%m-%d')
        end_date = yesterday.strftime('%Y-%m-%d')
    
    elif preset_type == 'last7days':
        last_week = today - timedelta(days=7)
        start_date = last_week.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    elif preset_type == 'thisweek':
        # Monday as the first day of the week
        start = today - timedelta(days=today.weekday())
        start_date = start.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    elif preset_type == 'lastweek':
        # Last week Monday to Sunday
        this_week_start = today - timedelta(days=today.weekday())
        last_week_start = this_week_start - timedelta(days=7)
        last_week_end = this_week_start - timedelta(days=1)
        start_date = last_week_start.strftime('%Y-%m-%d')
        end_date = last_week_end.strftime('%Y-%m-%d')
    
    elif preset_type == 'thismonth':
        # First day of the current month
        start = today.replace(day=1)
        start_date = start.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    else:
        # Default to last 7 days
        last_week = today - timedelta(days=7)
        start_date = last_week.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # Final validation to ensure start date is not after end date
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
    
    if start_date_obj > end_date_obj:
        app_logger.warning(f"Fixing invalid date range: {start_date} to {end_date}")
        return end_date, start_date
    
    return start_date, end_date


@app.route('/', methods=['GET', 'POST'])
def index():
    form = DateRangeForm()
    
    if form.validate_on_submit():
        start_date = form.start_date.data
        end_date = form.end_date.data
        
        # Validate that start date is not after end date
        if start_date > end_date:
            # Swap the dates
            start_date, end_date = end_date, start_date
            flash('Start date was after end date. Dates have been swapped.', 'warning')
        
        # Format dates for storage and API calls
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        output_format = form.output_format.data
        
        # Store in session to redirect to results
        session['start_date'] = start_date_str
        session['end_date'] = end_date_str
        session['output_format'] = output_format
        
        return redirect(url_for('results'))
    
    return render_template('index.html', form=form)


@app.route('/preset/<report_type>')
def preset_report(report_type):
    """Handle preset report requests"""
    start_date, end_date = get_preset_dates(report_type)
    
    # Store in session to redirect to results
    session['start_date'] = start_date
    session['end_date'] = end_date
    session['output_format'] = 'html'
    
    return redirect(url_for('results'))


@app.route('/results')
def results():
    start_date = session.get('start_date')
    end_date = session.get('end_date')
    output_format = session.get('output_format', 'html')
    download_format = request.args.get('download_format')
    
    if download_format:
        output_format = download_format
    
    if not start_date or not end_date:
        flash('Please enter date range first')
        return redirect(url_for('index'))
    
    # Ensure the date range is valid (start date not after end date)
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    
    if start_dt > end_dt:
        # Swap dates if they're in the wrong order
        start_date, end_date = end_date, start_date
        # Update session values
        session['start_date'] = start_date
        session['end_date'] = end_date
        flash('Date range was reversed to ensure start date is before end date', 'warning')
    
    try:
        # Get environment variables
        route4me_api_key = os.environ.get("ROUTE4ME_API_KEY")
        
        if not route4me_api_key:
            flash('Missing required environment variables')
            return render_template('error.html', 
                                 error="Missing API credentials. Please check your .env file.")
        
        # Create session
        session_obj = create_session()
        
        # Get routes using the more efficient method without Shopify API dependency
        routes = fetch_routes_for_daterange(session_obj, route4me_api_key, start_dt, end_dt, limit=0)
        
        # Calculate route values directly from Route4Me data
        report_data = calculate_route_values(routes)
        
        # Report data now has a different structure
        routes_data = report_data["routes"]
        top_products_by_day = report_data["top_products_by_day"]
        top_products_overall = report_data["top_products_overall"]
        
        # Debug logging - only log detailed info in debug mode
        app_logger.info(f"Processed {len(routes_data)} routes with a total of {sum(route.get('total_orders', 0) for route in routes_data)} orders")
        
        if DEBUG_MODE:
            app_logger.debug(f"Top Products Overall: {len(top_products_overall)}")
            for product in top_products_overall:
                app_logger.debug(f"Product: {product['name']}, Quantity: {product['quantity']}, Value: ${product['value']:.2f}")
                
            app_logger.debug(f"Days with product data: {len(top_products_by_day)}")
            for day, products in top_products_by_day.items():
                app_logger.debug(f"Day {day}: {len(products)} products")
                # Log each product in this day
                for product in products:
                    app_logger.debug(f"  - {product['name']}: {product['quantity']} units, ${product['value']:.2f}")

            # Add detailed product debugging
            app_logger.debug("========= PRODUCT DATA DEBUGGING =========")
            app_logger.debug(f"Routes: {len(routes)}")
            # Look through the routes data for product fields
            product_fields_count = 0
            for route in routes:
                for addr in route.get("addresses", []):
                    if addr.get("is_depot", False):
                        continue
                    if "custom_fields" in addr and isinstance(addr["custom_fields"], dict):
                        custom_fields = addr["custom_fields"]
                        product_keys = [k for k in custom_fields.keys() if k.startswith('product_')]
                        if product_keys:
                            product_fields_count += 1
                            # Print first 2 addresses with product data for debugging
                            if product_fields_count <= 2:
                                app_logger.debug(f"Found address with {len(product_keys)} product fields")
                                for key in sorted(product_keys):
                                    app_logger.debug(f"  {key}: {custom_fields[key]}")
                                
                                # Check if these fields can be parsed
                                for i in range(1, 10):
                                    price_field = f"product_{i}_price"
                                    name_field = f"product_{i}_name"
                                    quantity_field = f"product_{i}_quantity"
                                    
                                    if price_field in custom_fields and custom_fields[price_field]:
                                        app_logger.debug(f"  Product {i} - Can extract price: {price_field}")
                                        try:
                                            price = float(custom_fields[price_field])
                                            app_logger.debug(f"  Price parsed successfully: {price}")
                                        except (ValueError, TypeError) as e:
                                            app_logger.debug(f"  Error parsing price: {e}, value: '{custom_fields[price_field]}'")
                                            
                                    if name_field in custom_fields and custom_fields[name_field]:
                                        app_logger.debug(f"  Product {i} - Can extract name: {name_field}")
                                        
                                    if quantity_field in custom_fields and custom_fields[quantity_field]:
                                        app_logger.debug(f"  Product {i} - Can extract quantity: {quantity_field}")
                                        try:
                                            quantity = int(custom_fields[quantity_field])
                                            app_logger.debug(f"  Quantity parsed successfully: {quantity}")
                                        except (ValueError, TypeError) as e:
                                            app_logger.debug(f"  Error parsing quantity: {e}, value: '{custom_fields[quantity_field]}'")
                                
            app_logger.debug(f"Total addresses with product fields: {product_fields_count}")
            app_logger.debug("======================================")
        
        # Calculate total across all routes
        total_value = sum(route['total_order_value'] for route in routes_data)
        total_orders = sum(route.get('total_orders', 0) for route in routes_data)
        total_orders_with_value = sum(route.get('orders_with_value', 0) for route in routes_data)
        
        app_logger.info(f"Direct totals from routes_data: Total Orders: {total_orders}, Orders with value: {total_orders_with_value}, Value: ${total_value:.2f}")
        
        # Group routes by date
        routes_by_date = {}
        for route in routes_data:                
            # Extract date for grouping
            created_date = route.get('created_date', 'No Date')
            
            # Use created_date as key, initialize if not exists
            if created_date not in routes_by_date:
                routes_by_date[created_date] = {
                    'date': created_date,
                    'routes': [],
                    'total_value': 0,
                    'total_orders': 0,
                    'orders_with_value': 0
                }
            
            # Ensure route has all required fields, even if empty
            total_order_value = route.get('total_order_value', 0.0)
            route_total_orders = route.get('total_orders', 0)  
            route_orders_with_value = route.get('orders_with_value', 0)
            
            # Add route to its date group
            routes_by_date[created_date]['routes'].append(route)
            routes_by_date[created_date]['total_value'] += total_order_value
            routes_by_date[created_date]['total_orders'] += route_total_orders
            routes_by_date[created_date]['orders_with_value'] += route_orders_with_value
        
        # Sort dates chronologically
        sorted_dates = sorted(routes_by_date.keys())
        daily_totals = [routes_by_date[date] for date in sorted_dates]
        
        # Add top products to daily totals
        for day_total in daily_totals:
            day_date = day_total['date']
            if day_date in top_products_by_day:
                day_total['top_products'] = top_products_by_day[day_date]
            else:
                day_total['top_products'] = []
        
        # Check if any routes have incomplete order values
        any_missing_values = False  # All orders must have values
        
        # Return results based on selected format
        if output_format == 'json':
            # Include products data in the JSON output
            combined_data = {
                "report_data": routes_data,
                "top_products_by_day": top_products_by_day,
                "top_products_overall": top_products_overall,
                "start_date": start_date,
                "end_date": end_date
            }
            return Response(
                json.dumps(combined_data, indent=2),
                mimetype='application/json',
                headers={'Content-Disposition': f'attachment;filename=report_{start_date}_to_{end_date}.json'}
            )
        elif output_format == 'csv':
            # Create CSV in memory
            output = io.StringIO()
            writer = csv.writer(output)
            # Add header
            writer.writerow(['route_id', 'route_name', 'created_date', 'total_order_value', 'orders_with_value', 'total_orders'])
            for route in routes_data:
                # Get date from route
                route_date = route.get('created_date', '')
                
                writer.writerow([
                    route['route_id'], 
                    route['route_name'],
                    route_date,
                    f"{route['total_order_value']:.2f}",
                    route.get('orders_with_value', 0),
                    route.get('total_orders', 0)
                ])
            
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment;filename=report_{start_date}_to_{end_date}.csv'}
            )
        else:  # HTML
            # Sort dates chronologically
            sorted_dates = sorted(routes_by_date.keys())
            daily_totals = [routes_by_date[date] for date in sorted_dates]
            
            # Add top products to daily totals
            for day_total in daily_totals:
                day_date = day_total['date']
                if day_date in top_products_by_day:
                    day_total['top_products'] = top_products_by_day[day_date]
                else:
                    day_total['top_products'] = []
            
            return render_template('results.html', 
                                 report_data=routes_data,
                                 daily_totals=daily_totals,
                                 top_products_overall=top_products_overall,
                                 start_date=start_date, 
                                 end_date=end_date,
                                 total_value=total_value,
                                 total_orders=total_orders,
                                 total_orders_with_value=total_orders,  # All orders have values
                                 any_missing_values=any_missing_values)
    
    except Exception as e:
        app_logger.error(f"Error generating report: {e}")
        app_logger.error(traceback.format_exc())
        return render_template('error.html', error=str(e))


if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Parse command line arguments for port
    import argparse
    parser = argparse.ArgumentParser(description='Route4Me Dashboard')
    parser.add_argument('--port', type=int, default=10000, help='Port to run the server on')
    args = parser.parse_args()
    
    # Get port from command line or environment
    port = args.port or int(os.environ.get('PORT', 10000))
    
    # Print startup message
    print(f"Starting server on port {port}...")
    
    # Run the app
    app.run(host='0.0.0.0', port=port, debug=True)