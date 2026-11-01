# Full-scale acceptance and reproducibility proof

**Run date:** 2026-10-31  
**Seed:** 20261022  
**Scale:** full

## Full-scale generated volume

| Entity | Rows |
|---|---:|
| Products | 2,500 |
| SKUs | 5,000 |
| Locations | 100 |
| Inventory balances | 20,000 |
| Inventory movements | 1,000,000 |
| Orders | 50,000 |
| Order lines | 99,878 |
| Reservations | 53,518 |
| Shipments (customer, transfer, supplier receipt) | 107,400 |
| Replenishment rules | 20,000 |
| Order lifecycle events | 100,000 |
| Reservation lifecycle events | 90,908 |
| Ground-truth scenarios | 6 |
| Separate anomaly fixtures | 6 |

## Acceptance validation

The independent validation command `python validation/validate.py` completed successfully:

- **98 checks passed**
- **0 checks failed**
- **100.00% pass rate**

Coverage includes PK uniqueness, FK integrity, IDs, enums, one-balance-per-SKU/location, order totals, reservation parent and lifecycle consistency, movement reference integrity, reconciliation of on-hand/reserved/blocked/inbound/outbound, reservation hold/release movements, order shipment traceability, transfer dispatch/receipt events, approved inbound, ATP formula, order/reservation event history, anomaly separation, full-scale row counts, manifest counts and SHA-256 checksums.

The clean baseline remains reconciled. The deliberately invalid required cases are represented as separate labelled fixtures and do not contaminate baseline balances or input features.

## Full-scale reproducibility

Two independent full-scale generations were compared using seed `20261022`:

- Copy A: the generated `data/` directory included in this ZIP.
- Copy B: an independent generator run in a temporary output directory.
- Row counts: identical across all 14 CSV files.
- SHA-256 checksums: identical across all 14 CSV files.
- Seed and scale: both `20261022` / `full`.

**Result: reproducibility passed.** The independent copy was created outside the project and did not overwrite the packaged dataset.

## SQL seed import

The compressed SQL seed was imported into an in-memory SQLite database after applying `docs/schema.sql`:

- Inventory movements imported: 1,000,000.
- Shipments imported: 107,400.
- SQLite foreign-key violations: 0.

See `data/validation_summary.json`, `data/manifest.json` and `data/seed.sql.gz`.
