import React, { useState, useMemo } from 'react';
import {
  Layers,
  Plus,
  SlidersHorizontal,
  History,
  Calendar,
  Search,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { InventoryBatch, StockMovement, Product } from '../types';
import { api } from '../services/api';
import { getProductImageUrl, onProductImageError } from '../utils/imageHelper';

interface InventoryPageProps {
  batches: InventoryBatch[];
  movements: StockMovement[];
  products: Product[];
  onInventoryChanged: () => void;
}

export const InventoryPage: React.FC<InventoryPageProps> = ({
  batches,
  movements,
  products,
  onInventoryChanged,
}) => {
  const [tab, setTab] = useState<'batches' | 'movements'>('batches');
  const [searchTerm, setSearchTerm] = useState('');
  const [isReceiptModalOpen, setIsReceiptModalOpen] = useState(false);

  // Form state for stock receipt
  const [selectedProductId, setSelectedProductId] = useState<number>(products[0]?.id || 1);
  const [receiptQty, setReceiptQty] = useState<number>(10);
  const [receiptCost, setReceiptCost] = useState<number>(100);
  const [batchNo, setBatchNo] = useState<string>(`BAT-${Date.now().toString().slice(-6)}`);
  const [expiryDate, setExpiryDate] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const productMap = useMemo(() => new Map(products.map((p) => [p.id, p])), [products]);

  const filteredBatches = batches.filter((b) =>
    (b.product_name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (b.batch_number || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredMovements = movements.filter((m) =>
    (m.product_name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (m.movement_type || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleCreateReceipt = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await api.createStockReceipt({
        product_id: selectedProductId,
        quantity: receiptQty,
        unit_cost: receiptCost,
        batch_number: batchNo,
        expiry_date: expiryDate || null,
        source_type: 'DIRECT_RECEIPT',
        notes: 'Counter stock receipt entry',
      });
      setIsReceiptModalOpen(false);
      onInventoryChanged();
      alert('Stock receipt created successfully and ledger updated!');
    } catch (err: any) {
      alert(`Receipt failed: ${err.message || 'Error creating batch'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Action Bar */}
      <div className="glass-card" style={{ padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={() => setTab('batches')}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: tab === 'batches' ? '1px solid #c7d2fe' : '1px solid transparent',
              background: tab === 'batches' ? '#eef2ff' : 'transparent',
              color: tab === 'batches' ? '#4f46e5' : '#4b5563',
              fontWeight: 700,
              fontSize: '0.85rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Layers size={16} /> Batch Ledger ({batches.length})
          </button>
          <button
            onClick={() => setTab('movements')}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: tab === 'movements' ? '1px solid #c7d2fe' : '1px solid transparent',
              background: tab === 'movements' ? '#eef2ff' : 'transparent',
              color: tab === 'movements' ? '#4f46e5' : '#4b5563',
              fontWeight: 700,
              fontSize: '0.85rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <History size={16} /> Audit Trail ({movements.length})
          </button>
        </div>

        <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
          <div style={{ position: 'relative', width: '260px' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
            <input
              type="text"
              placeholder="Search batches..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ paddingLeft: '36px', paddingRight: '12px', paddingTop: '8px', paddingBottom: '8px' }}
            />
          </div>
          <button className="btn btn-primary" onClick={() => setIsReceiptModalOpen(true)} style={{ padding: '8px 16px', fontSize: '0.825rem' }}>
            <Plus size={15} /> Receive Batch
          </button>
        </div>
      </div>

      {/* VIEW 1: Batches Ledger */}
      {tab === 'batches' && (
        <div className="glass-card" style={{ padding: '24px' }}>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Batch Lot ID</th>
                  <th>Product</th>
                  <th>Received Qty</th>
                  <th>Remaining Qty</th>
                  <th>Unit Cost</th>
                  <th>Expiry Date</th>
                  <th>Source</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredBatches.map((batch) => {
                  const isExpiringSoon = batch.days_to_expiry !== undefined && batch.days_to_expiry <= 3;
                  const isDepleted = batch.remaining_quantity <= 0;
                  const prod = productMap.get(batch.product_id);

                  return (
                    <tr key={batch.id} style={{ opacity: isDepleted ? 0.5 : 1 }}>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#4f46e5', fontSize: '0.85rem' }}>
                          {batch.batch_number || `BAT-${batch.id}`}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <img
                            src={getProductImageUrl(prod?.image_url)}
                            alt={batch.product_name || 'Product'}
                            onError={onProductImageError}
                            style={{
                              width: '38px',
                              height: '38px',
                              borderRadius: '6px',
                              objectFit: 'cover',
                              border: '1px solid #e2e8f0',
                              backgroundColor: '#f8fafc',
                              flexShrink: 0,
                            }}
                          />
                          <div>
                            <span style={{ fontWeight: 600, color: '#111827', display: 'block' }}>
                              {batch.product_name || `Product #${batch.product_id}`}
                            </span>
                            {prod?.sku && (
                              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                                {prod.sku}
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td>{batch.received_quantity}</td>
                      <td>
                        <span style={{ fontWeight: 800, color: isDepleted ? 'var(--text-muted)' : isExpiringSoon ? '#dc2626' : '#059669' }}>
                          {batch.remaining_quantity}
                        </span>
                      </td>
                      <td>₹{batch.unit_cost.toFixed(2)}</td>
                      <td>
                        {batch.expiry_date ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <Calendar size={13} color="#94a3b8" />
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: isExpiringSoon ? '#dc2626' : '#4b5563' }}>
                              {batch.expiry_date}
                            </span>
                          </div>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>Non-perishable</span>
                        )}
                      </td>
                      <td>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          {batch.source_type}
                        </span>
                      </td>
                      <td>
                        {isDepleted ? (
                          <span className="badge" style={{ background: '#f3f4f6', color: '#6b7280' }}>CONSUMED</span>
                        ) : isExpiringSoon ? (
                          <span className="badge badge-urgent pulse-urgent">EXPIRING</span>
                        ) : (
                          <span className="badge badge-low">USABLE</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* VIEW 2: Audit Trail (Stock Movements) */}
      {tab === 'movements' && (
        <div className="glass-card" style={{ padding: '24px' }}>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Product</th>
                  <th>Movement Type</th>
                  <th>Quantity Delta</th>
                  <th>Reference</th>
                  <th>Ledger Notes</th>
                </tr>
              </thead>
              <tbody>
                {filteredMovements.map((mov) => {
                  const isPositive = mov.quantity > 0;
                  const prod = productMap.get(mov.product_id);
                  return (
                    <tr key={mov.id}>
                      <td style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {mov.created_at ? new Date(mov.created_at).toLocaleString('en-IN') : '-'}
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <img
                            src={getProductImageUrl(prod?.image_url)}
                            alt={mov.product_name || 'Product'}
                            onError={onProductImageError}
                            style={{
                              width: '32px',
                              height: '32px',
                              borderRadius: '6px',
                              objectFit: 'cover',
                              border: '1px solid #e2e8f0',
                              backgroundColor: '#f8fafc',
                              flexShrink: 0,
                            }}
                          />
                          <span style={{ fontWeight: 600, color: '#111827' }}>
                            {mov.product_name || `Product #${mov.product_id}`}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${mov.movement_type === 'RECEIPT' || mov.movement_type === 'OPENING' ? 'badge-low' : 'badge-medium'}`}>
                          {mov.movement_type}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontWeight: 800, color: isPositive ? '#059669' : '#dc2626' }}>
                          {isPositive ? `+${mov.quantity}` : mov.quantity}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                          {mov.reference_type || '-'}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.78rem', color: '#4b5563' }}>
                        {mov.notes || '-'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Stock Receipt Modal */}
      {isReceiptModalOpen && (
        <div className="modal-overlay" onClick={() => setIsReceiptModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#111827', marginBottom: '18px' }}>
              Receive Inbound Inventory Batch
            </h3>

            <form onSubmit={handleCreateReceipt} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Product
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <img
                    src={getProductImageUrl(productMap.get(selectedProductId)?.image_url)}
                    alt="Selected Product"
                    onError={onProductImageError}
                    style={{
                      width: '44px',
                      height: '44px',
                      borderRadius: '8px',
                      objectFit: 'cover',
                      border: '1px solid #e2e8f0',
                      backgroundColor: '#f8fafc',
                      flexShrink: 0,
                    }}
                  />
                  <select
                    style={{ flex: 1 }}
                    value={selectedProductId}
                    onChange={(e) => {
                      const id = Number(e.target.value);
                      setSelectedProductId(id);
                      const p = products.find((prod) => prod.id === id);
                      if (p) setReceiptCost(p.purchase_cost);
                    }}
                  >
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.sku})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Received Quantity
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={receiptQty}
                    onChange={(e) => setReceiptQty(Number(e.target.value))}
                    required
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Unit Cost (₹)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    value={receiptCost}
                    onChange={(e) => setReceiptCost(Number(e.target.value))}
                    required
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Batch Lot Number
                  </label>
                  <input
                    type="text"
                    value={batchNo}
                    onChange={(e) => setBatchNo(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Expiry Date (Optional)
                  </label>
                  <input
                    type="date"
                    value={expiryDate}
                    onChange={(e) => setExpiryDate(e.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsReceiptModalOpen(false)}
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
                  {isSubmitting ? 'Receiving...' : 'Add to Inventory'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
