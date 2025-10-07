# API Reference - Improved Order Processing System

## Base URL
```
http://localhost:5000/api
```

## Authentication
Currently no authentication required. Add authentication middleware for production use.

---

## Core Endpoints

### 1. Health Check
Check system health and cache status.

**Endpoint:** `GET /api/health`

**Response:**
```json
{
  "status": "healthy",
  "cache_info": {
    "version": 1,
    "last_refresh": "2025-01-15T10:30:45",
    "total_products": 1500,
    "total_synonyms": 250,
    "unique_articles": 1500,
    "unique_product_names": 1450
  },
  "timestamp": "2025-01-15T10:35:22"
}
```

---

### 2. Process Order File
Process an uploaded order file (Excel, CSV, JSON, or Text).

**Endpoint:** `POST /api/process-order`

**Content-Type:** `multipart/form-data`

**Parameters:**
- `file` (required): Order file to process
- `customer_id` (optional): Customer identifier (default: "UNKNOWN")

**Response:**
```json
{
  "success": true,
  "customer_id": "CUST001",
  "output_file": "order_CUST001_20250115_103045.xlsx",
  "unmatched_json": "order_CUST001_20250115_103045_unmatched.json",
  "unmatched_txt": "order_CUST001_20250115_103045_unmatched.txt",
  "order_id": 123,
  "statistics": {
    "total_items": 50,
    "matched_items": 45,
    "unmatched_items": 5,
    "unmatched_summary": {
      "total_unmatched": 5,
      "total_warnings": 3,
      "by_reason": {
        "no_match_found": {
          "count": 3,
          "items": [...]
        },
        "invalid_quantity": {
          "count": 2,
          "items": [...]
        }
      }
    }
  },
  "orders": [
    {
      "original_product": "Rakza 9 Black 2.0mm",
      "original_article": null,
      "matched_article": "12345",
      "matched_product": "Rakza 9 Black 2.0mm",
      "quantity": 5,
      "match_score": 100,
      "match_method": "exact_product",
      "status": "matched",
      "warnings": null,
      "row_number": 2,
      "metadata": {}
    }
  ]
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:5000/api/process-order \
  -F "file=@order.xlsx" \
  -F "customer_id=CUST001"
```

---

### 3. Process Text Order
Process order from text input (e.g., copy-pasted from email).

**Endpoint:** `POST /api/process-text-order`

**Content-Type:** `application/json`

**Request Body:**
```json
{
  "text": "Rakza 9 Black 2.0mm, 5\nTenergy 05, 3\nDignics 09c Red, 2",
  "customer_id": "CUST001"
}
```

**Response:** Same as `/api/process-order`

**cURL Example:**
```bash
curl -X POST http://localhost:5000/api/process-text-order \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Rakza 9 Black 2.0mm, 5\nTenergy 05, 3",
    "customer_id": "CUST001"
  }'
```

---

### 4. Download File
Download a generated file (ERP sheet or report).

**Endpoint:** `GET /api/download/<filename>`

**Parameters:**
- `filename` (path): Name of file to download

**Response:** File download

**cURL Example:**
```bash
curl -O http://localhost:5000/api/download/order_CUST001_20250115_103045.xlsx
```

---

## Product Management

### 5. Get All Products
Retrieve all products from the database.

**Endpoint:** `GET /api/products`

**Response:**
```json
{
  "success": true,
  "products": [
    {
      "id": 1,
      "article_number": "12345",
      "product_name": "Rakza 9 Black 2.0mm",
      "category": "Rubber",
      "is_available": 1,
      "is_discontinued": 0,
      "synonyms": "[&quot;Rakza9&quot;, &quot;R9&quot;]",
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ]
}
```

---

### 6. Add Product
Add a new product to the catalog.

**Endpoint:** `POST /api/products`

**Content-Type:** `application/json`

**Request Body:**
```json
{
  "article_number": "12345",
  "product_name": "Rakza 9 Black 2.0mm",
  "category": "Rubber",
  "synonyms": ["Rakza9", "R9"]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Product added successfully"
}
```

---

### 7. Update Product
Update an existing product.

**Endpoint:** `PUT /api/products/<article_number>`

**Content-Type:** `application/json`

**Request Body:**
```json
{
  "product_name": "Rakza 9 Pro Black 2.0mm",
  "category": "Rubber",
  "is_available": true,
  "is_discontinued": false,
  "synonyms": ["Rakza9", "R9", "R9Pro"],
  "change_reason": "Product name update",
  "changed_by": "admin@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Product updated successfully"
}
```

---

