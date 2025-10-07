from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import openpyxl
import json
import os
from datetime import datetime
from fuzzywuzzy import fuzz, process
import re
import database as db

app = Flask(__name__)
CORS(app)

# Initialize database
db.init_database()

# Configuration
PRODUCT_CATALOG_PATH = "products.csv"
ORDER_TEMPLATE_PATH = "order_template.xlsx"
OUTPUT_DIR = "output"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load product catalog
product_catalog = pd.read_csv(PRODUCT_CATALOG_PATH)
product_catalog.columns = product_catalog.columns.str.strip()

# Create lookup dictionaries for faster matching
article_to_product = dict(zip(product_catalog['Article Number'], product_catalog['Product']))
product_to_article = dict(zip(product_catalog['Product'], product_catalog['Article Number']))


def validate_quantity(quantity):
    """
    Validate quantity and return validation result with warnings.
    Returns: (is_valid, cleaned_quantity, warnings)
    """
    warnings = []
    
    try:
        # Convert to float first to handle decimals
        qty_float = float(quantity)
        
        # Check for negative numbers
        if qty_float < 0:
            return False, 0, ["Negative quantity is not allowed"]
        
        # Check for zero
        if qty_float == 0:
            return False, 0, ["Quantity cannot be zero"]
        
        # Check for decimals
        if qty_float != int(qty_float):
            warnings.append(f"Decimal quantity ({qty_float}) rounded to {int(qty_float)}")
            qty_float = int(qty_float)
        
        # Check for unusually high quantities
        if qty_float > 100:
            warnings.append(f"Unusually high quantity: {int(qty_float)}")
        
        # Check for unusually low quantities (but valid)
        if qty_float < 1 and qty_float > 0:
            warnings.append(f"Unusually low quantity: {qty_float}")
        
        return True, int(qty_float), warnings
        
    except (ValueError, TypeError):
        return False, 0, [f"Invalid quantity format: {quantity}"]


def fuzzy_match_product(input_product, threshold=80):
    """
    Fuzzy match a product name against the catalog with synonym support.
    Returns the best match (Article Number, Product Name, Score) or (None, None, 0) if no good match.
    """
    # First try exact match (case-insensitive)
    for article, product in article_to_product.items():
        if product.lower() == input_product.lower():
            return article, product, 100
    
    # Check database for synonyms
    db_products = db.get_all_products()
    for db_product in db_products:
        if db_product['synonyms']:
            synonyms = json.loads(db_product['synonyms'])
            for synonym in synonyms:
                if synonym.lower() == input_product.lower():
                    return db_product['article_number'], db_product['product_name'], 100
    
    # Try fuzzy matching
    product_list = list(article_to_product.values())
    best_match = process.extractOne(input_product, product_list, scorer=fuzz.token_sort_ratio)
    
    if best_match and best_match[1] >= threshold:
        matched_product = best_match[0]
        matched_article = product_to_article[matched_product]
        return matched_article, matched_product, best_match[1]
    
    return None, None, 0


def parse_excel_order(file_path):
    """Parse an Excel order file."""
    try:
        df = pd.read_excel(file_path)
        # Look for columns that might contain product info and quantities
        # Common patterns: Product, Article, Item, Quantity, Qty, Amount
        
        # Try to identify columns
        product_col = None
        quantity_col = None
        article_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'product' in col_lower or 'item' in col_lower or 'name' in col_lower:
                product_col = col
            elif 'quantity' in col_lower or 'qty' in col_lower or 'amount' in col_lower:
                quantity_col = col
            elif 'article' in col_lower or 'sku' in col_lower or 'code' in col_lower:
                article_col = col
        
        orders = []
        for _, row in df.iterrows():
            # Skip empty rows
            if row.isna().all():
                continue
            
            product_name = None
            article_number = None
            quantity = None
            
            # Get article number if available
            if article_col and pd.notna(row[article_col]):
                article_number = str(row[article_col]).strip()
            
            # Get product name
            if product_col and pd.notna(row[product_col]):
                product_name = str(row[product_col]).strip()
            
            # Get quantity
            if quantity_col and pd.notna(row[quantity_col]):
                try:
                    quantity = int(float(row[quantity_col]))
                except:
                    continue
            
            if (product_name or article_number) and quantity and quantity > 0:
                orders.append({
                    'product_name': product_name,
                    'article_number': article_number,
                    'quantity': quantity
                })
        
        return orders
    except Exception as e:
        raise Exception(f"Error parsing Excel file: {str(e)}")


