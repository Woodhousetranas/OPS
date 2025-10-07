"""
Improved Order Processing System
Integrates all enhancements: better parsing, caching, versioning, synonym management
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import openpyxl
import json
import os
from datetime import datetime
from fuzzywuzzy import fuzz, process
import re
import logging

# Import our new modules
import database as db
from parsing_engine import (
    QuantityValidator, RegexPatterns, ColumnDetector, 
    TextOrderParser, ParsingAuditor, ParsedOrder, MatchMethod
)
from product_matcher import (
    ProductCache, EnhancedProductMatcher, SynonymManager
)
from unmatched_tracker import (
    UnmatchedTracker, UnmatchedReason, UnmatchedAnalyzer
)
from product_versioning import ProductVersionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# Initialize global components
product_cache = ProductCache()
synonym_manager = SynonymManager(db)
version_manager = ProductVersionManager(db)
product_matcher = EnhancedProductMatcher(product_cache)

# Load and cache product catalog
def refresh_product_cache():
    """Refresh the product cache from CSV and database"""
    try:
        # Load from CSV
        product_catalog = pd.read_csv(PRODUCT_CATALOG_PATH)
        product_catalog.columns = product_catalog.columns.str.strip()
        
        products_data = product_catalog.to_dict('records')
        
        # Load from database (for synonyms)
        db_products = db.get_all_products()
        
        # Refresh cache
        product_cache.refresh(products_data, db_products)
        
        logger.info(f"Product cache refreshed: {product_cache.get_cache_info()}")
        
    except Exception as e:
        logger.error(f"Error refreshing product cache: {e}")
        raise

# Initial cache load
refresh_product_cache()


def validate_quantity(quantity):
    """Validate quantity using the new validator"""
    return QuantityValidator.validate(quantity)


def fuzzy_match_product(input_product, input_article=None, threshold=80):
    """
    Enhanced fuzzy matching using the new product matcher.
    Returns: (article_number, product_name, score, method)
    """
    article, product, score, method = product_matcher.match_product(
        input_product, input_article, threshold
    )
    
    # Track synonym usage if it was a synonym match
    if method == 'synonym_match' and input_product:
        synonym_manager.track_usage(input_product)
    
    # Suggest synonym if it's a good fuzzy match
    if article and 85 <= score < 100 and input_product:
        synonym_manager.suggest_synonym(
            input_product, article, product, score
        )
    
    return article, product, score, method


def parse_excel_order(file_path):
    """Parse an Excel order file with improved column detection."""
    try:
        df = pd.read_excel(file_path)
        
        # Use improved column detector
        detected_cols = ColumnDetector.detect_columns(df.columns.tolist())
        
        product_col = detected_cols['product_col']
        quantity_col = detected_cols['quantity_col']
        article_col = detected_cols['article_col']
        
        logger.info(f"Detected columns: {detected_cols}")
        
        orders = []
        for idx, row in df.iterrows():
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
                quantity = row[quantity_col]
            
            if (product_name or article_number) and quantity is not None:
                orders.append({
                    'product_name': product_name,
                    'article_number': article_number,
                    'quantity': quantity,
                    'row_number': idx + 2,  # Excel row number (1-indexed + header)
                    'source': 'excel'
                })
        
        return orders
    except Exception as e:
        raise Exception(f"Error parsing Excel file: {str(e)}")


def parse_csv_order(file_path):
    """Parse a CSV order file with improved column detection."""
    try:
        df = pd.read_csv(file_path)
        
        # Use improved column detector
        detected_cols = ColumnDetector.detect_columns(df.columns.tolist())
        
        product_col = detected_cols['product_col']
        quantity_col = detected_cols['quantity_col']
        article_col = detected_cols['article_col']
        
        logger.info(f"Detected columns: {detected_cols}")
        
        orders = []
        for idx, row in df.iterrows():
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
                quantity = row[quantity_col]
            
            if (product_name or article_number) and quantity is not None:
                orders.append({
                    'product_name': product_name,
                    'article_number': article_number,
                    'quantity': quantity,
                    'row_number': idx + 2,
                    'source': 'csv'
                })
        
        return orders
    except Exception as e:
        raise Exception(f"Error parsing CSV file: {str(e)}")


def parse_json_order(file_path):
    """Parse a JSON order file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        orders = []
        
        # Support different JSON structures
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('items', data.get('orders', data.get('products', [])))
        else:
            raise Exception("Unsupported JSON structure")
        
        for idx, item in enumerate(items):
            product_name = item.get('product', item.get('product_name', item.get('name', None)))
            article_number = item.get('article', item.get('article_number', item.get('sku', None)))
            quantity = item.get('quantity', item.get('qty', item.get('amount', None)))
            
            if (product_name or article_number) and quantity is not None:
                orders.append({
                    'product_name': product_name,
                    'article_number': article_number,
                    'quantity': quantity,
                    'row_number': idx + 1,
                    'source': 'json'
                })
        
        return orders
    except Exception as e:
        raise Exception(f"Error parsing JSON file: {str(e)}")


