"""
Test Suite for Order Processing System Improvements
Tests all bug fixes and new features
"""

import unittest
import json
import tempfile
import os
from datetime import datetime

# Import modules to test
from parsing_engine import (
    QuantityValidator, RegexPatterns, ColumnDetector,
    TextOrderParser, TokenMatcher
)
from product_matcher import ProductCache, EnhancedProductMatcher, TokenMatcher as PMTokenMatcher
from unmatched_tracker import UnmatchedTracker, UnmatchedReason
from product_versioning import ProductVersionManager


class TestQuantityValidator(unittest.TestCase):
    """Test quantity validation improvements"""
    
    def test_reject_fractional_between_zero_and_one(self):
        """Test that fractional quantities between 0 and 1 are rejected"""
        is_valid, qty, warnings = QuantityValidator.validate(0.5)
        self.assertFalse(is_valid)
        self.assertEqual(qty, 0)
        self.assertIn("between 0 and 1", warnings[0])
    
    def test_round_decimal_and_recheck_zero(self):
        """Test that decimals are rounded and zero is rechecked"""
        # Test rounding up
        is_valid, qty, warnings = QuantityValidator.validate(2.7)
        self.assertTrue(is_valid)
        self.assertEqual(qty, 3)
        self.assertTrue(any("decimal_rounded" in w for w in warnings))
        
        # Test rounding down
        is_valid, qty, warnings = QuantityValidator.validate(2.3)
        self.assertTrue(is_valid)
        self.assertEqual(qty, 2)
        
        # Test that 0.4 rounds to 0 and is rejected
        is_valid, qty, warnings = QuantityValidator.validate(0.4)
        self.assertFalse(is_valid)
    
    def test_reject_negative_quantities(self):
        """Test that negative quantities are rejected"""
        is_valid, qty, warnings = QuantityValidator.validate(-5)
        self.assertFalse(is_valid)
        self.assertIn("Negative", warnings[0])
    
    def test_warn_high_quantities(self):
        """Test that high quantities generate warnings"""
        is_valid, qty, warnings = QuantityValidator.validate(150)
        self.assertTrue(is_valid)
        self.assertEqual(qty, 150)
        self.assertTrue(any("high_quantity" in w for w in warnings))
    
    def test_warn_low_quantities(self):
        """Test that low quantities generate warnings"""
        is_valid, qty, warnings = QuantityValidator.validate(1)
        self.assertTrue(is_valid)
        self.assertEqual(qty, 1)
        self.assertTrue(any("low_quantity" in w for w in warnings))


class TestRegexPatterns(unittest.TestCase):
    """Test improved regex patterns"""
    
    def test_product_qty_delimited_anchored(self):
        """Test that quantity is properly anchored to end of line"""
        # Should NOT match - number in middle
        match = RegexPatterns.PRODUCT_QTY_DELIMITED.match("Rakza 9 Black (2.0 mm)")
        self.assertIsNone(match)
        
        # Should match - quantity at end
        match = RegexPatterns.PRODUCT_QTY_DELIMITED.match("Rakza 9 Black (2.0 mm), 5")
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1).strip(), "Rakza 9 Black (2.0 mm)")
        self.assertEqual(match.group(2), "5")
    
    def test_article_product_qty_pattern(self):
        """Test article-product-quantity pattern"""
        match = RegexPatterns.ARTICLE_PRODUCT_QTY.match("12345 - Rakza 9 Black, 5")
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "12345")
        self.assertEqual(match.group(2), "Rakza 9 Black")
        self.assertEqual(match.group(3), "5")
    
    def test_qty_product_pattern(self):
        """Test quantity-product pattern"""
        match = RegexPatterns.QTY_PRODUCT.match("5 x Rakza 9 Black")
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "5")
        self.assertEqual(match.group(2), "Rakza 9 Black")


class TestTextOrderParser(unittest.TestCase):
    """Test text order parsing with improved regex"""
    
    def test_parse_product_with_number_in_name(self):
        """Test parsing products with numbers in the name"""
        parser = TextOrderParser()
        
        # Should not extract 9 as quantity
        result = parser.parse_line("Rakza 9 Black (2.0 mm)")
        self.assertIsNone(result)  # No quantity found
        
        # Should correctly extract quantity at end
        result = parser.parse_line("Rakza 9 Black (2.0 mm), 5")
        self.assertIsNotNone(result)
        self.assertEqual(result['product_name'], "Rakza 9 Black (2.0 mm)")
        self.assertEqual(result['quantity'], "5")
    
    def test_parse_with_colon_delimiter(self):
        """Test parsing with colon delimiter"""
        parser = TextOrderParser()
        result = parser.parse_line("Tenergy 05: 10")
        self.assertIsNotNone(result)
        self.assertEqual(result['product_name'], "Tenergy 05")
        self.assertEqual(result['quantity'], "10")
    
    def test_parse_quantity_first(self):
        """Test parsing with quantity first"""
        parser = TextOrderParser()
        result = parser.parse_line("5 x Dignics 09c")
        self.assertIsNotNone(result)
        self.assertEqual(result['product_name'], "Dignics 09c")
        self.assertEqual(result['quantity'], "5")


