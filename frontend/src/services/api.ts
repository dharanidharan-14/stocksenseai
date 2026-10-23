/**
 * StockSense AI - API Client & Mock Data Service
 */

import axios from 'axios';
import {
  Product,
  Category,
  Supplier,
  InventoryBatch,
  StockMovement,
  Sale,
  PurchaseOrder,
  ReorderRecommendation,
  BudgetPlan,
  ExpiryAlert,
  DashboardStats,
  User,
  AssistantResponse,
} from '../types';

const API_BASE_URL = 'http://localhost:8000/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 6000,
});

// Attach JWT token from localStorage if present
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('stocksense_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Fallback Mock Dataset for Instant Testing & Offline Resilience
const mockCategories: Category[] = [
  { id: 1, name: 'Grains & Flours', description: 'Staple wheat flour, basmati rice, rava' },
  { id: 2, name: 'Pulses & Dals', description: 'Toor dal, moong dal, chana dal' },
  { id: 3, name: 'Cooking Oils & Ghee', description: 'Refined sunflower oil, pure cow ghee' },
  { id: 4, name: 'Dairy & Bakery', description: 'Fresh milk, butter, whole wheat bread' },
  { id: 5, name: 'Spices & Masalas', description: 'Iodized salt, turmeric, garam masala' },
  { id: 6, name: 'Snacks & Biscuits', description: 'Instant noodles, glucose biscuits' },
  { id: 7, name: 'Beverages', description: 'Leaf tea, filter coffee, health drinks' },
  { id: 8, name: 'Household & Cleaning', description: 'Detergents, dishwash bars, floor cleaners' },
];

const mockSuppliers: Supplier[] = [
  {
    id: 1,
    name: 'Sri Krishna FMCG Wholesalers',
    contact_person: 'Venkatesh Rao',
    phone: '+91 98450 12345',
    email: 'orders@srikrishnafmcg.in',
    address: 'Shop 42, Wholesale APMC Market Yard, Bengaluru',
    lead_time_days: 2,
    min_order_quantity: 10,
    min_order_value: 4000,
    notes: 'Fastest FMCG supplier for staples and packaged goods.',
    is_active: true,
  },
  {
    id: 2,
    name: 'Annapurna Grain & Dal Millers',
    contact_person: 'Suresh Patel',
    phone: '+91 98200 54321',
    email: 'suresh@annapurnagrains.com',
    address: 'Grain Merchant Street, Old City, Hyderabad',
    lead_time_days: 4,
    min_order_quantity: 25,
    min_order_value: 5000,
    notes: 'Direct mill rates for pulses, rice and flours.',
    is_active: true,
  },
  {
    id: 3,
    name: 'Om Shakti Fresh Dairy & Bakery',
    contact_person: 'Manoj Yadav',
    phone: '+91 97110 98765',
    email: 'dispatch@omshaktidairy.com',
    address: 'Dairy Circle, Bengaluru',
    lead_time_days: 1,
    min_order_quantity: 5,
    min_order_value: 1000,
    notes: 'Daily morning deliveries for fresh milk, bread, butter.',
    is_active: true,
  },
  {
    id: 4,
    name: 'Balaji Spices & Edible Oils Ltd',
    contact_person: 'Chandresh Shah',
    phone: '+91 99001 23456',
    email: 'chandresh@balajispices.co.in',
    address: 'Trade Center, APMC Market, Chennai',
    lead_time_days: 3,
    min_order_quantity: 15,
    min_order_value: 3500,
    notes: 'Authorized distributor for Fortune, Amul Ghee, Tata Salt.',
    is_active: true,
  },
  {
    id: 5,
    name: 'Hindustan Retail Logistics',
    contact_person: 'Deepak Verma',
    phone: '+91 98190 67890',
    email: 'orders@hindustanretail.com',
    address: 'Central Warehouse Complex, Hosur Road',
    lead_time_days: 5,
    min_order_quantity: 20,
    min_order_value: 6000,
    notes: 'Home care and personal hygiene products distributor.',
    is_active: true,
  },
];

let mockProducts: Product[] = [
  {
    id: 1,
    name: 'Aashirvaad Shudh Chakki Atta 5kg',
    sku: 'GRN-ATTA-005',
    category_id: 1,
    category_name: 'Grains & Flours',
    unit: 'packet',
    purchase_cost: 210,
    selling_price: 245,
    preferred_supplier_id: 2,
    supplier_name: 'Annapurna Grain & Dal Millers',
    supplier_lead_time_days: 4,
    safety_stock: 15,
    reorder_threshold: 25,
    shelf_life_days: 90,
    usable_stock: 43,
    total_stock: 43,
    expired_stock: 0,
    is_active: true,
  },
  {
    id: 2,
    name: 'India Gate Basmati Rice Rozzana 5kg',
    sku: 'GRN-RICE-005',
    category_id: 1,
    category_name: 'Grains & Flours',
    unit: 'packet',
    purchase_cost: 380,
    selling_price: 440,
    preferred_supplier_id: 2,
    supplier_name: 'Annapurna Grain & Dal Millers',
    supplier_lead_time_days: 4,
    safety_stock: 10,
    reorder_threshold: 18,
    shelf_life_days: 365,
    usable_stock: 24,
    total_stock: 24,
    expired_stock: 0,
    is_active: true,
  },
  {
    id: 3,
    name: 'Tata Salt Vacuum Evaporated Iodized 1kg',
    sku: 'SPC-SALT-001',
    category_id: 5,
    category_name: 'Spices & Masalas',
    unit: 'packet',
    purchase_cost: 22,
    selling_price: 28,
    preferred_supplier_id: 4,
    supplier_name: 'Balaji Spices & Edible Oils Ltd',
    supplier_lead_time_days: 3,
    safety_stock: 30,
    reorder_threshold: 45,
    shelf_life_days: 730,
    usable_stock: 4, // CRITICAL LOW STOCK
    total_stock: 4,
    expired_stock: 0,
    is_active: true,
  },
  {
    id: 4,
    name: 'Fortune Sunlite Refined Sunflower Oil 1L Pouch',
    sku: 'OIL-SUN-001',
    category_id: 3,
    category_name: 'Cooking Oils & Ghee',
    unit: 'packet',
    purchase_cost: 118,
    selling_price: 138,
    preferred_supplier_id: 4,
    supplier_name: 'Balaji Spices & Edible Oils Ltd',
    supplier_lead_time_days: 3,
    safety_stock: 20,
    reorder_threshold: 32,
    shelf_life_days: 270,
    usable_stock: 28,
    total_stock: 28,
    expired_stock: 0,
    is_active: true,
  },
  {
    id: 5,
    name: 'Amul Pure Ghee 1L Tin',
    sku: 'OIL-GHEE-001',
    category_id: 3,
    category_name: 'Cooking Oils & Ghee',
    unit: 'bottle',
    purchase_cost: 565,
    selling_price: 640,
    preferred_supplier_id: 4,
    supplier_name: 'Balaji Spices & Edible Oils Ltd',
    supplier_lead_time_days: 3,
    safety_stock: 8,
    reorder_threshold: 14,
    shelf_life_days: 270,
    usable_stock: 12,
    total_stock: 12,
    expired_stock: 0,
    is_active: true,
  },
  {
    id: 6,
    name: 'Toor Dal Premium Unpolished 1kg',
    sku: 'PUL-TOOR-001',
    category_id: 2,
    category_name: 'Pulses & Dals',
    unit: 'kg',
    purchase_cost: 142,
    selling_price: 168,
    preferred_supplier_id: 2,
    supplier_name: 'Annapurna Grain & Dal Millers',
    supplier_lead_time_days: 4,
    safety_stock: 18,
    reorder_threshold: 28,
    shelf_life_days: 180,
    usable_stock: 28,
    total_stock: 28,
    expired_stock: 0,
    is_active: true,
  },
  {
    id: 7,
    name: 'Amul Taaza Fresh Toned Milk 500ml',
    sku: 'DAY-MILK-001',
    category_id: 4,
    category_name: 'Dairy & Bakery',
    unit: 'packet',
    purchase_cost: 25.5,
    selling_price: 28,
    preferred_supplier_id: 3,
    supplier_name: 'Om Shakti Fresh Dairy & Bakery',
    supplier_lead_time_days: 1,
    safety_stock: 35,
    reorder_threshold: 45,
    shelf_life_days: 2,
    usable_stock: 36,
    total_stock: 36,
    expired_stock: 0,
    is_active: true,
  },
  {
    id: 8,
    name: 'Britannia 100% Whole Wheat Bread 400g',
    sku: 'DAY-BRED-001',
    category_id: 4,
    category_name: 'Dairy & Bakery',
    unit: 'packet',
    purchase_cost: 42,
    selling_price: 50,
    preferred_supplier_id: 3,
    supplier_name: 'Om Shakti Fresh Dairy & Bakery',
    supplier_lead_time_days: 1,
    safety_stock: 15,
    reorder_threshold: 22,
    shelf_life_days: 5,
    usable_stock: 22,
    total_stock: 22,
    expired_stock: 0,
    is_active: true,
  },
  {
    id: 9,
    name: 'Maggi 2-Minute Masala Instant Noodles 4-Pack',
    sku: 'SNK-MAGI-004',
    category_id: 6,
    category_name: 'Snacks & Biscuits',
    unit: 'packet',
    purchase_cost: 48,
    selling_price: 56,
    preferred_supplier_id: 1,
    supplier_name: 'Sri Krishna FMCG Wholesalers',
    supplier_lead_time_days: 2,
    safety_stock: 40,
    reorder_threshold: 60,
    shelf_life_days: 270,
    usable_stock: 7, // CRITICAL LOW STOCK
    total_stock: 7,
    expired_stock: 0,
    is_active: true,
  },
  {
    id: 10,
    name: 'Parle-G Gold Original Glucose Biscuits 1kg',
    sku: 'SNK-PARL-001',
    category_id: 6,
    category_name: 'Snacks & Biscuits',
    unit: 'packet',
    purchase_cost: 85,
    selling_price: 100,
    preferred_supplier_id: 1,
    supplier_name: 'Sri Krishna FMCG Wholesalers',
    supplier_lead_time_days: 2,
    safety_stock: 20,
    reorder_threshold: 30,
    shelf_life_days: 180,
    usable_stock: 22,
    total_stock: 22,
    expired_stock: 0,
    is_active: true,
  },
  {
    id: 11,
    name: 'Tata Tea Gold Leaf 500g',
    sku: 'BEV-TTEA-500',
    category_id: 7,
    category_name: 'Beverages',
    unit: 'packet',
    purchase_cost: 295,
    selling_price: 340,
    preferred_supplier_id: 1,
    supplier_name: 'Sri Krishna FMCG Wholesalers',
    supplier_lead_time_days: 2,
    safety_stock: 12,
    reorder_threshold: 18,
    shelf_life_days: 365,
    usable_stock: 15,
    total_stock: 15,
    expired_stock: 0,
    is_active: true,
  },
  {
    id: 12,
    name: 'Surf Excel Easy Wash Detergent Powder 1kg',
    sku: 'HSD-SURF-001',
    category_id: 8,
    category_name: 'Household & Cleaning',
    unit: 'packet',
    purchase_cost: 125,
    selling_price: 148,
    preferred_supplier_id: 5,
    supplier_name: 'Hindustan Retail Logistics',
    supplier_lead_time_days: 5,
    safety_stock: 15,
    reorder_threshold: 25,
    usable_stock: 19,
    total_stock: 19,
    expired_stock: 0,
    is_active: true,
  },
];

let mockBatches: InventoryBatch[] = [
  {
    id: 1,
    product_id: 7, // Milk
    product_name: 'Amul Taaza Fresh Toned Milk 500ml',
    batch_number: 'BAT-MILK-EXP',
    received_quantity: 15,
    remaining_quantity: 8,
    unit_cost: 25.5,
    manufacture_date: new Date(Date.now() - 86400000).toISOString().split('T')[0],
    expiry_date: new Date(Date.now() + 86400000).toISOString().split('T')[0], // TOMORROW!
    source_type: 'OPENING',
    days_to_expiry: 1,
    is_expired: false,
  },
  {
    id: 2,
    product_id: 7, // Milk Fresh
    product_name: 'Amul Taaza Fresh Toned Milk 500ml',
    batch_number: 'BAT-MILK-FRS',
    received_quantity: 30,
    remaining_quantity: 28,
    unit_cost: 25.5,
    manufacture_date: new Date().toISOString().split('T')[0],
    expiry_date: new Date(Date.now() + 172800000).toISOString().split('T')[0],
    source_type: 'OPENING',
    days_to_expiry: 2,
    is_expired: false,
  },
  {
    id: 3,
    product_id: 8, // Bread Urgent
    product_name: 'Britannia 100% Whole Wheat Bread 400g',
    batch_number: 'BAT-BRED-01',
    received_quantity: 12,
    remaining_quantity: 4,
    unit_cost: 42,
    manufacture_date: new Date(Date.now() - 259200000).toISOString().split('T')[0],
    expiry_date: new Date(Date.now() + 172800000).toISOString().split('T')[0], // In 2 days!
    source_type: 'OPENING',
    days_to_expiry: 2,
    is_expired: false,
  },
  {
    id: 4,
    product_id: 8, // Bread Fresh
    product_name: 'Britannia 100% Whole Wheat Bread 400g',
    batch_number: 'BAT-BRED-02',
    received_quantity: 20,
    remaining_quantity: 18,
    unit_cost: 42,
    manufacture_date: new Date(Date.now() - 86400000).toISOString().split('T')[0],
    expiry_date: new Date(Date.now() + 345600000).toISOString().split('T')[0],
    source_type: 'OPENING',
    days_to_expiry: 4,
    is_expired: false,
  },
  {
    id: 5,
    product_id: 3, // Salt Low
    product_name: 'Tata Salt Vacuum Evaporated Iodized 1kg',
    batch_number: 'BAT-SALT-01',
    received_quantity: 40,
    remaining_quantity: 4,
    unit_cost: 22,
    manufacture_date: '2026-08-01',
    expiry_date: '2028-08-01',
    source_type: 'OPENING',
    days_to_expiry: 650,
    is_expired: false,
  },
  {
    id: 6,
    product_id: 9, // Maggi Low
    product_name: 'Maggi 2-Minute Masala Instant Noodles 4-Pack',
    batch_number: 'BAT-MAGI-01',
    received_quantity: 50,
    remaining_quantity: 7,
    unit_cost: 48,
    manufacture_date: '2026-09-01',
    expiry_date: '2027-06-01',
    source_type: 'OPENING',
    days_to_expiry: 220,
    is_expired: false,
  },
  {
    id: 7,
    product_id: 1, // Atta Batch 1
    product_name: 'Aashirvaad Shudh Chakki Atta 5kg',
    batch_number: 'BAT-ATTA-01',
    received_quantity: 20,
    remaining_quantity: 18,
    unit_cost: 210,
    manufacture_date: '2026-10-01',
    expiry_date: '2027-01-01',
    source_type: 'OPENING',
    days_to_expiry: 70,
    is_expired: false,
  },
  {
    id: 8,
    product_id: 1, // Atta Batch 2
    product_name: 'Aashirvaad Shudh Chakki Atta 5kg',
    batch_number: 'BAT-ATTA-02',
    received_quantity: 25,
    remaining_quantity: 25,
    unit_cost: 210,
    manufacture_date: '2026-10-18',
    expiry_date: '2027-01-18',
    source_type: 'OPENING',
    days_to_expiry: 87,
    is_expired: false,
  },
];

let mockMovements: StockMovement[] = [
  {
    id: 101,
    product_id: 3,
    product_name: 'Tata Salt Vacuum Evaporated Iodized 1kg',
    batch_id: 5,
    batch_number: 'BAT-SALT-01',
    movement_type: 'SALE',
    quantity: -6,
    reference_type: 'SALE',
    reference_id: 42,
    notes: 'FEFO stock deduction: sale POS counter bill #1042',
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: 102,
    product_id: 7,
    product_name: 'Amul Taaza Fresh Toned Milk 500ml',
    batch_id: 1,
    batch_number: 'BAT-MILK-EXP',
    movement_type: 'SALE',
    quantity: -4,
    reference_type: 'SALE',
    reference_id: 43,
    notes: 'FEFO stock deduction: earliest batch BAT-MILK-EXP',
    created_at: new Date(Date.now() - 7200000).toISOString(),
  },
  {
    id: 103,
    product_id: 1,
    product_name: 'Aashirvaad Shudh Chakki Atta 5kg',
    batch_id: 7,
    batch_number: 'BAT-ATTA-01',
    movement_type: 'RECEIPT',
    quantity: 25,
    reference_type: 'PURCHASE',
    notes: 'Supplier delivery receipt from Annapurna Grain Traders',
    created_at: new Date(Date.now() - 86400000).toISOString(),
  },
];

let mockPurchaseOrders: PurchaseOrder[] = [
  {
    id: 1,
    po_number: 'PO-2026-0001',
    supplier_id: 4,
    supplier_name: 'Balaji Spices & Edible Oils Ltd',
    order_date: new Date(Date.now() - 86400000).toISOString().split('T')[0],
    expected_delivery_date: new Date(Date.now() + 172800000).toISOString().split('T')[0],
    status: 'ORDERED',
    total_amount: 1100,
    notes: 'Urgent replenishment for low stock Tata Salt',
    items: [
      {
        id: 1,
        product_id: 3,
        product_name: 'Tata Salt Vacuum Evaporated Iodized 1kg',
        ordered_quantity: 50,
        received_quantity: 0,
        unit_cost: 22,
        line_total: 1100,
      },
    ],
  },
  {
    id: 2,
    po_number: 'PO-2026-0002',
    supplier_id: 2,
    supplier_name: 'Annapurna Grain & Dal Millers',
    order_date: new Date().toISOString().split('T')[0],
    expected_delivery_date: new Date(Date.now() + 345600000).toISOString().split('T')[0],
    status: 'DRAFT',
    total_amount: 8000,
    notes: 'Weekly staples replenishment draft',
    items: [
      {
        id: 2,
        product_id: 1,
        product_name: 'Aashirvaad Shudh Chakki Atta 5kg',
        ordered_quantity: 20,
        received_quantity: 0,
        unit_cost: 210,
        line_total: 4200,
      },
      {
        id: 3,
        product_id: 2,
        product_name: 'India Gate Basmati Rice Rozzana 5kg',
        ordered_quantity: 10,
        received_quantity: 0,
        unit_cost: 380,
        line_total: 3800,
      },
    ],
  },
];

let mockReorders: ReorderRecommendation[] = [
  {
    id: 1,
    product_id: 3,
    product_name: 'Tata Salt Vacuum Evaporated Iodized 1kg',
    sku: 'SPC-SALT-001',
    category_name: 'Spices & Masalas',
    usable_stock: 4,
    incoming_stock: 50,
    daily_demand: 7.2,
    lead_time_demand: 21.6,
    safety_stock: 30,
    target_stock: 51.6,
    inventory_position: 54,
    suggested_quantity: 50,
    estimated_cost: 1100,
    priority: 'URGENT',
    explanation: 'Current stock is only 4 units. Stock will exhaust in 0.5 days. 50 units already on order PO-2026-0001 arriving in 2 days.',
    forecast_confidence: 'HIGH',
    run_date: new Date().toISOString(),
  },
  {
    id: 2,
    product_id: 9,
    product_name: 'Maggi 2-Minute Masala Instant Noodles 4-Pack',
    sku: 'SNK-MAGI-004',
    category_name: 'Snacks & Biscuits',
    usable_stock: 7,
    incoming_stock: 0,
    daily_demand: 14.5,
    lead_time_demand: 29.0,
    safety_stock: 40,
    target_stock: 69.0,
    inventory_position: 7,
    suggested_quantity: 62,
    estimated_cost: 2976,
    priority: 'URGENT',
    explanation: 'High velocity product with only 7 units remaining (exhausts in 11 hours). Supplier lead time is 2 days. Immediate order required!',
    forecast_confidence: 'HIGH',
    run_date: new Date().toISOString(),
  },
  {
    id: 3,
    product_id: 7,
    product_name: 'Amul Taaza Fresh Toned Milk 500ml',
    sku: 'DAY-MILK-001',
    category_name: 'Dairy & Bakery',
    usable_stock: 36,
    incoming_stock: 0,
    daily_demand: 18.0,
    lead_time_demand: 18.0,
    safety_stock: 35,
    target_stock: 53.0,
    inventory_position: 36,
    suggested_quantity: 20,
    estimated_cost: 510,
    priority: 'HIGH',
    explanation: 'Daily fresh dairy item. 8 units are expiring tomorrow. Net fresh stock is 28 units, which will sell out within 1.5 days.',
    forecast_confidence: 'HIGH',
    run_date: new Date().toISOString(),
  },
  {
    id: 4,
    product_id: 8,
    product_name: 'Britannia 100% Whole Wheat Bread 400g',
    sku: 'DAY-BRED-001',
    category_name: 'Dairy & Bakery',
    usable_stock: 22,
    incoming_stock: 0,
    daily_demand: 9.0,
    lead_time_demand: 9.0,
    safety_stock: 15,
    target_stock: 24.0,
    inventory_position: 22,
    suggested_quantity: 10,
    estimated_cost: 420,
    priority: 'MEDIUM',
    explanation: 'Fast moving bakery staple. 4 units expire in 2 days. Suggested reorder to maintain safety stock after weekend rush.',
    forecast_confidence: 'MEDIUM',
    run_date: new Date().toISOString(),
  },
  {
    id: 5,
    product_id: 1,
    product_name: 'Aashirvaad Shudh Chakki Atta 5kg',
    sku: 'GRN-ATTA-005',
    category_name: 'Grains & Flours',
    usable_stock: 43,
    incoming_stock: 20,
    daily_demand: 4.8,
    lead_time_demand: 19.2,
    safety_stock: 15,
    target_stock: 34.2,
    inventory_position: 63,
    suggested_quantity: 0,
    estimated_cost: 0,
    priority: 'LOW',
    explanation: 'Optimal inventory levels. Stock lasts for 9+ days. No order needed.',
    forecast_confidence: 'HIGH',
    run_date: new Date().toISOString(),
  },
];

// Unified API Service
export const api = {
  // Check Connection & Ensure Live Auth
  async checkConnection(): Promise<boolean> {
    try {
      let token = localStorage.getItem('stocksense_token');
      if (!token || token === 'demo-token') {
        const loginResp = await axios.post(`${API_BASE_URL}/auth/login`, {
          email: 'admin@stocksense.ai',
          password: 'Admin@12345',
        });
        token = loginResp.data.access_token;
        if (token) {
          localStorage.setItem('stocksense_token', token);
        }
      }
      await apiClient.get('/products?page_size=1');
      return true;
    } catch {
      try {
        const loginResp = await axios.post(`${API_BASE_URL}/auth/login`, {
          email: 'admin@stocksense.ai',
          password: 'Admin@12345',
        });
        const token = loginResp.data.access_token;
        if (token) {
          localStorage.setItem('stocksense_token', token);
        }
        await apiClient.get('/products?page_size=1');
        return true;
      } catch {
        return false;
      }
    }
  },

  // Auth
  async login(email: string, password: string):Promise<{ access_token: string; user: User }> {
    try {
      const resp = await apiClient.post('/auth/login', { email, password });
      localStorage.setItem('stocksense_token', resp.data.access_token);
      return resp.data;
    } catch {
      // Demo login
      const demoUser: User = {
        id: '3539b026-9671-4ae0-91b3-18f17f07d2bf',
        email: email || 'admin@stocksense.ai',
        username: 'admin',
        full_name: 'Ramesh Kumar (Store Owner)',
        is_active: true,
        is_superuser: true,
      };
      localStorage.setItem('stocksense_token', 'demo-token');
      return { access_token: 'demo-token', user: demoUser };
    }
  },

  // Products
  async getProducts(): Promise<Product[]> {
    try {
      const resp = await apiClient.get('/products?page_size=100');
      if (resp.data && Array.isArray(resp.data.items)) {
        return resp.data.items.map((p: any) => {
          const stock = Number(p.usable_stock ?? p.current_stock ?? p.total_stock ?? 0);
          return {
            ...p,
            purchase_cost: Number(p.purchase_cost),
            selling_price: Number(p.selling_price),
            safety_stock: Number(p.safety_stock || 0),
            reorder_threshold: Number(p.reorder_threshold || 0),
            usable_stock: stock,
            current_stock: stock,
            total_stock: Number(p.total_stock ?? stock),
            category_name: p.category_name || (p.category ? p.category.name : undefined),
            supplier_name: p.supplier_name || (p.preferred_supplier ? p.preferred_supplier.name : undefined),
          };
        });
      }
    } catch (e) {
      console.warn('Backend unavailable, using mock products', e);
    }
    return mockProducts;
  },

  async createProduct(prodData: Partial<Product>): Promise<Product> {
    try {
      const resp = await apiClient.post('/products', prodData);
      return resp.data;
    } catch {
      const newProd: Product = {
        id: mockProducts.length + 1,
        name: prodData.name || 'New Product',
        sku: prodData.sku || `SKU-${Date.now()}`,
        unit: prodData.unit || 'packet',
        purchase_cost: Number(prodData.purchase_cost) || 100,
        selling_price: Number(prodData.selling_price) || 120,
        supplier_lead_time_days: Number(prodData.supplier_lead_time_days) || 3,
        safety_stock: Number(prodData.safety_stock) || 10,
        reorder_threshold: Number(prodData.reorder_threshold) || 15,
        shelf_life_days: prodData.shelf_life_days ? Number(prodData.shelf_life_days) : undefined,
        usable_stock: 0,
        total_stock: 0,
        is_active: true,
      };
      mockProducts.unshift(newProd);
      return newProd;
    }
  },

  async getCategories(): Promise<Category[]> {
    try {
      const resp = await apiClient.get('/products/categories');
      return resp.data;
    } catch {
      return mockCategories;
    }
  },

  // Suppliers
  async getSuppliers(): Promise<Supplier[]> {
    try {
      const resp = await apiClient.get('/suppliers?limit=100');
      return resp.data.items || resp.data;
    } catch {
      return mockSuppliers;
    }
  },

  // Inventory & Batches
  async getInventoryBatches(): Promise<InventoryBatch[]> {
    try {
      const resp = await apiClient.get('/inventory/batches?limit=100');
      return resp.data.items.map((b: any) => ({
        ...b,
        received_quantity: Number(b.received_quantity),
        remaining_quantity: Number(b.remaining_quantity),
        unit_cost: Number(b.unit_cost),
      }));
    } catch {
      return mockBatches;
    }
  },

  async getStockMovements(): Promise<StockMovement[]> {
    try {
      const resp = await apiClient.get('/inventory/movements?limit=100');
      return resp.data.items.map((m: any) => ({
        ...m,
        quantity: Number(m.quantity),
      }));
    } catch {
      return mockMovements;
    }
  },

  async createStockReceipt(data: any): Promise<any> {
    try {
      const resp = await apiClient.post('/inventory/receipts', data);
      return resp.data;
    } catch {
      // Mock local addition
      const batch: InventoryBatch = {
        id: mockBatches.length + 1,
        product_id: data.product_id,
        batch_number: data.batch_number || `BAT-${Date.now()}`,
        received_quantity: Number(data.quantity),
        remaining_quantity: Number(data.quantity),
        unit_cost: Number(data.unit_cost),
        expiry_date: data.expiry_date,
        source_type: data.source_type || 'DIRECT_RECEIPT',
        is_expired: false,
      };
      mockBatches.unshift(batch);
      const prod = mockProducts.find((p) => p.id === data.product_id);
      if (prod) {
        prod.usable_stock = (prod.usable_stock || 0) + Number(data.quantity);
        prod.total_stock = (prod.total_stock || 0) + Number(data.quantity);
        prod.current_stock = prod.usable_stock;
      }
      return batch;
    }
  },

  // Sales / POS Checkout
  async createSale(saleData: { items: { product_id: number; quantity: number; unit_price: number }[]; notes?: string }): Promise<Sale> {
    try {
      const resp = await apiClient.post('/sales', saleData);
      return resp.data;
    } catch {
      // Mock local FEFO sale execution
      let totalAmount = 0;
      let totalItems = 0;
      const saleItems: any[] = [];

      for (const item of saleData.items) {
        const prod = mockProducts.find((p) => p.id === item.product_id);
        const lineTotal = item.quantity * item.unit_price;
        totalAmount += lineTotal;
        totalItems += item.quantity;

        if (prod && prod.usable_stock !== undefined) {
          prod.usable_stock = Math.max(0, prod.usable_stock - item.quantity);
          prod.total_stock = Math.max(0, (prod.total_stock || 0) - item.quantity);
        }

        saleItems.push({
          product_id: item.product_id,
          product_name: prod ? prod.name : 'Item',
          quantity: item.quantity,
          unit_price: item.unit_price,
          line_total: lineTotal,
        });

        // Add to mock movements
        mockMovements.unshift({
          id: mockMovements.length + 1,
          product_id: item.product_id,
          product_name: prod ? prod.name : 'Item',
          movement_type: 'SALE',
          quantity: -item.quantity,
          reference_type: 'SALE',
          notes: 'POS checkout sale transaction',
          created_at: new Date().toISOString(),
        });
      }

      const newSale: Sale = {
        id: Date.now(),
        sale_number: `SAL-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${Math.floor(Math.random() * 90 + 10)}`,
        sale_date: new Date().toISOString(),
        total_amount: totalAmount,
        total_items: totalItems,
        status: 'COMPLETED',
        notes: saleData.notes || 'Counter POS Bill',
        items: saleItems,
      };
      return newSale;
    }
  },

  // Purchase Orders
  async getPurchaseOrders(): Promise<PurchaseOrder[]> {
    try {
      const resp = await apiClient.get('/purchases?limit=100');
      return resp.data.items || resp.data;
    } catch {
      return mockPurchaseOrders;
    }
  },

  async createPurchaseOrder(poData: any): Promise<PurchaseOrder> {
    try {
      const resp = await apiClient.post('/purchases', poData);
      return resp.data;
    } catch {
      const sup = mockSuppliers.find((s) => s.id === poData.supplier_id);
      const newPo: PurchaseOrder = {
        id: mockPurchaseOrders.length + 1,
        po_number: `PO-2026-${String(mockPurchaseOrders.length + 1).padStart(4, '0')}`,
        supplier_id: poData.supplier_id,
        supplier_name: sup ? sup.name : 'Wholesaler',
        order_date: new Date().toISOString().split('T')[0],
        status: 'ORDERED',
        total_amount: poData.items.reduce((sum: number, it: any) => sum + it.ordered_quantity * it.unit_cost, 0),
        notes: poData.notes,
        items: poData.items.map((it: any, idx: number) => {
          const p = mockProducts.find((prod) => prod.id === it.product_id);
          return {
            id: idx + 1,
            product_id: it.product_id,
            product_name: p ? p.name : 'Product',
            ordered_quantity: it.ordered_quantity,
            received_quantity: 0,
            unit_cost: it.unit_cost,
            line_total: it.ordered_quantity * it.unit_cost,
          };
        }),
      };
      mockPurchaseOrders.unshift(newPo);
      return newPo;
    }
  },

  // AI Reorder & Forecasting
  async getReorderRecommendations(): Promise<ReorderRecommendation[]> {
    try {
      const resp = await apiClient.get('/forecast/reorder/recommendations');
      if (resp.data && Array.isArray(resp.data)) {
        return resp.data.map((r: any) => ({
          ...r,
          usable_stock: Number(r.usable_stock),
          incoming_stock: Number(r.incoming_stock),
          daily_demand: Number(r.daily_demand),
          suggested_quantity: Number(r.suggested_quantity),
          estimated_cost: Number(r.estimated_cost),
        }));
      }
    } catch (e) {
      console.warn('Reorders API unavailable, using engine mock data', e);
    }
    return mockReorders;
  },

  async runDemandForecast(horizonDays: number = 7): Promise<any> {
    try {
      const resp = await apiClient.post('/forecast/run', { horizon_days: horizonDays });
      return resp.data;
    } catch {
      return { status: 'SUCCESS', message: `Forecast run generated for ${horizonDays} days across active SKUs.` };
    }
  },

  // Budget Optimizer Simulation
  async simulateBudgetPlan(budgetAmount: number): Promise<BudgetPlan> {
    try {
      const resp = await apiClient.post('/forecast/budget/plan', { budget_amount: budgetAmount });
      return resp.data;
    } catch {
      // Client-side simulation of the greedy priority optimizer
      let remaining = budgetAmount;
      let totalAllocated = 0;
      const items: any[] = [];
      let includedCount = 0;
      let excludedCount = 0;

      // Priority sort: URGENT > HIGH > MEDIUM > LOW
      const priorityWeights = { URGENT: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
      const sorted = [...mockReorders].sort((a, b) => priorityWeights[b.priority] - priorityWeights[a.priority]);

      for (const rec of sorted) {
        if (rec.suggested_quantity <= 0) continue;
        const prod = mockProducts.find((p) => p.id === rec.product_id);
        const costPerUnit = prod ? prod.purchase_cost : rec.estimated_cost / rec.suggested_quantity;
        const lineCost = rec.suggested_quantity * costPerUnit;

        if (remaining >= lineCost) {
          remaining -= lineCost;
          totalAllocated += lineCost;
          includedCount++;
          items.push({
            product_id: rec.product_id,
            product_name: rec.product_name,
            sku: rec.sku,
            suggested_quantity: rec.suggested_quantity,
            unit_cost: costPerUnit,
            line_cost: lineCost,
            priority: rec.priority,
            included: true,
          });
        } else {
          excludedCount++;
          items.push({
            product_id: rec.product_id,
            product_name: rec.product_name,
            sku: rec.sku,
            suggested_quantity: rec.suggested_quantity,
            unit_cost: costPerUnit,
            line_cost: lineCost,
            priority: rec.priority,
            included: false,
            exclusion_reason: `Insufficient budget remaining (Needs ₹${lineCost.toLocaleString('en-IN')}, Remaining ₹${remaining.toLocaleString('en-IN')})`,
          });
        }
      }

      return {
        budget_amount: budgetAmount,
        total_allocated: totalAllocated,
        remaining_budget: remaining,
        items_included: includedCount,
        items_excluded: excludedCount,
        items: items,
        notes: `Plan dynamically generated for ₹${budgetAmount.toLocaleString('en-IN')} budget constraint.`,
      };
    }
  },

  // Expiry Alerts
  async getExpiryAlerts(daysThreshold: number = 30): Promise<ExpiryAlert[]> {
    try {
      const resp = await apiClient.get(`/forecast/expiry/alerts?days_threshold=${daysThreshold}`);
      return resp.data;
    } catch {
      // Mock alerts
      return [
        {
          product_id: 7,
          product_name: 'Amul Taaza Fresh Toned Milk 500ml',
          sku: 'DAY-MILK-001',
          batch_id: 1,
          batch_number: 'BAT-MILK-EXP',
          remaining_quantity: 8,
          unit: 'packet',
          expiry_date: new Date(Date.now() + 86400000).toISOString().split('T')[0],
          days_until_expiry: 1,
          purchase_cost: 25.5,
          potential_loss: 204.0,
          status: 'CRITICAL',
        },
        {
          product_id: 8,
          product_name: 'Britannia 100% Whole Wheat Bread 400g',
          sku: 'DAY-BRED-001',
          batch_id: 3,
          batch_number: 'BAT-BRED-01',
          remaining_quantity: 4,
          unit: 'packet',
          expiry_date: new Date(Date.now() + 172800000).toISOString().split('T')[0],
          days_until_expiry: 2,
          purchase_cost: 42.0,
          potential_loss: 168.0,
          status: 'CRITICAL',
        },
        {
          product_id: 1,
          product_name: 'Aashirvaad Shudh Chakki Atta 5kg',
          sku: 'GRN-ATTA-005',
          batch_id: 7,
          batch_number: 'BAT-ATTA-01',
          remaining_quantity: 18,
          unit: 'packet',
          expiry_date: new Date(Date.now() + 6048000000).toISOString().split('T')[0],
          days_until_expiry: 70,
          purchase_cost: 210.0,
          potential_loss: 3780.0,
          status: 'ATTENTION',
        },
      ];
    }
  },

  // Dashboard Stats
  async getDashboardStats(): Promise<DashboardStats> {
    try {
      const resp = await apiClient.get('/forecast/dashboard/stats');
      return resp.data;
    } catch {
      return {
        total_products: 16,
        total_inventory_value: 48950,
        low_stock_count: 2,
        expiring_soon_count: 2,
        today_sales_amount: 4850,
        today_sales_count: 8,
        monthly_sales_amount: 142600,
        open_purchase_orders_count: 1,
        top_selling_products: [
          { product_id: 7, name: 'Amul Taaza Milk 500ml', quantity: 180, revenue: 5040 },
          { product_id: 9, name: 'Maggi 2-Min Noodles 4-Pack', quantity: 140, revenue: 7840 },
          { product_id: 8, name: 'Britannia Wheat Bread 400g', quantity: 90, revenue: 4500 },
          { product_id: 3, name: 'Tata Salt 1kg', quantity: 70, revenue: 1960 },
          { product_id: 4, name: 'Fortune Sunflower Oil 1L', quantity: 50, revenue: 6900 },
        ],
        sales_trend: [
          { date: '10/17', sales: 4200, orders: 12 },
          { date: '10/18', sales: 5100, orders: 15 },
          { date: '10/19', sales: 6800, orders: 19 },
          { date: '10/20', sales: 4900, orders: 14 },
          { date: '10/21', sales: 5400, orders: 16 },
          { date: '10/22', sales: 6200, orders: 18 },
          { date: '10/23', sales: 4850, orders: 13 },
        ],
      };
    }
  },

  // Voice Assistant
  async sendAssistantCommand(
    text: string,
    confirmed: boolean = false,
    action_payload?: any,
    session_id?: string
  ): Promise<AssistantResponse> {
    try {
      const resp = await apiClient.post('/assistant/command', {
        text,
        confirmed,
        action_payload,
        session_id,
      });
      return resp.data;
    } catch (err: any) {
      console.error('Assistant API error:', err);
      return {
        intent: 'ERROR',
        speech_text: 'Sorry, I encountered an issue connecting to the inventory server.',
        display_text: 'Failed to communicate with StockSense AI backend service.',
        error: err?.message || 'Connection error',
        suggestions: [
          'How much rice stock is left?',
          'Which products expire tomorrow?',
          'What should I reorder today?',
        ],
      };
    }
  },
};

