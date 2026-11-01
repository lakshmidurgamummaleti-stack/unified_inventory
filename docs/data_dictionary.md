# Data dictionary and relationship catalogue

**Project:** Unified Inventory Control Tower  
**Seed:** `20261022` (default) · **As-of:** `2026-10-31T00:00:00Z`  
**Provenance:** 100% deterministic synthetic data; no personal or confidential records.

Conventions: IDs are immutable strings; timestamps are ISO-8601 UTC; quantities are integer units; money is USD. `Y` = required, `N` = optional. Every primary key is unique. CSV headers match these names.

## Product
| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| product_id | string | Y | `PRD-000001` | PK | `^PRD-\d{6}$` |
| name | string(200) | Y | descriptive | N | 3–200 chars |
| category | enum | Y | Electronics, Apparel, Home, Beauty, Sports, Grocery, Toys | N | allowed enum |
| brand | string(100) | Y | synthetic brand | N | non-empty |
| description | text | N | free text | N | — |
| status | enum | Y | active, discontinued, seasonal | N | allowed enum |
| created_at | datetime | Y | UTC | N | valid timestamp |
| updated_at | datetime | Y | UTC | N | >= created_at |

**Cardinality:** Product 1:N SKU.

## SKU
| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| sku_id | string | Y | `SKU-000001` | PK | `^SKU-\d{6}$` |
| product_id | string | Y | Product ID | FK | exists in Product |
| sku_code | string(50) | Y | `ITEM-000001` | UQ | unique |
| size | string | N | XS,S,M,L,XL,One Size | N | catalog enum |
| color | string | N | Black,Blue,White,Green,Red,Grey | N | catalog enum |
| unit_cost | decimal | Y | USD/unit | N | >= 0 |
| unit_price | decimal | Y | USD/unit | N | >= 0 |
| weight_kg | decimal | N | kg | N | >= 0 |
| status | enum | Y | active,inactive,blocked | N | allowed enum |
| created_at | datetime | Y | UTC | N | valid timestamp |

**Cardinality:** SKU N:1 Product; SKU 1:N InventoryBalance, InventoryMovement, OrderLine, Reservation.

## Location
| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| location_id | string | Y | `LOC-000001` | PK | `^LOC-\d{6}$` |
| name | string(100) | Y | descriptive | N | non-empty |
| location_type | enum | Y | dc,warehouse,store,online_virtual | N | allowed enum |
| parent_location_id | string | N | Location ID | FK | exists; no hierarchy cycle |
| channel | enum | Y | all,retail,ecom | N | allowed enum |
| address_city | string | N | city | N | — |
| address_country | string(3) | Y | ISO alpha-3 | N | 3 uppercase letters |
| timezone | string | Y | IANA timezone | N | valid timezone |
| status | enum | Y | active,closed,maintenance | N | allowed enum |
| safety_stock_days | integer | N | days | N | >= 0 |
| created_at | datetime | Y | UTC | N | valid timestamp |

**Cardinality:** Location 1:N child Location (self hierarchy); Location 1:N InventoryBalance, Shipment.

## InventoryBalance (derived current snapshot)
| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| balance_id | string | Y | `BAL-<sku>-<loc>` | PK | unique |
| sku_id | string | Y | SKU ID | FK | exists |
| location_id | string | Y | Location ID | FK | exists |
| on_hand | integer | Y | physical units | N | >= 0; equals movement delta sum |
| reserved | integer | Y | reserved units | N | >= 0; equals active reservation events |
| blocked | integer | Y | QA/damaged units | N | 0..on_hand |
| in_transit_in | integer | Y | inbound units | N | >= 0; open transfers |
| in_transit_out | integer | Y | outbound units | N | >= 0; open transfers |
| safety_stock_units | integer | Y | units | N | >= 0; replenishment rule |
| channel_buffer_units | integer | Y | units | N | >= 0; channel policy |
| approved_inbound | integer | Y | units | N | ETA within inbound policy |
| available_to_promise | integer | Y | units | N | exact ATP formula below |
| last_movement_id | string | N | Movement ID | FK | exists when non-null |
| as_of_ts | datetime | Y | UTC | N | snapshot timestamp |

**Unique composite:** (sku_id, location_id).  
**ATP:** `max(0, on_hand - reserved - blocked - safety_stock_units - channel_buffer_units + approved_inbound)`.

**Cardinality:** InventoryBalance is the associative entity for SKU N:M Location (one row per stocked pair).

