import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Textarea } from '@/components/ui/textarea.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { 
  Upload, Download, CheckCircle, XCircle, AlertCircle, Package, FileText, Type,
  History, Database, BarChart3, Plus, AlertTriangle
} from 'lucide-react'
import './App.css'

const API_BASE = 'http://localhost:5000/api'

function App() {
  const [file, setFile] = useState(null)
  const [textInput, setTextInput] = useState('')
  const [customerId, setCustomerId] = useState('')
  const [processing, setProcessing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('file')
  const [mainTab, setMainTab] = useState('process')
  
  // Order history state
  const [orderHistory, setOrderHistory] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  
  // Product management state
  const [products, setProducts] = useState([])
  const [loadingProducts, setLoadingProducts] = useState(false)
  const [newProduct, setNewProduct] = useState({
    article_number: '',
    product_name: '',
    category: '',
    synonyms: ''
  })
  
  // Statistics state
  const [statistics, setStatistics] = useState(null)
  const [loadingStats, setLoadingStats] = useState(false)

  useEffect(() => {
    if (mainTab === 'history') {
      loadOrderHistory()
    } else if (mainTab === 'products') {
      loadProducts()
    } else if (mainTab === 'statistics') {
      loadStatistics()
    }
  }, [mainTab])

  const loadOrderHistory = async () => {
    setLoadingHistory(true)
    try {
      const response = await fetch(`${API_BASE}/order-history?limit=20`)
      const data = await response.json()
      if (data.success) {
        setOrderHistory(data.orders)
      }
    } catch (err) {
      console.error('Failed to load order history:', err)
    } finally {
      setLoadingHistory(false)
    }
  }

  const loadProducts = async () => {
    setLoadingProducts(true)
    try {
      const response = await fetch(`${API_BASE}/products`)
      const data = await response.json()
      if (data.success) {
        setProducts(data.products)
      }
    } catch (err) {
      console.error('Failed to load products:', err)
    } finally {
      setLoadingProducts(false)
    }
  }

  const loadStatistics = async () => {
    setLoadingStats(true)
    try {
      const response = await fetch(`${API_BASE}/product-statistics`)
      const data = await response.json()
      if (data.success) {
        setStatistics(data.statistics)
      }
    } catch (err) {
      console.error('Failed to load statistics:', err)
    } finally {
      setLoadingStats(false)
    }
  }

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    setFile(selectedFile)
    setResult(null)
    setError(null)
  }

  const handleTextChange = (e) => {
    setTextInput(e.target.value)
    setResult(null)
    setError(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (activeTab === 'file' && !file) {
      setError('Please select a file to upload')
      return
    }

    if (activeTab === 'text' && !textInput.trim()) {
      setError('Please enter order text')
      return
    }
    
    if (!customerId.trim()) {
      setError('Please enter a customer ID')
      return
    }

    setProcessing(true)
    setError(null)
    setResult(null)

    try {
      let response;
      
      if (activeTab === 'file') {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('customer_id', customerId)

        response = await fetch(`${API_BASE}/process-order`, {
          method: 'POST',
          body: formData
        })
      } else {
        response = await fetch(`${API_BASE}/process-text-order`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            text: textInput,
            customer_id: customerId
          })
        })
      }

      const data = await response.json()

      if (response.ok) {
        setResult(data)
      } else {
        setError(data.error || 'An error occurred while processing the order')
      }
    } catch (err) {
      setError('Failed to connect to the server. Please ensure the backend is running.')
    } finally {
      setProcessing(false)
    }
  }

  const handleDownload = (filename) => {
    window.open(`${API_BASE}/download/${filename}`, '_blank')
  }

  const handleAddProduct = async (e) => {
    e.preventDefault()
    
    try {
      const synonyms = newProduct.synonyms ? newProduct.synonyms.split(',').map(s => s.trim()) : []
      
      const response = await fetch(`${API_BASE}/products`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ...newProduct,
          synonyms
        })
      })
      
      const data = await response.json()
      
      if (data.success) {
        setNewProduct({ article_number: '', product_name: '', category: '', synonyms: '' })
        loadProducts()
        alert('Product added successfully!')
      } else {
        alert(`Error: ${data.error}`)
      }
    } catch (err) {
      alert('Failed to add product')
    }
  }

  const getFileIcon = (filename) => {
    if (!filename) return <FileText className="h-4 w-4" />
    return <FileText className="h-4 w-4" />
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-4">
            <Package className="h-10 w-10 text-blue-600" />
            <h1 className="text-4xl font-bold text-slate-900">Order Processing System</h1>
          </div>
          <p className="text-slate-600 text-lg">
            Process orders, manage products, and track history
          </p>
        </div>

        <Tabs value={mainTab} onValueChange={setMainTab} className="w-full">
          <TabsList className="grid w-full grid-cols-4 mb-8">
            <TabsTrigger value="process" className="flex items-center gap-2">
              <Upload className="h-4 w-4" />
              Process Order
            </TabsTrigger>
            <TabsTrigger value="history" className="flex items-center gap-2">
              <History className="h-4 w-4" />
              Order History
            </TabsTrigger>
            <TabsTrigger value="products" className="flex items-center gap-2">
              <Database className="h-4 w-4" />
              Products
            </TabsTrigger>
            <TabsTrigger value="statistics" className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              Statistics
            </TabsTrigger>
          </TabsList>

          {/* Process Order Tab */}
          <TabsContent value="process">
            <div className="grid md:grid-cols-2 gap-6 mb-8">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Upload className="h-5 w-5" />
                    Submit Order
                  </CardTitle>
                  <CardDescription>
                    Upload a file or paste order text directly
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="customer-id">Customer ID</Label>
                      <Input
                        id="customer-id"
                        type="text"
                        placeholder="Enter customer ID"
                        value={customerId}
                        onChange={(e) => setCustomerId(e.target.value)}
                        disabled={processing}
                      />
                    </div>

                    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                      <TabsList className="grid w-full grid-cols-2">
                        <TabsTrigger value="file" className="flex items-center gap-2">
                          <Upload className="h-4 w-4" />
                          File Upload
                        </TabsTrigger>
                        <TabsTrigger value="text" className="flex items-center gap-2">
                          <Type className="h-4 w-4" />
                          Text Input
                        </TabsTrigger>
                      </TabsList>

                      <TabsContent value="file" className="space-y-2">
                        <Label htmlFor="file-upload">Order File</Label>
                        <div className="border-2 border-dashed border-slate-300 rounded-lg p-6 text-center hover:border-blue-400 transition-colors">
                          <input
                            id="file-upload"
                            type="file"
                            accept=".xlsx,.xls,.csv,.json,.txt"
                            onChange={handleFileChange}
                            disabled={processing}
                            className="hidden"
                          />
                          <label htmlFor="file-upload" className="cursor-pointer">
                            {file ? (
                              <div className="flex items-center justify-center gap-2">
                                {getFileIcon(file.name)}
                                <span className="text-sm text-slate-700">{file.name}</span>
                              </div>
                            ) : (
                              <div className="space-y-2">
                                <Upload className="h-8 w-8 mx-auto text-slate-400" />
                                <p className="text-sm text-slate-600">
                                  Click to select a file or drag and drop
                                </p>
                                <p className="text-xs text-slate-500">
                                  Excel, CSV, JSON, or Text files
                                </p>
                              </div>
                            )}
                          </label>
                        </div>
                      </TabsContent>

                      <TabsContent value="text" className="space-y-2">
                        <Label htmlFor="text-input">Order Text</Label>
                        <Textarea
                          id="text-input"
                          placeholder="Paste your order here...&#10;&#10;Example formats:&#10;Mark V Black (2.0 mm), 5&#10;5x Rakza 7 Red (2.0 mm)&#10;Sweden Classic (Flared): 2"
                          value={textInput}
                          onChange={handleTextChange}
                          disabled={processing}
                          rows={10}
                          className="font-mono text-sm"
                        />
                        <p className="text-xs text-slate-500">
                          Supports formats: "Product, Qty" or "Qty x Product" or "Product: Qty"
                        </p>
                      </TabsContent>
                    </Tabs>

                    <Button 
                      type="submit" 
                      className="w-full" 
                      disabled={processing || (!file && !textInput.trim()) || !customerId.trim()}
                    >
                      {processing ? (
                        <>
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                          Processing...
                        </>
                      ) : (
                        <>
                          <Upload className="h-4 w-4 mr-2" />
                          Process Order
                        </>
                      )}
                    </Button>
                  </form>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Supported Formats</CardTitle>
                  <CardDescription>
                    The system can process orders in various formats
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-3">
                    <div className="flex items-start gap-3">
                      <Badge variant="outline" className="mt-1">Excel</Badge>
                      <div>
                        <p className="text-sm font-medium">Excel Spreadsheets</p>
                        <p className="text-xs text-slate-600">
                          Columns: Product/Item, Article/SKU, Quantity/Qty
                        </p>
                      </div>
                    </div>

                    <div className="flex items-start gap-3">
                      <Badge variant="outline" className="mt-1">CSV</Badge>
                      <div>
                        <p className="text-sm font-medium">Comma-Separated Values</p>
                        <p className="text-xs text-slate-600">
                          Same structure as Excel files
                        </p>
                      </div>
                    </div>

                    <div className="flex items-start gap-3">
                      <Badge variant="outline" className="mt-1">JSON</Badge>
                      <div>
                        <p className="text-sm font-medium">JSON Format</p>
                        <p className="text-xs text-slate-600">
                          Array of objects with product, article, and quantity fields
                        </p>
                      </div>
                    </div>

                    <div className="flex items-start gap-3">
                      <Badge variant="outline" className="mt-1">Text</Badge>
                      <div>
                        <p className="text-sm font-medium">Plain Text / Email</p>
                        <p className="text-xs text-slate-600">
                          Formats: "Product, 5" or "5x Product" or "Product: 5"
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {result && (
              <Card className="mb-6">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <CheckCircle className="h-5 w-5 text-green-600" />
                    Processing Complete
                  </CardTitle>
                  <CardDescription>
                    Order processed successfully for customer: {result.customer_id}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <p className="text-sm text-slate-600 mb-1">Total Items</p>
                      <p className="text-2xl font-bold text-blue-600">
                        {result.statistics.total_items}
                      </p>
                    </div>
                    <div className="bg-green-50 p-4 rounded-lg">
                      <p className="text-sm text-slate-600 mb-1">Matched</p>
                      <p className="text-2xl font-bold text-green-600">
                        {result.statistics.matched_items}
                      </p>
                    </div>
                    <div className="bg-red-50 p-4 rounded-lg">
                      <p className="text-sm text-slate-600 mb-1">Unmatched</p>
                      <p className="text-2xl font-bold text-red-600">
                        {result.statistics.unmatched_items}
                      </p>
                    </div>
                  </div>

                  <Button onClick={() => handleDownload(result.output_file)} className="w-full">
                    <Download className="h-4 w-4 mr-2" />
                    Download ERP Template
                  </Button>

                  {result.orders && result.orders.length > 0 && (
                    <div className="border rounded-lg overflow-hidden">
                      <div className="bg-slate-50 px-4 py-2 border-b">
                        <h3 className="font-semibold text-sm">Order Details</h3>
                      </div>
                      <div className="max-h-96 overflow-y-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-slate-100 sticky top-0">
                            <tr>
                              <th className="px-4 py-2 text-left">Original Product</th>
                              <th className="px-4 py-2 text-left">Matched Product</th>
                              <th className="px-4 py-2 text-left">Article #</th>
                              <th className="px-4 py-2 text-center">Qty</th>
                              <th className="px-4 py-2 text-center">Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {result.orders.map((order, index) => (
                              <tr key={index} className="border-b hover:bg-slate-50">
                                <td className="px-4 py-2">
                                  {order.original_product}
                                  {order.warnings && order.warnings.length > 0 && (
                                    <div className="mt-1">
                                      {order.warnings.map((warning, idx) => (
                                        <div key={idx} className="flex items-center gap-1 text-xs text-orange-600">
                                          <AlertTriangle className="h-3 w-3" />
                                          {warning}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </td>
                                <td className="px-4 py-2">
                                  {order.matched_product || '-'}
                                </td>
                                <td className="px-4 py-2 font-mono text-xs">
                                  {order.matched_article || '-'}
                                </td>
                                <td className="px-4 py-2 text-center">{order.quantity}</td>
                                <td className="px-4 py-2 text-center">
                                  {order.status === 'matched' ? (
                                    <Badge variant="success" className="bg-green-100 text-green-800">
                                      <CheckCircle className="h-3 w-3 mr-1" />
                                      Matched
                                    </Badge>
                                  ) : order.status === 'invalid_quantity' ? (
                                    <Badge variant="destructive">
                                      <XCircle className="h-3 w-3 mr-1" />
                                      Invalid Qty
                                    </Badge>
                                  ) : (
                                    <Badge variant="destructive">
                                      <XCircle className="h-3 w-3 mr-1" />
                                      Unmatched
                                    </Badge>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Order History Tab */}
          <TabsContent value="history">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <History className="h-5 w-5" />
                  Order History
                </CardTitle>
                <CardDescription>
                  View all previously processed orders
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loadingHistory ? (
                  <div className="text-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                    <p className="text-sm text-slate-600 mt-2">Loading history...</p>
                  </div>
                ) : orderHistory.length === 0 ? (
                  <div className="text-center py-8 text-slate-600">
                    No orders found in history
                  </div>
                ) : (
                  <div className="space-y-4">
                    {orderHistory.map((order) => (
                      <div key={order.id} className="border rounded-lg p-4 hover:bg-slate-50">
                        <div className="flex justify-between items-start mb-2">
                          <div>
                            <p className="font-semibold">Customer: {order.customer_id}</p>
                            <p className="text-sm text-slate-600">
                              {new Date(order.timestamp).toLocaleString()}
                            </p>
                          </div>
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => handleDownload(order.output_file)}
                          >
                            <Download className="h-4 w-4 mr-1" />
                            Download
                          </Button>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-sm">
                          <div>
                            <span className="text-slate-600">Total:</span>
                            <span className="font-semibold ml-1">{order.total_items}</span>
                          </div>
                          <div>
                            <span className="text-slate-600">Matched:</span>
                            <span className="font-semibold ml-1 text-green-600">{order.matched_items}</span>
                          </div>
                          <div>
                            <span className="text-slate-600">Unmatched:</span>
                            <span className="font-semibold ml-1 text-red-600">{order.unmatched_items}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Products Tab */}
          <TabsContent value="products">
            <div className="grid md:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Plus className="h-5 w-5" />
                    Add New Product
                  </CardTitle>
                  <CardDescription>
                    Add a new product to the catalog
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleAddProduct} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="article-number">Article Number</Label>
                      <Input
                        id="article-number"
                        value={newProduct.article_number}
                        onChange={(e) => setNewProduct({...newProduct, article_number: e.target.value})}
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="product-name">Product Name</Label>
                      <Input
                        id="product-name"
                        value={newProduct.product_name}
                        onChange={(e) => setNewProduct({...newProduct, product_name: e.target.value})}
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="category">Category (Optional)</Label>
                      <Input
                        id="category"
                        value={newProduct.category}
                        onChange={(e) => setNewProduct({...newProduct, category: e.target.value})}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="synonyms">Synonyms (Optional, comma-separated)</Label>
                      <Input
                        id="synonyms"
                        placeholder="e.g., Mark 5, Mark Five"
                        value={newProduct.synonyms}
                        onChange={(e) => setNewProduct({...newProduct, synonyms: e.target.value})}
                      />
                    </div>
                    <Button type="submit" className="w-full">
                      <Plus className="h-4 w-4 mr-2" />
                      Add Product
                    </Button>
                  </form>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Database className="h-5 w-5" />
                    Product Catalog
                  </CardTitle>
                  <CardDescription>
                    Total products: {products.length}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {loadingProducts ? (
                    <div className="text-center py-8">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                      <p className="text-sm text-slate-600 mt-2">Loading products...</p>
                    </div>
                  ) : (
                    <div className="max-h-96 overflow-y-auto space-y-2">
                      {products.slice(0, 50).map((product) => (
                        <div key={product.id} className="border rounded p-3 text-sm">
                          <div className="flex justify-between items-start">
                            <div>
                              <p className="font-semibold">{product.product_name}</p>
                              <p className="text-xs text-slate-600 font-mono">{product.article_number}</p>
                              {product.category && (
                                <Badge variant="outline" className="mt-1 text-xs">
                                  {product.category}
                                </Badge>
                              )}
                            </div>
                            <div className="flex gap-1">
                              {product.is_discontinued ? (
                                <Badge variant="destructive" className="text-xs">Discontinued</Badge>
                              ) : !product.is_available ? (
                                <Badge variant="secondary" className="text-xs">Unavailable</Badge>
                              ) : null}
                            </div>
                          </div>
                        </div>
                      ))}
                      {products.length > 50 && (
                        <p className="text-xs text-slate-600 text-center pt-2">
                          Showing first 50 of {products.length} products
                        </p>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Statistics Tab */}
          <TabsContent value="statistics">
            <div className="grid md:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5" />
                    Most Matched Products
                  </CardTitle>
                  <CardDescription>
                    Products that are frequently ordered
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {loadingStats ? (
                    <div className="text-center py-8">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                      <p className="text-sm text-slate-600 mt-2">Loading statistics...</p>
                    </div>
                  ) : statistics && statistics.most_matched && statistics.most_matched.length > 0 ? (
                    <div className="space-y-2">
                      {statistics.most_matched.map((item, index) => (
                        <div key={index} className="flex justify-between items-center border-b pb-2">
                          <div>
                            <p className="text-sm font-medium">{item.product_name}</p>
                            <p className="text-xs text-slate-600 font-mono">{item.article_number}</p>
                          </div>
                          <Badge variant="outline">{item.match_count || 0} matches</Badge>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-center text-slate-600 py-8">No statistics available yet</p>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <AlertCircle className="h-5 w-5" />
                    Never Matched Products
                  </CardTitle>
                  <CardDescription>
                    Products that have never been ordered
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {loadingStats ? (
                    <div className="text-center py-8">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                      <p className="text-sm text-slate-600 mt-2">Loading statistics...</p>
                    </div>
                  ) : statistics && statistics.never_matched && statistics.never_matched.length > 0 ? (
                    <div className="max-h-96 overflow-y-auto space-y-2">
                      {statistics.never_matched.map((item, index) => (
                        <div key={index} className="border-b pb-2">
                          <p className="text-sm font-medium">{item.product_name}</p>
                          <p className="text-xs text-slate-600 font-mono">{item.article_number}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-center text-slate-600 py-8">All products have been matched!</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

export default App