def parse_csv_order(file_path):
    """Parse a CSV order file."""
    try:
        df = pd.read_csv(file_path)
            # Reuse the logic for identifying product and quantity columns from parse_excel_order
        # after loading as CSV
        
        # Try to identify columns
        product_col = None
        quantity_col = None
        article_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'product' in col_lower or 'item' in col_lower or 'name' in col_lower:
                product_col = col
            elif 'quantity' in col_lower or 'qty' in col_lower or 'amount' in col_lower:
                quantity_col = col
            elif 'article' in col_lower or 'sku' in col_lower or 'code' in col_lower:
                article_col = col
        
        orders = []
        for _, row in df.iterrows():
            if row.isna().all():
                continue
            
            product_name = None
            article_number = None
            quantity = None
            
            if article_col and pd.notna(row[article_col]):
                article_number = str(row[article_col]).strip()
            
            if product_col and pd.notna(row[product_col]):
                product_name = str(row[product_col]).strip()
            
            if quantity_col and pd.notna(row[quantity_col]):
                try:
                    quantity = int(float(row[quantity_col]))
                except:
                    continue
            
            if (product_name or article_number) and quantity and quantity > 0:
                orders.append({
                    'product_name': product_name,
                    'article_number': article_number,
                    'quantity': quantity
                })
        
        return orders
    except Exception as e:
        raise Exception(f"Error parsing CSV file: {str(e)}")