def parse_text_order(file_path):
    """Parse a plain text order file with improved regex patterns."""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        orders = []
        parser = TextOrderParser()
        
        for idx, line in enumerate(lines):
            parsed = parser.parse_line(line)
            
            if parsed:
                parsed['row_number'] = idx + 1
                parsed['source'] = 'text'
                orders.append(parsed)
        
        return orders
    except Exception as e:
        raise Exception(f"Error parsing text file: {str(e)}")


def process_order(orders):
    """
    Process and validate orders with enhanced tracking and logging.
    Returns validated orders and unmatched tracker.
    """
    validated_orders = []
    unmatched_tracker = UnmatchedTracker()
    auditor = ParsingAuditor()
    
    for order in orders:
        article_number = order.get('article_number')
        product_name = order.get('product_name')
        quantity = order.get('quantity')
        row_number = order.get('row_number', 0)
        metadata = order.get('metadata', {})
        
        # Validate quantity
        is_valid_qty, cleaned_qty, qty_warnings = validate_quantity(quantity)
        
        if not is_valid_qty:
            # Track as unmatched due to invalid quantity
            unmatched_tracker.add_unmatched(
                original_text=product_name or article_number or str(quantity),
                reason=UnmatchedReason.INVALID_QUANTITY,
                details={
                    'quantity': quantity,
                    'warnings': qty_warnings,
                    'row_number': row_number
                }
            )
            
            validated_orders.append({
                'original_product': product_name or article_number,
                'original_article': article_number,
                'matched_article': None,
                'matched_product': None,
                'quantity': 0,
                'match_score': 0,
                'match_method': None,
                'status': 'invalid_quantity',
                'warnings': qty_warnings,
                'row_number': row_number,
                'metadata': metadata
            })
            continue
        
        # Try to match product
        matched_article, matched_product, match_score, match_method = fuzzy_match_product(
            product_name, article_number
        )
        
        # Check product availability in database
        product_warnings = qty_warnings.copy()
        if matched_article:
            db_product = db.get_product_by_article(matched_article)
            if db_product:
                if not db_product['is_available']:
                    product_warnings.append("Product is marked as unavailable")
                if db_product['is_discontinued']:
                    product_warnings.append("Product is discontinued")
        
        # Determine status
        if not matched_article:
            status = 'unmatched'
            
            # Get suggestions for unmatched items
            suggestions = []
            if product_name:
                all_products = product_cache.get_all_products()
                product_names = [p['name'] for p in all_products]
                matches = process.extract(
                    product_name, product_names,
                    scorer=fuzz.token_sort_ratio, limit=5
                )
                
                for match in matches:
                    if match[1] >= 60:
                        articles = product_cache.get_articles_by_product(match[0])
                        if articles:
                            suggestions.append({
                                'product_name': match[0],
                                'article_number': articles[0],
                                'score': match[1]
                            })
            
            # Track as unmatched
            unmatched_tracker.add_unmatched(
                original_text=product_name or article_number,
                reason=UnmatchedReason.NO_MATCH_FOUND if match_score == 0 else UnmatchedReason.LOW_MATCH_SCORE,
                details={
                    'product_name': product_name,
                    'article_number': article_number,
                    'best_score': match_score,
                    'row_number': row_number
                },
                suggestions=suggestions
            )
        else:
            status = 'matched'
            
            # Track warnings if any
            if product_warnings:
                unmatched_tracker.add_warning(
                    matched_item={
                        'original_product': product_name or article_number,
                        'matched_article': matched_article,
                        'matched_product': matched_product,
                        'quantity': cleaned_qty,
                        'row_number': row_number
                    },
                    warnings=product_warnings
                )
        
        validated_order = {
            'original_product': product_name or article_number,
            'original_article': article_number,
            'matched_article': matched_article,
            'matched_product': matched_product,
            'quantity': cleaned_qty,
            'match_score': match_score,
            'match_method': match_method,
            'status': status,
            'warnings': product_warnings if product_warnings else None,
            'row_number': row_number,
            'metadata': metadata
        }
        
        validated_orders.append(validated_order)
        
        # Log parsing decision
        auditor.log_parsing_decision(
            input_data=order,
            result=ParsedOrder(
                original_text=product_name or article_number or '',
                product_name=product_name,
                article_number=article_number,
                quantity=cleaned_qty,
                matched_article=matched_article,
                matched_product=matched_product,
                match_score=match_score,
                match_method=MatchMethod(match_method) if match_method else None,
                status=status,
                warnings=product_warnings,
                metadata=metadata
            ),
            context={
                'timestamp': datetime.now().isoformat(),
                'row_number': row_number
            }
        )
    
    return validated_orders, unmatched_tracker


