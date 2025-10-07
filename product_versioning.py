"""
Product Versioning and Soft Deletion
Maintains historical product information for audit trails
"""

import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ProductVersion:
    """Represents a version of a product"""
    version_id: int
    article_number: str
    product_name: str
    category: Optional[str]
    is_available: bool
    is_discontinued: bool
    synonyms: List[str]
    created_at: str
    updated_at: str
    version_created_at: str
    change_reason: Optional[str]
    changed_by: Optional[str]


class ProductVersionManager:
    """Manages product versioning and soft deletion"""
    
    def __init__(self, db_module):
        self.db = db_module
        self._ensure_version_table()
    
    def _ensure_version_table(self) -> None:
        """Ensure the product_versions table exists"""
        import sqlite3
        
        conn = sqlite3.connect(self.db.DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_versions (
                version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_number TEXT NOT NULL,
                product_name TEXT NOT NULL,
                category TEXT,
                is_available INTEGER DEFAULT 1,
                is_discontinued INTEGER DEFAULT 0,
                synonyms TEXT,
                created_at TEXT,
                updated_at TEXT,
                version_created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                change_reason TEXT,
                changed_by TEXT,
                FOREIGN KEY (article_number) REFERENCES products (article_number)
            )
        ''')
        
        # Create index for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_product_versions_article 
            ON product_versions(article_number)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_product_versions_created 
            ON product_versions(version_created_at)
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("Product versioning table initialized")
    
    def create_version(
        self,
        article_number: str,
        change_reason: Optional[str] = None,
        changed_by: Optional[str] = None
    ) -> int:
        """
        Create a new version of a product before making changes.
        
        Args:
            article_number: The article number
            change_reason: Reason for the change
            changed_by: User who made the change
            
        Returns:
            Version ID
        """
        import sqlite3
        
        # Get current product state
        product = self.db.get_product_by_article(article_number)
        
        if not product:
            logger.error(f"Product {article_number} not found")
            return -1
        
        conn = sqlite3.connect(self.db.DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO product_versions 
            (article_number, product_name, category, is_available, 
             is_discontinued, synonyms, created_at, updated_at, 
             change_reason, changed_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            product['article_number'],
            product['product_name'],
            product.get('category'),
            product.get('is_available', 1),
            product.get('is_discontinued', 0),
            product.get('synonyms'),
            product.get('created_at'),
            product.get('updated_at'),
            change_reason,
            changed_by
        ))
        
        version_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"Created version {version_id} for product {article_number}")
        
        return version_id
    
    def get_product_history(
        self,
        article_number: str
    ) -> List[ProductVersion]:
        """
        Get the complete history of a product.
        
        Args:
            article_number: The article number
            
        Returns:
            List of product versions
        """
        import sqlite3
        
        conn = sqlite3.connect(self.db.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM product_versions
            WHERE article_number = ?
            ORDER BY version_created_at DESC
        ''', (article_number,))
        
        versions = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            
            # Parse synonyms
            if row_dict.get('synonyms'):
                try:
                    row_dict['synonyms'] = json.loads(row_dict['synonyms'])
                except json.JSONDecodeError:
                    row_dict['synonyms'] = []
            else:
                row_dict['synonyms'] = []
            
            versions.append(ProductVersion(**row_dict))
        
        conn.close()
        
        return versions
    
    def get_product_at_time(
        self,
        article_number: str,
        timestamp: str
    ) -> Optional[ProductVersion]:
        """
        Get the product state at a specific time.
        
        Args:
            article_number: The article number
            timestamp: ISO format timestamp
            
        Returns:
            Product version at that time or None
        """
        import sqlite3
        
        conn = sqlite3.connect(self.db.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM product_versions
            WHERE article_number = ? 
            AND version_created_at <= ?
            ORDER BY version_created_at DESC
            LIMIT 1
        ''', (article_number, timestamp))
        
        row = cursor.fetchone()
        
        if row:
            row_dict = dict(row)
            
            # Parse synonyms
            if row_dict.get('synonyms'):
                try:
                    row_dict['synonyms'] = json.loads(row_dict['synonyms'])
                except json.JSONDecodeError:
                    row_dict['synonyms'] = []
            else:
                row_dict['synonyms'] = []
            
            conn.close()
            return ProductVersion(**row_dict)
        
        conn.close()
        return None
    
    def soft_delete_product(
        self,
        article_number: str,
        reason: Optional[str] = None,
        deleted_by: Optional[str] = None
    ) -> bool:
        """
        Soft delete a product (mark as discontinued).
        
        Args:
            article_number: The article number
            reason: Reason for deletion
            deleted_by: User who deleted it
            
        Returns:
            True if successful
        """
        # Create version before deletion
        self.create_version(
            article_number,
            change_reason=f"Soft deletion: {reason}" if reason else "Soft deletion",
            changed_by=deleted_by
        )
        
        # Mark as discontinued and unavailable
        success, message = self.db.update_product(
            article_number,
            is_available=False,
            is_discontinued=True
        )
        
        if success:
            logger.info(f"Soft deleted product {article_number}")
        else:
            logger.error(f"Failed to soft delete product {article_number}: {message}")
        
        return success
    
    def restore_product(
        self,
        article_number: str,
        reason: Optional[str] = None,
        restored_by: Optional[str] = None
    ) -> bool:
        """
        Restore a soft-deleted product.
        
        Args:
            article_number: The article number
            reason: Reason for restoration
            restored_by: User who restored it
            
        Returns:
            True if successful
        """
        # Create version before restoration
        self.create_version(
            article_number,
            change_reason=f"Restoration: {reason}" if reason else "Restoration",
            changed_by=restored_by
        )
        
        # Mark as available and not discontinued
        success, message = self.db.update_product(
            article_number,
            is_available=True,
            is_discontinued=False
        )
        
        if success:
            logger.info(f"Restored product {article_number}")
        else:
            logger.error(f"Failed to restore product {article_number}: {message}")
        
        return success
    
    def get_change_log(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """
        Get recent product changes.
        
        Args:
            limit: Maximum number of records
            offset: Offset for pagination
            
        Returns:
            List of change records
        """
        import sqlite3
        
        conn = sqlite3.connect(self.db.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                version_id,
                article_number,
                product_name,
                version_created_at,
                change_reason,
                changed_by
            FROM product_versions
            ORDER BY version_created_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        changes = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return changes
    
    def explain_old_order(
        self,
        article_number: str,
        order_timestamp: str
    ) -> Dict:
        """
        Explain an old order by showing product state at that time.
        
        Args:
            article_number: The article number
            order_timestamp: When the order was placed
            
        Returns:
            Dictionary with explanation
        """
        # Get product state at order time
        historical_product = self.get_product_at_time(
            article_number,
            order_timestamp
        )
        
        # Get current product state
        current_product = self.db.get_product_by_article(article_number)
        
        explanation = {
            'article_number': article_number,
            'order_timestamp': order_timestamp,
            'historical_state': asdict(historical_product) if historical_product else None,
            'current_state': current_product,
            'changes': []
        }
        
        # Identify changes
        if historical_product and current_product:
            if historical_product.product_name != current_product['product_name']:
                explanation['changes'].append({
                    'field': 'product_name',
                    'old_value': historical_product.product_name,
                    'new_value': current_product['product_name']
                })
            
            if historical_product.is_available != current_product['is_available']:
                explanation['changes'].append({
                    'field': 'is_available',
                    'old_value': historical_product.is_available,
                    'new_value': current_product['is_available']
                })
            
            if historical_product.is_discontinued != current_product['is_discontinued']:
                explanation['changes'].append({
                    'field': 'is_discontinued',
                    'old_value': historical_product.is_discontinued,
                    'new_value': current_product['is_discontinued']
                })
        
        return explanation