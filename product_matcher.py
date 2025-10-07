"""
Enhanced Product Matching Engine
Handles multi-candidate matching, caching, and synonym management
"""

import json
import logging
from typing import List, Dict, Tuple, Optional, Set
from datetime import datetime
from fuzzywuzzy import fuzz, process
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


class ProductCache:
    """Thread-safe cache for product data with refresh capability"""
    
    def __init__(self):
        self._lock = threading.RLock()
        self._article_to_products = defaultdict(list)  # Article -> List of product variants
        self._product_to_articles = defaultdict(list)  # Product -> List of article numbers
        self._synonym_map = {}  # Synonym -> (article, product, score)
        self._all_products = []
        self._last_refresh = None
        self._version = 0
    
    def refresh(self, products_data: List[Dict], db_products: List[Dict]) -> None:
        """
        Refresh the cache with new product data.
        
        Args:
            products_data: List of products from CSV
            db_products: List of products from database with synonyms
        """
        with self._lock:
            self._article_to_products.clear()
            self._product_to_articles.clear()
            self._synonym_map.clear()
            self._all_products = []
            
            # Build article -> products mapping (handles duplicates)
            for product in products_data:
                article = product.get('Article Number')
                name = product.get('Product')
                
                if article and name:
                    self._article_to_products[article].append({
                        'article': article,
                        'name': name,
                        'source': 'csv'
                    })
                    self._product_to_articles[name].append(article)
                    self._all_products.append({
                        'article': article,
                        'name': name
                    })
            
            # Build synonym map from database
            for db_product in db_products:
                article = db_product.get('article_number')
                name = db_product.get('product_name')
                synonyms_json = db_product.get('synonyms')
                
                if synonyms_json:
                    try:
                        synonyms = json.loads(synonyms_json)
                        for synonym in synonyms:
                            self._synonym_map[synonym.lower()] = {
                                'article': article,
                                'product': name,
                                'score': 100
                            }
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid synonyms JSON for {article}")
            
            self._last_refresh = datetime.now()
            self._version += 1
            
            logger.info(f"Cache refreshed: {len(self._all_products)} products, "
                       f"{len(self._synonym_map)} synonyms, version {self._version}")
    
    def get_products_by_article(self, article: str) -> List[Dict]:
        """Get all product variants for an article number"""
        with self._lock:
            return self._article_to_products.get(article, [])
    
    def get_articles_by_product(self, product: str) -> List[str]:
        """Get all article numbers for a product name"""
        with self._lock:
            return self._product_to_articles.get(product, [])
    
    def get_all_products(self) -> List[Dict]:
        """Get all products"""
        with self._lock:
            return self._all_products.copy()
    
    def get_synonym_match(self, text: str) -> Optional[Dict]:
        """Check if text matches a known synonym"""
        with self._lock:
            return self._synonym_map.get(text.lower())
    
    def get_cache_info(self) -> Dict:
        """Get cache statistics"""
        with self._lock:
            return {
                'version': self._version,
                'last_refresh': self._last_refresh.isoformat() if self._last_refresh else None,
                'total_products': len(self._all_products),
                'total_synonyms': len(self._synonym_map),
                'unique_articles': len(self._article_to_products),
                'unique_product_names': len(self._product_to_articles)
            }


class TokenMatcher:
    """Handles token-based matching for size/color variants"""
    
    @staticmethod
    def extract_tokens(text: str) -> Set[str]:
        """Extract meaningful tokens from product text"""
        import re
        
        tokens = set()
        
        # Extract sizes (e.g., "2.0 mm", "2.0mm", "2.0")
        size_patterns = [
            r'(\d+\.?\d*)\s*mm',
            r'(\d+\.?\d*)\s*"',
            r'\((\d+\.?\d*)\)',
        ]
        
        for pattern in size_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            tokens.update(m.lower() for m in matches)
        
        # Extract colors
        colors = ['black', 'red', 'blue', 'green', 'white', 'yellow', 
                 'orange', 'purple', 'pink', 'brown', 'grey', 'gray']
        
        text_lower = text.lower()
        for color in colors:
            if color in text_lower:
                tokens.add(color)
        
        return tokens
    
    @staticmethod
    def token_similarity(tokens1: Set[str], tokens2: Set[str]) -> float:
        """Calculate similarity based on token overlap"""
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        return len(intersection) / len(union) if union else 0.0