def parse_json_order(file_path):
    """Parse a JSON order file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Support different JSON structures
        orders = []
        
        # If data is a list
        if isinstance(data, list):
            items = data
        # If data is a dict with an 'items' or 'orders' key
        elif isinstance(data, dict):
            items = data.get('items', data.get('orders', data.get('products', [])))
        else:
            raise Exception("Unsupported JSON structure")
        
        for item in items:
            product_name = item.get('product', item.get('product_name', item.get('name', None)))
            article_number = item.get('article', item.get('article_number', item.get('sku', None)))
            quantity = item.get('quantity', item.get('qty', item.get('amount', 0)))
            
            if (product_name or article_number) and quantity and quantity > 0:
                orders.append({
                    'product_name': product_name,
                    'article_number': article_number,
                    'quantity': int(quantity)
                })
        
        return orders
    except Exception as e:
        raise Exception(f"Error parsing JSON file: {str(e)}")


def parse_text_order(file_path):
    """Parse a plain text order file."""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        orders = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Try to parse patterns like:
            # "Product Name, 5"
            # "Product Name: 5"
            # "5x Product Name"
            # "Article Number - 5"
            
            # Pattern 1: Article Number - Product Name, Quantity
            match = re.match(r'([A-Z0-9]+)\s*-\s*(.+?)[,: ]*(\d+)', line, re.IGNORECASE)
            if match:
                article_number = match.group(1).strip()
                product_name = match.group(2).strip()
                quantity = int(match.group(3))
                orders.append({
                    'product_name': product_name,
                    'article_number': article_number,
                    'quantity': quantity
                })
                continue

            # Pattern 2: Product Name, Quantity or Product Name: Quantity
            match = re.match(r'(.+?)[,: ]*(\d+)', line)
            if match:
                product_name = match.group(1).strip()
                quantity = int(match.group(2))
                orders.append({
                    'product_name': product_name,
                    'article_number': None,
                    'quantity': quantity
                })
                continue
            
            # Pattern 3: Quantity x Product Name or Quantity Product Name
            match = re.match(r'(\d+)\s*[x×]?\s*(.+)', line)
            if match:
                quantity = int(match.group(1))
                product_name = match.group(2).strip()
                orders.append({
                    'product_name': product_name,
                    'article_number': None,
                    'quantity': quantity
                })
                continue
        
        return orders
    except Exception as e:
        raise Exception(f"Error parsing text file: {str(e)}")


def process_order(orders):
    """
    Process and validate orders against the product catalog.
    Returns a list of validated orders with match information.
    """
    validated_orders = []
    
    for order in orders:
        article_number = order.get('article_number')
        product_name = order.get('product_name')
        quantity = order['quantity']
        
        # Validate quantity
        is_valid_qty, cleaned_qty, qty_warnings = validate_quantity(quantity)
        
        if not is_valid_qty:
            validated_orders.append({
                'original_product': product_name or article_number,
                'original_article': article_number,
                'matched_article': None,
                'matched_product': None,
                'quantity': 0,
                'match_score': 0,
                'match_method': None,
                'status': 'invalid_quantity',
                'warnings': qty_warnings
            })
            continue
        
        matched_article = None
        matched_product = None
        match_score = 0
        match_method = None
        
        # If article number is provided, try to match by article number first
        if article_number:
            if article_number in article_to_product:
                matched_article = article_number
                matched_product = article_to_product[article_number]
                match_score = 100
                match_method = "Article Number"
            else:
                # Try fuzzy match on article number
                article_list = list(article_to_product.keys())
                best_match = process.extractOne(article_number, article_list, scorer=fuzz.ratio)
                if best_match and best_match[1] >= 85:
                    matched_article = best_match[0]
                    matched_product = article_to_product[matched_article]
                    match_score = best_match[1]
                    match_method = "Fuzzy Article Number"
        
        # If no match yet and product name is provided, try to match by product name
        if not matched_article and product_name:
            matched_article, matched_product, match_score = fuzzy_match_product(product_name)
            if matched_article:
                match_method = "Product Name"
        
        # Check product availability in database
        product_warnings = []
        if matched_article:
            db_product = db.get_product_by_article(matched_article)
            if db_product:
                if not db_product['is_available']:
                    product_warnings.append("Product is marked as unavailable")
                if db_product['is_discontinued']:
                    product_warnings.append("Product is discontinued")
        
        all_warnings = qty_warnings + product_warnings
        
        validated_orders.append({
            'original_product': product_name or article_number,
            'original_article': article_number,
            'matched_article': matched_article,
            'matched_product': matched_product,
            'quantity': cleaned_qty,
            'match_score': match_score,
            'match_method': match_method,
            'status': 'matched' if matched_article else 'unmatched',
            'warnings': all_warnings if all_warnings else None
        })
    
    return validated_orders


def generate_erp_sheet(customer_id, validated_orders, output_filename):
    """
    Generate an ERP order sheet by filling the template.
    """
    try:
        workbook = openpyxl.load_workbook(ORDER_TEMPLATE_PATH)
        sheet = workbook.active
        
        # Set Customer ID in B1
        sheet["B1"] = customer_id
        
        # Create a mapping from Article Number to row index
        article_to_row = {}
        for row_idx in range(3, sheet.max_row + 1):
            article_number = sheet[f"B{row_idx}"].value
            if article_number:
                article_to_row[str(article_number).strip()] = row_idx
        
        # Fill in quantities for matched orders
        for order in validated_orders:
            if order['status'] == 'matched':
                article_number = order['matched_article']
                quantity = order['quantity']
                
                if article_number in article_to_row:
                    row_to_fill = article_to_row[article_number]
                    sheet[f"G{row_to_fill}"] = quantity
        
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        workbook.save(output_path)
        return output_path
    except Exception as e:
        raise Exception(f"Error generating ERP sheet: {str(e)}")


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'catalog_products': len(product_catalog),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/process-order', methods=['POST'])
def process_order_endpoint():
    """
    Process an order file and generate an ERP sheet.
    Accepts: Excel, CSV, JSON, or plain text files.
    """
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get customer ID from form data
        customer_id = request.form.get('customer_id', 'UNKNOWN')
        
        # Save uploaded file temporarily
        temp_filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        temp_path = os.path.join(OUTPUT_DIR, temp_filename)
        file.save(temp_path)
        
        # Determine file type and parse accordingly
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext in ['.xlsx', '.xls']:
            orders = parse_excel_order(temp_path)
        elif file_ext == '.csv':
            orders = parse_csv_order(temp_path)
        elif file_ext == '.json':
            orders = parse_json_order(temp_path)
        elif file_ext in ['.txt', '.text']:
            orders = parse_text_order(temp_path)
        else:
            os.remove(temp_path)
            return jsonify({'error': f'Unsupported file type: {file_ext}'}), 400
        
        # Process and validate orders
        validated_orders = process_order(orders)
        
        # Generate ERP sheet
        output_filename = f"order_{customer_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        erp_sheet_path = generate_erp_sheet(customer_id, validated_orders, output_filename)
        
        # Clean up temp file
        os.remove(temp_path)
        
        # Calculate statistics
        total_items = len(validated_orders)
        matched_items = sum(1 for order in validated_orders if order['status'] == 'matched')
        unmatched_items = total_items - matched_items
        
        statistics = {
            'total_items': total_items,
            'matched_items': matched_items,
            'unmatched_items': unmatched_items
        }
        
        # Save to order history
        order_id = db.save_order_to_history(customer_id, statistics, validated_orders, output_filename)
        
        return jsonify({
            'success': True,
            'customer_id': customer_id,
            'output_file': output_filename,
            'order_id': order_id,
            'statistics': statistics,
            'orders': validated_orders
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    """Download a generated ERP sheet."""
    try:
        file_path = os.path.join(OUTPUT_DIR, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/process-text-order', methods=['POST'])
def process_text_order_endpoint():
    """
    Process an order from text input (e.g., copy-pasted from email).
    Accepts JSON with 'text' and 'customer_id' fields.
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400
        
        text_content = data.get('text', '')
        customer_id = data.get('customer_id', 'UNKNOWN')
        
        if not text_content.strip():
            return jsonify({'error': 'Text content is empty'}), 400
        
        # Save text to a temporary file
        temp_filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_text_order.txt"
        temp_path = os.path.join(OUTPUT_DIR, temp_filename)
        
        with open(temp_path, 'w') as f:
            f.write(text_content)
        
        # Parse the text order
        orders = parse_text_order(temp_path)
        
        # Clean up temp file
        os.remove(temp_path)
        
        # Process and validate orders
        validated_orders = process_order(orders)
        
        # Generate ERP sheet
        output_filename = f"order_{customer_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        erp_sheet_path = generate_erp_sheet(customer_id, validated_orders, output_filename)
        
        # Calculate statistics
        total_items = len(validated_orders)
        matched_items = sum(1 for order in validated_orders if order['status'] == 'matched')
        unmatched_items = total_items - matched_items
        
        statistics = {
            'total_items': total_items,
            'matched_items': matched_items,
            'unmatched_items': unmatched_items
        }
        
        # Save to order history
        order_id = db.save_order_to_history(customer_id, statistics, validated_orders, output_filename)
        
        return jsonify({
            'success': True,
            'customer_id': customer_id,
            'output_file': output_filename,
            'order_id': order_id,
            'statistics': statistics,
            'orders': validated_orders
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/search-product', methods=['GET'])
def search_product():
    """Search for products in the catalog."""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'results': []})
    
    # Fuzzy search
    product_list = list(article_to_product.values())
    matches = process.extract(query, product_list, scorer=fuzz.token_sort_ratio, limit=10)
    
    results = []
    for match in matches:
        if match[1] >= 60:  # Minimum score threshold
            product_name = match[0]
            article_number = product_to_article[product_name]
            results.append({
                'article_number': article_number,
                'product_name': product_name,
                'score': match[1]
            })
    
    return jsonify({'results': results})


