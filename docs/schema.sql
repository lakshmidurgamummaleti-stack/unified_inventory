-- Unified Inventory Control Tower schema (SQLite 3.35+ / PostgreSQL adaptation).
PRAGMA foreign_keys = ON;

CREATE TABLE product (
 product_id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
 brand TEXT NOT NULL, description TEXT, status TEXT NOT NULL CHECK(status IN ('active','discontinued','seasonal')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, CHECK(updated_at >= created_at)
);
CREATE TABLE sku (
 sku_id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES product(product_id),
 sku_code TEXT NOT NULL UNIQUE, size TEXT, color TEXT, unit_cost REAL NOT NULL CHECK(unit_cost>=0),
 unit_price REAL NOT NULL CHECK(unit_price>=0), weight_kg REAL CHECK(weight_kg>=0),
 status TEXT NOT NULL CHECK(status IN ('active','inactive','blocked')), created_at TEXT NOT NULL
);
CREATE TABLE location (
 location_id TEXT PRIMARY KEY, name TEXT NOT NULL,
 location_type TEXT NOT NULL CHECK(location_type IN ('store','warehouse','dc','online_virtual')),
 parent_location_id TEXT REFERENCES location(location_id), channel TEXT NOT NULL,
 address_city TEXT, address_country TEXT NOT NULL, timezone TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('active','closed','maintenance')),
 safety_stock_days INTEGER CHECK(safety_stock_days>=0), created_at TEXT NOT NULL
);
CREATE TABLE orders (
 order_id TEXT PRIMARY KEY, channel TEXT NOT NULL CHECK(channel IN ('ecom','retail','marketplace')),
 customer_id TEXT NOT NULL, status TEXT NOT NULL,
 fulfillment_location_id TEXT NOT NULL REFERENCES location(location_id),
 order_ts TEXT NOT NULL, total_amount REAL NOT NULL CHECK(total_amount>=0), currency TEXT NOT NULL
);
CREATE TABLE order_line (
 order_line_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(order_id),
 sku_id TEXT NOT NULL REFERENCES sku(sku_id), quantity INTEGER NOT NULL CHECK(quantity>0),
 unit_price REAL NOT NULL CHECK(unit_price>=0), line_status TEXT NOT NULL,
 allocated_location_id TEXT REFERENCES location(location_id)
);
CREATE TABLE shipment (
 shipment_id TEXT PRIMARY KEY, shipment_type TEXT NOT NULL CHECK(shipment_type IN ('customer_order','internal_transfer','supplier_receipt')),
 order_id TEXT REFERENCES orders(order_id), from_location_id TEXT REFERENCES location(location_id),
 to_location_id TEXT REFERENCES location(location_id), sku_id TEXT NOT NULL REFERENCES sku(sku_id),
 quantity INTEGER NOT NULL CHECK(quantity>0),
 status TEXT NOT NULL CHECK(status IN ('planned','in_transit','received','delivered')),
 shipped_at TEXT, eta TEXT, received_at TEXT,
 CHECK(shipment_type!='internal_transfer' OR (from_location_id IS NOT NULL AND to_location_id IS NOT NULL AND from_location_id<>to_location_id))
);
CREATE TABLE reservation (
 reservation_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(order_id),
 order_line_id TEXT NOT NULL REFERENCES order_line(order_line_id), sku_id TEXT NOT NULL REFERENCES sku(sku_id),
 location_id TEXT NOT NULL REFERENCES location(location_id), quantity INTEGER NOT NULL CHECK(quantity>0),
 status TEXT NOT NULL CHECK(status IN ('active','expired','fulfilled','cancelled','released')),
 reserved_at TEXT NOT NULL, expires_at TEXT NOT NULL, released_at TEXT,
 CHECK(expires_at>reserved_at)
);
CREATE TABLE replenishment_rule (
 rule_id TEXT PRIMARY KEY, sku_id TEXT NOT NULL REFERENCES sku(sku_id),
 location_id TEXT NOT NULL REFERENCES location(location_id),
 min_stock INTEGER NOT NULL CHECK(min_stock>=0), max_stock INTEGER NOT NULL CHECK(max_stock>=min_stock),
 reorder_point INTEGER NOT NULL CHECK(reorder_point>=0), reorder_qty INTEGER NOT NULL CHECK(reorder_qty>0),
 lead_time_days INTEGER NOT NULL CHECK(lead_time_days>=0), channel_buffer INTEGER NOT NULL DEFAULT 0,
 safety_stock_units INTEGER NOT NULL DEFAULT 0, channel_buffer_units INTEGER NOT NULL DEFAULT 0,
 inbound_policy_days INTEGER NOT NULL DEFAULT 14, active INTEGER NOT NULL CHECK(active IN (0,1)),
 effective_from TEXT NOT NULL, effective_to TEXT, UNIQUE(sku_id,location_id),
 CHECK(effective_to IS NULL OR effective_to>=effective_from)
);
CREATE TABLE inventory_movement (
 movement_id TEXT PRIMARY KEY, sku_id TEXT NOT NULL REFERENCES sku(sku_id),
 location_id TEXT NOT NULL REFERENCES location(location_id), movement_type TEXT NOT NULL,
 quantity INTEGER NOT NULL CHECK(quantity>0), reference_id TEXT, reference_type TEXT,
 reason_code TEXT, occurred_at TEXT NOT NULL, created_by TEXT NOT NULL, notes TEXT,
 delta_on_hand INTEGER NOT NULL DEFAULT 0, delta_reserved INTEGER NOT NULL DEFAULT 0,
 delta_blocked INTEGER NOT NULL DEFAULT 0, delta_in_transit_in INTEGER NOT NULL DEFAULT 0,
 delta_in_transit_out INTEGER NOT NULL DEFAULT 0,
 order_id_ref TEXT REFERENCES orders(order_id),
 reservation_id_ref TEXT REFERENCES reservation(reservation_id),
 shipment_id_ref TEXT REFERENCES shipment(shipment_id)
);
CREATE TABLE inventory_balance (
 balance_id TEXT PRIMARY KEY, sku_id TEXT NOT NULL REFERENCES sku(sku_id),
 location_id TEXT NOT NULL REFERENCES location(location_id),
 on_hand INTEGER NOT NULL CHECK(on_hand>=0), reserved INTEGER NOT NULL CHECK(reserved>=0),
 blocked INTEGER NOT NULL CHECK(blocked>=0), in_transit_in INTEGER NOT NULL CHECK(in_transit_in>=0),
 in_transit_out INTEGER NOT NULL CHECK(in_transit_out>=0),
 safety_stock_units INTEGER NOT NULL, channel_buffer_units INTEGER NOT NULL,
 approved_inbound INTEGER NOT NULL, available_to_promise INTEGER NOT NULL CHECK(available_to_promise>=0),
 last_movement_id TEXT REFERENCES inventory_movement(movement_id), as_of_ts TEXT NOT NULL,
 UNIQUE(sku_id,location_id), CHECK(blocked<=on_hand)
);
CREATE TABLE order_event (
 order_event_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(order_id),
 from_status TEXT, to_status TEXT NOT NULL, event_type TEXT NOT NULL, event_ts TEXT NOT NULL, actor TEXT NOT NULL
);
CREATE TABLE reservation_event (
 reservation_event_id TEXT PRIMARY KEY, reservation_id TEXT NOT NULL REFERENCES reservation(reservation_id),
 from_status TEXT, to_status TEXT NOT NULL, event_type TEXT NOT NULL, event_ts TEXT NOT NULL, actor TEXT NOT NULL
);
CREATE INDEX idx_balance_sku_location ON inventory_balance(sku_id,location_id);
CREATE INDEX idx_movement_sku_time ON inventory_movement(sku_id,occurred_at);
CREATE INDEX idx_movement_reference ON inventory_movement(reference_type,reference_id);
CREATE INDEX idx_reservation_status_expiry ON reservation(status,expires_at);
CREATE INDEX idx_order_channel_status ON orders(channel,status);
CREATE INDEX idx_shipment_status_eta ON shipment(status,eta);
-- N:M SKU<->Location is resolved by InventoryBalance (one row per stocked pair).
-- All state transitions are append-only rows in order_event, reservation_event and inventory_movement.

CREATE TABLE ground_truth_fixture (
 scenario_id TEXT PRIMARY KEY, issue_type TEXT NOT NULL, entity_type TEXT NOT NULL,
 entity_id TEXT NOT NULL, observed_condition TEXT NOT NULL, expected_action TEXT NOT NULL,
 severity TEXT NOT NULL CHECK(severity IN ('low','medium','high')), fixture_only INTEGER NOT NULL CHECK(fixture_only=1)
);
CREATE TABLE anomaly_fixture (
 scenario_id TEXT PRIMARY KEY, issue_type TEXT NOT NULL, entity_type TEXT NOT NULL,
 entity_id TEXT NOT NULL, observed_condition TEXT NOT NULL, expected_action TEXT NOT NULL,
 severity TEXT NOT NULL CHECK(severity IN ('low','medium','high')), fixture_only INTEGER NOT NULL CHECK(fixture_only=1)
);