class EnhancedProductMatcher:
    """Enhanced product matcher with multi-candidate support and caching"""
    
    def __init__(self, cache: ProductCache):
        self.cache = cache
        self.token_matcher = TokenMatcher()
    
    def match_product(
        self,
        input_product: Optional[str],
        input_article: Optional[str],
        threshold: int = 80
    ) -> Tuple[Optional[str], Optional[str], int, Optional[str]]:
        """
        Match a product with enhanced logic.
        
        Args:
            input_product: Product name to match
            input_article: Article number to match
            threshold: Minimum fuzzy match score
            
        Returns:
            Tuple of (matched_article, matched_product, score, method)
        """
        
        # Strategy 1: Exact article number match
        if input_article:
            products = self.cache.get_products_by_article(input_article)
            if products:
                # If multiple products for same article, try to disambiguate
                if len(products) == 1:
                    return (products[0]['article'], products[0]['name'], 
                           100, 'exact_article')
                elif input_product:
                    # Multiple candidates - use product name to choose best
                    best_match = self._choose_best_candidate(
                        input_product, products
                    )
                    if best_match:
                        return (best_match['article'], best_match['name'],
                               100, 'exact_article_disambiguated')
                else:
                    # No product name to disambiguate - return first
                    return (products[0]['article'], products[0]['name'],
                           100, 'exact_article_first')
        
        # Strategy 2: Exact product name match (case-insensitive)
        if input_product:
            articles = self.cache.get_articles_by_product(input_product)
            if articles:
                if len(articles) == 1:
                    return (articles[0], input_product, 100, 'exact_product')
                else:
                    # Multiple articles for same product name
                    # Try to use tokens to disambiguate
                    best_article = self._choose_best_article_by_tokens(
                        input_product, articles
                    )
                    if best_article:
                        return (best_article, input_product, 100, 
                               'exact_product_token_disambiguated')
                    else:
                        return (articles[0], input_product, 100, 
                               'exact_product_first')
        
        # Strategy 3: Synonym match
        if input_product:
            synonym_match = self.cache.get_synonym_match(input_product)
            if synonym_match:
                return (synonym_match['article'], synonym_match['product'],
                       synonym_match['score'], 'synonym_match')
        
        # Strategy 4: Fuzzy article number match
        if input_article:
            all_articles = list(self.cache._article_to_products.keys())
            if all_articles:
                best_match = process.extractOne(
                    input_article, all_articles, scorer=fuzz.ratio
                )
                if best_match and best_match[1] >= 85:
                    products = self.cache.get_products_by_article(best_match[0])
                    if products:
                        return (products[0]['article'], products[0]['name'],
                               best_match[1], 'fuzzy_article')
        
        # Strategy 5: Fuzzy product name match with token enhancement
        if input_product:
            all_products = self.cache.get_all_products()
            product_names = [p['name'] for p in all_products]
            
            # Get top fuzzy matches
            matches = process.extract(
                input_product, product_names, 
                scorer=fuzz.token_sort_ratio, limit=5
            )
            
            if matches:
                # Filter by threshold
                valid_matches = [m for m in matches if m[1] >= threshold]
                
                if valid_matches:
                    # If we have multiple good matches, use token matching
                    if len(valid_matches) > 1:
                        best_match = self._enhance_with_tokens(
                            input_product, valid_matches, all_products
                        )
                    else:
                        best_match = valid_matches[0]
                    
                    # Find the article for this product
                    matched_product = best_match[0]
                    articles = self.cache.get_articles_by_product(matched_product)
                    
                    if articles:
                        if len(articles) > 1:
                            # Multiple articles - try token disambiguation
                            best_article = self._choose_best_article_by_tokens(
                                input_product, articles
                            )
                            article = best_article if best_article else articles[0]
                        else:
                            article = articles[0]
                        
                        return (article, matched_product, best_match[1],
                               'fuzzy_product_token_enhanced')
        
        # No match found
        return None, None, 0, None
    
    def _choose_best_candidate(
        self, 
        input_product: str, 
        candidates: List[Dict]
    ) -> Optional[Dict]:
        """Choose best candidate from multiple products with same article"""
        
        # Use fuzzy matching to find best name match
        candidate_names = [c['name'] for c in candidates]
        best_match = process.extractOne(
            input_product, candidate_names, scorer=fuzz.token_sort_ratio
        )
        
        if best_match:
            for candidate in candidates:
                if candidate['name'] == best_match[0]:
                    return candidate
        
        return None
    
    def _choose_best_article_by_tokens(
        self,
        input_product: str,
        articles: List[str]
    ) -> Optional[str]:
        """Choose best article using token matching"""
        
        input_tokens = self.token_matcher.extract_tokens(input_product)
        
        if not input_tokens:
            return None
        
        best_article = None
        best_score = 0
        
        for article in articles:
            # Get all products for this article
            products = self.cache.get_products_by_article(article)
            
            for product in products:
                product_tokens = self.token_matcher.extract_tokens(
                    product['name']
                )
                score = self.token_matcher.token_similarity(
                    input_tokens, product_tokens
                )
                
                if score > best_score:
                    best_score = score
                    best_article = article
        
        return best_article if best_score > 0.5 else None
    
    def _enhance_with_tokens(
        self,
        input_product: str,
        fuzzy_matches: List[Tuple[str, int]],
        all_products: List[Dict]
    ) -> Tuple[str, int]:
        """Enhance fuzzy matches with token matching"""
        
        input_tokens = self.token_matcher.extract_tokens(input_product)
        
        best_match = fuzzy_matches[0]
        best_combined_score = fuzzy_matches[0][1]
        
        for match in fuzzy_matches:
            product_name = match[0]
            fuzzy_score = match[1]
            
            product_tokens = self.token_matcher.extract_tokens(product_name)
            token_score = self.token_matcher.token_similarity(
                input_tokens, product_tokens
            )
            
            # Combined score: 70% fuzzy + 30% token
            combined_score = (fuzzy_score * 0.7) + (token_score * 100 * 0.3)
            
            if combined_score > best_combined_score:
                best_combined_score = combined_score
                best_match = (product_name, int(combined_score))
        
        return best_match


