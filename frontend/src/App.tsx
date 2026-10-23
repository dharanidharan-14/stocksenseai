import React, { useState, useEffect, useCallback } from 'react';
import { Sidebar, NavTab } from './components/Sidebar';
import { Header } from './components/Header';
import { DashboardPage } from './pages/DashboardPage';
import { VoiceAssistantPage } from './pages/VoiceAssistantPage';
import { PosSalesPage } from './pages/PosSalesPage';
import { AiReorderPage } from './pages/AiReorderPage';
import { ExpiryManagerPage } from './pages/ExpiryManagerPage';
import { InventoryPage } from './pages/InventoryPage';
import { ProductsPage } from './pages/ProductsPage';
import { PurchaseOrdersPage } from './pages/PurchaseOrdersPage';
import { SuppliersPage } from './pages/SuppliersPage';
import { ReportsPage } from './pages/ReportsPage';
import {
  Product,
  Category,
  Supplier,
  InventoryBatch,
  StockMovement,
  PurchaseOrder,
  ReorderRecommendation,
  ExpiryAlert,
  DashboardStats,
  ClearancePromotion,
} from './types';
import { api } from './services/api';

export function App() {
  const [currentTab, setCurrentTab] = useState<NavTab>('dashboard');
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Core Data
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [batches, setBatches] = useState<InventoryBatch[]>([]);
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [reorders, setReorders] = useState<ReorderRecommendation[]>([]);
  const [expiryAlerts, setExpiryAlerts] = useState<ExpiryAlert[]>([]);
  const [clearancePromotions, setClearancePromotions] = useState<ClearancePromotion[]>(() => {
    try {
      const saved = localStorage.getItem('stocksense_clearance_promos');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const handleApplyClearancePromotion = useCallback((promo: ClearancePromotion) => {
    setClearancePromotions((prev) => {
      const filtered = prev.filter((p) => p.batch_id !== promo.batch_id);
      const updated = [...filtered, promo];
      try {
        localStorage.setItem('stocksense_clearance_promos', JSON.stringify(updated));
      } catch (err) {
        console.error('Failed to save clearance promo', err);
      }
      return updated;
    });
  }, []);

  const handleRemoveClearancePromotion = useCallback((batchId: number) => {
    setClearancePromotions((prev) => {
      const updated = prev.filter((p) => p.batch_id !== batchId);
      try {
        localStorage.setItem('stocksense_clearance_promos', JSON.stringify(updated));
      } catch (err) {
        console.error('Failed to remove clearance promo', err);
      }
      return updated;
    });
  }, []);

  const [stats, setStats] = useState<DashboardStats>({
    total_products: 16,
    total_inventory_value: 48950,
    low_stock_count: 2,
    expiring_soon_count: 2,
    today_sales_amount: 4850,
    today_sales_count: 8,
    monthly_sales_amount: 142600,
    open_purchase_orders_count: 1,
    top_selling_products: [],
    sales_trend: [],
  });

  const loadAllData = useCallback(async () => {
    setIsLoading(true);
    try {
      const connected = await api.checkConnection();
      setIsBackendConnected(connected);

      const [
        prodsData,
        catsData,
        supsData,
        batchesData,
        movesData,
        ordersData,
        reordersData,
        expAlertsData,
        statsData,
      ] = await Promise.all([
        api.getProducts(),
        api.getCategories(),
        api.getSuppliers(),
        api.getInventoryBatches(),
        api.getStockMovements(),
        api.getPurchaseOrders(),
        api.getReorderRecommendations(),
        api.getExpiryAlerts(30),
        api.getDashboardStats(),
      ]);

      setProducts(prodsData);
      setCategories(catsData);
      setSuppliers(supsData);
      setBatches(batchesData);
      setMovements(movesData);
      setOrders(ordersData);
      setReorders(reordersData);
      setExpiryAlerts(expAlertsData);
      setStats(statsData);
    } catch (err) {
      console.error('Error loading data', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAllData();
  }, [loadAllData]);

  const handleQuickAction = (action: 'new-sale' | 'new-receipt' | 'refresh' | 'voice-assistant') => {
    if (action === 'new-sale') {
      setCurrentTab('pos');
    } else if (action === 'new-receipt') {
      setCurrentTab('inventory');
    } else if (action === 'refresh') {
      loadAllData();
    } else if (action === 'voice-assistant') {
      setCurrentTab('assistant');
    }
  };

  return (
    <div style={{ display: 'flex', width: '100%', minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* Left Sidebar */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        isBackendConnected={isBackendConnected}
      />

      {/* Main Content Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflowX: 'hidden' }}>
        <Header
          currentTab={currentTab}
          onQuickAction={handleQuickAction}
          isLoading={isLoading}
        />

        <main style={{ flex: 1, padding: '28px 32px', maxWidth: '1440px', width: '100%', margin: '0 auto' }}>
          {currentTab === 'dashboard' && (
            <DashboardPage
              stats={stats}
              products={products}
              reorders={reorders}
              expiryAlerts={expiryAlerts}
              onNavigate={setCurrentTab}
            />
          )}

          {currentTab === 'assistant' && (
            <VoiceAssistantPage
              products={products}
              onNavigateTab={setCurrentTab}
              onDataChanged={loadAllData}
            />
          )}

          {currentTab === 'pos' && (
            <PosSalesPage
              products={products}
              clearancePromotions={clearancePromotions}
              onSaleCompleted={loadAllData}
            />
          )}

          {currentTab === 'reorder' && (
            <AiReorderPage
              reorders={reorders}
              onReordersUpdated={loadAllData}
              onNavigateToPurchases={() => setCurrentTab('purchases')}
            />
          )}

          {currentTab === 'expiry' && (
            <ExpiryManagerPage
              alerts={expiryAlerts}
              products={products}
              clearancePromotions={clearancePromotions}
              onApplyPromotion={handleApplyClearancePromotion}
              onRemovePromotion={handleRemoveClearancePromotion}
            />
          )}

          {currentTab === 'inventory' && (
            <InventoryPage
              batches={batches}
              movements={movements}
              products={products}
              onInventoryChanged={loadAllData}
            />
          )}

          {currentTab === 'products' && (
            <ProductsPage
              products={products}
              categories={categories}
              suppliers={suppliers}
              onProductCreated={loadAllData}
            />
          )}

          {currentTab === 'purchases' && (
            <PurchaseOrdersPage
              orders={orders}
              suppliers={suppliers}
              products={products}
              onOrderChanged={loadAllData}
            />
          )}

          {currentTab === 'suppliers' && (
            <SuppliersPage
              suppliers={suppliers}
            />
          )}

          {currentTab === 'reports' && (
            <ReportsPage
              stats={stats}
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
