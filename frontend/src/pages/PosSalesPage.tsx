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
} from 'lucide-react';
import { Product, Sale, ClearancePromotion } from '../types';
import { api } from '../services/api';

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

  const clearCart = () => setCart([]);

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
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '24px', alignItems: 'start' }}>
      {/* Left: Product Selector */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
        {/* Search & Category Filter Bar */}
        <div className="glass-card" style={{ padding: '16px 20px', display: 'flex', gap: '14px', alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
            <input
              type="text"
              placeholder="Search products by name or SKU (e.g. Atta, Salt, Milk)..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ paddingLeft: '40px' }}
            />
          </div>
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            style={{ width: '180px' }}
          >
            {categories.map((c) => (
              <option key={c} value={c}>
                {c === 'all' ? 'All Categories' : c}
              </option>
            ))}
          </select>
        </div>

        {/* Product Cards Grid */}
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
                  padding: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  cursor: isOutOfStock ? 'not-allowed' : 'pointer',
                  opacity: isOutOfStock ? 0.6 : 1,
                  position: 'relative',
                  border: pricing.hasDiscount
                    ? '1px solid #fde68a'
                    : cartItem
                    ? '1px solid #0891b2'
                    : '1px solid #e5e7eb',
                  background: pricing.hasDiscount
                    ? '#fffbeb'
                    : cartItem
                    ? '#ecfeff'
                    : '#ffffff',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                    <span style={{ fontSize: '0.7rem', color: '#6b7280', fontFamily: 'var(--font-mono)' }}>
                      {prod.sku}
                    </span>
                    <span style={{
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      color: isOutOfStock ? '#e02424' : stock < 10 ? '#d97706' : '#0e9f6e',
                    }}>
                      {isOutOfStock ? 'Out of Stock' : `${stock} ${prod.unit} left`}
                    </span>
                  </div>

                  {pricing.hasDiscount && (
                    <div style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      background: '#fef3c7',
                      color: '#92400e',
                      border: '1px solid #fde68a',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      marginBottom: '6px',
                    }}>
                      <Tag size={11} /> {pricing.discountPct}% CLEARANCE
                    </div>
                  )}

                  <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#111827', lineHeight: 1.3, marginBottom: '4px' }}>
                    {prod.name}
                  </h4>
                  <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                    {prod.category_name}
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px', paddingTop: '10px', borderTop: '1px solid #e5e7eb' }}>
                  <div>
                    {pricing.hasDiscount ? (
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                        <span style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0e9f6e' }}>
                          ₹{pricing.unitPrice.toFixed(2)}
                        </span>
                        <span style={{ fontSize: '0.78rem', color: '#9ca3af', textDecoration: 'line-through' }}>
                          ₹{pricing.originalPrice.toFixed(2)}
                        </span>
                      </div>
                    ) : (
                      <span style={{ fontSize: '1.15rem', fontWeight: 800, color: '#111827' }}>
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
                    style={{ padding: '6px 12px', fontSize: '0.75rem' }}
                  >
                    <Plus size={14} /> {cartItem ? `(${cartItem.quantity})` : 'Add'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right: Cart & Checkout Ledger */}
      <div className="glass-card" style={{ padding: '24px', position: 'sticky', top: '90px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '16px', borderBottom: '1px solid #e5e7eb' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShoppingCart size={18} color="#0891b2" />
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#111827', margin: 0 }}>
              Current Basket
            </h3>
          </div>
          {cart.length > 0 && (
            <button
              onClick={clearCart}
              style={{ background: 'none', border: 'none', color: '#e02424', fontSize: '0.75rem', cursor: 'pointer', fontWeight: 600 }}
            >
              Clear All
            </button>
          )}
        </div>

        {/* Cart Item List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', margin: '16px 0', maxHeight: '340px', overflowY: 'auto' }}>
          {cart.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '36px 16px', color: '#9ca3af' }}>
              <ShoppingCart size={36} style={{ margin: '0 auto 10px auto', opacity: 0.3 }} />
              <p style={{ fontSize: '0.85rem' }}>Basket is empty</p>
              <p style={{ fontSize: '0.75rem' }}>Click products on the left to add items</p>
            </div>
          ) : (
            cart.map((item) => {
              const pricing = getProductPricing(item.product);
              return (
                <div
                  key={item.product.id}
                  style={{
                    padding: '12px',
                    borderRadius: '8px',
                    background: pricing.hasDiscount ? '#fffbeb' : '#f9fafb',
                    border: pricing.hasDiscount ? '1px solid #fde68a' : '1px solid #e5e7eb',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div style={{ flex: 1, marginRight: '10px' }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#111827', lineHeight: 1.2 }}>
                      {item.product.name}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: '#0e9f6e', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '3px' }}>
                      <Sparkles size={11} /> FEFO batch auto-selected
                    </div>
                    {pricing.hasDiscount && (
                      <div style={{ fontSize: '0.7rem', color: '#92400e', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '2px', fontWeight: 600 }}>
                        <Tag size={10} /> {pricing.discountPct}% Clearance Promo Applied
                      </div>
                    )}
                    <div style={{ fontSize: '0.85rem', color: pricing.hasDiscount ? '#0e9f6e' : '#111827', fontWeight: 700, marginTop: '4px' }}>
                      ₹{(item.quantity * pricing.unitPrice).toFixed(2)}
                      {pricing.hasDiscount && (
                        <span style={{ fontSize: '0.7rem', color: '#9ca3af', textDecoration: 'line-through', marginLeft: '6px' }}>
                          ₹{(item.quantity * pricing.originalPrice).toFixed(2)}
                        </span>
                      )}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <button
                      onClick={() => updateQuantity(item.product.id, -1)}
                      style={{ width: '26px', height: '26px', borderRadius: '4px', background: '#ffffff', border: '1px solid #d1d5db', color: '#374151', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                    >
                      <Minus size={13} />
                    </button>
                    <span style={{ fontSize: '0.9rem', fontWeight: 700, minWidth: '20px', textAlign: 'center', color: '#111827' }}>
                      {item.quantity}
                    </span>
                    <button
                      onClick={() => updateQuantity(item.product.id, 1)}
                      style={{ width: '26px', height: '26px', borderRadius: '4px', background: '#ffffff', border: '1px solid #d1d5db', color: '#374151', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                    >
                      <Plus size={13} />
                    </button>
                    <button
                      onClick={() => removeFromCart(item.product.id)}
                      style={{ background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', marginLeft: '4px' }}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Bill Summary */}
        <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: '#6b7280', marginBottom: '6px' }}>
            <span>Total Items:</span>
            <span style={{ fontWeight: 600, color: '#111827' }}>{totalItems}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '1.25rem', fontWeight: 800, color: '#111827', margin: '12px 0 16px 0' }}>
            <span>Grand Total:</span>
            <span style={{ color: '#0891b2' }}>₹{subtotal.toFixed(2)}</span>
          </div>

          <button
            className="btn btn-emerald"
            disabled={cart.length === 0 || isSubmitting}
            onClick={handleCheckout}
            style={{ width: '100%', padding: '12px', fontSize: '0.95rem', fontWeight: 600 }}
          >
            {isSubmitting ? 'Recording Sale...' : `Charge ₹${subtotal.toFixed(2)} & Print Bill`}
          </button>
        </div>
      </div>

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