## InventoryMovement (append-only event ledger)
| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| movement_id | string | Y | `MOV-2026-00000001` | PK | immutable sequence |
| sku_id | string | Y | SKU ID | FK | exists |
| location_id | string | Y | Location ID | FK | exists |
| movement_type | enum | Y | opening_balance,receipt,sale,return,transfer_out,transfer_in,transfer_receipt,transfer_out_complete,adjustment,damage,cycle_count,reservation_hold,reservation_release | N | allowed enum |
| quantity | integer | Y | absolute units | N | > 0 |
| reference_id | string | N | business event ID | N | resolves by reference_type |
| reference_type | enum | N | opening,order,reservation,shipment,manual | N | allowed enum |
| reason_code | string | N | documented reason | N | non-empty when supplied |
| occurred_at | datetime | Y | UTC | N | valid timestamp |
| created_by | string | Y | system,ecommerce,warehouse,operator | N | non-empty |
| notes | text | N | free text | N | optional operator note (omitted from generated CSV when empty) |
| delta_on_hand | integer | Y | signed units | N | sum reconciles to on_hand |
| delta_reserved | integer | Y | signed units | N | sum reconciles to reserved |
| delta_blocked | integer | Y | signed units | N | sum reconciles to blocked |
| delta_in_transit_in | integer | Y | signed units | N | sum reconciles to inbound |
| delta_in_transit_out | integer | Y | signed units | N | sum reconciles to outbound |
| order_id_ref | string | N | Order ID | FK | set only for order references |
| reservation_id_ref | string | N | Reservation ID | FK | set only for reservation references |
| shipment_id_ref | string | N | Shipment ID | FK | set only for shipment references |

**Cardinality:** SKU 1:N Movement; Location 1:N Movement; each movement has at most one optional Order, Reservation or Shipment reference. Event rows are never overwritten.

## Reservation
| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| reservation_id | string | Y | `RES-<order-id>-01` | PK | deterministic per order line |
| order_id | string | Y | Order ID | FK | exists |
| order_line_id | string | Y | OrderLine ID | FK | exists |
| sku_id | string | Y | SKU ID | FK | agrees with line |
| location_id | string | Y | Location ID | FK | agrees with allocated location |
| quantity | integer | Y | units | N | > 0; agrees with line |
| status | enum | Y | active,expired,fulfilled,cancelled,released | N | lifecycle-valid |
| reserved_at | datetime | Y | UTC | N | valid timestamp |
| expires_at | datetime | Y | UTC | N | > reserved_at |
| released_at | datetime | N | UTC | N | required for non-active; >= reserved_at |

**Cardinality:** Order 1:N Reservation; OrderLine 1:N Reservation; SKU/Location 1:N Reservation. Reservation status changes are retained in ReservationEvent and corresponding hold/release movements.

## Order
| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| order_id | string | Y | `ORD-2026-000001` | PK | exact format |
| channel | enum | Y | ecom,retail,marketplace | N | allowed enum |
| customer_id | string | Y | synthetic `CUST-...` | N | no real personal data |
| status | enum | Y | pending,confirmed,reserved,allocated,shipped,delivered,cancelled,backordered | N | lifecycle-valid |
| fulfillment_location_id | string | Y | Location ID | FK | physical active location |
| order_ts | datetime | Y | UTC | N | valid timestamp |
| total_amount | decimal | Y | USD | N | equals sum of order lines |
| currency | string(3) | Y | USD | N | ISO currency |

**Cardinality:** Order 1:N OrderLine, Reservation, Shipment (customer shipment), OrderEvent.

## OrderLine
| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| order_line_id | string | Y | `<order-id>-L01` | PK | unique |
| order_id | string | Y | Order ID | FK | exists |
| sku_id | string | Y | SKU ID | FK | exists |
| quantity | integer | Y | units | N | > 0 |
| unit_price | decimal | Y | USD/unit | N | >= 0 |
| line_status | enum | Y | pending,reserved,allocated,shipped,cancelled,backordered | N | compatible with order |
| allocated_location_id | string | N | Location ID | FK | valid SKU/location balance |

**Cardinality:** Order 1:N OrderLine; SKU 1:N OrderLine.

## Shipment
| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| shipment_id | string | Y | `SHP-2026-000001` | PK | exact format |
| shipment_type | enum | Y | customer_order,internal_transfer,supplier_receipt | N | allowed enum |
| order_id | string | N | Order ID | FK | required for customer_order |
| from_location_id | string | N | Location ID | FK | valid source |
| to_location_id | string | N | Location ID | FK | transfer destination; optional for customer delivery |
| sku_id | string | Y | SKU ID | FK | exists |
| quantity | integer | Y | units | N | > 0 |
| status | enum | Y | planned,in_transit,received,delivered | N | lifecycle-valid |
| shipped_at | datetime | N | UTC | N | <= ETA |
| eta | datetime | N | UTC | N | valid timestamp |
| received_at | datetime | N | UTC | N | required for received/delivered |

