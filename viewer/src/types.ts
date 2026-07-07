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
  maps_url?: string;
  photo_count?: number;
}

export interface CreateStoreLocationResult extends StoreLocation {
  matched_existing?: boolean;
}

export interface StoreLabelRequest {
  imageId: string;
  thumbnailUrl: string;
  latitude: number | null;
  longitude: number | null;
}

export type AppPage = "browse" | "settings";

export interface BrowseStats {
  shown: number;
  total: number;
  photoCount: number;
  storeCount: number;
  avgPriceLabel: string;
}

export interface Product {
  id: string;
  image_id: string;
  image_path: string;
  product_name: string;
  price: number | null;
  price_currency: string;
  unit?: string;
  unit_price?: number;
  category: string;
  other?: Record<string, string | number | boolean | null>;
  captured_at?: string;
  location: Location;
  extraction_empty?: boolean;
  photo_type?: "shelf" | "receipt";
}
