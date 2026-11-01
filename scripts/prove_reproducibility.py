#!/usr/bin/env python3
"""Regenerate twice in isolated temporary directories; never modifies shipped data."""
import argparse, hashlib, json, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
GEN=ROOT/"generator"/"generate_data.py"
def snapshot(folder):
    files={}
    counts={}
    for p in sorted(Path(folder).glob("*.csv")):
        files[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
        import pandas as pd
        counts[p.name]=len(pd.read_csv(p))
    return files,counts
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--scale",choices=["starter","standard","full"],default="starter")
    ap.add_argument("--seed",type=int,default=20261022)
    a=ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        a_dir=Path(tmp)/"copy_a"; b_dir=Path(tmp)/"copy_b"
        for folder in (a_dir,b_dir):
            subprocess.run([sys.executable,str(GEN),"--scale",a.scale,"--seed",str(a.seed),"--output-dir",str(folder)],check=True)
        ah,ac=snapshot(a_dir); bh,bc=snapshot(b_dir)
        ok=ah==bh and ac==bc
        print(json.dumps({"seed":a.seed,"scale":a.scale,"row_counts_identical":ac==bc,
                          "checksums_identical":ah==bh,"file_count":len(ah),"passed":ok},indent=2))
        return 0 if ok else 1
if __name__=="__main__": raise SystemExit(main())
