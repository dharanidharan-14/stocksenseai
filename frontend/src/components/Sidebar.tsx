import React from 'react';
import {
  LayoutDashboard,
  Package,
  Layers,
  ShoppingCart,
  BrainCircuit,
  AlertTriangle,
  FileText,
  Truck,
  BarChart3,
  Sparkles,
  Store,
  Wifi,
  WifiOff,
  Mic,
} from 'lucide-react';

export type NavTab =
  | 'dashboard'
  | 'assistant'
  | 'products'
  | 'inventory'
  | 'pos'
  | 'reorder'
  | 'expiry'
  | 'purchases'
  | 'suppliers'
  | 'reports';

interface SidebarProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  isBackendConnected: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  isBackendConnected,
}) => {
  const navItems: { id: NavTab; label: string; icon: React.ReactNode; badge?: string }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={19} /> },
    { id: 'assistant', label: 'Voice Assistant', icon: <Mic size={19} />, badge: 'AI Live' },
    { id: 'pos', label: 'POS Billing Counter', icon: <ShoppingCart size={19} />, badge: 'FEFO' },
    { id: 'reorder', label: 'AI Reorder Planner', icon: <BrainCircuit size={19} />, badge: 'AI' },
    { id: 'expiry', label: 'Expiry Risk Manager', icon: <AlertTriangle size={19} /> },
    { id: 'inventory', label: 'Inventory & Batches', icon: <Layers size={19} /> },
    { id: 'products', label: 'Products & Catalog', icon: <Package size={19} /> },
    { id: 'purchases', label: 'Purchase Orders', icon: <FileText size={19} /> },
    { id: 'suppliers', label: 'Suppliers Directory', icon: <Truck size={19} /> },
    { id: 'reports', label: 'Reports & Analytics', icon: <BarChart3 size={19} /> },
  ];

  return (
    <aside style={{
      width: '260px',
      background: '#ffffff',
      borderRight: '1px solid #e5e7eb',
      display: 'flex',
      flexDirection: 'column',
      padding: '20px 16px',
      flexShrink: 0,
      height: '100vh',
      position: 'sticky',
      top: 0,
      zIndex: 40,
    }}>
      {/* Brand Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '0 8px 20px 8px', borderBottom: '1px solid #e5e7eb' }}>
        <div style={{
          width: '38px',
          height: '38px',
          borderRadius: '8px',
          background: '#0891b2',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#ffffff',
          boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
        }}>
          <Sparkles size={20} />
        </div>
        <div>
          <h2 style={{ fontSize: '1.15rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#111827', display: 'flex', alignItems: 'center', gap: '6px' }}>
            StockSense <span style={{ color: '#0891b2', fontWeight: 700 }}>AI</span>
          </h2>
          <p style={{ fontSize: '0.72rem', color: '#6b7280', fontWeight: 500 }}>
            Smart Kirana ERP
          </p>
        </div>
      </div>

      {/* Navigation Items */}
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '16px', flex: 1, overflowY: 'auto' }}>
        {navItems.map((item) => {
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 12px',
                borderRadius: '8px',
                border: '1px solid transparent',
                background: isActive ? '#f3f4f6' : 'transparent',
                color: isActive ? '#111827' : '#4b5563',
                fontWeight: isActive ? 600 : 500,
                fontSize: '0.875rem',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = '#f9fafb';
                  e.currentTarget.style.color = '#111827';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#4b5563';
                }
              }}
            >
              <span style={{ color: isActive ? '#0891b2' : '#6b7280' }}>
                {item.icon}
              </span>
              <span style={{ flex: 1 }}>{item.label}</span>
              {item.badge && (
                <span style={{
                  fontSize: '0.65rem',
                  fontWeight: 700,
                  padding: '2px 6px',
                  borderRadius: '4px',
                  background: item.badge === 'AI' ? '#f3e8ff' : '#ecfeff',
                  color: item.badge === 'AI' ? '#7e3af2' : '#0891b2',
                  border: item.badge === 'AI' ? '1px solid #d8b4fe' : '1px solid #a5f3fc',
                }}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer Store & Connection Info */}
      <div style={{
        padding: '12px',
        borderRadius: '8px',
        background: '#f9fafb',
        border: '1px solid #e5e7eb',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <Store size={15} color="#4b5563" />
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#111827' }}>
            Sri Lakshmi Provisions
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {isBackendConnected ? (
            <>
              <Wifi size={13} color="#0e9f6e" />
              <span style={{ fontSize: '0.72rem', color: '#0e9f6e', fontWeight: 600 }}>FastAPI Connected</span>
            </>
          ) : (
            <>
              <WifiOff size={13} color="#d97706" />
              <span style={{ fontSize: '0.72rem', color: '#d97706', fontWeight: 600 }}>Offline / Demo Mode</span>
            </>
          )}
        </div>
      </div>
    </aside>
  );
};