@app.route('/api/order-history', methods=['GET'])
def get_order_history_endpoint():
    """Get order history with pagination."""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        orders = db.get_order_history(limit, offset)
        return jsonify({'success': True, 'orders': orders})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/order-details/<int:order_id>', methods=['GET'])
def get_order_details_endpoint(order_id):
    """Get detailed information about a specific order."""
    try:
        order = db.get_order_details(order_id)
        if order:
            return jsonify({'success': True, 'order': order})
        else:
            return jsonify({'error': 'Order not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/products', methods=['GET'])
def get_products_endpoint():
    """Get all products from the database."""
    try:
        products = db.get_all_products()
        return jsonify({'success': True, 'products': products})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/products', methods=['POST'])
def add_product_endpoint():
    """Add a new product to the catalog."""
    try:
        data = request.get_json()
        
        article_number = data.get('article_number')
        product_name = data.get('product_name')
        category = data.get('category')
        synonyms = data.get('synonyms', [])
        
        if not article_number or not product_name:
            return jsonify({'error': 'Article number and product name are required'}), 400
        
        success, message = db.add_product(article_number, product_name, category, synonyms)
        
        if success:
            # Reload product catalog
            global product_catalog, article_to_product, product_to_article
            product_catalog = pd.read_csv(PRODUCT_CATALOG_PATH)
            product_catalog.columns = product_catalog.columns.str.strip()
            article_to_product = dict(zip(product_catalog['Article Number'], product_catalog['Product']))
            product_to_article = dict(zip(product_catalog['Product'], product_catalog['Article Number']))
            
            # Also add to CSV file
            with open(PRODUCT_CATALOG_PATH, 'a') as f:
                f.write(f'\n{article_number},{product_name}')
            
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/products/<article_number>', methods=['PUT'])
def update_product_endpoint(article_number):
    """Update an existing product."""
    try:
        data = request.get_json()
        
        product_name = data.get('product_name')
        category = data.get('category')
        is_available = data.get('is_available')
        is_discontinued = data.get('is_discontinued')
        synonyms = data.get('synonyms')
        
        success, message = db.update_product(
            article_number, 
            product_name, 
            category, 
            is_available, 
            is_discontinued, 
            synonyms
        )
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/product-statistics', methods=['GET'])
def get_product_statistics_endpoint():
    """Get statistics about product matching."""
    try:
        stats = db.get_product_statistics()
        return jsonify({'success': True, 'statistics': stats})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("Order Processing System - Backend Server")
    print("=" * 60)
    print(f"Product Catalog: {len(product_catalog)} products loaded")
    print(f"Server starting on http://localhost:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
