"""Read-only REST API for the Unified Inventory Control Tower."""
from pathlib import Path
from typing import Optional
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
app=FastAPI(title="Unified Inventory Control Tower API",version="2.0.0",
            description="Inventory ATP, reservations, event ledger, transfers, orders and exceptions.")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
_cache={}
def frame(name):
    if name not in _cache:
        path=DATA/f"{name}.csv"
        if not path.exists(): raise HTTPException(404,f"Dataset {name} is not available")
        _cache[name]=pd.read_csv(path,low_memory=False)
    return _cache[name]
def records(df):
    return df.astype(object).where(pd.notna(df),None).to_dict(orient="records")

@app.get("/health")
def health(): return {"status":"ok","service":"inventory-control-tower"}
@app.get("/api/v1/summary")
def summary():
    b,o,r,m,g=frame("inventory_balances"),frame("orders"),frame("reservations"),frame("inventory_movements"),frame("ground_truth")
    return {"sku_count":int(frame("skus").shape[0]),"location_count":int(frame("locations").shape[0]),
            "on_hand_units":int(b.on_hand.sum()),"reserved_units":int(b.reserved.sum()),
            "blocked_units":int(b.blocked.sum()),"available_to_promise_units":int(b.available_to_promise.sum()),
            "order_count":len(o),"active_reservations":int((r.status=="active").sum()),
            "movement_count":len(m),"labelled_scenarios":len(g)}
@app.get("/api/v1/atp")
def atp(sku_id:Optional[str]=None,location_id:Optional[str]=None,min_atp:int=0,limit:int=Query(100,ge=1,le=5000)):
    b=frame("inventory_balances"); q=b[b.available_to_promise>=min_atp]
    if sku_id:q=q[q.sku_id==sku_id]
    if location_id:q=q[q.location_id==location_id]
    return records(q.head(limit))
@app.get("/api/v1/reservations")
def reservations(status:Optional[str]=None,limit:int=Query(100,ge=1,le=5000)):
    q=frame("reservations")
    if status:q=q[q.status==status]
    return records(q.head(limit))
@app.get("/api/v1/orders/{order_id}")
def order_detail(order_id:str):
    o=frame("orders"); q=o[o.order_id==order_id]
    if q.empty: raise HTTPException(404,"Order not found")
    return {"order":records(q)[0],"lines":records(frame("order_lines").query("order_id == @order_id")),
            "reservations":records(frame("reservations").query("order_id == @order_id")),
            "shipments":records(frame("shipments").query("order_id == @order_id"))}
@app.get("/api/v1/anomalies")
def anomalies(): return records(frame("ground_truth"))
@app.get("/api/v1/movements")
def movements(sku_id:Optional[str]=None,location_id:Optional[str]=None,limit:int=Query(100,ge=1,le=10000)):
    q=frame("inventory_movements")
    if sku_id:q=q[q.sku_id==sku_id]
    if location_id:q=q[q.location_id==location_id]
    return records(q.tail(limit).iloc[::-1])
@app.get("/api/v1/locations")
def locations(): return records(frame("locations"))
@app.get("/api/v1/skus")
def skus(limit:int=Query(100,ge=1,le=5000)): return records(frame("skus").head(limit))
@app.get("/api/v1/transfers")
def transfers(status:Optional[str]=None,limit:int=Query(100,ge=1,le=5000)):
    q=frame("shipments"); q=q[q.shipment_type=="internal_transfer"]
    if status:q=q[q.status==status]
    return records(q.head(limit))
@app.get("/api/v1/data-quality")
def data_quality():
    path=DATA/"validation_summary.json"
    return __import__("json").loads(path.read_text()) if path.exists() else {"status":"not_run"}