class SynonymManager:
    """Manages synonym learning and tracking"""
    
    def __init__(self, db_module):
        self.db = db_module
        self.pending_synonyms = []  # Synonyms awaiting approval
        self.usage_stats = defaultdict(int)  # Track synonym usage frequency
    
    def suggest_synonym(
        self,
        original_text: str,
        matched_article: str,
        matched_product: str,
        match_score: int
    ) -> None:
        """
        Suggest a new synonym based on successful fuzzy match.
        
        Args:
            original_text: The original input text
            matched_article: The matched article number
            matched_product: The matched product name
            match_score: The match score
        """
        
        # Only suggest if it's a good fuzzy match but not exact
        if 85 <= match_score < 100:
            suggestion = {
                'synonym': original_text,
                'article': matched_article,
                'product': matched_product,
                'score': match_score,
                'suggested_at': datetime.now().isoformat(),
                'status': 'pending'
            }
            
            self.pending_synonyms.append(suggestion)
            logger.info(f"Suggested synonym: {original_text} -> {matched_product}")
    
    def track_usage(self, synonym: str) -> None:
        """Track synonym usage frequency"""
        self.usage_stats[synonym] += 1
    
    def get_pending_synonyms(self) -> List[Dict]:
        """Get all pending synonym suggestions"""
        return self.pending_synonyms.copy()
    
    def approve_synonym(self, synonym: str, article: str) -> bool:
        """
        Approve a synonym and add it to the database.
        
        Args:
            synonym: The synonym to approve
            article: The article number
            
        Returns:
            True if successful
        """
        try:
            # Get current product
            product = self.db.get_product_by_article(article)
            
            if not product:
                return False
            
            # Get existing synonyms
            existing_synonyms = []
            if product.get('synonyms'):
                try:
                    existing_synonyms = json.loads(product['synonyms'])
                except json.JSONDecodeError:
                    pass
            
            # Add new synonym if not already present
            if synonym not in existing_synonyms:
                existing_synonyms.append(synonym)
                
                # Update database
                self.db.update_product(
                    article,
                    synonyms=existing_synonyms
                )
                
                # Remove from pending
                self.pending_synonyms = [
                    s for s in self.pending_synonyms 
                    if s['synonym'] != synonym or s['article'] != article
                ]
                
                logger.info(f"Approved synonym: {synonym} -> {article}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error approving synonym: {e}")
            return False
    
    def reject_synonym(self, synonym: str, article: str) -> bool:
        """
        Reject a synonym suggestion.
        
        Args:
            synonym: The synonym to reject
            article: The article number
            
        Returns:
            True if successful
        """
        original_count = len(self.pending_synonyms)
        
        self.pending_synonyms = [
            s for s in self.pending_synonyms 
            if s['synonym'] != synonym or s['article'] != article
        ]
        
        removed = original_count - len(self.pending_synonyms)
        
        if removed > 0:
            logger.info(f"Rejected synonym: {synonym} -> {article}")
            return True
        
        return False
    
    def get_usage_statistics(self) -> Dict:
        """Get synonym usage statistics"""
        sorted_stats = sorted(
            self.usage_stats.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return {
            'total_synonyms': len(self.usage_stats),
            'top_used': sorted_stats[:20],
            'total_usage': sum(self.usage_stats.values())
        }