def generate_erp_sheet(customer_id, validated_orders, output_filename):
    """Generate an ERP order sheet by filling the template."""
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


def generate_unmatched_report(unmatched_tracker, output_filename):
    """Generate a detailed report of unmatched items."""
    try:
        # Generate JSON report
        json_filename = output_filename.replace('.xlsx', '_unmatched.json')
        json_path = os.path.join(OUTPUT_DIR, json_filename)
        unmatched_tracker.export_to_json(json_path)
        
        # Generate text report
        txt_filename = output_filename.replace('.xlsx', '_unmatched.txt')
        txt_path = os.path.join(OUTPUT_DIR, txt_filename)
        
        report = unmatched_tracker.generate_report()
        
        with open(txt_path, 'w') as f:
            f.write(report)
        
        return json_path, txt_path
    except Exception as e:
        logger.error(f"Error generating unmatched report: {e}")
        return None, None


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint with cache info."""
    cache_info = product_cache.get_cache_info()
    
    return jsonify({
        'status': 'healthy',
        'cache_info': cache_info,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/refresh-cache', methods=['POST'])
def refresh_cache_endpoint():
    """Manually refresh the product cache."""
    try:
        refresh_product_cache()
        return jsonify({
            'success': True,
            'message': 'Cache refreshed successfully',
            'cache_info': product_cache.get_cache_info()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/process-order', methods=['POST'])
def process_order_endpoint():
    """Process an order file and generate an ERP sheet."""
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
        validated_orders, unmatched_tracker = process_order(orders)
        
        # Generate ERP sheet
        output_filename = f"order_{customer_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        erp_sheet_path = generate_erp_sheet(customer_id, validated_orders, output_filename)
        
        # Generate unmatched report
        json_report, txt_report = generate_unmatched_report(unmatched_tracker, output_filename)
        
        # Clean up temp file
        os.remove(temp_path)
        
        # Calculate statistics
        total_items = len(validated_orders)
        matched_items = sum(1 for order in validated_orders if order['status'] == 'matched')
        unmatched_items = total_items - matched_items
        
        statistics = {
            'total_items': total_items,
            'matched_items': matched_items,
            'unmatched_items': unmatched_items,
            'unmatched_summary': unmatched_tracker.get_summary()
        }
        
        # Save to order history
        order_id = db.save_order_to_history(customer_id, statistics, validated_orders, output_filename)
        
        return jsonify({
            'success': True,
            'customer_id': customer_id,
            'output_file': output_filename,
            'unmatched_json': os.path.basename(json_report) if json_report else None,
            'unmatched_txt': os.path.basename(txt_report) if txt_report else None,
            'order_id': order_id,
            'statistics': statistics,
            'orders': validated_orders
        })
    
    except Exception as e:
        logger.error(f"Error processing order: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    """Download a generated file."""
    try:
        file_path = os.path.join(OUTPUT_DIR, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/synonyms/pending', methods=['GET'])
def get_pending_synonyms():
    """Get pending synonym suggestions."""
    try:
        pending = synonym_manager.get_pending_synonyms()
        return jsonify({
            'success': True,
            'pending_synonyms': pending,
            'count': len(pending)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/synonyms/approve', methods=['POST'])
def approve_synonym():
    """Approve a synonym suggestion."""
    try:
        data = request.get_json()
        synonym = data.get('synonym')
        article = data.get('article')
        
        if not synonym or not article:
            return jsonify({'error': 'Synonym and article are required'}), 400
        
        success = synonym_manager.approve_synonym(synonym, article)
        
        if success:
            # Refresh cache to include new synonym
            refresh_product_cache()
            
            return jsonify({
                'success': True,
                'message': f'Synonym "{synonym}" approved for article {article}'
            })
        else:
            return jsonify({'error': 'Failed to approve synonym'}), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/synonyms/reject', methods=['POST'])
def reject_synonym():
    """Reject a synonym suggestion."""
    try:
        data = request.get_json()
        synonym = data.get('synonym')
        article = data.get('article')
        
        if not synonym or not article:
            return jsonify({'error': 'Synonym and article are required'}), 400
        
        success = synonym_manager.reject_synonym(synonym, article)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Synonym "{synonym}" rejected'
            })
        else:
            return jsonify({'error': 'Synonym not found'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/synonyms/statistics', methods=['GET'])
def get_synonym_statistics():
    """Get synonym usage statistics."""
    try:
        stats = synonym_manager.get_usage_statistics()
        return jsonify({
            'success': True,
            'statistics': stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/products/history/<article_number>', methods=['GET'])
def get_product_history(article_number):
    """Get the complete history of a product."""
    try:
        history = version_manager.get_product_history(article_number)
        
        return jsonify({
            'success': True,
            'article_number': article_number,
            'history': [
                {
                    'version_id': v.version_id,
                    'product_name': v.product_name,
                    'category': v.category,
                    'is_available': v.is_available,
                    'is_discontinued': v.is_discontinued,
                    'synonyms': v.synonyms,
                    'version_created_at': v.version_created_at,
                    'change_reason': v.change_reason,
                    'changed_by': v.changed_by
                }
                for v in history
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/products/soft-delete', methods=['POST'])
def soft_delete_product():
    """Soft delete a product."""
    try:
        data = request.get_json()
        article_number = data.get('article_number')
        reason = data.get('reason')
        deleted_by = data.get('deleted_by')
        
        if not article_number:
            return jsonify({'error': 'Article number is required'}), 400
        
        success = version_manager.soft_delete_product(
            article_number, reason, deleted_by
        )
        
        if success:
            # Refresh cache
            refresh_product_cache()
            
            return jsonify({
                'success': True,
                'message': f'Product {article_number} soft deleted'
            })
        else:
            return jsonify({'error': 'Failed to soft delete product'}), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/products/restore', methods=['POST'])
def restore_product():
    """Restore a soft-deleted product."""
    try:
        data = request.get_json()
        article_number = data.get('article_number')
        reason = data.get('reason')
        restored_by = data.get('restored_by')
        
        if not article_number:
            return jsonify({'error': 'Article number is required'}), 400
        
        success = version_manager.restore_product(
            article_number, reason, restored_by
        )
        
        if success:
            # Refresh cache
            refresh_product_cache()
            
            return jsonify({
                'success': True,
                'message': f'Product {article_number} restored'
            })
        else:
            return jsonify({'error': 'Failed to restore product'}), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/products/explain-order', methods=['POST'])
def explain_old_order():
    """Explain an old order by showing product state at that time."""
    try:
        data = request.get_json()
        article_number = data.get('article_number')
        order_timestamp = data.get('order_timestamp')
        
        if not article_number or not order_timestamp:
            return jsonify({'error': 'Article number and timestamp are required'}), 400
        
        explanation = version_manager.explain_old_order(
            article_number, order_timestamp
        )
        
        return jsonify({
            'success': True,
            'explanation': explanation
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/products/changelog', methods=['GET'])
def get_changelog():
    """Get recent product changes."""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        changes = version_manager.get_change_log(limit, offset)
        
        return jsonify({
            'success': True,
            'changes': changes,
            'limit': limit,
            'offset': offset
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Keep existing endpoints from original app.py
@app.route('/api/process-text-order', methods=['POST'])
def process_text_order_endpoint():
    """Process an order from text input."""
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
        validated_orders, unmatched_tracker = process_order(orders)
        
        # Generate ERP sheet
        output_filename = f"order_{customer_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        erp_sheet_path = generate_erp_sheet(customer_id, validated_orders, output_filename)
        
        # Generate unmatched report
        json_report, txt_report = generate_unmatched_report(unmatched_tracker, output_filename)
        
        # Calculate statistics
        total_items = len(validated_orders)
        matched_items = sum(1 for order in validated_orders if order['status'] == 'matched')
        unmatched_items = total_items - matched_items
        
        statistics = {
            'total_items': total_items,
            'matched_items': matched_items,
            'unmatched_items': unmatched_items,
            'unmatched_summary': unmatched_tracker.get_summary()
        }
        
        # Save to order history
        order_id = db.save_order_to_history(customer_id, statistics, validated_orders, output_filename)
        
        return jsonify({
            'success': True,
            'customer_id': customer_id,
            'output_file': output_filename,
            'unmatched_json': os.path.basename(json_report) if json_report else None,
            'unmatched_txt': os.path.basename(txt_report) if txt_report else None,
            'order_id': order_id,
            'statistics': statistics,
            'orders': validated_orders
        })
    
    except Exception as e:
        logger.error(f"Error processing text order: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/search-product', methods=['GET'])
def search_product():
    """Search for products in the catalog."""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'results': []})
    
    # Use the cached product matcher
    all_products = product_cache.get_all_products()
    product_names = [p['name'] for p in all_products]
    
    matches = process.extract(query, product_names, scorer=fuzz.token_sort_ratio, limit=10)
    
    results = []
    for match in matches:
        if match[1] >= 60:  # Minimum score threshold
            product_name = match[0]
            articles = product_cache.get_articles_by_product(product_name)
            
            if articles:
                results.append({
                    'article_number': articles[0],
                    'product_name': product_name,
                    'score': match[1],
                    'all_articles': articles
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
            # Refresh cache
            refresh_product_cache()
            
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
        
        # Create version before update
        version_manager.create_version(
            article_number,
            change_reason=data.get('change_reason', 'Manual update'),
            changed_by=data.get('changed_by', 'API')
        )
        
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
            # Refresh cache
            refresh_product_cache()
            
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
    print("Improved Order Processing System - Backend Server")
    print("=" * 60)
    cache_info = product_cache.get_cache_info()
    print(f"Product Cache: {cache_info['total_products']} products loaded")
    print(f"Synonyms: {cache_info['total_synonyms']}")
    print(f"Cache Version: {cache_info['version']}")
    print(f"Server starting on http://localhost:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)