class TestColumnDetector(unittest.TestCase):
    """Test improved column detection"""
    
    def test_prefer_strong_matches(self):
        """Test that strong matches are preferred over weak matches"""
        columns = ["Product Description", "Product", "Item Count", "Quantity"]
        
        detected = ColumnDetector.detect_columns(columns)
        
        # Should prefer "Product" over "Product Description"
        self.assertEqual(detected['product_col'], "Product")
        
        # Should prefer "Quantity" over "Item Count"
        self.assertEqual(detected['quantity_col'], "Quantity")
    
    def test_locale_variants(self):
        """Test support for locale variants"""
        # German columns
        columns = ["Artikel", "Produkt", "Menge"]
        
        detected = ColumnDetector.detect_columns(columns)
        
        self.assertEqual(detected['article_col'], "Artikel")
        self.assertEqual(detected['product_col'], "Produkt")
        self.assertEqual(detected['quantity_col'], "Menge")
    
    def test_fallback_to_weak_matches(self):
        """Test fallback to weak matches when no strong match"""
        columns = ["Description", "ID", "Count"]
        
        detected = ColumnDetector.detect_columns(columns)
        
        # Should use weak matches as fallback
        self.assertEqual(detected['product_col'], "Description")
        self.assertEqual(detected['article_col'], "ID")
        self.assertEqual(detected['quantity_col'], "Count")


class TestProductCache(unittest.TestCase):
    """Test product caching functionality"""
    
    def setUp(self):
        """Set up test cache"""
        self.cache = ProductCache()
        
        # Sample product data
        self.products_data = [
            {'Article Number': '12345', 'Product': 'Rakza 9 Black 2.0mm'},
            {'Article Number': '12346', 'Product': 'Rakza 9 Red 2.0mm'},
            {'Article Number': '12347', 'Product': 'Rakza 9 Black 2.0mm'},  # Duplicate name
        ]
        
        self.db_products = [
            {
                'article_number': '12345',
                'product_name': 'Rakza 9 Black 2.0mm',
                'synonyms': '["R9 Black", "Rakza9"]'
            }
        ]
        
        self.cache.refresh(self.products_data, self.db_products)
    
    def test_cache_stores_multiple_articles_per_product(self):
        """Test that cache stores multiple articles for same product name"""
        articles = self.cache.get_articles_by_product('Rakza 9 Black 2.0mm')
        self.assertEqual(len(articles), 2)
        self.assertIn('12345', articles)
        self.assertIn('12347', articles)
    
    def test_cache_stores_synonyms(self):
        """Test that cache stores synonyms correctly"""
        synonym_match = self.cache.get_synonym_match('r9 black')
        self.assertIsNotNone(synonym_match)
        self.assertEqual(synonym_match['article'], '12345')
    
    def test_cache_info(self):
        """Test cache info retrieval"""
        info = self.cache.get_cache_info()
        self.assertEqual(info['total_products'], 3)
        self.assertEqual(info['total_synonyms'], 2)
        self.assertIsNotNone(info['last_refresh'])


class TestEnhancedProductMatcher(unittest.TestCase):
    """Test enhanced product matching"""
    
    def setUp(self):
        """Set up test matcher"""
        self.cache = ProductCache()
        
        self.products_data = [
            {'Article Number': '12345', 'Product': 'Rakza 9 Black 2.0mm'},
            {'Article Number': '12346', 'Product': 'Rakza 9 Red 2.0mm'},
            {'Article Number': '12347', 'Product': 'Tenergy 05'},
        ]
        
        self.db_products = [
            {
                'article_number': '12345',
                'product_name': 'Rakza 9 Black 2.0mm',
                'synonyms': '["R9 Black"]'
            }
        ]
        
        self.cache.refresh(self.products_data, self.db_products)
        self.matcher = EnhancedProductMatcher(self.cache)
    
    def test_exact_article_match(self):
        """Test exact article number matching"""
        article, product, score, method = self.matcher.match_product(None, '12345')
        self.assertEqual(article, '12345')
        self.assertEqual(score, 100)
        self.assertEqual(method, 'exact_article')
    
    def test_exact_product_match(self):
        """Test exact product name matching"""
        article, product, score, method = self.matcher.match_product('Rakza 9 Black 2.0mm', None)
        self.assertEqual(article, '12345')
        self.assertEqual(score, 100)
        self.assertEqual(method, 'exact_product')
    
    def test_synonym_match(self):
        """Test synonym matching"""
        article, product, score, method = self.matcher.match_product('R9 Black', None)
        self.assertEqual(article, '12345')
        self.assertEqual(score, 100)
        self.assertEqual(method, 'synonym_match')
    
    def test_token_disambiguation(self):
        """Test token-based disambiguation"""
        # When searching for "Rakza 9 Black", should prefer black variant
        article, product, score, method = self.matcher.match_product('Rakza 9 Black', None)
        self.assertEqual(article, '12345')
        self.assertIn('Black', product)


