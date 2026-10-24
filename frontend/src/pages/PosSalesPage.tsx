import React, { useState } from 'react';
import {
  Search,
  ShoppingCart,
  Plus,
  Minus,
  Trash2,
  CheckCircle2,
  Printer,
  Sparkles,
  Receipt,
  Store,
  Tag,
  AlertTriangle,
  X,
  RotateCcw,
} from 'lucide-react';
import { Product, Sale, ClearancePromotion } from '../types';
import { api } from '../services/api';
import { getProductImageUrl, onProductImageError } from '../utils/imageHelper';

interface PosSalesPageProps {
  products: Product[];
  clearancePromotions?: ClearancePromotion[];
  onSaleCompleted: () => void;
}

interface CartItem {
  product: Product;
  quantity: number;
}

export const PosSalesPage: React.FC<PosSalesPageProps> = ({
  products,
  clearancePromotions = [],
  onSaleCompleted,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [cart, setCart] = useState<CartItem[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [completedSale, setCompletedSale] = useState<Sale | null>(null);
  const [isClearModalOpen, setIsClearModalOpen] = useState(false);

  // Categories
  const categories = ['all', ...Array.from(new Set(products.map((p) => p.category_name || 'Other')))];

  // Filtered products
  const filteredProducts = products.filter((p) => {
    const matchesSearch =
      p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.sku.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCat = selectedCategory === 'all' || p.category_name === selectedCategory;
    return matchesSearch && matchesCat && p.is_active;
  });

  const addToCart = (product: Product) => {
    const usable = product.usable_stock ?? (product as any).current_stock ?? 0;
    if (usable <= 0) return;

    setCart((prev) => {
      const existing = prev.find((item) => item.product.id === product.id);
      if (existing) {
        if (existing.quantity >= usable) return prev; // Cannot exceed stock
        return prev.map((item) =>
          item.product.id === product.id ? { ...item, quantity: item.quantity + 1 } : item
        );
      }
      return [...prev, { product, quantity: 1 }];
    });
  };

  const updateQuantity = (productId: number, delta: number) => {
    setCart((prev) =>
      prev
        .map((item) => {
          if (item.product.id === productId) {
            const usable = item.product.usable_stock ?? (item.product as any).current_stock ?? 0;
            const newQty = item.quantity + delta;
            if (newQty <= 0) return null;
            if (newQty > usable) return item;
            return { ...item, quantity: newQty };
          }
          return item;
        })
        .filter(Boolean) as CartItem[]
    );
  };

  const getProductPricing = (product: Product) => {
    const promo = clearancePromotions.find((p) => p.product_id === product.id);
    if (promo) {
      return {
        unitPrice: promo.discounted_price,
        originalPrice: promo.original_price || product.selling_price,
        hasDiscount: true,
        discountPct: promo.discount_pct,
      };
    }
    return {
      unitPrice: product.selling_price,
      originalPrice: product.selling_price,
      hasDiscount: false,
      discountPct: 0,
    };
  };

  const removeFromCart = (productId: number) => {
    setCart((prev) => prev.filter((item) => item.product.id !== productId));
  };

  const handleConfirmClear = () => {
    setCart([]);
    setIsClearModalOpen(false);
  };

  const subtotal = cart.reduce((sum, item) => {
    const pricing = getProductPricing(item.product);
    return sum + item.quantity * pricing.unitPrice;
  }, 0);
  const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);

  const handleCheckout = async () => {
    if (cart.length === 0) return;
    setIsSubmitting(true);

    try {
      const salePayload = {
        items: cart.map((it) => {
          const pricing = getProductPricing(it.product);
          return {
            product_id: it.product.id,
            quantity: it.quantity,
            unit_price: pricing.unitPrice,
          };
        }),
        notes: 'Counter Walk-in Customer Sale',
      };

      const result = await api.createSale(salePayload);
      setCompletedSale(result);
      setCart([]);
      onSaleCompleted();
    } catch (err: any) {
      alert(`Sale failed: ${err.message || 'Please check stock levels'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 390px', gap: '24px', alignItems: 'start' }}>
      {/* Left: Product Grid with Images */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
        {/* Search & Category Filter Bar */}
        <div className="glass-card" style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <Search size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
              <input
                type="text"
                placeholder="Search products by name or SKU (e.g. Atta, Salt, Milk)..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ paddingLeft: '40px', width: '100%' }}
              />
            </div>
          </div>

          {/* Category Filter Pills */}
          <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
            {categories.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setSelectedCategory(c)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '20px',
                  border: selectedCategory === c ? '1px solid #4f46e5' : '1px solid #e2e8f0',
                  background: selectedCategory === c ? '#4f46e5' : '#ffffff',
                  color: selectedCategory === c ? '#ffffff' : '#475569',
                  fontSize: '0.78rem',
                  fontWeight: selectedCategory === c ? 700 : 500,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  transition: 'all 0.15s ease',
                }}
              >
                {c === 'all' ? 'All Products' : c}
              </button>
            ))}
          </div>
        </div>

        {/* Visual Product Cards Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))', gap: '16px' }}>
          {filteredProducts.map((prod) => {
            const stock = prod.usable_stock ?? (prod as any).current_stock ?? 0;
            const isOutOfStock = stock <= 0;
            const cartItem = cart.find((c) => c.product.id === prod.id);
            const pricing = getProductPricing(prod);

            return (
              <div
                key={prod.id}
                className="glass-card"
                onClick={() => !isOutOfStock && addToCart(prod)}
                style={{
                  padding: '0',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                  cursor: isOutOfStock ? 'not-allowed' : 'pointer',
                  opacity: isOutOfStock ? 0.6 : 1,
                  position: 'relative',
                  border: cartItem
                    ? '2px solid #4f46e5'
                    : pricing.hasDiscount
                    ? '1px solid #fde68a'
                    : '1px solid #e5e7eb',
                  background: cartItem ? '#f8faff' : '#ffffff',
                  transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                }}
              >
                {/* Product Image Header */}
                <div style={{ position: 'relative', width: '100%', height: '130px', backgroundColor: '#f8fafc', overflow: 'hidden' }}>
                  <img
                    src={getProductImageUrl(prod.image_url)}
                    alt={prod.name}
                    onError={onProductImageError}
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'contain',
                      padding: '8px',
                      transition: 'transform 0.2s ease',
                    }}
                  />
                  {/* Stock Badge Overlay */}
                  <div
                    style={{
                      position: 'absolute',
                      top: '8px',
                      right: '8px',
                      padding: '3px 8px',
                      borderRadius: '12px',
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      background: isOutOfStock
                        ? '#fee2e2'
                        : stock < 10
                        ? '#fef3c7'
                        : '#d1fae5',
                      color: isOutOfStock
                        ? '#b91c1c'
                        : stock < 10
                        ? '#b45309'
                        : '#047857',
                      border: `1px solid ${
                        isOutOfStock
                          ? '#fca5a5'
                          : stock < 10
                          ? '#fcd34d'
                          : '#6ee7b7'
                      }`,
                    }}
                  >
                    {isOutOfStock ? 'Out of Stock' : `${stock} ${prod.unit}s`}
                  </div>

                  {pricing.hasDiscount && (
                    <div
                      style={{
                        position: 'absolute',
                        top: '8px',
                        left: '8px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        background: '#f59e0b',
                        color: '#ffffff',
                        padding: '3px 7px',
                        borderRadius: '4px',
                        fontSize: '0.68rem',
                        fontWeight: 800,
                      }}
                    >
                      <Tag size={10} /> {pricing.discountPct}% OFF
                    </div>
                  )}
                </div>

                {/* Card Body */}
                <div style={{ padding: '12px', display: 'flex', flexDirection: 'column', flex: 1, justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ fontSize: '0.7rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
                      {prod.sku} • {prod.category_name}
                    </div>
                    <h4
                      style={{
                        fontSize: '0.9rem',
                        fontWeight: 700,
                        color: '#111827',
                        lineHeight: 1.3,
                        margin: '4px 0 8px 0',
                        minHeight: '2.4em',
                      }}
                      title={prod.name}
                    >
                      {prod.name}
                    </h4>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '8px', borderTop: '1px solid #f1f5f9' }}>
                    <div>
                      {pricing.hasDiscount ? (
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                          <span style={{ fontSize: '1.1rem', fontWeight: 800, color: '#059669' }}>
                            ₹{pricing.unitPrice.toFixed(2)}
                          </span>
                          <span style={{ fontSize: '0.75rem', color: '#94a3b8', textDecoration: 'line-through' }}>
                            ₹{pricing.originalPrice.toFixed(2)}
                          </span>
                        </div>
                      ) : (
                        <span style={{ fontSize: '1.1rem', fontWeight: 800, color: '#111827' }}>
                          ₹{prod.selling_price.toFixed(2)}
                        </span>
                      )}
                    </div>

                    <button
                      className={`btn ${cartItem ? 'btn-primary' : 'btn-secondary'}`}
                      disabled={isOutOfStock}
                      onClick={(e) => {
                        e.stopPropagation();
                        addToCart(prod);
                      }}
                      style={{
                        padding: '6px 12px',
                        fontSize: '0.75rem',
                        borderRadius: '6px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                      }}
                    >
                      <Plus size={13} /> {cartItem ? `(${cartItem.quantity})` : 'Add'}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right: Cart & Checkout Ledger */}
      <div className="glass-card" style={{ padding: '22px', position: 'sticky', top: '90px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '14px', borderBottom: '1px solid #e5e7eb' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShoppingCart size={19} color="#4f46e5" />
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#111827', margin: 0 }}>
              Current Bill ({totalItems})
            </h3>
          </div>
          {cart.length > 0 && (
            <button
              onClick={() => setIsClearModalOpen(true)}
              style={{
                background: 'none',
                border: 'none',
                color: '#dc2626',
                fontSize: '0.75rem',
                cursor: 'pointer',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <RotateCcw size={12} /> Clear Bill
            </button>
          )}
        </div>

        {/* Cart Item List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', margin: '16px 0', maxHeight: '380px', overflowY: 'auto' }}>
          {cart.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '36px 16px', color: '#9ca3af' }}>
              <ShoppingCart size={36} style={{ margin: '0 auto 10px auto', opacity: 0.3 }} />
              <p style={{ fontSize: '0.85rem', fontWeight: 600, color: '#64748b' }}>Bill is empty</p>
              <p style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Click products on the left or use Voice Assistant to add items</p>
            </div>
          ) : (
            cart.map((item) => {
              const pricing = getProductPricing(item.product);
              return (
                <div
                  key={item.product.id}
                  style={{
                    padding: '10px 12px',
                    borderRadius: '8px',
                    background: pricing.hasDiscount ? '#fffbeb' : '#f8fafc',
                    border: pricing.hasDiscount ? '1px solid #fde68a' : '1px solid #e2e8f0',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                  }}
                >
                  {/* Cart Item Thumbnail */}
                  <img
                    src={getProductImageUrl(item.product.image_url)}
                    alt={item.product.name}
                    onError={onProductImageError}
                    style={{
                      width: '42px',
                      height: '42px',
                      borderRadius: '6px',
                      objectFit: 'cover',
                      border: '1px solid #e2e8f0',
                      backgroundColor: '#ffffff',
                      flexShrink: 0,
                    }}
                  />

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#111827', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {item.product.name}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: '#059669', display: 'flex', alignItems: 'center', gap: '3px' }}>
                      <Sparkles size={10} /> FEFO batch auto-selected
                    </div>
                    <div style={{ fontSize: '0.85rem', color: pricing.hasDiscount ? '#059669' : '#111827', fontWeight: 800, marginTop: '2px' }}>
                      ₹{(item.quantity * pricing.unitPrice).toFixed(2)}
                      <span style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 500, marginLeft: '4px' }}>
                        (₹{pricing.unitPrice.toFixed(2)} / {item.product.unit})
                      </span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <button
                      onClick={() => updateQuantity(item.product.id, -1)}
                      style={{
                        width: '26px',
                        height: '26px',
                        borderRadius: '4px',
                        background: '#ffffff',
                        border: '1px solid #cbd5e1',
                        color: '#334155',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Minus size={12} />
                    </button>
                    <span style={{ fontSize: '0.88rem', fontWeight: 700, minWidth: '18px', textAlign: 'center', color: '#111827' }}>
                      {item.quantity}
                    </span>
                    <button
                      onClick={() => updateQuantity(item.product.id, 1)}
                      style={{
                        width: '26px',
                        height: '26px',
                        borderRadius: '4px',
                        background: '#ffffff',
                        border: '1px solid #cbd5e1',
                        color: '#334155',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Plus size={12} />
                    </button>
                    <button
                      onClick={() => removeFromCart(item.product.id)}
                      style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '2px' }}
                      title="Remove item"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Bill Summary */}
        <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', color: '#64748b', marginBottom: '6px' }}>
            <span>Total Items:</span>
            <span style={{ fontWeight: 600, color: '#111827' }}>{totalItems}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '1.25rem', fontWeight: 800, color: '#111827', margin: '10px 0 16px 0' }}>
            <span>Grand Total:</span>
            <span style={{ color: '#4f46e5' }}>₹{subtotal.toFixed(2)}</span>
          </div>

          <button
            className="btn btn-emerald"
            disabled={cart.length === 0 || isSubmitting}
            onClick={handleCheckout}
            style={{ width: '100%', padding: '12px', fontSize: '0.95rem', fontWeight: 700 }}
          >
            {isSubmitting ? 'Recording Sale...' : `Charge ₹${subtotal.toFixed(2)} & Print Bill`}
          </button>
        </div>
      </div>

      {/* Clear Bill Confirmation Modal */}
      {isClearModalOpen && (
        <div className="modal-overlay" onClick={() => setIsClearModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '380px', textAlign: 'center' }}>
            <AlertTriangle size={36} color="#dc2626" style={{ margin: '0 auto 12px auto' }} />
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#111827', marginBottom: '8px' }}>
              Clear Entire Bill?
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '20px' }}>
              Are you sure you want to remove all {totalItems} items (₹{subtotal.toFixed(2)}) from the current basket?
            </p>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setIsClearModalOpen(false)}
                style={{ flex: 1 }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn"
                onClick={handleConfirmClear}
                style={{ flex: 1, background: '#dc2626', color: '#ffffff' }}
              >
                Yes, Clear All
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sale Success Invoice Modal */}
      {completedSale && (
        <div className="modal-overlay" onClick={() => setCompletedSale(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '420px' }}>
            <div style={{ textAlign: 'center', paddingBottom: '16px', borderBottom: '1px dashed var(--border-hover)' }}>
              <CheckCircle2 size={42} color="#10b981" style={{ margin: '0 auto 8px auto' }} />
              <h2 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#ffffff', margin: 0 }}>
                Sale Completed!
              </h2>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                Inventory batches deducted using FEFO.
              </p>
            </div>

            {/* Receipt Preview */}
            <div style={{ background: '#0b0f19', borderRadius: '12px', padding: '16px', margin: '16px 0', border: '1px solid var(--border-subtle)', fontFamily: 'var(--font-mono)' }}>
              <div style={{ textAlign: 'center', marginBottom: '12px', borderBottom: '1px dashed #334155', paddingBottom: '10px' }}>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#ffffff' }}>SRI LAKSHMI PROVISIONS</div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>APMC Market, Bengaluru - 560001</div>
                <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '4px' }}>Bill No: {completedSale.sale_number}</div>
              </div>

              <div style={{ fontSize: '0.78rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {completedSale.items?.map((it, idx) => (
                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', color: '#e2e8f0' }}>
                    <span>{it.quantity}x {it.product_name}</span>
                    <span>₹{Number(it.line_total).toFixed(2)}</span>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px dashed #334155', display: 'flex', justifyContent: 'space-between', fontWeight: 800, fontSize: '1rem', color: '#34d399' }}>
                <span>TOTAL PAID</span>
                <span>₹{Number(completedSale.total_amount).toFixed(2)}</span>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                className="btn btn-secondary"
                onClick={() => window.print()}
                style={{ flex: 1 }}
              >
                <Printer size={16} /> Print Receipt
              </button>
              <button
                className="btn btn-primary"
                onClick={() => setCompletedSale(null)}
                style={{ flex: 1 }}
              >
                Next Customer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