**Cardinality:** Location 1:N Shipment as source/destination; SKU 1:N Shipment; Order 1:N customer Shipment. An internal transfer has distinct source and destination.

## ReplenishmentRule
| Field | Type | Req. | Allowed values / units | Unique | Validation |
|---|---|---:|---|---|---|
| rule_id | string | Y | `RPL-000001` | PK | unique |
| sku_id | string | Y | SKU ID | FK | exists |
| location_id | string | Y | Location ID | FK | exists |
| min_stock | integer | Y | units | N | >= 0 |
| max_stock | integer | Y | units | N | >= min_stock |
| reorder_point | integer | Y | units | N | >= 0 |
| reorder_qty | integer | Y | units | N | > 0 |
| lead_time_days | integer | Y | days | N | >= 0 |
| channel_buffer | integer | Y | units | N | >= 0 |
| safety_stock_units | integer | Y | units | N | >= 0 |
| channel_buffer_units | integer | Y | units | N | >= 0 |
| inbound_policy_days | integer | Y | days | N | >= 0 |
| active | boolean | Y | true/false | N | boolean |
| effective_from | datetime | Y | UTC | N | valid |
| effective_to | datetime | N | UTC | N | >= effective_from |

**Cardinality:** SKU 1:N Rule; Location 1:N Rule; unique (SKU, Location).

## Event-history entities
- **OrderEvent:** `order_event_id` PK, `order_id` FK, `from_status` nullable, `to_status`, `event_type`, `event_ts`, `actor`. 1:N per Order; final event must equal Order.status.
- **ReservationEvent:** `reservation_event_id` PK, `reservation_id` FK, `from_status` nullable, `to_status`, `event_type`, `event_ts`, `actor`. 1:N per Reservation; final event must equal Reservation.status.
- **Ground truth / anomaly fixtures:** separate `ground_truth.csv/json` and `anomaly_fixtures.csv`; fixture labels never join into model/input feature tables. They deliberately describe four required failure conditions plus oversell and expiry-release scenarios. Baseline operational data remains internally consistent.

## Relationships, optionality and lifecycle summary
| Parent | Child | Cardinality | Optionality / rule |
|---|---|---|---|
| Product | SKU | 1:N | SKU requires one Product |
| Location | Location | 1:N | parent optional for root; no cycles |
| SKU + Location | InventoryBalance | N:M via balance | one balance per stocked pair |
| SKU / Location | InventoryMovement | 1:N each | event is immutable |
| Order | OrderLine | 1:N | each order has >=1 line |
| OrderLine | Reservation | 1:N | reservation optional by channel/status |
| Order | Reservation | 1:N | reservation belongs to one order |
| SKU / Location | Reservation | 1:N | both required |
| Order | Shipment | 1:N | optional for non-shipped orders |
| Location | Shipment | 1:N | source required for customer shipments; both ends for transfers; supplier receipts have a destination |
| SKU | Shipment | 1:N | required |
| SKU + Location | ReplenishmentRule | 1:1 in generated baseline | effective-dated policy |
| Order | OrderEvent | 1:N | append-only lifecycle |
| Reservation | ReservationEvent | 1:N | append-only lifecycle |

## ATP and lifecycle decision rules
1. Opening stock is a positive `opening_balance` movement.
2. Sales reduce `on_hand`; returns/receipts increase it; damage increases `blocked` without pretending the stock is sellable.
3. Reservation hold/release deltas change `reserved`, not `on_hand`.
4. Transfer dispatch reduces source `on_hand`, increases source `in_transit_out`, and creates destination `in_transit_in`; only receipt adds destination `on_hand`.
5. `approved_inbound` includes only in-transit transfer quantity whose ETA is within the rule's `inbound_policy_days`.
6. ATP is `max(0, on_hand - reserved - blocked - safety_stock_units - channel_buffer_units + approved_inbound)`.
7. Expired/cancelled/fulfilled reservations have a release event and a matching negative reserved delta. Active reservations must have expiry after the as-of timestamp.
8. The clean baseline is reconciled. Required deliberately-bad cases live in separate labelled fixtures to avoid silently corrupting unrelated operational records.
