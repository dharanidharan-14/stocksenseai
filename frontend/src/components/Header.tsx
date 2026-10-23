import React from 'react';
import {
  Search,
  Plus,
  ShoppingCart,
  User,
  ShieldCheck,
  RefreshCw,
  Mic,
} from 'lucide-react';
import { NavTab } from './Sidebar';

interface HeaderProps {
  currentTab: NavTab;
  onQuickAction: (action: 'new-sale' | 'new-receipt' | 'refresh' | 'voice-assistant') => void;
  isLoading: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  currentTab,
  onQuickAction,
  isLoading,
}) => {
  const titles: Record<NavTab, { title: string; subtitle: string }> = {
    dashboard: {
      title: 'Store Performance Overview',
      subtitle: 'Real-time sales, inventory position, and AI stock alerts',
    },
    assistant: {
      title: 'Voice-Controlled Inventory Assistant',
      subtitle: 'Natural language speech recognition & spoken responses backed by PostgreSQL',
    },
    pos: {
      title: 'POS Billing Counter',
      subtitle: 'Fast cashier checkout with automatic FEFO batch allocation',
    },
    reorder: {
      title: 'AI Smart Reorder Planner',
      subtitle: 'Holt-Winters demand forecasting & rupee budget optimizer',
    },
    expiry: {
      title: 'Expiry Risk & Markdown Manager',
      subtitle: 'Actionable alerts to eliminate food wastage and markdown dead stock',
    },
    inventory: {
      title: 'Inventory & Batch Ledger',
      subtitle: 'Authoritative batch tracking, manufacture dates & stock movements',
    },
    products: {
      title: 'Product Catalog & Pricing',
      subtitle: 'Manage SKUs, wholesale purchase costs, units & retail margins',
    },
    purchases: {
      title: 'Purchase Orders & Inbound Shipments',
      subtitle: 'Track wholesale vendor orders, pending quantities & batch receipts',
    },
    suppliers: {
      title: 'Supplier & Vendor Directory',
      subtitle: 'Vendor contact information, lead times & order minimums',
    },
    reports: {
      title: 'Financial & Inventory Reports',
      subtitle: 'Sales velocity, inventory turnover, and profitability analysis',
    },
  };

  const currentMeta = titles[currentTab] || { title: 'StockSense AI', subtitle: '' };

  return (
    <header style={{
      height: '70px',
      borderBottom: '1px solid #e5e7eb',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 32px',
      background: '#ffffff',
      position: 'sticky',
      top: 0,
      zIndex: 30,
    }}>
      {/* Title & Subtitle */}
      <div>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#111827', margin: 0, letterSpacing: '-0.01em' }}>
          {currentMeta.title}
        </h1>
        <p style={{ fontSize: '0.8rem', color: '#6b7280', margin: 0 }}>
          {currentMeta.subtitle}
        </p>
      </div>

      {/* Right Controls: Refresh, Quick Actions, Profile */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {/* Refresh button */}
        <button
          className="btn btn-secondary"
          onClick={() => onQuickAction('refresh')}
          title="Refresh Data"
          style={{ padding: '8px 12px' }}
        >
          <RefreshCw size={15} style={{ animation: isLoading ? 'spin 1s linear infinite' : 'none' }} />
          <span style={{ fontSize: '0.8rem' }}>Sync</span>
        </button>

        {/* Voice Assistant button */}
        <button
          className="btn"
          onClick={() => onQuickAction('voice-assistant')}
          style={{
            padding: '8px 14px',
            fontSize: '0.825rem',
            background: currentTab === 'assistant' ? '#0e7490' : '#0891b2',
            color: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            border: 'none',
            borderRadius: '6px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
          title="Open Voice Assistant"
        >
          <Mic size={15} />
          <span>Voice AI</span>
        </button>

        {/* Quick Sale button */}
        <button
          className="btn btn-emerald"
          onClick={() => onQuickAction('new-sale')}
          style={{ padding: '8px 16px', fontSize: '0.825rem' }}
        >
          <ShoppingCart size={15} />
          <span>New Bill</span>
        </button>

        {/* Quick Inbound Stock button */}
        <button
          className="btn btn-primary"
          onClick={() => onQuickAction('new-receipt')}
          style={{ padding: '8px 16px', fontSize: '0.825rem' }}
        >
          <Plus size={15} />
          <span>Add Stock</span>
        </button>

        {/* User Profile Badge */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: '6px 12px',
          borderRadius: '8px',
          background: '#f9fafb',
          border: '1px solid #e5e7eb',
          marginLeft: '6px',
        }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '6px',
            background: '#0891b2',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
          }}>
            <User size={16} />
          </div>
          <div>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#111827', display: 'flex', alignItems: 'center', gap: '4px' }}>
              Ramesh Kumar <ShieldCheck size={13} color="#10b981" />
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
              Store Owner (Admin)
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
