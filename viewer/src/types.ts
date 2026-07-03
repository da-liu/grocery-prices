export interface Location {
  store: string;
  maps_url?: string;
  latitude?: number;
  longitude?: number;
  store_location_id?: string;
}

export interface StoreLocation {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  match_radius_m: number;
  maps_url: string | null;
}

export interface StoreLabelRequest {
  imageId: string;
  thumbnailUrl: string;
  latitude: number | null;
  longitude: number | null;
}

export interface PriceInsight {
  product_id: string;
  product_name: string;
  price: number;
  store?: string;
  captured_at?: string;
  image_id: string;
  insight_type: "history" | "same_store_history" | "other_store";
  price_delta?: number | null;
}

export interface OverlappingProduct {
  match_key: string;
  new_product_name?: string;
  existing_product_id: string;
  existing_product_name: string;
  existing_price?: number | null;
  existing_store?: string;
  existing_captured_at?: string;
}

export interface Product {
  id: string;
  image_id: string;
  image_path: string;
  product_name: string;
  product_name_zh?: string;
  brand?: string;
  price: number | null;
  price_currency: string;
  unit?: string;
  unit_price?: number;
  unit_price_per_100g?: number;
  regular_price?: number | null;
  is_special?: boolean;
  promo?: string;
  barcode?: string;
  size?: string;
  net_weight?: number;
  net_weight_lb?: number;
  packed_on?: string;
  category: string;
  notes?: string;
  captured_at?: string;
  location: Location;
  extraction_empty?: boolean;
  price_insights?: PriceInsight[];
}
