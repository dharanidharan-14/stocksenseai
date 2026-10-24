import React, { useState, useRef } from 'react';
import {
  Package,
  Plus,
  Search,
  Percent,
  CheckCircle2,
  AlertTriangle,
  Upload,
  Image as ImageIcon,
  Edit,
  Trash2,
  X,
} from 'lucide-react';
import { Product, Category, Supplier } from '../types';
import { api } from '../services/api';
import { getProductImageUrl, onProductImageError } from '../utils/imageHelper';

interface ProductsPageProps {
  products: Product[];
  categories: Category[];
  suppliers: Supplier[];
  onProductCreated: () => void;
}

export const ProductsPage: React.FC<ProductsPageProps> = ({
  products,
  categories,
  suppliers,
  onProductCreated,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  // Add Form state
  const [name, setName] = useState('');
  const [sku, setSku] = useState('');
  const [categoryId, setCategoryId] = useState<number>(categories[0]?.id || 1);
  const [unit, setUnit] = useState('packet');
  const [purchaseCost, setPurchaseCost] = useState(100);
  const [sellingPrice, setSellingPrice] = useState(120);
  const [leadTime, setLeadTime] = useState(3);
  const [safetyStock, setSafetyStock] = useState(15);
  const [shelfLifeDays, setShelfLifeDays] = useState<number | undefined>(90);
  const [selectedImageFile, setSelectedImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const editFileInputRef = useRef<HTMLInputElement>(null);

  // Edit Form state
  const [editSellingPrice, setEditSellingPrice] = useState<number>(0);
  const [editPurchaseCost, setEditPurchaseCost] = useState<number>(0);
  const [editSafetyStock, setEditSafetyStock] = useState<number>(0);
  const [editImageFile, setEditImageFile] = useState<File | null>(null);
  const [editImagePreview, setEditImagePreview] = useState<string | null>(null);

  const filteredProducts = products.filter((p) => {
    const matchesSearch =
      p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.sku.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCat = categoryFilter === 'all' || p.category_name === categoryFilter;
    return matchesSearch && matchesCat;
  });

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        alert('File size exceeds 5MB limit. Please select a smaller image.');
        return;
      }
      setSelectedImageFile(file);
      const reader = new FileReader();
      reader.onload = () => setImagePreview(reader.result as string);
      reader.readAsDataURL(file);
    }
  };

  const handleEditImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        alert('File size exceeds 5MB limit. Please select a smaller image.');
        return;
      }
      setEditImageFile(file);
      const reader = new FileReader();
      reader.onload = () => setEditImagePreview(reader.result as string);
      reader.readAsDataURL(file);
    }
  };

  const openEditModal = (p: Product) => {
    setEditingProduct(p);
    setEditSellingPrice(p.selling_price);
    setEditPurchaseCost(p.purchase_cost);
    setEditSafetyStock(p.safety_stock);
    setEditImageFile(null);
    setEditImagePreview(p.image_url ? getProductImageUrl(p.image_url) : null);
  };

  const handleCreateProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const created = await api.createProduct({
        name,
        sku: sku || `SKU-${Date.now().toString().slice(-6)}`,
        category_id: categoryId,
        unit,
        purchase_cost: purchaseCost,
        selling_price: sellingPrice,
        supplier_lead_time_days: leadTime,
        safety_stock: safetyStock,
        reorder_threshold: Math.ceil(safetyStock * 1.5),
        shelf_life_days: shelfLifeDays,
        is_active: true,
      });

      // If image was selected, upload it
      if (selectedImageFile && created?.id) {
        await api.uploadProductImage(created.id, selectedImageFile);
      }

      setIsAddModalOpen(false);
      onProductCreated();
      // Reset form
      setName('');
      setSku('');
      setSelectedImageFile(null);
      setImagePreview(null);
    } catch (err: any) {
      alert(`Error creating product: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdateProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingProduct) return;
    setIsSubmitting(true);
    try {
      await api.updateProduct(editingProduct.id, {
        selling_price: editSellingPrice,
        purchase_cost: editPurchaseCost,
        safety_stock: editSafetyStock,
      });

      if (editImageFile) {
        await api.uploadProductImage(editingProduct.id, editImageFile);
      }

      setEditingProduct(null);
      onProductCreated();
    } catch (err: any) {
      alert(`Error updating product: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemoveImage = async (productId: number) => {
    if (!confirm('Are you sure you want to remove this product image?')) return;
    try {
      await api.deleteProductImage(productId);
      setEditImagePreview(null);
      setEditImageFile(null);
      onProductCreated();
    } catch (err: any) {
      alert(`Failed to remove image: ${err.message}`);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Search & Actions Bar */}
      <div className="glass-card" style={{ padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
          <div style={{ position: 'relative', width: '280px' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
            <input
              type="text"
              placeholder="Search products by name or SKU..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ paddingLeft: '36px', paddingRight: '12px', paddingTop: '8px', paddingBottom: '8px' }}
            />
          </div>

          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            style={{ width: '180px', padding: '8px 12px' }}
          >
            <option value="all">All Categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.name}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        <button className="btn btn-primary" onClick={() => setIsAddModalOpen(true)} style={{ padding: '8px 16px', fontSize: '0.825rem' }}>
          <Plus size={15} /> Add New SKU
        </button>
      </div>

      {/* Product Catalog Table */}
      <div className="glass-card" style={{ padding: '24px' }}>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>Category</th>
                <th>Unit</th>
                <th>Cost (₹)</th>
                <th>Selling Price (₹)</th>
                <th>Gross Margin</th>
                <th>Usable Stock</th>
                <th>Safety Stock</th>
                <th>Lead Time</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredProducts.map((p) => {
                const margin = p.selling_price > 0 ? ((p.selling_price - p.purchase_cost) / p.selling_price) * 100 : 0;
                const stock = p.usable_stock || 0;

                return (
                  <tr key={p.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <img
                          src={getProductImageUrl(p.image_url)}
                          alt={p.name}
                          onError={onProductImageError}
                          style={{
                            width: '42px',
                            height: '42px',
                            objectFit: 'cover',
                            borderRadius: '8px',
                            border: '1px solid #e2e8f0',
                            backgroundColor: '#f8fafc',
                            flexShrink: 0,
                          }}
                        />
                        <div>
                          <div style={{ fontWeight: 700, color: '#111827' }}>{p.name}</div>
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                            {p.sku}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        {p.category_name || 'Grocery'}
                      </span>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {p.unit}
                      </span>
                    </td>
                    <td>₹{p.purchase_cost.toFixed(2)}</td>
                    <td>
                      <span style={{ fontWeight: 700, color: '#111827' }}>
                        ₹{p.selling_price.toFixed(2)}
                      </span>
                    </td>
                    <td>
                      <span style={{ fontWeight: 700, color: margin >= 15 ? '#059669' : '#d97706' }}>
                        {margin.toFixed(1)}%
                      </span>
                    </td>
                    <td>
                      <span style={{ fontWeight: 800, color: stock <= p.safety_stock ? '#dc2626' : '#059669' }}>
                        {stock} {p.unit}s
                      </span>
                    </td>
                    <td>{p.safety_stock}</td>
                    <td>{p.supplier_lead_time_days} days</td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        className="btn btn-secondary"
                        style={{ padding: '6px 10px', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                        onClick={() => openEditModal(p)}
                        title="Edit product & image"
                      >
                        <Edit size={13} /> Edit
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Product Modal */}
      {isAddModalOpen && (
        <div className="modal-overlay" onClick={() => setIsAddModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#111827', marginBottom: '18px' }}>
              Add New Grocery Product (SKU)
            </h3>

            <form onSubmit={handleCreateProduct} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Product Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Sona Masoori Rice 5kg"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>

              {/* Image Picker */}
              <div>
                <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Product Image (JPEG, PNG, WebP &lt; 5MB)
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    style={{
                      width: '64px',
                      height: '64px',
                      borderRadius: '8px',
                      border: '2px dashed #cbd5e1',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: 'pointer',
                      background: '#f8fafc',
                      overflow: 'hidden',
                      flexShrink: 0,
                    }}
                  >
                    {imagePreview ? (
                      <img src={imagePreview} alt="Preview" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    ) : (
                      <Upload size={22} color="#94a3b8" />
                    )}
                  </div>
                  <div style={{ flex: 1 }}>
                    <input
                      type="file"
                      ref={fileInputRef}
                      accept="image/jpeg,image/png,image/webp"
                      style={{ display: 'none' }}
                      onChange={handleImageChange}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => fileInputRef.current?.click()}
                      style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                    >
                      {selectedImageFile ? 'Change Photo' : 'Select Photo'}
                    </button>
                    {selectedImageFile && (
                      <span style={{ marginLeft: '10px', fontSize: '0.75rem', color: '#059669' }}>
                        ✓ {selectedImageFile.name}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    SKU Code
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. GRN-RICE-007"
                    value={sku}
                    onChange={(e) => setSku(e.target.value)}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Category
                  </label>
                  <select
                    value={categoryId}
                    onChange={(e) => setCategoryId(Number(e.target.value))}
                  >
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '14px' }}>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Unit
                  </label>
                  <select value={unit} onChange={(e) => setUnit(e.target.value)}>
                    <option value="packet">packet</option>
                    <option value="piece">piece</option>
                    <option value="kg">kg</option>
                    <option value="bottle">bottle</option>
                    <option value="box">box</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Purchase Cost (₹)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    value={purchaseCost}
                    onChange={(e) => setPurchaseCost(Number(e.target.value))}
                    required
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Selling Price (₹)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    value={sellingPrice}
                    onChange={(e) => setSellingPrice(Number(e.target.value))}
                    required
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '14px' }}>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Safety Stock
                  </label>
                  <input
                    type="number"
                    value={safetyStock}
                    onChange={(e) => setSafetyStock(Number(e.target.value))}
                    required
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Supplier Lead Time (Days)
                  </label>
                  <input
                    type="number"
                    value={leadTime}
                    onChange={(e) => setLeadTime(Number(e.target.value))}
                    required
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Shelf Life (Days)
                  </label>
                  <input
                    type="number"
                    placeholder="Null if non-perishable"
                    value={shelfLifeDays || ''}
                    onChange={(e) => setShelfLifeDays(e.target.value ? Number(e.target.value) : undefined)}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsAddModalOpen(false)}
                  style={{ flex: 1 }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isSubmitting}
                  style={{ flex: 1 }}
                >
                  {isSubmitting ? 'Saving...' : 'Create SKU'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Product Modal */}
      {editingProduct && (
        <div className="modal-overlay" onClick={() => setEditingProduct(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#111827' }}>
                Edit Product: {editingProduct.name}
              </h3>
              <button
                onClick={() => setEditingProduct(null)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: '#64748b' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleUpdateProduct} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Image Preview & Upload / Delete */}
              <div>
                <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Product Image
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <img
                    src={editImagePreview || getProductImageUrl(editingProduct.image_url)}
                    alt={editingProduct.name}
                    onError={onProductImageError}
                    style={{
                      width: '72px',
                      height: '72px',
                      borderRadius: '8px',
                      objectFit: 'cover',
                      border: '1px solid #e2e8f0',
                      backgroundColor: '#f8fafc',
                    }}
                  />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div style={{ display: 'flex', gap: '10px' }}>
                      <input
                        type="file"
                        ref={editFileInputRef}
                        accept="image/jpeg,image/png,image/webp"
                        style={{ display: 'none' }}
                        onChange={handleEditImageChange}
                      />
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => editFileInputRef.current?.click()}
                        style={{ padding: '6px 12px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '6px' }}
                      >
                        <Upload size={14} /> Change Photo
                      </button>
                      {(editingProduct.image_url || editImagePreview) && (
                        <button
                          type="button"
                          className="btn"
                          style={{
                            padding: '6px 12px',
                            fontSize: '0.8rem',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            color: '#dc2626',
                            border: '1px solid #fecaca',
                            background: '#fef2f2',
                          }}
                          onClick={() => handleRemoveImage(editingProduct.id)}
                        >
                          <Trash2 size={14} /> Remove Photo
                        </button>
                      )}
                    </div>
                    {editImageFile && (
                      <span style={{ fontSize: '0.75rem', color: '#059669' }}>
                        ✓ New image selected: {editImageFile.name}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '14px' }}>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Selling Price (₹)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    value={editSellingPrice}
                    onChange={(e) => setEditSellingPrice(Number(e.target.value))}
                    required
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Purchase Cost (₹)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    value={editPurchaseCost}
                    onChange={(e) => setEditPurchaseCost(Number(e.target.value))}
                    required
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Safety Stock
                  </label>
                  <input
                    type="number"
                    value={editSafetyStock}
                    onChange={(e) => setEditSafetyStock(Number(e.target.value))}
                    required
                  />
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setEditingProduct(null)}
                  style={{ flex: 1 }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isSubmitting}
                  style={{ flex: 1 }}
                >
                  {isSubmitting ? 'Updating...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