### 8. Search Products
Search for products in the catalog.

**Endpoint:** `GET /api/search-product?q=<query>`

**Parameters:**
- `q` (required): Search query

**Response:**
```json
{
  "results": [
    {
      "article_number": "12345",
      "product_name": "Rakza 9 Black 2.0mm",
      "score": 95,
      "all_articles": ["12345"]
    }
  ]
}
```

**cURL Example:**
```bash
curl "http://localhost:5000/api/search-product?q=Rakza"
```

---

## Product Versioning

### 9. Get Product History
Get the complete version history of a product.

**Endpoint:** `GET /api/products/history/<article_number>`

**Response:**
```json
{
  "success": true,
  "article_number": "12345",
  "history": [
    {
      "version_id": 3,
      "product_name": "Rakza 9 Pro Black 2.0mm",
      "category": "Rubber",
      "is_available": true,
      "is_discontinued": false,
      "synonyms": ["Rakza9", "R9", "R9Pro"],
      "version_created_at": "2024-06-01T10:00:00",
      "change_reason": "Product name update",
      "changed_by": "admin@example.com"
    },
    {
      "version_id": 2,
      "product_name": "Rakza 9 Black 2.0mm",
      "category": "Rubber",
      "is_available": true,
      "is_discontinued": false,
      "synonyms": ["Rakza9", "R9"],
      "version_created_at": "2024-01-15T10:00:00",
      "change_reason": "Initial version",
      "changed_by": "system"
    }
  ]
}
```

---

### 10. Soft Delete Product
Mark a product as discontinued (soft delete).

**Endpoint:** `POST /api/products/soft-delete`

**Content-Type:** `application/json`

**Request Body:**
```json
{
  "article_number": "12345",
  "reason": "Product discontinued by manufacturer",
  "deleted_by": "admin@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Product 12345 soft deleted"
}
```

---

### 11. Restore Product
Restore a soft-deleted product.

**Endpoint:** `POST /api/products/restore`

**Content-Type:** `application/json`

**Request Body:**
```json
{
  "article_number": "12345",
  "reason": "Product back in stock",
  "restored_by": "admin@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Product 12345 restored"
}
```

---

### 12. Explain Old Order
Explain an old order by showing product state at that time.

**Endpoint:** `POST /api/products/explain-order`

**Content-Type:** `application/json`

**Request Body:**
```json
{
  "article_number": "12345",
  "order_timestamp": "2024-01-15T10:30:00"
}
```

**Response:**
```json
{
  "success": true,
  "explanation": {
    "article_number": "12345",
    "order_timestamp": "2024-01-15T10:30:00",
    "historical_state": {
      "product_name": "Rakza 9 Black 2.0mm",
      "is_available": true,
      "is_discontinued": false
    },
    "current_state": {
      "product_name": "Rakza 9 Pro Black 2.0mm",
      "is_available": true,
      "is_discontinued": false
    },
    "changes": [
      {
        "field": "product_name",
        "old_value": "Rakza 9 Black 2.0mm",
        "new_value": "Rakza 9 Pro Black 2.0mm"
      }
    ]
  }
}
```

---

### 13. Get Change Log
Get recent product changes.

**Endpoint:** `GET /api/products/changelog?limit=50&offset=0`

**Parameters:**
- `limit` (optional): Maximum number of records (default: 50)
- `offset` (optional): Offset for pagination (default: 0)

**Response:**
```json
{
  "success": true,
  "changes": [
    {
      "version_id": 3,
      "article_number": "12345",
      "product_name": "Rakza 9 Pro Black 2.0mm",
      "version_created_at": "2024-06-01T10:00:00",
      "change_reason": "Product name update",
      "changed_by": "admin@example.com"
    }
  ],
  "limit": 50,
  "offset": 0
}
```

---

## Synonym Management

### 14. Get Pending Synonyms
Get all pending synonym suggestions.

**Endpoint:** `GET /api/synonyms/pending`

**Response:**
```json
{
  "success": true,
  "pending_synonyms": [
    {
      "synonym": "TT Rubber",
      "article": "12345",
      "product": "Tibhar Rubber",
      "score": 88,
      "suggested_at": "2024-01-15T10:30:00",
      "status": "pending"
    }
  ],
  "count": 1
}
```

---

### 15. Approve Synonym
Approve a pending synonym suggestion.

**Endpoint:** `POST /api/synonyms/approve`

**Content-Type:** `application/json`

**Request Body:**
```json
{
  "synonym": "TT Rubber",
  "article": "12345"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Synonym &quot;TT Rubber&quot; approved for article 12345"
}
```