class TestTokenMatcher(unittest.TestCase):
    """Test token extraction and matching"""
    
    def test_extract_size_tokens(self):
        """Test extraction of size tokens"""
        matcher = PMTokenMatcher()
        
        tokens = matcher.extract_tokens("Rakza 9 Black (2.0 mm)")
        self.assertIn("2.0", tokens)
        
        tokens = matcher.extract_tokens("Rubber 2.0mm")
        self.assertIn("2.0", tokens)
    
    def test_extract_color_tokens(self):
        """Test extraction of color tokens"""
        matcher = PMTokenMatcher()
        
        tokens = matcher.extract_tokens("Rakza 9 Black")
        self.assertIn("black", tokens)
        
        tokens = matcher.extract_tokens("Tenergy Red")
        self.assertIn("red", tokens)
    
    def test_token_similarity(self):
        """Test token similarity calculation"""
        matcher = PMTokenMatcher()
        
        tokens1 = {"black", "2.0"}
        tokens2 = {"black", "2.0"}
        similarity = matcher.token_similarity(tokens1, tokens2)
        self.assertEqual(similarity, 1.0)
        
        tokens1 = {"black", "2.0"}
        tokens2 = {"red", "2.0"}
        similarity = matcher.token_similarity(tokens1, tokens2)
        self.assertEqual(similarity, 0.5)


class TestUnmatchedTracker(unittest.TestCase):
    """Test unmatched items tracking"""
    
    def setUp(self):
        """Set up test tracker"""
        self.tracker = UnmatchedTracker()
    
    def test_add_unmatched_item(self):
        """Test adding unmatched items"""
        self.tracker.add_unmatched(
            "Unknown Product",
            UnmatchedReason.NO_MATCH_FOUND,
            {"score": 0},
            [{"product_name": "Similar Product", "score": 65}]
        )
        
        summary = self.tracker.get_summary()
        self.assertEqual(summary['total_unmatched'], 1)
        self.assertEqual(summary['by_reason']['no_match_found']['count'], 1)
    
    def test_add_warning_item(self):
        """Test adding items with warnings"""
        self.tracker.add_warning(
            {"matched_product": "Test Product"},
            ["Product is discontinued"]
        )
        
        summary = self.tracker.get_summary()
        self.assertEqual(summary['total_warnings'], 1)
    
    def test_group_by_reason(self):
        """Test grouping by reason"""
        self.tracker.add_unmatched(
            "Product 1",
            UnmatchedReason.NO_MATCH_FOUND,
            {}
        )
        self.tracker.add_unmatched(
            "Product 2",
            UnmatchedReason.NO_MATCH_FOUND,
            {}
        )
        self.tracker.add_unmatched(
            "Product 3",
            UnmatchedReason.INVALID_QUANTITY,
            {}
        )
        
        summary = self.tracker.get_summary()
        self.assertEqual(summary['by_reason']['no_match_found']['count'], 2)
        self.assertEqual(summary['by_reason']['invalid_quantity']['count'], 1)
    
    def test_export_to_json(self):
        """Test JSON export"""
        self.tracker.add_unmatched(
            "Test Product",
            UnmatchedReason.NO_MATCH_FOUND,
            {}
        )
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        
        try:
            self.tracker.export_to_json(temp_path)
            
            with open(temp_path, 'r') as f:
                data = json.load(f)
            
            self.assertIn('summary', data)
            self.assertIn('unmatched_items', data)
            self.assertEqual(len(data['unmatched_items']), 1)
        finally:
            os.unlink(temp_path)


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflow"""
    
    def test_complete_order_processing_workflow(self):
        """Test complete order processing from parsing to matching"""
        # Set up cache
        cache = ProductCache()
        products_data = [
            {'Article Number': '12345', 'Product': 'Rakza 9 Black 2.0mm'},
        ]
        db_products = []
        cache.refresh(products_data, db_products)
        
        # Set up matcher
        matcher = EnhancedProductMatcher(cache)
        
        # Parse text order
        parser = TextOrderParser()
        result = parser.parse_line("Rakza 9 Black 2.0mm, 5")
        
        self.assertIsNotNone(result)
        
        # Validate quantity
        is_valid, qty, warnings = QuantityValidator.validate(result['quantity'])
        self.assertTrue(is_valid)
        self.assertEqual(qty, 5)
        
        # Match product
        article, product, score, method = matcher.match_product(
            result['product_name'],
            result.get('article_number')
        )
        
        self.assertEqual(article, '12345')
        self.assertEqual(score, 100)


def run_tests():
    """Run all tests and generate report"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestQuantityValidator))
    suite.addTests(loader.loadTestsFromTestCase(TestRegexPatterns))
    suite.addTests(loader.loadTestsFromTestCase(TestTextOrderParser))
    suite.addTests(loader.loadTestsFromTestCase(TestColumnDetector))
    suite.addTests(loader.loadTestsFromTestCase(TestProductCache))
    suite.addTests(loader.loadTestsFromTestCase(TestEnhancedProductMatcher))
    suite.addTests(loader.loadTestsFromTestCase(TestTokenMatcher))
    suite.addTests(loader.loadTestsFromTestCase(TestUnmatchedTracker))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)