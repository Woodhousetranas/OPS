import sqlite3
import json
from datetime import datetime
import os

DB_PATH = "order_processing.db"

def init_database():
    """Initialize the database with required tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create order history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_items INTEGER,
            matched_items INTEGER,
            unmatched_items INTEGER,
            output_file TEXT,
            order_data TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create product catalog table with additional fields
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_number TEXT UNIQUE NOT NULL,
            product_name TEXT NOT NULL,
            category TEXT,
            is_available INTEGER DEFAULT 1,
            is_discontinued INTEGER DEFAULT 0,
            synonyms TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create order items table for detailed tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            original_product TEXT,
            matched_article TEXT,
            matched_product TEXT,
            quantity INTEGER,
            match_score INTEGER,
            match_method TEXT,
            status TEXT,
            FOREIGN KEY (order_id) REFERENCES order_history (id)
        )
    ''')
    
    # Create product matching statistics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_stats (
            article_number TEXT PRIMARY KEY,
            match_count INTEGER DEFAULT 0,
            last_matched DATETIME,
            FOREIGN KEY (article_number) REFERENCES products (article_number)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

def save_order_to_history(customer_id, statistics, orders, output_file):
    """Save processed order to history."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Insert order history
    cursor.execute('''
        INSERT INTO order_history 
        (customer_id, total_items, matched_items, unmatched_items, output_file, order_data)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        customer_id,
        statistics['total_items'],
        statistics['matched_items'],
        statistics['unmatched_items'],
        output_file,
        json.dumps(orders)
    ))
    
    order_id = cursor.lastrowid
    
    # Insert order items
    for order in orders:
        cursor.execute('''
            INSERT INTO order_items
            (order_id, original_product, matched_article, matched_product, 
             quantity, match_score, match_method, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_id,
            order.get('original_product'),
            order.get('matched_article'),
            order.get('matched_product'),
            order.get('quantity'),
            order.get('match_score', 0),
            order.get('match_method'),
            order.get('status')
        ))
        
        # Update product statistics
        if order.get('status') == 'matched' and order.get('matched_article'):
            cursor.execute('''
                INSERT INTO product_stats (article_number, match_count, last_matched)
                VALUES (?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(article_number) DO UPDATE SET
                    match_count = match_count + 1,
                    last_matched = CURRENT_TIMESTAMP
            ''', (order['matched_article'],))
    
    conn.commit()
    conn.close()
    
    return order_id

def get_order_history(limit=50, offset=0):
    """Retrieve order history with pagination."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM order_history
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    
    orders = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return orders

def get_order_details(order_id):
    """Get detailed information about a specific order."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get order header
    cursor.execute('SELECT * FROM order_history WHERE id = ?', (order_id,))
    order = dict(cursor.fetchone())
    
    # Get order items
    cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order_id,))
    order['items'] = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return order

def add_product(article_number, product_name, category=None, synonyms=None):
    """Add a new product to the catalog."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO products (article_number, product_name, category, synonyms)
            VALUES (?, ?, ?, ?)
        ''', (article_number, product_name, category, json.dumps(synonyms) if synonyms else None))
        
        conn.commit()
        conn.close()
        return True, "Product added successfully"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Product with this article number already exists"
    except Exception as e:
        conn.close()
        return False, str(e)

def update_product(article_number, product_name=None, category=None, 
                   is_available=None, is_discontinued=None, synonyms=None):
    """Update an existing product."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if product_name is not None:
        updates.append("product_name = ?")
        params.append(product_name)
    if category is not None:
        updates.append("category = ?")
        params.append(category)
    if is_available is not None:
        updates.append("is_available = ?")
        params.append(1 if is_available else 0)
    if is_discontinued is not None:
        updates.append("is_discontinued = ?")
        params.append(1 if is_discontinued else 0)
    if synonyms is not None:
        updates.append("synonyms = ?")
        params.append(json.dumps(synonyms))
    
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(article_number)
    
    query = f"UPDATE products SET {', '.join(updates)} WHERE article_number = ?"
    cursor.execute(query, params)
    
    conn.commit()
    conn.close()
    
    return True, "Product updated successfully"

def get_all_products():
    """Get all products from the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM products ORDER BY product_name')
    products = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return products

def get_product_by_article(article_number):
    """Get a specific product by article number."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM products WHERE article_number = ?', (article_number,))
    row = cursor.fetchone()
    product = dict(row) if row else None
    
    conn.close()
    return product

def get_product_statistics():
    """Get statistics about product matching."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Most matched products
    cursor.execute('''
        SELECT p.article_number, p.product_name, ps.match_count, ps.last_matched
        FROM products p
        LEFT JOIN product_stats ps ON p.article_number = ps.article_number
        ORDER BY ps.match_count DESC
        LIMIT 20
    ''')
    most_matched = [dict(row) for row in cursor.fetchall()]
    
    # Never matched products
    cursor.execute('''
        SELECT p.article_number, p.product_name
        FROM products p
        LEFT JOIN product_stats ps ON p.article_number = ps.article_number
        WHERE ps.match_count IS NULL OR ps.match_count = 0
        ORDER BY p.product_name
        LIMIT 20
    ''')
    never_matched = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        'most_matched': most_matched,
        'never_matched': never_matched
    }

if __name__ == '__main__':
    init_database()
