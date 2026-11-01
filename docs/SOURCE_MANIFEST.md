# Source and provenance manifest

- Data provenance: 100% synthetic; generated locally by `generator/generate_data.py`.
- Fixed seed: `20261022`.
- As-of timestamp: `2026-10-31T00:00:00Z`.
- External sources: none; no public data is redistributed.
- Personal/confidential data: none. Customer IDs are synthetic placeholders.
- Reproduction: `python generator/generate_data.py --scale full --seed 20261022`.
- Validation: `python validation/validate.py`; checksums and row counts are in `data/manifest.json`.
- Reproducibility: two independent full-scale runs with the same seed produced identical row counts and SHA-256 hashes for all 14 CSV files. See `VALIDATION_AND_REPRODUCIBILITY.md`.
- SQL: `python scripts/export_sql_seed.py` exports all CSV data to compressed SQL INSERT statements in foreign-key order. Apply `docs/schema.sql` first.
- License/terms: generated project code and synthetic examples are supplied for educational/demo use. No third-party dataset license is involved.
