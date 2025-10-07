"""
Enhanced Order Parsing Engine
Addresses all regex, quantity validation, and column detection issues
"""

import re
import logging
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MatchMethod(Enum):
    """Enumeration of matching methods for auditing"""
    EXACT_ARTICLE = "exact_article"
    EXACT_PRODUCT = "exact_product"
    FUZZY_ARTICLE = "fuzzy_article"
    FUZZY_PRODUCT = "fuzzy_product"
    SYNONYM_MATCH = "synonym_match"
    TOKEN_ENHANCED = "token_enhanced"


class ParseWarning(Enum):
    """Enumeration of parsing warnings"""
    DECIMAL_ROUNDED = "decimal_rounded"
    HIGH_QUANTITY = "high_quantity"
    LOW_QUANTITY = "low_quantity"
    PRODUCT_UNAVAILABLE = "product_unavailable"
    PRODUCT_DISCONTINUED = "product_discontinued"
    AMBIGUOUS_MATCH = "ambiguous_match"
    WEAK_MATCH = "weak_match"


@dataclass
class ParsedOrder:
    """Data class for parsed order with full metadata"""
    original_text: str
    product_name: Optional[str]
    article_number: Optional[str]
    quantity: int
    matched_article: Optional[str]
    matched_product: Optional[str]
    match_score: int
    match_method: Optional[MatchMethod]
    status: str
    warnings: List[str]
    metadata: Dict[str, Any]


class QuantityValidator:
    """Handles all quantity validation logic"""
    
    @staticmethod
    def validate(quantity: Any) -> Tuple[bool, int, List[str]]:
        """
        Validate quantity and return validation result with warnings.
        
        Args:
            quantity: The quantity value to validate
            
        Returns:
            Tuple of (is_valid, cleaned_quantity, warnings)
        """
        warnings = []
        
        try:
            # Convert to float first to handle decimals
            qty_float = float(quantity)
            
            # Check for negative numbers
            if qty_float < 0:
                return False, 0, ["Negative quantity is not allowed"]
            
            # Check for fractional quantities between 0 and 1
            if 0 < qty_float < 1:
                return False, 0, [f"Fractional quantity ({qty_float}) between 0 and 1 is invalid"]
            
            # Round decimal quantities
            if qty_float != int(qty_float):
                original_qty = qty_float
                qty_float = round(qty_float)
                warnings.append(f"{ParseWarning.DECIMAL_ROUNDED.value}: {original_qty} → {qty_float}")
            
            qty_int = int(qty_float)
            
            # Re-run zero check after rounding
            if qty_int == 0:
                return False, 0, ["Quantity cannot be zero (after rounding)"]
            
            # Check for unusually high quantities
            if qty_int > 100:
                warnings.append(f"{ParseWarning.HIGH_QUANTITY.value}: {qty_int}")
            
            # Check for unusually low quantities (but valid)
            if 1 <= qty_int <= 2:
                warnings.append(f"{ParseWarning.LOW_QUANTITY.value}: {qty_int}")
            
            return True, qty_int, warnings
            
        except (ValueError, TypeError):
            return False, 0, [f"Invalid quantity format: {quantity}"]


class RegexPatterns:
    """Centralized regex patterns with proper anchoring"""
    
    # Pattern 1: Article Number - Product Name, Quantity (at end of line)
    # Anchored to ensure quantity is at the end
    ARTICLE_PRODUCT_QTY = re.compile(
        r'^([A-Z0-9]+)\s*-\s*(.+?)[,:\s]+(\d+)\s*$',
        re.IGNORECASE
    )
    
    # Pattern 2: Product Name, Quantity (anchored to end)
    # This prevents "Rakza 9 Black (2.0 mm)" from matching 9 as quantity
    PRODUCT_QTY_DELIMITED = re.compile(
        r'^(.+?)[,:\s]+(\d+)\s*$'
    )
    
    # Pattern 3: Quantity x Product Name or Quantity Product Name
    QTY_PRODUCT = re.compile(
        r'^(\d+)\s*[x×]?\s*(.+)$',
        re.IGNORECASE
    )
    
    # Pattern 4: Product Name (Size/Color) - extract tokens
    SIZE_COLOR_TOKENS = re.compile(
        r'\(([^)]+)\)|(\d+\.?\d*\s*mm)|(\d+\.?\d*")|'
        r'(black|red|blue|green|white|yellow|orange|purple|pink|brown|grey|gray)',
        re.IGNORECASE
    )


