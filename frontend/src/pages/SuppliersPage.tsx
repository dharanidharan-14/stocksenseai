import React from 'react';
import {
  Truck,
  Phone,
  Mail,
  MapPin,
  Clock,
  Package,
  DollarSign,
} from 'lucide-react';
import { Supplier } from '../types';

interface SuppliersPageProps {
  suppliers: Supplier[];
}

export const SuppliersPage: React.FC<SuppliersPageProps> = ({ suppliers }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="glass-card" style={{ padding: '20px 24px' }}>
        <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#111827', margin: 0 }}>
          Authorized Wholesaler & FMCG Distributors
        </h3>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Vendor directory with verified lead times and MOQ parameters for AI reorder planning.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '18px' }}>
        {suppliers.map((sup) => (
          <div
            key={sup.id}
            className="glass-card"
            style={{ padding: '22px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}
          >
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div style={{
                  width: '42px',
                  height: '42px',
                  borderRadius: '10px',
                  background: '#eef2ff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#4f46e5',
                }}>
                  <Truck size={20} />
                </div>
                <span className="badge badge-low">ACTIVE DISTRIBUTOR</span>
              </div>

              <h4 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#111827', marginBottom: '6px' }}>
                {sup.name}
              </h4>
              <p style={{ fontSize: '0.825rem', color: '#4b5563', marginBottom: '16px' }}>
                Contact: <strong style={{ color: '#111827' }}>{sup.contact_person || 'Representative'}</strong>
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.78rem', color: '#4b5563' }}>
                {sup.phone && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Phone size={13} color="#6b7280" />
                    <span>{sup.phone}</span>
                  </div>
                )}
                {sup.email && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Mail size={13} color="#6b7280" />
                    <span>{sup.email}</span>
                  </div>
                )}
                {sup.address && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <MapPin size={13} color="#6b7280" />
                    <span>{sup.address}</span>
                  </div>
                )}
              </div>
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '10px',
              marginTop: '20px',
              paddingTop: '16px',
              borderTop: '1px solid var(--border-subtle)',
            }}>
              <div style={{ background: '#f9fafb', border: '1px solid #f3f4f6', padding: '10px', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 600 }}>SUPPLIER LEAD TIME</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#d97706', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Clock size={13} /> {sup.lead_time_days} Days
                </div>
              </div>

              <div style={{ background: '#f9fafb', border: '1px solid #f3f4f6', padding: '10px', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 600 }}>MIN ORDER VALUE</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#059669', marginTop: '2px' }}>
                  ₹{sup.min_order_value ? sup.min_order_value.toLocaleString('en-IN') : 'None'}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
