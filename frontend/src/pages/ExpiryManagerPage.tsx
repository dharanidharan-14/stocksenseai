import React, { useState } from 'react';
import {
  AlertTriangle,
  Clock,
  TrendingDown,
  Tag,
  ShieldCheck,
  CheckCircle,
  HelpCircle,
  Sparkles,
  X,
} from 'lucide-react';
import { ExpiryAlert, Product, ClearancePromotion } from '../types';

interface ExpiryManagerPageProps {
  alerts: ExpiryAlert[];
  products?: Product[];
  clearancePromotions?: ClearancePromotion[];
  onApplyPromotion?: (promo: ClearancePromotion) => void;
  onRemovePromotion?: (batchId: number) => void;
}

export const ExpiryManagerPage: React.FC<ExpiryManagerPageProps> = ({
  alerts,
  products = [],
  clearancePromotions = [],
  onApplyPromotion,
  onRemovePromotion,
}) => {
  const [filter, setFilter] = useState<string>('all');
  const [markdownItem, setMarkdownItem] = useState<ExpiryAlert | null>(null);

  const filteredAlerts = alerts.filter((a) => {
    if (filter === 'all') return true;
    if (filter === 'critical') return a.days_until_expiry <= 3;
    if (filter === 'warning') return a.days_until_expiry <= 7 && a.days_until_expiry > 3;
    if (filter === 'attention') return a.days_until_expiry > 7;
    return true;
  });

  const totalLossAtRisk = alerts.reduce((sum, a) => sum + a.potential_loss, 0);
  const criticalCount = alerts.filter((a) => a.days_until_expiry <= 3).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Banner */}
      <div className="glass-card" style={{
        padding: '24px',
        background: '#fffbeb',
        border: '1px solid #fde68a',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            width: '52px',
            height: '52px',
            borderRadius: '14px',
            background: '#f59e0b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            boxShadow: '0 2px 4px rgba(245, 158, 11, 0.25)',
          }}>
            <AlertTriangle size={28} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#92400e', margin: 0 }}>
              Perishable Expiry & Markdown Engine
            </h2>
            <p style={{ fontSize: '0.825rem', color: '#b45309', margin: '4px 0 0 0', fontWeight: 500 }}>
              FEFO ensures earliest expiring batches are sold first at POS. Apply dynamic promotional markdowns before expiry.
            </p>
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '0.75rem', color: '#92400e', fontWeight: 700, letterSpacing: '0.04em' }}>FINANCIAL VALUE AT RISK</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#dc2626', marginTop: '2px' }}>
            ₹{totalLossAtRisk.toFixed(2)}
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '18px' }}>
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>CRITICAL RISK (≤ 3 DAYS)</div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#e11d48', marginTop: '6px' }}>
            {criticalCount} Batches
          </div>
          <p style={{ fontSize: '0.75rem', color: '#e11d48', marginTop: '10px', fontWeight: 600 }}>
            Fresh milk, sliced bread
          </p>
        </div>

        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>EARLIEST EXPIRING BATCH</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#111827', marginTop: '6px' }}>
            Amul Milk (Tomorrow)
          </div>
          <p style={{ fontSize: '0.75rem', color: '#059669', marginTop: '10px', fontWeight: 600 }}>
            8 units remaining in front
          </p>
        </div>

        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>FEFO AUTOMATION</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#34d399', marginTop: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            Active & Enforced <ShieldCheck size={20} color="#10b981" />
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '10px' }}>
            Zero manual batch sorting needed
          </p>
        </div>
      </div>

      {/* Expiry Risk Table */}
      <div className="glass-card" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#111827', margin: 0 }}>
              Batch Expiry Countdown
            </h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Individual inventory lots tracked by manufacture & best-before date
            </p>
          </div>

          {/* Filter Pills */}
          <div style={{ display: 'flex', gap: '8px' }}>
            {[
              { id: 'all', label: 'All Lots' },
              { id: 'critical', label: 'Critical (≤ 3d)' },
              { id: 'warning', label: 'Warning (≤ 7d)' },
              { id: 'attention', label: 'Attention (≤ 30d)' },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                style={{
                  padding: '5px 12px',
                  borderRadius: '8px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  border: filter === f.id ? '1px solid #d97706' : '1px solid var(--border-subtle)',
                  background: filter === f.id ? '#fef3c7' : 'var(--bg-input)',
                  color: filter === f.id ? '#92400e' : 'var(--text-secondary)',
                  cursor: 'pointer',
                }}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Product & Batch</th>
                <th>Remaining Quantity</th>
                <th>Expiry Date</th>
                <th>Countdown</th>
                <th>Potential Loss</th>
                <th>FEFO Status</th>
                <th>Liquidation Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredAlerts.map((alert, idx) => {
                const isCritical = alert.days_until_expiry <= 3;
                const isWarning = alert.days_until_expiry <= 7;
                const activePromo = clearancePromotions.find((p) => p.batch_id === alert.batch_id);

                return (
                  <tr key={idx}>
                    <td>
                      <div style={{ fontWeight: 700, color: '#111827' }}>{alert.product_name}</div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        Batch: {alert.batch_number}
                      </div>
                    </td>
                    <td>
                      <span style={{ fontWeight: 700, color: '#111827' }}>
                        {alert.remaining_quantity} {alert.unit}s
                      </span>
                    </td>
                    <td>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: '#374151' }}>
                        {alert.expiry_date}
                      </span>
                    </td>
                    <td>
                      <span style={{
                        fontWeight: 800,
                        fontSize: '0.9rem',
                        color: isCritical ? '#f43f5e' : isWarning ? '#f59e0b' : '#34d399',
                      }}>
                        {alert.days_until_expiry <= 0
                          ? 'EXPIRED'
                          : alert.days_until_expiry === 1
                          ? '1 day (Tomorrow!)'
                          : `${alert.days_until_expiry} days`}
                      </span>
                    </td>
                    <td>
                      <span style={{ fontWeight: 700, color: '#f87171' }}>
                        ₹{alert.potential_loss.toFixed(2)}
                      </span>
                    </td>
                    <td>
                      {activePromo ? (
                        <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <Sparkles size={11} /> {activePromo.discount_pct}% PROMO ACTIVE
                        </span>
                      ) : isCritical ? (
                        <span className="badge badge-urgent pulse-urgent">CRITICAL LOT</span>
                      ) : (
                        <span className="badge badge-medium">ACTIVE LOT</span>
                      )}
                    </td>
                    <td>
                      {activePromo ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 700 }}>
                            ₹{activePromo.discounted_price.toFixed(2)}
                          </span>
                          <button
                            className="btn btn-secondary"
                            onClick={() => onRemovePromotion && onRemovePromotion(alert.batch_id)}
                            title="Cancel Promotional Markdown"
                            style={{ padding: '4px 8px', fontSize: '0.7rem', color: '#f43f5e' }}
                          >
                            <X size={12} /> Remove
                          </button>
                        </div>
                      ) : (
                        <button
                          className="btn btn-secondary"
                          onClick={() => setMarkdownItem(alert)}
                          style={{ padding: '6px 12px', fontSize: '0.75rem', color: '#fbbf24' }}
                        >
                          <Tag size={13} /> Clearance Markdown
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Markdown Calculator Modal */}
      {markdownItem && (() => {
        const prod = products.find((p) => p.id === markdownItem.product_id);
        const originalPrice = prod ? prod.selling_price : markdownItem.purchase_cost * 1.2;
        const discountPct = 20;
        const discountedPrice = Math.round(originalPrice * (1 - discountPct / 100) * 100) / 100;

        return (
          <div className="modal-overlay" onClick={() => setMarkdownItem(null)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '460px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
                <Tag size={22} color="#f59e0b" />
                <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#111827', margin: 0 }}>
                  Clearance Markdown Recommendation
                </h3>
              </div>

              <p style={{ fontSize: '0.825rem', color: '#4b5563', lineHeight: 1.4 }}>
                <strong style={{ color: '#111827' }}>{markdownItem.product_name}</strong> (Batch: {markdownItem.batch_number}) expires in {markdownItem.days_until_expiry} days.
              </p>

              <div style={{ background: '#f8fafc', borderRadius: '12px', padding: '16px', margin: '16px 0', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.85rem' }}>
                  <span style={{ color: '#64748b' }}>Remaining Lot:</span>
                  <span style={{ fontWeight: 700, color: '#111827' }}>{markdownItem.remaining_quantity} {markdownItem.unit}s</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.85rem' }}>
                  <span style={{ color: '#64748b' }}>Original Retail Price:</span>
                  <span style={{ fontWeight: 600, color: '#111827' }}>₹{originalPrice.toFixed(2)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.85rem' }}>
                  <span style={{ color: '#64748b' }}>Suggested Clearance Promo:</span>
                  <span style={{ fontWeight: 800, color: '#059669' }}>{discountPct}% OFF (Quick Sale)</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: '10px', borderTop: '1px dashed #cbd5e1', fontSize: '0.95rem' }}>
                  <span style={{ fontWeight: 700, color: '#111827' }}>Discounted Promo Rate (at POS):</span>
                  <span style={{ fontWeight: 800, color: '#059669' }}>₹{discountedPrice.toFixed(2)}</span>
                </div>
              </div>

              <p style={{ fontSize: '0.75rem', color: '#64748b', fontStyle: 'italic', marginBottom: '16px' }}>
                Selling at 20% discount clears stock before expiration and shows a live Clearance Discount tag in the POS Billing Counter.
              </p>

              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  className="btn btn-secondary"
                  onClick={() => setMarkdownItem(null)}
                  style={{ flex: 1 }}
                >
                  Close
                </button>
                <button
                  className="btn btn-emerald"
                  onClick={() => {
                    if (onApplyPromotion) {
                      onApplyPromotion({
                        batch_id: markdownItem.batch_id,
                        product_id: markdownItem.product_id,
                        product_name: markdownItem.product_name,
                        batch_number: markdownItem.batch_number,
                        discount_pct: discountPct,
                        original_price: originalPrice,
                        discounted_price: discountedPrice,
                        applied_at: new Date().toISOString(),
                      });
                    }
                    setMarkdownItem(null);
                  }}
                  style={{ flex: 1 }}
                >
                  Apply Promotion
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
};
