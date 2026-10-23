/**
 * StockSense AI - TypeScript Type Definitions
 */

export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
}

export interface Category {
  id: number;
  name: string;
  description?: string;
}

export interface Supplier {
  id: number;
  name: string;
  contact_person?: string;
  phone?: string;
  email?: string;
  address?: string;
  lead_time_days: number;
  min_order_quantity?: number;
  min_order_value?: number;
  notes?: string;
  is_active: boolean;
}

export interface Product {
  id: number;
  name: string;
  sku: string;
  category_id?: number;
  category_name?: string;
  unit: string;
  purchase_cost: number;
  selling_price: number;
  preferred_supplier_id?: number;
  supplier_name?: string;
  supplier_lead_time_days: number;
  safety_stock: number;
  reorder_threshold: number;
  shelf_life_days?: number;
  is_active: boolean;
  usable_stock?: number;
  total_stock?: number;
  current_stock?: number;
  expired_stock?: number;
}

export interface InventoryBatch {
  id: number;
  product_id: number;
  product_name?: string;
  batch_number?: string;
  received_quantity: number;
  remaining_quantity: number;
  unit_cost: number;
  manufacture_date?: string;
  expiry_date?: string;
  receipt_reference?: string;
  source_type: string;
  days_to_expiry?: number;
  is_expired?: boolean;
}

export interface StockMovement {
  id: number;
  product_id: number;
  product_name?: string;
  batch_id?: number;
  batch_number?: string;
  movement_type: string;
  quantity: number;
  reference_type?: string;
  reference_id?: number;
  notes?: string;
  created_at: string;
}

export interface SaleItem {
  id?: number;
  product_id: number;
  product_name?: string;
  product_sku?: string;
  quantity: number;
  unit_price: number;
  line_total: number;
}

export interface Sale {
  id: number;
  sale_number: string;
  sale_date: string;
  total_amount: number;
  total_items: number;
  reference_number?: string;
  status: string;
  notes?: string;
  items?: SaleItem[];
}

export interface PurchaseOrderItem {
  id?: number;
  product_id: number;
  product_name?: string;
  ordered_quantity: number;
  received_quantity: number;
  unit_cost: number;
  line_total: number;
}

export interface PurchaseOrder {
  id: number;
  po_number: string;
  supplier_id: number;
  supplier_name?: string;
  order_date: string;
  expected_delivery_date?: string;
  status: 'DRAFT' | 'ORDERED' | 'PARTIALLY_RECEIVED' | 'RECEIVED' | 'CANCELLED';
  total_amount: number;
  notes?: string;
  items?: PurchaseOrderItem[];
}

export interface ReorderRecommendation {
  id: number;
  product_id: number;
  product_name: string;
  sku: string;
  category_name?: string;
  usable_stock: number;
  incoming_stock: number;
  daily_demand: number;
  lead_time_demand: number;
  safety_stock: number;
  target_stock: number;
  inventory_position: number;
  suggested_quantity: number;
  estimated_cost: number;
  priority: 'URGENT' | 'HIGH' | 'MEDIUM' | 'LOW';
  explanation: string;
  forecast_confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  run_date: string;
}

export interface BudgetPlanItem {
  id?: number;
  product_id: number;
  product_name: string;
  sku: string;
  suggested_quantity: number;
  unit_cost: number;
  line_cost: number;
  priority: string;
  included: boolean;
  exclusion_reason?: string;
}

export interface BudgetPlan {
  id?: number;
  budget_amount: number;
  total_allocated: number;
  remaining_budget: number;
  items_included: number;
  items_excluded: number;
  items: BudgetPlanItem[];
  notes?: string;
}

export interface ExpiryAlert {
  product_id: number;
  product_name: string;
  sku: string;
  batch_id: number;
  batch_number: string;
  remaining_quantity: number;
  unit: string;
  expiry_date: string;
  days_until_expiry: number;
  purchase_cost: number;
  potential_loss: number;
  status: 'EXPIRED' | 'CRITICAL' | 'WARNING' | 'ATTENTION';
}

export interface ClearancePromotion {
  batch_id: number;
  product_id: number;
  product_name: string;
  batch_number: string;
  discount_pct: number;
  discounted_price: number;
  original_price: number;
  applied_at: string;
}

export interface DashboardStats {
  total_products: number;
  total_inventory_value: number;
  low_stock_count: number;
  expiring_soon_count: number;
  today_sales_amount: number;
  today_sales_count: number;
  monthly_sales_amount: number;
  open_purchase_orders_count: number;
  top_selling_products: {
    product_id: number;
    name: string;
    quantity: number;
    revenue: number;
  }[];
  sales_trend: {
    date: string;
    sales: number;
    orders?: number;
  }[];
}

export interface AssistantResponse {
  intent: string;
  speech_text: string;
  display_text: string;
  data?: any;
  requires_confirmation?: boolean;
  action_payload?: any;
  error?: string;
  suggestions?: string[];
}

export interface AssistantChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  speechText?: string;
  intent?: string;
  data?: any;
  requiresConfirmation?: boolean;
  actionPayload?: any;
  error?: string;
  suggestions?: string[];
  timestamp: Date;
}

