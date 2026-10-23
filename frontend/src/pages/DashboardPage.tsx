import React from 'react';
import {
  TrendingUp,
  PackageCheck,
  AlertOctagon,
  Clock,
  ArrowUpRight,
  ShoppingCart,
  BrainCircuit,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  CartesianGrid,
} from 'recharts';
import { DashboardStats, Product, ReorderRecommendation, ExpiryAlert } from '../types';
import { NavTab } from '../components/Sidebar';

interface DashboardPageProps {
  stats: DashboardStats;
  products: Product[];
  reorders: ReorderRecommendation[];
  expiryAlerts: ExpiryAlert[];
  onNavigate: (tab: NavTab) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  stats,
  products,
  reorders,
  expiryAlerts,
  onNavigate,
}) => {
  const urgentReorders = reorders.filter((r) => r.priority === 'URGENT' || r.priority === 'HIGH');
  const criticalExpiries = expiryAlerts.filter((e) => e.days_until_expiry <= 3);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Urgent Alert Banner if shortages exist */}
      {urgentReorders.length > 0 && (
        <div style={{
          background: '#fff1f2',
          border: '1px solid #fecdd3',
          borderRadius: 'var(--radius-lg)',
          padding: '16px 22px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              background: '#ffe4e6',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#e11d48',
            }}>
              <ShieldAlert size={22} />
            </div>
            <div>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#9f1239', margin: 0 }}>
                Attention Required: {urgentReorders.length} Fast-Moving Items Critically Low!
              </h3>
              <p style={{ fontSize: '0.8rem', color: '#be123c', margin: '2px 0 0 0' }}>
                {urgentReorders.map((r) => r.product_name.split(' ')[0]).join(', ')} are projected to stock out before supplier delivery.
              </p>
            </div>
          </div>
          <button
            className="btn btn-danger"
            onClick={() => onNavigate('reorder')}
            style={{ padding: '8px 16px', fontSize: '0.8rem', fontWeight: 700 }}
          >
            Review AI Plan <ArrowRight size={14} />
          </button>
        </div>
      )}

      {/* KPI Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '18px' }}>
        {/* Card 1: Inventory Value */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <p style={{ fontSize: '0.78rem', color: '#6b7280', fontWeight: 600, textTransform: 'uppercase' }}>
                Usable Stock Value
              </p>
              <h2 style={{ fontSize: '1.65rem', fontWeight: 800, color: '#111827', marginTop: '6px' }}>
                ₹{stats.total_inventory_value.toLocaleString('en-IN')}
              </h2>
            </div>
            <div style={{
              padding: '10px',
              borderRadius: '8px',
              background: '#ecfeff',
              color: '#0891b2',
            }}>
              <PackageCheck size={22} />
            </div>
          </div>
          <p style={{ fontSize: '0.75rem', color: '#0e9f6e', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '12px', fontWeight: 600 }}>
            <TrendingUp size={14} /> 16 Active Grocery SKUs tracked
          </p>
        </div>

        {/* Card 2: Today's Sales */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <p style={{ fontSize: '0.78rem', color: '#6b7280', fontWeight: 600, textTransform: 'uppercase' }}>
                Today's Counter Sales
              </p>
              <h2 style={{ fontSize: '1.65rem', fontWeight: 800, color: '#111827', marginTop: '6px' }}>
                ₹{stats.today_sales_amount.toLocaleString('en-IN')}
              </h2>
            </div>
            <div style={{
              padding: '10px',
              borderRadius: '8px',
              background: '#def7ec',
              color: '#0e9f6e',
            }}>
              <ShoppingCart size={22} />
            </div>
          </div>
          <p style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '12px' }}>
            {stats.today_sales_count} bills completed today
          </p>
        </div>

        {/* Card 3: Stockout Urgency */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <p style={{ fontSize: '0.78rem', color: '#6b7280', fontWeight: 600, textTransform: 'uppercase' }}>
                Low Stock Items
              </p>
              <h2 style={{ fontSize: '1.65rem', fontWeight: 800, color: urgentReorders.length > 0 ? '#e02424' : '#111827', marginTop: '6px' }}>
                {stats.low_stock_count} SKUs
              </h2>
            </div>
            <div style={{
              padding: '10px',
              borderRadius: '8px',
              background: '#fde8e8',
              color: '#e02424',
            }}>
              <AlertOctagon size={22} />
            </div>
          </div>
          <p style={{ fontSize: '0.75rem', color: '#e02424', marginTop: '12px', fontWeight: 600 }}>
            {urgentReorders.length} items require immediate PO
          </p>
        </div>

        {/* Card 4: Expiring Soon */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <p style={{ fontSize: '0.78rem', color: '#6b7280', fontWeight: 600, textTransform: 'uppercase' }}>
                Expiry Risk (≤ 48 Hours)
              </p>
              <h2 style={{ fontSize: '1.65rem', fontWeight: 800, color: criticalExpiries.length > 0 ? '#d97706' : '#111827', marginTop: '6px' }}>
                {criticalExpiries.length} Batches
              </h2>
            </div>
            <div style={{
              padding: '10px',
              borderRadius: '8px',
              background: '#fef3c7',
              color: '#d97706',
            }}>
              <Clock size={22} />
            </div>
          </div>
          <p style={{ fontSize: '0.75rem', color: '#d97706', marginTop: '12px', fontWeight: 600 }}>
            FEFO prioritizing early consumption
          </p>
        </div>
      </div>

      {/* Charts Section: 7-Day Revenue & Top Selling Products */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '20px' }}>
        {/* Sales Trend Chart */}
        <div className="glass-card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#111827', margin: 0 }}>
                Daily Revenue Trend
              </h3>
              <p style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                Past 7 days counter sales volume
              </p>
            </div>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#0891b2', background: '#ecfeff', padding: '4px 10px', borderRadius: '4px' }}>
              7 Days
            </span>
          </div>

          <div style={{ height: '260px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={stats.sales_trend} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="salesGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0891b2" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#0891b2" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="date" stroke="#9ca3af" fontSize={12} tickLine={false} />
                <YAxis stroke="#9ca3af" fontSize={12} tickLine={false} tickFormatter={(v) => `₹${v}`} />
                <Tooltip
                  contentStyle={{ background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)', fontSize: '12px', color: '#111827' }}
                  formatter={(val: any) => [`₹${Number(val).toLocaleString('en-IN')}`, 'Sales']}
                />
                <Area type="monotone" dataKey="sales" stroke="#0891b2" strokeWidth={2.5} fillOpacity={1} fill="url(#salesGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top Moving Products Chart */}
        <div className="glass-card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#111827', margin: 0 }}>
                Fastest-Selling Grocery Items
              </h3>
              <p style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                Units consumed by customers
              </p>
            </div>
            <button
              onClick={() => onNavigate('products')}
              style={{ background: 'none', border: 'none', color: '#0891b2', fontSize: '0.78rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}
            >
              View All <ArrowUpRight size={14} />
            </button>
          </div>

          <div style={{ height: '260px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.top_selling_products} layout="vertical" margin={{ top: 5, right: 20, left: 30, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis type="number" stroke="#9ca3af" fontSize={12} />
                <YAxis dataKey="name" type="category" stroke="#4b5563" fontSize={11} width={130} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)', fontSize: '12px', color: '#111827' }}
                  formatter={(val: any, name: any) => [name === 'revenue' ? `₹${val}` : `${val} units`, name === 'revenue' ? 'Revenue' : 'Units Sold']}
                />
                <Bar dataKey="quantity" fill="#0891b2" radius={[0, 4, 4, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Critical Stock Health & FEFO Status Table */}
      <div className="glass-card" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#111827', margin: 0 }}>
              Inventory Health & FEFO Overview
            </h3>
            <p style={{ fontSize: '0.75rem', color: '#6b7280' }}>
              Current usable stock vs safety threshold
            </p>
          </div>
          <button className="btn btn-secondary" onClick={() => onNavigate('inventory')} style={{ padding: '6px 14px', fontSize: '0.78rem' }}>
            Full Inventory Ledger
          </button>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Product SKU & Name</th>
                <th>Category</th>
                <th>Usable Stock</th>
                <th>Safety Threshold</th>
                <th>Selling Price</th>
                <th>Stock Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {products.slice(0, 7).map((prod) => {
                const stock = prod.usable_stock || 0;
                const isCritical = stock <= 5;
                const isLow = stock <= prod.reorder_threshold;

                return (
                  <tr key={prod.id}>
                    <td>
                      <div style={{ fontWeight: 600, color: '#111827' }}>{prod.name}</div>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280', fontFamily: 'var(--font-mono)' }}>
                        {prod.sku}
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.8rem', color: '#4b5563' }}>
                        {prod.category_name || 'Grocery'}
                      </span>
                    </td>
                    <td>
                      <span style={{ fontWeight: 700, fontSize: '0.95rem', color: isCritical ? '#e02424' : isLow ? '#d97706' : '#0e9f6e' }}>
                        {stock} {prod.unit}s
                      </span>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.85rem', color: '#6b7280' }}>
                        {prod.reorder_threshold} {prod.unit}s
                      </span>
                    </td>
                    <td>
                      <span style={{ fontWeight: 600, color: '#111827' }}>
                        ₹{prod.selling_price.toFixed(2)}
                      </span>
                    </td>
                    <td>
                      {isCritical ? (
                        <span className="badge badge-urgent pulse-urgent">CRITICAL LOW</span>
                      ) : isLow ? (
                        <span className="badge badge-high">REORDER SOON</span>
                      ) : (
                        <span className="badge badge-low">HEALTHY</span>
                      )}
                    </td>
                    <td>
                      {isLow ? (
                        <button
                          className="btn btn-primary"
                          onClick={() => onNavigate('reorder')}
                          style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                        >
                          <BrainCircuit size={13} /> Order
                        </button>
                      ) : (
                        <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>OK</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
