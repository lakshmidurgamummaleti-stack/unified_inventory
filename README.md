# Unified Inventory Control Tower

A deterministic, end-to-end synthetic inventory unification project. The Streamlit interface intentionally preserves the uploaded screen recording's dark Control Tower design and navigation: Overview, ATP Explorer, Reservations, Movement Ledger, Orders & Fulfillment, Anomaly Workbench and Data Quality.

## What is included
- Product, SKU and hierarchical Location master data.
- InventoryBalance snapshot derived from immutable InventoryMovement deltas.
- Orders, OrderLines, Reservations, Shipments and effective-dated ReplenishmentRules.
- Append-only OrderEvent and ReservationEvent lifecycle history.
- ATP calculation including reserved, blocked, safety stock, channel buffers and policy-approved inbound transfers.
- Transfer dispatch/receipt lifecycle; destination on-hand changes only on receipt.
- Separate ground-truth and anomaly fixture datasets. Deliberately invalid scenarios do not corrupt clean operational records.
- CSV + JSON datasets, SQL schema, SQL seed export script, data dictionary, manifest/checksums and independent acceptance validation.
- FastAPI read-only API and Streamlit dashboard.

## Quick start (Windows PowerShell)
```powershell
# Extract ZIP and open the project directory in VS Code
cd unified_inventory_control_tower

py -m venv .venv
.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

# Run independent acceptance checks
python validation/validate.py
python -m pytest -q

# Launch the same dark UI shown in your screen recording
streamlit run app/dashboard.py
# Browser: http://localhost:8501

# In a second terminal, launch API
uvicorn app.api:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

## Dataset scales
The generator is parameterized; every scale uses the same rules and fixed seed.

| Scale | SKUs | Locations | Movements | Orders |
|---|---:|---:|---:|---:|
| starter | 300 | 30 | 30,000 | 1,500 |
| standard | 1,500 | 60 | 200,000 | 12,000 |
| full | 5,000 | 100 | 1,000,000 | 50,000 |

Regenerate the full required volume:
```powershell
python generator/generate_data.py --scale full --seed 20261022
python validation/validate.py
python -m pytest -q
```
The ZIP already contains the full-scale dataset (5,000 SKUs, 100 locations, 1,000,000 movements and 50,000 orders). The command below deterministically regenerates that full dataset. To generate into another directory without overwriting the shipped data:
```powershell
python generator/generate_data.py --scale full --seed 20261022 --output-dir ./full_data
```

## Business rules
1. Master data is generated before dependent records.
2. Every SKU/location pair has one replenishment rule and one balance snapshot.
3. `on_hand`, `reserved`, `blocked`, `in_transit_in` and `in_transit_out` are sums of movement delta columns.
4. Reservations create a positive `reservation_hold` delta. Expired, cancelled and fulfilled reservations emit a matching `reservation_release` delta and a ReservationEvent transition.
5. Internal transfer dispatch decreases source on-hand and adds source in-transit-out plus destination in-transit-in. Destination on-hand increases only after `transfer_receipt`.
6. Approved inbound includes only in-transit shipments with ETA inside the effective rule's inbound policy window.
7. ATP is `max(0, on_hand - reserved - blocked - safety_stock_units - channel_buffer_units + approved_inbound)`.
8. Orders and reservations have append-only event history. InventoryMovement is an immutable ledger.
9. Clean baseline rows reconcile. Required deliberately bad scenarios (balance mismatch, reservation oversell, fulfilled from blocked stock, premature transfer count) are in `ground_truth.csv` and `anomaly_fixtures.csv`, not silently injected into the clean balance ledger. Additional oversell and expiry scenarios are also labelled.

## Validation and acceptance
`validation/validate.py` independently checks primary keys, foreign keys, nomenclature, enums, composite uniqueness, order totals, reservation-to-line relationships, reservation expiry, movement references, all five balance dimensions, reservation hold/release history, shipped order allocation traceability, transfer dispatch/receipt, approved inbound, ATP, event history, ground-truth separation, manifest counts and SHA-256 checksums.

The validator writes `data/validation_summary.json` and exits non-zero if any check fails. Run it after regeneration. Tests in `tests/` invoke the same acceptance validator plus focused invariants.

## Reproducibility
```powershell
python scripts/prove_reproducibility.py --scale starter --seed 20261022
```
It generates two independent datasets in temporary folders and compares every CSV row count and SHA-256 checksum. It does not move, delete or overwrite the current `data/` directory.

## SQL
- `docs/schema.sql` contains the relational schema, PK/FK constraints, checks, unique constraints and indexes.
- Export INSERT statements for the current generated CSV files:
```powershell
python scripts/export_sql_seed.py
```
This writes compressed `data/seed.sql.gz`. The seed export includes all data tables in foreign-key order; ground truth is exported to separate fixture tables.

## API
- `GET /health`
- `GET /api/v1/summary`
- `GET /api/v1/atp?sku_id=&location_id=&min_atp=`
- `GET /api/v1/reservations?status=`
- `GET /api/v1/orders/{order_id}`
- `GET /api/v1/anomalies`
- `GET /api/v1/movements?sku_id=&location_id=`
- `GET /api/v1/locations`
- `GET /api/v1/skus`
- `GET /api/v1/transfers?status=`
- `GET /api/v1/data-quality`

## Lawful provenance
All data is generated locally from a fixed seed. No public or private dataset is scraped or redistributed; there are no personal, confidential or customer-identifying records. Customer identifiers are synthetic placeholders. The manifest records seed, scale, as-of date, row counts and checksums.

## Project structure
```
unified_inventory_control_tower/
├── app/                 # Streamlit UI and FastAPI
├── data/                # CSV/JSON synthetic data and validation summary
├── docs/                # schema and field-level data dictionary
├── generator/           # parameterized deterministic generator
├── scripts/             # reproducibility and SQL seed export
├── tests/               # automated acceptance tests
├── validation/          # independent rule validator
├── .streamlit/          # dark theme matching supplied recording
└── requirements.txt
```

## Anomaly Workbench schema compatibility

The dashboard accepts both `description` and the source dataset's
`observed_condition` field. The loader normalizes `observed_condition` to
`description`, while preserving the original column. Missing optional anomaly
fields are displayed as `Not provided` instead of crashing the page.

Run the application from this project directory:

```bash
streamlit run app/dashboard.py
```

Run the automated acceptance tests:

```bash
python -m pytest -q
```
