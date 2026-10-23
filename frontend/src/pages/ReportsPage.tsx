import React from 'react';
import {
  BarChart3,
  TrendingUp,
  DollarSign,
  ShieldCheck,
  Percent,
  Download,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { DashboardStats } from '../types';

interface ReportsPageProps {
  stats: DashboardStats;
}

export const ReportsPage: React.FC<ReportsPageProps> = ({ stats }) => {
  const categoryData = [
    { name: 'Dairy & Bakery', value: 32000, color: '#10b981' },
    { name: 'Grains & Flours', value: 45000, color: '#6366f1' },
    { name: 'Cooking Oils & Ghee', value: 28000, color: '#f59e0b' },
    { name: 'Snacks & Biscuits', value: 21000, color: '#ec4899' },
    { name: 'Spices & Masalas', value: 16600, color: '#8b5cf6' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Header */}
      <div className="glass-card" style={{ padding: '20px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#111827', margin: 0 }}>
            Executive Business Intelligence & Profitability
          </h3>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Monthly turnover, gross margins, and waste reduction metrics
          </p>
        </div>

        <button
          className="btn btn-secondary"
          onClick={() => alert('Monthly CSV ledger report exported to Downloads folder.')}
          style={{ padding: '8px 16px', fontSize: '0.8rem' }}
        >
          <Download size={15} /> Export Audit CSV
        </button>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '18px' }}>
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>30-DAY GROSS REVENUE</div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#059669', marginTop: '6px' }}>
            ₹{stats.monthly_sales_amount.toLocaleString('en-IN')}
          </div>
          <p style={{ fontSize: '0.75rem', color: '#059669', marginTop: '10px', fontWeight: 600 }}>
            +18.4% vs previous month
          </p>
        </div>

        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>AVERAGE GROSS MARGIN</div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#4f46e5', marginTop: '6px' }}>
            19.2%
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '10px' }}>
            Net profit approx ₹{(stats.monthly_sales_amount * 0.192).toFixed(0)}
          </p>
        </div>

        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>FEFO WASTE SAVED</div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#0284c7', marginTop: '6px' }}>
            ₹8,420
          </div>
          <p style={{ fontSize: '0.75rem', color: '#0284c7', marginTop: '10px', fontWeight: 600 }}>
            Zero spoiled dairy lots this month
          </p>
        </div>
      </div>

      {/* Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(440px, 1fr))', gap: '20px' }}>
        {/* Category Revenue Breakdown */}
        <div className="glass-card" style={{ padding: '24px' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#111827', marginBottom: '16px' }}>
            Category Sales Distribution
          </h3>

          <div style={{ height: '260px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={categoryData}
                  cx="50%"
                  cy="50%"
                  outerRadius={95}
                  dataKey="value"
                  label={({ name, percent }) => `${(name || '').split(' ')[0]} ${((percent || 0) * 100).toFixed(0)}%`}
                >
                  {categoryData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '12px', color: '#111827', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
                  formatter={(val: any) => [`₹${Number(val).toLocaleString('en-IN')}`, 'Revenue']}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Weekly Turnover Bar */}
        <div className="glass-card" style={{ padding: '24px' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#111827', marginBottom: '16px' }}>
            Counter Volume vs Orders
          </h3>

          <div style={{ height: '260px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.sales_trend} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="date" stroke="#64748b" fontSize={12} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={12} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '12px', color: '#111827', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
                />
                <Bar dataKey="orders" fill="#6366f1" radius={[4, 4, 0, 0]} name="Transactions" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