---

### 16. Reject Synonym
Reject a pending synonym suggestion.

**Endpoint:** `POST /api/synonyms/reject`

**Content-Type:** `application/json`

**Request Body:**
```json
{
  "synonym": "TT Rubber",
  "article": "12345"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Synonym &quot;TT Rubber&quot; rejected"
}
```

---

### 17. Get Synonym Statistics
Get synonym usage statistics.

**Endpoint:** `GET /api/synonyms/statistics`

**Response:**
```json
{
  "success": true,
  "statistics": {
    "total_synonyms": 250,
    "top_used": [
      ["TT Rubber", 45],
      ["R9", 32],
      ["D05", 28]
    ],
    "total_usage": 1250
  }
}
```

---

## Cache Management

### 18. Refresh Cache
Manually refresh the product cache.

**Endpoint:** `POST /api/refresh-cache`

**Response:**
```json
{
  "success": true,
  "message": "Cache refreshed successfully",
  "cache_info": {
    "version": 2,
    "last_refresh": "2025-01-15T11:00:00",
    "total_products": 1500,
    "total_synonyms": 250,
    "unique_articles": 1500,
    "unique_product_names": 1450
  }
}
```

---

## Order History

### 19. Get Order History
Get order history with pagination.

**Endpoint:** `GET /api/order-history?limit=50&offset=0`

**Parameters:**
- `limit` (optional): Maximum number of records (default: 50)
- `offset` (optional): Offset for pagination (default: 0)

**Response:**
```json
{
  "success": true,
  "orders": [
    {
      "id": 123,
      "customer_id": "CUST001",
      "timestamp": "2025-01-15T10:30:45",
      "total_items": 50,
      "matched_items": 45,
      "unmatched_items": 5,
      "output_file": "order_CUST001_20250115_103045.xlsx",
      "created_at": "2025-01-15T10:30:45"
    }
  ]
}
```

---

### 20. Get Order Details
Get detailed information about a specific order.

**Endpoint:** `GET /api/order-details/<order_id>`

**Response:**
```json
{
  "success": true,
  "order": {
    "id": 123,
    "customer_id": "CUST001",
    "timestamp": "2025-01-15T10:30:45",
    "total_items": 50,
    "matched_items": 45,
    "unmatched_items": 5,
    "output_file": "order_CUST001_20250115_103045.xlsx",
    "items": [
      {
        "id": 1,
        "order_id": 123,
        "original_product": "Rakza 9 Black 2.0mm",
        "matched_article": "12345",
        "matched_product": "Rakza 9 Black 2.0mm",
        "quantity": 5,
        "match_score": 100,
        "match_method": "exact_product",
        "status": "matched"
      }
    ]
  }
}
```

---

### 21. Get Product Statistics
Get statistics about product matching.

**Endpoint:** `GET /api/product-statistics`

**Response:**
```json
{
  "success": true,
  "statistics": {
    "most_matched": [
      {
        "article_number": "12345",
        "product_name": "Rakza 9 Black 2.0mm",
        "match_count": 150,
        "last_matched": "2025-01-15T10:30:00"
      }
    ],
    "never_matched": [
      {
        "article_number": "99999",
        "product_name": "Obscure Product"
      }
    ]
  }
}
```

---

## Error Responses

All endpoints return error responses in the following format:

```json
{
  "error": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
- `200 OK`: Request successful
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

---

## Rate Limiting

Currently no rate limiting implemented. Consider adding rate limiting for production use:
- Recommended: 100 requests per minute per IP
- Use Flask-Limiter or similar middleware

---

## CORS

CORS is enabled for all origins. For production, restrict to specific origins:

```python
CORS(app, origins=["https://yourdomain.com"])
```

---

## Webhooks (Future Feature)

Plan to add webhooks for:
- Order processing completion
- Synonym suggestions
- Product changes
- Cache refresh events

---

## Best Practices

1. **Always check the health endpoint** before processing orders
2. **Refresh cache** after bulk product updates
3. **Review pending synonyms** regularly to improve matching
4. **Monitor unmatched reports** to identify catalog gaps
5. **Use product versioning** to track changes over time
6. **Implement authentication** for production use
7. **Add rate limiting** to prevent abuse
8. **Use HTTPS** in production
9. **Backup database** regularly
10. **Monitor logs** for parsing issues

---

## Support

For API issues or questions:
- Check logs: Console output shows detailed parsing decisions
- Review unmatched reports: Identify patterns in failed matches
- Use health endpoint: Verify system status
- Check cache info: Ensure cache is up to date