class ColumnDetector:
    """Improved column detection with preference for strong matches"""
    
    # Strong match keywords (exact matches preferred)
    STRONG_PRODUCT_KEYWORDS = ['product', 'item', 'name', 'artikel', 'produkt']
    STRONG_ARTICLE_KEYWORDS = ['article', 'sku', 'code', 'artikelnummer', 'artikelnr']
    STRONG_QUANTITY_KEYWORDS = ['quantity', 'qty', 'amount', 'menge', 'anzahl']
    
    # Weak match keywords (fallback)
    WEAK_PRODUCT_KEYWORDS = ['description', 'desc', 'title']
    WEAK_ARTICLE_KEYWORDS = ['id', 'number', 'nr', 'no']
    WEAK_QUANTITY_KEYWORDS = ['count', 'num', 'pieces']
    
    @classmethod
    def detect_columns(cls, columns: List[str]) -> Dict[str, Optional[str]]:
        """
        Detect product, article, and quantity columns with preference for strong matches.
        
        Args:
            columns: List of column names
            
        Returns:
            Dictionary with detected column names
        """
        result = {
            'product_col': None,
            'article_col': None,
            'quantity_col': None
        }
        
        # Track match strength
        match_strength = {
            'product_col': 0,
            'article_col': 0,
            'quantity_col': 0
        }
        
        for col in columns:
            col_lower = str(col).lower().strip()
            
            # Check for product column
            for keyword in cls.STRONG_PRODUCT_KEYWORDS:
                if keyword in col_lower:
                    if match_strength['product_col'] < 2:
                        result['product_col'] = col
                        match_strength['product_col'] = 2
                    break
            
            if match_strength['product_col'] < 2:
                for keyword in cls.WEAK_PRODUCT_KEYWORDS:
                    if keyword in col_lower and match_strength['product_col'] < 1:
                        result['product_col'] = col
                        match_strength['product_col'] = 1
                        break
            
            # Check for article column
            for keyword in cls.STRONG_ARTICLE_KEYWORDS:
                if keyword in col_lower:
                    if match_strength['article_col'] < 2:
                        result['article_col'] = col
                        match_strength['article_col'] = 2
                    break
            
            if match_strength['article_col'] < 2:
                for keyword in cls.WEAK_ARTICLE_KEYWORDS:
                    if keyword in col_lower and match_strength['article_col'] < 1:
                        result['article_col'] = col
                        match_strength['article_col'] = 1
                        break
            
            # Check for quantity column
            for keyword in cls.STRONG_QUANTITY_KEYWORDS:
                if keyword in col_lower:
                    if match_strength['quantity_col'] < 2:
                        result['quantity_col'] = col
                        match_strength['quantity_col'] = 2
                    break
            
            if match_strength['quantity_col'] < 2:
                for keyword in cls.WEAK_QUANTITY_KEYWORDS:
                    if keyword in col_lower and match_strength['quantity_col'] < 1:
                        result['quantity_col'] = col
                        match_strength['quantity_col'] = 1
                        break
        
        # Log detection results
        logger.info(f"Column detection: {result}")
        logger.info(f"Match strengths: {match_strength}")
        
        return result


class TextOrderParser:
    """Enhanced text order parser with improved regex patterns"""
    
    @staticmethod
    def parse_line(line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single line of text order with improved regex patterns.
        
        Args:
            line: The line to parse
            
        Returns:
            Dictionary with parsed data or None if no match
        """
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith('#'):
            return None
        
        metadata = {
            'original_line': line,
            'regex_used': None
        }
        
        # Try Pattern 1: Article Number - Product Name, Quantity
        match = RegexPatterns.ARTICLE_PRODUCT_QTY.match(line)
        if match:
            metadata['regex_used'] = 'ARTICLE_PRODUCT_QTY'
            return {
                'article_number': match.group(1).strip(),
                'product_name': match.group(2).strip(),
                'quantity': match.group(3),
                'metadata': metadata
            }
        
        # Try Pattern 2: Product Name, Quantity (with proper anchoring)
        match = RegexPatterns.PRODUCT_QTY_DELIMITED.match(line)
        if match:
            product_part = match.group(1).strip()
            quantity_part = match.group(2)
            
            # Additional validation: ensure the quantity isn't part of the product name
            # Check if there's a clear delimiter before the quantity
            if any(delim in line for delim in [',', ':', '\t']):
                # Find the last delimiter
                last_delim_pos = max(
                    line.rfind(','),
                    line.rfind(':'),
                    line.rfind('\t')
                )
                
                # Extract product and quantity based on delimiter
                if last_delim_pos > 0:
                    product_part = line[:last_delim_pos].strip()
                    quantity_part = line[last_delim_pos + 1:].strip()
                    
                    # Verify quantity_part is purely numeric
                    if quantity_part.isdigit():
                        metadata['regex_used'] = 'PRODUCT_QTY_DELIMITED'
                        return {
                            'article_number': None,
                            'product_name': product_part,
                            'quantity': quantity_part,
                            'metadata': metadata
                        }
        
        # Try Pattern 3: Quantity x Product Name
        match = RegexPatterns.QTY_PRODUCT.match(line)
        if match:
            metadata['regex_used'] = 'QTY_PRODUCT'
            return {
                'article_number': None,
                'product_name': match.group(2).strip(),
                'quantity': match.group(1),
                'metadata': metadata
            }
        
        # No match found
        logger.warning(f"Could not parse line: {line}")
        return None
    
    @staticmethod
    def extract_tokens(text: str) -> List[str]:
        """
        Extract size/color tokens from product text for enhanced matching.
        
        Args:
            text: The product text
            
        Returns:
            List of extracted tokens
        """
        tokens = []
        matches = RegexPatterns.SIZE_COLOR_TOKENS.finditer(text)
        
        for match in matches:
            for group in match.groups():
                if group:
                    tokens.append(group.lower().strip())
        
        return tokens


class ParsingAuditor:
    """Handles logging and auditing of parsing decisions"""
    
    @staticmethod
    def log_parsing_decision(
        input_data: Dict[str, Any],
        result: ParsedOrder,
        context: Dict[str, Any]
    ) -> None:
        """
        Log a parsing decision with structured metadata.
        
        Args:
            input_data: Original input data
            result: Parsed order result
            context: Additional context information
        """
        log_entry = {
            'timestamp': context.get('timestamp'),
            'input': input_data,
            'output': {
                'matched_article': result.matched_article,
                'matched_product': result.matched_product,
                'quantity': result.quantity,
                'match_score': result.match_score,
                'match_method': result.match_method.value if result.match_method else None,
                'status': result.status
            },
            'warnings': result.warnings,
            'metadata': result.metadata,
            'context': context
        }
        
        logger.info(f"Parsing decision: {log_entry}")
        
        # In production, this would write to a structured log file or database
        # For now, we'll just log to console