#!/usr/bin/env python3
"""Export generated CSVs as a compressed SQL INSERT seed; run schema.sql first."""
import argparse, csv, gzip, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
# Parent tables precede children so foreign keys can be enabled during import.
MAP=[("products","product"),("skus","sku"),("locations","location"),("orders","orders"),
("order_lines","order_line"),("shipments","shipment"),("reservations","reservation"),
("replenishment_rules","replenishment_rule"),("inventory_movements","inventory_movement"),
("inventory_balances","inventory_balance"),("order_events","order_event"),
("reservation_events","reservation_event"),("ground_truth","ground_truth_fixture"),
("anomaly_fixtures","anomaly_fixture")]
def literal(v):
    if v is None or v=="": return "NULL"
    if v.lower() in ("true","false"): return "1" if v.lower()=="true" else "0"
    if re.fullmatch(r"-?\d+",v): return v
    if re.fullmatch(r"-?\d+\.\d+",v): return v
    return "'"+v.replace("'","''")+"'"
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default=str(DATA/"seed.sql.gz"))
    args=ap.parse_args()
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        w.write("-- Generated synthetic seed. Execute docs/schema.sql first.\nPRAGMA foreign_keys=ON;\nBEGIN TRANSACTION;\n")
        for file,table in MAP:
            path=DATA/f"{file}.csv"
            if not path.exists(): continue
            with path.open(newline="",encoding="utf-8") as f:
                reader=csv.DictReader(f); cols=reader.fieldnames
                col_sql=",".join('"'+c+'"' for c in cols)
                batch=[]
                for row in reader:
                    vals=",".join(literal(row[c]) for c in cols)
                    batch.append(f'INSERT INTO "{table}" ({col_sql}) VALUES ({vals});\n')
                    if len(batch)>=5000:
                        w.write("".join(batch)); batch.clear()
                if batch: w.write("".join(batch))
        w.write("COMMIT;\n")
    print(f"Wrote {out} ({out.stat().st_size:,} compressed bytes)")
if __name__=="__main__": main()
