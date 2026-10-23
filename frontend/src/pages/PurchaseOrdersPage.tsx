import React, { useState } from 'react';
import {
  FileText,
  Plus,
  CheckCircle2,
  Clock,
  Truck,
  ArrowRight,
  PackageCheck,
} from 'lucide-react';
import { PurchaseOrder, Supplier, Product } from '../types';
import { api } from '../services/api';

interface PurchaseOrdersPageProps {
  orders: PurchaseOrder[];
  suppliers: Supplier[];
  products: Product[];
  onOrderChanged: () => void;
}

export const PurchaseOrdersPage: React.FC<PurchaseOrdersPageProps> = ({
  orders,
  suppliers,
  products,
  onOrderChanged,
}) => {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedSupplierId, setSelectedSupplierId] = useState<number>(suppliers[0]?.id || 1);
  const [orderItems, setOrderItems] = useState<{ product_id: number; quantity: number; unit_cost: number }[]>([
    { product_id: products[0]?.id || 1, quantity: 20, unit_cost: products[0]?.purchase_cost || 100 },
  ]);
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const addItemRow = () => {
    setOrderItems((prev) => [
      ...prev,
      { product_id: products[0]?.id || 1, quantity: 10, unit_cost: products[0]?.purchase_cost || 100 },
    ]);
  };

  const removeItemRow = (idx: number) => {
    setOrderItems((prev) => prev.filter((_, i) => i !== idx));
  };

  const updateItemRow = (idx: number, field: string, val: any) => {
    setOrderItems((prev) =>
      prev.map((item, i) => {
        if (i !== idx) return item;
        if (field === 'product_id') {
          const prod = products.find((p) => p.id === Number(val));
          return {
            ...item,
            product_id: Number(val),
            unit_cost: prod ? prod.purchase_cost : item.unit_cost,
          };
        }
        return { ...item, [field]: Number(val) };
      })
    );
  };

  const handleCreateOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await api.createPurchaseOrder({
        supplier_id: selectedSupplierId,
        notes: notes || 'Replenishment order',
        items: orderItems.map((it) => ({
          product_id: it.product_id,
          ordered_quantity: it.quantity,
          unit_cost: it.unit_cost,
        })),
      });
      setIsCreateModalOpen(false);
      onOrderChanged();
      alert('Purchase Order created successfully!');
    } catch (err: any) {
      alert(`PO creation failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReceiveDelivery = async (order: PurchaseOrder) => {
    if (!confirm(`Mark delivery received for ${order.po_number}? This will add stock batches to your inventory.`)) return;
    try {
      // Create stock batches for all lines
      if (order.items) {
        for (const item of order.items) {
          await api.createStockReceipt({
            product_id: item.product_id,
            quantity: item.ordered_quantity,
            unit_cost: item.unit_cost,
            batch_number: `BAT-DELIV-${order.po_number.slice(-4)}`,
            source_type: 'PURCHASE',
            notes: `Received against ${order.po_number}`,
          });
        }
      }
      order.status = 'RECEIVED';
      onOrderChanged();
      alert(`Delivery received and batches added to inventory for ${order.po_number}!`);
    } catch (err: any) {
      alert(`Error receiving delivery: ${err.message}`);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Controls */}
      <div className="glass-card" style={{ padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#111827', margin: 0 }}>
            Vendor Purchase Orders
          </h3>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            Track incoming supplier stock shipments and pending receipts
          </p>
        </div>

        <button className="btn btn-primary" onClick={() => setIsCreateModalOpen(true)} style={{ padding: '8px 18px', fontSize: '0.825rem' }}>
          <Plus size={15} /> Create Purchase Order
        </button>
      </div>

      {/* Orders Table */}
      <div className="glass-card" style={{ padding: '24px' }}>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>PO Number</th>
                <th>Supplier Vendor</th>
                <th>Order Date</th>
                <th>Expected Delivery</th>
                <th>Total Value</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((po) => {
                const isOrdered = po.status === 'ORDERED';
                const isReceived = po.status === 'RECEIVED';

                return (
                  <tr key={po.id}>
                    <td>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#4f46e5', fontSize: '0.875rem' }}>
                        {po.po_number}
                      </span>
                    </td>
                    <td>
                      <span style={{ fontWeight: 600, color: '#111827' }}>
                        {po.supplier_name || `Supplier #${po.supplier_id}`}
                      </span>
                    </td>
                    <td>{po.order_date}</td>
                    <td>
                      {po.expected_delivery_date ? (
                        <span style={{ color: '#d97706', fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>
                          {po.expected_delivery_date}
                        </span>
                      ) : '-'}
                    </td>
                    <td>
                      <span style={{ fontWeight: 800, color: '#059669' }}>
                        ₹{Number(po.total_amount).toFixed(2)}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${isReceived ? 'badge-low' : isOrdered ? 'badge-high' : 'badge-medium'}`}>
                        {po.status}
                      </span>
                    </td>
                    <td>
                      {isOrdered ? (
                        <button
                          className="btn btn-emerald"
                          onClick={() => handleReceiveDelivery(po)}
                          style={{ padding: '5px 12px', fontSize: '0.75rem' }}
                        >
                          <PackageCheck size={14} /> Receive Delivery
                        </button>
                      ) : isReceived ? (
                        <span style={{ color: '#059669', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', fontWeight: 600 }}>
                          <CheckCircle2 size={14} /> Stock Added
                        </span>
                      ) : (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Draft</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create PO Modal */}
      {isCreateModalOpen && (
        <div className="modal-overlay" onClick={() => setIsCreateModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '680px' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#111827', marginBottom: '16px' }}>
              Create Purchase Order
            </h3>

            <form onSubmit={handleCreateOrder} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Wholesale Supplier
                </label>
                <select
                  value={selectedSupplierId}
                  onChange={(e) => setSelectedSupplierId(Number(e.target.value))}
                >
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} (Lead Time: {s.lead_time_days} days)
                    </option>
                  ))}
                </select>
              </div>

              {/* Line Items */}
              <div>
                <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '8px' }}>
                  Line Items
                </label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {orderItems.map((item, idx) => (
                    <div key={idx} style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr auto', gap: '10px', alignItems: 'center' }}>
                      <select
                        value={item.product_id}
                        onChange={(e) => updateItemRow(idx, 'product_id', e.target.value)}
                      >
                        {products.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                      <input
                        type="number"
                        min="1"
                        placeholder="Quantity"
                        value={item.quantity}
                        onChange={(e) => updateItemRow(idx, 'quantity', e.target.value)}
                        required
                      />
                      <input
                        type="number"
                        step="0.5"
                        placeholder="Cost"
                        value={item.unit_cost}
                        onChange={(e) => updateItemRow(idx, 'unit_cost', e.target.value)}
                        required
                      />
                      <button
                        type="button"
                        onClick={() => removeItemRow(idx)}
                        disabled={orderItems.length === 1}
                        style={{ background: 'none', border: 'none', color: '#f43f5e', cursor: 'pointer', fontSize: '1.2rem' }}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>

                <button
                  type="button"
                  onClick={addItemRow}
                  style={{ background: 'none', border: 'none', color: '#4f46e5', fontSize: '0.78rem', cursor: 'pointer', fontWeight: 600, marginTop: '10px' }}
                >
                  + Add Another Product
                </button>
              </div>

              <div>
                <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Purchase Notes
                </label>
                <input
                  type="text"
                  placeholder="e.g. Urgent delivery required for weekend sales"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsCreateModalOpen(false)}
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
                  {isSubmitting ? 'Placing Order...' : 'Dispatch Purchase Order'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
