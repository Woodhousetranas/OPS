"""
Unmatched Items Tracker
Groups and analyzes unmatched items by root cause
"""

import json
import logging
from typing import List, Dict, Optional
from collections import defaultdict
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class UnmatchedReason(Enum):
    """Enumeration of reasons for unmatched items"""
    NO_MATCH_FOUND = "no_match_found"
    LOW_MATCH_SCORE = "low_match_score"
    INVALID_QUANTITY = "invalid_quantity"
    AMBIGUOUS_MATCH = "ambiguous_match"
    PRODUCT_UNAVAILABLE = "product_unavailable"
    PRODUCT_DISCONTINUED = "product_discontinued"
    PARSING_ERROR = "parsing_error"
    MISSING_DATA = "missing_data"


class UnmatchedItem:
    """Represents an unmatched item with detailed information"""
    
    def __init__(
        self,
        original_text: str,
        reason: UnmatchedReason,
        details: Dict,
        suggestions: Optional[List[Dict]] = None
    ):
        self.original_text = original_text
        self.reason = reason
        self.details = details
        self.suggestions = suggestions or []
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'original_text': self.original_text,
            'reason': self.reason.value,
            'details': self.details,
            'suggestions': self.suggestions,
            'timestamp': self.timestamp
        }


class UnmatchedTracker:
    """Tracks and analyzes unmatched items"""
    
    def __init__(self):
        self.unmatched_items = []
        self.items_by_reason = defaultdict(list)
        self.warning_items = []  # Items that matched but have warnings
    
    def add_unmatched(
        self,
        original_text: str,
        reason: UnmatchedReason,
        details: Dict,
        suggestions: Optional[List[Dict]] = None
    ) -> None:
        """
        Add an unmatched item.
        
        Args:
            original_text: The original input text
            reason: The reason for not matching
            details: Additional details about the failure
            suggestions: Optional list of suggested matches
        """
        item = UnmatchedItem(original_text, reason, details, suggestions)
        self.unmatched_items.append(item)
        self.items_by_reason[reason].append(item)
        
        logger.warning(f"Unmatched item: {original_text} - Reason: {reason.value}")
    
    def add_warning(
        self,
        matched_item: Dict,
        warnings: List[str]
    ) -> None:
        """
        Add an item that matched but has warnings.
        
        Args:
            matched_item: The matched item data
            warnings: List of warning messages
        """
        warning_entry = {
            'matched_item': matched_item,
            'warnings': warnings,
            'timestamp': datetime.now().isoformat()
        }
        self.warning_items.append(warning_entry)
    
    def get_summary(self) -> Dict:
        """Get a summary of unmatched items grouped by reason"""
        summary = {
            'total_unmatched': len(self.unmatched_items),
            'total_warnings': len(self.warning_items),
            'by_reason': {}
        }
        
        for reason, items in self.items_by_reason.items():
            summary['by_reason'][reason.value] = {
                'count': len(items),
                'items': [item.to_dict() for item in items]
            }
        
        return summary
    
    def get_unmatched_by_reason(
        self,
        reason: UnmatchedReason
    ) -> List[UnmatchedItem]:
        """Get all unmatched items for a specific reason"""
        return self.items_by_reason[reason]
    
    def get_all_unmatched(self) -> List[Dict]:
        """Get all unmatched items"""
        return [item.to_dict() for item in self.unmatched_items]
    
    def get_all_warnings(self) -> List[Dict]:
        """Get all warning items"""
        return self.warning_items.copy()
    
    def export_to_json(self, filepath: str) -> None:
        """
        Export unmatched items to JSON file.
        
        Args:
            filepath: Path to output JSON file
        """
        data = {
            'summary': self.get_summary(),
            'unmatched_items': self.get_all_unmatched(),
            'warning_items': self.get_all_warnings(),
            'generated_at': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported unmatched items to {filepath}")
    
    def generate_report(self) -> str:
        """Generate a human-readable report of unmatched items"""
        report_lines = [
            "=" * 80,
            "UNMATCHED ITEMS REPORT",
            "=" * 80,
            f"Generated: {datetime.now().isoformat()}",
            f"Total Unmatched: {len(self.unmatched_items)}",
            f"Total Warnings: {len(self.warning_items)}",
            "",
            "BREAKDOWN BY REASON:",
            "-" * 80
        ]
        
        for reason, items in self.items_by_reason.items():
            report_lines.append(f"\n{reason.value.upper()} ({len(items)} items):")
            report_lines.append("-" * 40)
            
            for item in items[:10]:  # Show first 10 items per reason
                report_lines.append(f"  • {item.original_text}")
                if item.suggestions:
                    report_lines.append(f"    Suggestions: {len(item.suggestions)}")
            
            if len(items) > 10:
                report_lines.append(f"  ... and {len(items) - 10} more")
        
        if self.warning_items:
            report_lines.append("\n" + "=" * 80)
            report_lines.append("ITEMS WITH WARNINGS:")
            report_lines.append("-" * 80)
            
            for warning in self.warning_items[:20]:  # Show first 20 warnings
                item = warning['matched_item']
                report_lines.append(
                    f"  • {item.get('original_product')} -> "
                    f"{item.get('matched_product')}"
                )
                for w in warning['warnings']:
                    report_lines.append(f"    ⚠ {w}")
        
        report_lines.append("\n" + "=" * 80)
        
        return "\n".join(report_lines)


class UnmatchedAnalyzer:
    """Analyzes patterns in unmatched items to suggest improvements"""
    
    @staticmethod
    def analyze_patterns(unmatched_items: List[UnmatchedItem]) -> Dict:
        """
        Analyze patterns in unmatched items.
        
        Args:
            unmatched_items: List of unmatched items
            
        Returns:
            Dictionary with analysis results
        """
        analysis = {
            'common_prefixes': defaultdict(int),
            'common_suffixes': defaultdict(int),
            'common_words': defaultdict(int),
            'potential_synonyms': []
        }
        
        for item in unmatched_items:
            text = item.original_text.lower()
            words = text.split()
            
            # Track common words
            for word in words:
                if len(word) > 3:  # Ignore short words
                    analysis['common_words'][word] += 1
            
            # Track prefixes and suffixes
            if len(words) > 0:
                analysis['common_prefixes'][words[0]] += 1
                analysis['common_suffixes'][words[-1]] += 1
            
            # Check if item has suggestions (potential synonyms)
            if item.suggestions:
                for suggestion in item.suggestions:
                    analysis['potential_synonyms'].append({
                        'original': item.original_text,
                        'suggested': suggestion.get('product_name'),
                        'score': suggestion.get('score')
                    })
        
        # Sort by frequency
        analysis['common_prefixes'] = dict(
            sorted(analysis['common_prefixes'].items(),
                  key=lambda x: x[1], reverse=True)[:10]
        )
        analysis['common_suffixes'] = dict(
            sorted(analysis['common_suffixes'].items(),
                  key=lambda x: x[1], reverse=True)[:10]
        )
        analysis['common_words'] = dict(
            sorted(analysis['common_words'].items(),
                  key=lambda x: x[1], reverse=True)[:20]
        )
        
        return analysis
    
    @staticmethod
    def suggest_improvements(analysis: Dict) -> List[str]:
        """
        Suggest improvements based on analysis.
        
        Args:
            analysis: Analysis results from analyze_patterns
            
        Returns:
            List of improvement suggestions
        """
        suggestions = []
        
        # Check for common words that might need synonyms
        if analysis['common_words']:
            top_words = list(analysis['common_words'].keys())[:5]
            suggestions.append(
                f"Consider adding synonyms for common words: {', '.join(top_words)}"
            )
        
        # Check for potential synonyms
        if analysis['potential_synonyms']:
            high_score_synonyms = [
                s for s in analysis['potential_synonyms']
                if s['score'] >= 75
            ]
            if high_score_synonyms:
                suggestions.append(
                    f"Found {len(high_score_synonyms)} potential synonyms "
                    f"with high match scores (≥75). Review and approve them."
                )
        
        # Check for common prefixes/suffixes
        if analysis['common_prefixes']:
            suggestions.append(
                f"Common prefixes detected: {', '.join(list(analysis['common_prefixes'].keys())[:3])}. "
                f"Consider if these indicate a product category."
            )
        
        return suggestions