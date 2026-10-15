export type Loc = { id: number; name_uz: string; name_ru: string; region_uz: string; region_ru: string };

export type UserPublic = {
  id: number;
  name: string;
  rating: number | null;
  rating_count: number;
  /** completed orders (contract A); absent on older backends */
  trips?: number;
  /** carrier profile APPROVED (contract A) */
  verified?: boolean;
};

export type Review = { rating: number; text: string | null; author: string; created_at: string };

/** GET /api/users/{id} (contract B) */
export type UserTrust = UserPublic & {
  member_since?: string;
  checks?: { phone?: boolean; driver_license?: boolean; tech_passport?: boolean; vehicle_photo?: boolean };
  reviews?: Review[];
};

/** GET /api/price-hint (contract C) */
export type PriceHint = { min: number; max: number; typical: number; distance_km?: number; source?: "history" | "distance" };

/** GET /api/listings/{id}/activity (contract D) */
export type ListingActivity = { carriers_on_route: number; viewed: number };

export type TimelineEntry = { status: string; at: string };
export type UserContact = UserPublic & { full_name: string; phone: string | null; username: string | null };

export type Vehicle = {
  id: number;
  vehicle_type: string;
  make_model: string;
  color: string | null;
  seats: number;
  max_weight_kg: number;
  plate_number?: string;
};

export type Listing = {
  id: number;
  kind: "REQUEST" | "ROUTE";
  category: string;
  status: string;
  from: Loc;
  to: Loc;
  departure_at: string;
  time_flexible: boolean;
  price: number;
  capacity_total: number;
  capacity_available: number;
  details: Record<string, any>;
  comment: string | null;
  photo_ids: number[];
  author: UserPublic;
  vehicle: Vehicle | null;
  created_at: string;
  is_mine: boolean;
  from_address?: string;
  to_address?: string;
  recipient_name?: string;
  recipient_phone?: string;
  pending_offers?: number;
};

export type Offer = {
  id: number;
  listing_id: number;
  parent_id: number | null;
  status: string;
  price: number;
  quantity: number;
  details: Record<string, any>;
  comment: string | null;
  photo_ids: number[];
  counterparty: UserPublic;
  vehicle: Vehicle | null;
  proposed_by_me: boolean;
  can_respond: boolean;
  expires_at: string;
  created_at: string;
  listing_kind: string;
  listing_category: string;
  listing_status: string;
  route: { from: Loc; to: Loc; departure_at: string };
  from_address?: string;
  to_address?: string;
  recipient_name?: string;
  recipient_phone?: string;
};

export type Order = {
  id: number;
  listing_id: number;
  role: "client" | "carrier";
  category: string;
  status: string;
  price: number;
  quantity: number;
  from: Loc;
  to: Loc;
  departure_at: string;
  details: Record<string, any>;
  counterparty: UserContact;
  vehicle: Vehicle | null;
  confirm_deadline: string | null;
  auto_complete_at: string | null;
  my_review: { rating: number; text: string | null } | null;
  actions: string[];
  revealed: boolean;
  created_at?: string;
  /** first time each status was reached (contract F) */
  timeline?: TimelineEntry[];
  /** parcel hand-over code, client only (contract F) */
  delivery_code?: string | null;
  /** carrier: "deliver" requires the recipient's code (contract F) */
  needs_code?: boolean;
  code_attempts_left?: number | null;
  /** carrier: too many wrong codes, deliver is blocked until an admin resolves a complaint */
  code_locked?: boolean;
  from_address?: string;
  to_address?: string;
  recipient_name?: string;
  recipient_phone?: string;
};

export type OrderBrief = Pick<Order, "id" | "role" | "category" | "status" | "price" | "from" | "to" | "departure_at"> & {
  counterparty: UserPublic;
};

export type Me = {
  registered: boolean;
  blocked?: boolean;
  id?: number;
  first_name?: string;
  last_name?: string | null;
  phone?: string;
  lang?: "uz" | "ru";
  rating?: number | null;
  rating_count?: number;
  carrier?: { status: string; full_name: string | null; admin_comment: string | null; permissions: string[] };
};

export type Config = {
  enabled_categories: string[];
  all_categories: string[];
  required_documents: string[];
  document_kinds: string[];
  vehicle_types: string[];
  cancel_reasons: string[];
  complaint_reasons: string[];
  support_contact: string;
};
