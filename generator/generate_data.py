#!/usr/bin/env python3
"""Deterministic synthetic inventory generator. All operational records are synthetic."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import numpy as np
import pandas as pd

AS_OF = pd.Timestamp("2026-10-31T00:00:00Z")
DEFAULT_SEED = 20261022

def make_ids(prefix, n, width=6):
    return np.array([f"{prefix}-{i:0{width}d}" for i in range(1, n+1)], dtype=object)

def generate(scale="starter", seed=DEFAULT_SEED, out_dir=None):
    scales = {
        "starter": (300, 30, 30000, 1500),
        "standard": (1500, 60, 200000, 12000),
        "full": (5000, 100, 1000000, 50000),
    }
    n_skus, n_locs, n_mov, n_orders = scales[scale]
    rng = np.random.default_rng(seed)
    out = Path(out_dir) if out_dir else Path(__file__).resolve().parents[1] / "data"
    out.mkdir(parents=True, exist_ok=True)

    # 1. Product and SKU masters
    n_products = max(1, n_skus // 2)
    products = pd.DataFrame({
        "product_id": make_ids("PRD", n_products),
        "name": [f"Product Family {i:05d}" for i in range(1, n_products+1)],
        "category": rng.choice(["Electronics","Apparel","Home","Beauty","Sports","Grocery","Toys"], n_products),
        "brand": rng.choice(["Northstar","Evergreen","Aster","Vertex","Bluebird"], n_products),
        "description": ["Synthetic catalog item"] * n_products,
        "status": ["active"] * n_products,
        "created_at": [(AS_OF-pd.Timedelta(days=int(x))).isoformat() for x in rng.integers(180,900,n_products)],
        "updated_at": [AS_OF.isoformat()] * n_products,
    })
    sku_ids = make_ids("SKU", n_skus)
    product_idx = np.arange(n_skus) % n_products
    skus = pd.DataFrame({
        "sku_id": sku_ids,
        "product_id": products.product_id.to_numpy()[product_idx],
        "sku_code": [f"ITEM-{i:06d}" for i in range(1,n_skus+1)],
        "size": rng.choice(["XS","S","M","L","XL","One Size"],n_skus),
        "color": rng.choice(["Black","Blue","White","Green","Red","Grey"],n_skus),
        "unit_cost": np.round(rng.uniform(3,180,n_skus),2),
        "unit_price": np.round(rng.uniform(15,350,n_skus),2),
        "weight_kg": np.round(rng.uniform(.05,12,n_skus),3),
        "status": ["active"]*n_skus,
        "created_at": [AS_OF.isoformat()]*n_skus,
    })

    # 2. Location hierarchy: DCs, warehouses, stores and one online node
    physical_n = n_locs - 1
    loc_rows=[]
    cities=["New York","Chicago","Dallas","Seattle","Atlanta","Denver","Miami","Boston","Phoenix","Austin"]
    for i in range(1,n_locs+1):
        if i == 1: typ, channel, parent = "dc","all",None
        elif i <= min(4,n_locs): typ, channel, parent = "warehouse","all","LOC-000001"
        elif i == n_locs: typ, channel, parent = "online_virtual","ecom","LOC-000001"
        else: typ, channel, parent = "store",("retail" if i%4 else "all"),"LOC-000001"
        loc_rows.append({
            "location_id":f"LOC-{i:06d}","name":f"{cities[(i-1)%len(cities)]} {typ.title()} {i:03d}",
            "location_type":typ,"parent_location_id":parent,"channel":channel,
            "address_city":cities[(i-1)%len(cities)],"address_country":"USA",
            "timezone":"America/New_York","status":"active",
            "safety_stock_days":int(rng.integers(3,15)),"created_at":AS_OF.isoformat()
        })
    locations=pd.DataFrame(loc_rows)
    physical_ids=locations[locations.location_type!="online_virtual"].location_id.to_numpy()
    # Each SKU is stocked at four physical locations (or all available if tiny).
    slots=min(4,len(physical_ids))
    key_sku_idx=np.repeat(np.arange(n_skus),slots)
    key_loc_idx=np.concatenate([((np.arange(n_skus)*7+j*13)%len(physical_ids)) for j in range(slots)])
    key_sku_idx=np.concatenate([np.arange(n_skus) for _ in range(slots)])
    key_loc_idx=np.concatenate([((np.arange(n_skus)*7+j*13)%len(physical_ids)) for j in range(slots)])
    key_skus=sku_ids[key_sku_idx]
    key_locs=physical_ids[key_loc_idx]
    n_keys=len(key_skus)
    # lookup available SKUs by location for order allocations
    sku_by_loc={loc: key_skus[key_locs==loc] for loc in physical_ids}
    # rule data one per SKU-location balance
    rule_ids=make_ids("RPL",n_keys)
    safety=rng.integers(8,35,n_keys)
    buffers=rng.integers(0,16,n_keys)
    lead=rng.integers(2,15,n_keys)
    rules=pd.DataFrame({
        "rule_id":rule_ids,"sku_id":key_skus,"location_id":key_locs,
        "min_stock":safety,"max_stock":safety+rng.integers(80,220,n_keys),
        "reorder_point":safety+rng.integers(15,45,n_keys),
        "reorder_qty":rng.integers(30,100,n_keys),"lead_time_days":lead,
        "safety_stock_units":safety,"channel_buffer_units":buffers,
        "inbound_policy_days":14,"active":True,
        "effective_from":(AS_OF-pd.Timedelta(days=90)).isoformat(),"effective_to":None
    })
    key_lookup={(s,l):i for i,(s,l) in enumerate(zip(key_skus,key_locs))}
    # 3. Orders and order lines, allocated only to valid SKU/location pairs
    order_ids=make_ids("ORD-2026",n_orders)
    channels=rng.choice(["ecom","retail","marketplace"],n_orders,p=[.52,.33,.15])
    statuses=rng.choice(["pending","confirmed","reserved","allocated","shipped","delivered","cancelled","backordered"],
                        n_orders,p=[.10,.10,.14,.12,.18,.20,.10,.06])
    order_times=AS_OF-pd.to_timedelta(rng.integers(1*24*3600,50*24*3600,n_orders),unit="s")
    fulfill_locs=rng.choice(physical_ids,n_orders)
    orders_rows=[]; line_rows=[]; line_context=[]
    for i,oid in enumerate(order_ids):
        n_lines=int(rng.integers(1,4))
        total=0.0
        for ln in range(1,n_lines+1):
            loc=fulfill_locs[i]
            candidates=sku_by_loc[loc]
            sku=str(rng.choice(candidates))
            si=int(sku.split("-")[1])-1
            qty=int(rng.integers(1,5)); price=float(skus.iloc[si].unit_price)
            st=str(statuses[i])
            if st in ("shipped","delivered"): line_status="shipped"
            elif st=="allocated": line_status="allocated"
            elif st=="reserved": line_status="reserved"
            elif st=="cancelled": line_status="cancelled"
            elif st=="backordered": line_status="backordered"
            else: line_status="pending"
            lid=f"{oid}-L{ln:02d}"
            line_rows.append({"order_line_id":lid,"order_id":oid,"sku_id":sku,"quantity":qty,
                              "unit_price":price,"line_status":line_status,
                              "allocated_location_id":loc if line_status in ("reserved","allocated","shipped","backordered","cancelled") else None})
            line_context.append((i,ln,oid,lid,sku,loc,qty,price,line_status))
            total+=qty*price
        orders_rows.append({"order_id":oid,"channel":channels[i],
            "customer_id":f"CUST-{int(rng.integers(1,250000)):07d}","status":st,
            "fulfillment_location_id":fulfill_locs[i],"order_ts":order_times[i].isoformat(),
            "total_amount":round(total,2),"currency":"USD"})
    orders=pd.DataFrame(orders_rows); order_lines=pd.DataFrame(line_rows)

    # 4. Reservations; active reservations have future expiry. All expired reservations have release events.
    reservations_rows=[]
    for ctx in line_context:
        i,ln,oid,lid,sku,loc,qty,price,line_status=ctx
        channel=channels[i]; ost=str(statuses[i])
        if channel not in ("ecom","marketplace") or ost not in ("reserved","allocated","shipped","delivered","cancelled","backordered"):
            continue
        if ost in ("shipped","delivered"): rstatus="fulfilled"
        elif ost=="cancelled": rstatus="cancelled"
        elif ost=="backordered": rstatus="expired"
        else: rstatus="active" if rng.random()>.08 else "expired"
        reserved_at=order_times[i]+pd.Timedelta(minutes=2)
        if rstatus=="active": expires=AS_OF+pd.Timedelta(hours=int(rng.integers(1,72)))
        else: expires=reserved_at+pd.Timedelta(hours=int(rng.integers(1,7)))
        released=(expires+pd.Timedelta(minutes=1)) if rstatus in ("expired","cancelled","fulfilled") else pd.NaT
        reservations_rows.append({"reservation_id":f"RES-{oid}-{ln:02d}","order_id":oid,"order_line_id":lid,
            "sku_id":sku,"location_id":loc,"quantity":qty,"status":rstatus,
            "reserved_at":reserved_at.isoformat(),"expires_at":expires.isoformat(),
            "released_at":released.isoformat() if pd.notna(released) else None})
    reservations=pd.DataFrame(reservations_rows)
    # Explicit lifecycle event history (current-state tables are projections only).
    order_event_rows=[]
    for row in orders.itertuples(index=False):
        created_ts=pd.Timestamp(row.order_ts)-pd.Timedelta(seconds=1)
        order_event_rows.append({"order_event_id":f"OEV-{len(order_event_rows)+1:08d}","order_id":row.order_id,
            "from_status":None,"to_status":"created","event_type":"order_created",
            "event_ts":created_ts.isoformat(),"actor":"system"})
        order_event_rows.append({"order_event_id":f"OEV-{len(order_event_rows)+1:08d}","order_id":row.order_id,
            "from_status":"created","to_status":row.status,"event_type":"status_transition",
            "event_ts":row.order_ts,"actor":"system"})
    order_events=pd.DataFrame(order_event_rows)
    reservation_event_rows=[]
    for row in reservations.itertuples(index=False):
        reservation_event_rows.append({"reservation_event_id":f"REV-{len(reservation_event_rows)+1:08d}",
            "reservation_id":row.reservation_id,"from_status":None,"to_status":"active",
            "event_type":"reservation_created","event_ts":row.reserved_at,"actor":"ecommerce"})
        if row.status!="active":
            reservation_event_rows.append({"reservation_event_id":f"REV-{len(reservation_event_rows)+1:08d}",
                "reservation_id":row.reservation_id,"from_status":"active","to_status":row.status,
                "event_type":"reservation_state_changed","event_ts":row.released_at,"actor":"system"})
    reservation_events=pd.DataFrame(reservation_event_rows)

    # 5. Shipments: customer shipments and internal transfers.
    shipment_rows=[]; ship_counter=1
    for ctx in line_context:
        i,ln,oid,lid,sku,loc,qty,price,line_status=ctx
        if line_status=="shipped":
            shipment_rows.append({"shipment_id":f"SHP-2026-{ship_counter:06d}","shipment_type":"customer_order",
                "order_id":oid,"from_location_id":loc,"to_location_id":None,"sku_id":sku,"quantity":qty,
                "status":"delivered" if statuses[i]=="delivered" else "in_transit",
                "shipped_at":order_times[i].isoformat(),"eta":(order_times[i]+pd.Timedelta(days=2)).isoformat(),
                "received_at":(order_times[i]+pd.Timedelta(days=2)).isoformat() if statuses[i]=="delivered" else None})
            ship_counter+=1
    n_transfers=max(50,n_mov//500)
    transfer_meta=[]
    for j in range(n_transfers):
        si=int(rng.integers(0,n_skus)); sku=str(sku_ids[si])
        candidates=np.where(key_sku_idx==si)[0]
        src_i,dst_i=rng.choice(candidates,2,replace=False)
        src=str(key_locs[src_i]); dst=str(key_locs[dst_i]); qty=int(rng.integers(2,12))
        state="received" if rng.random()<.7 else "in_transit"
        shipped_at=AS_OF-pd.Timedelta(days=int(rng.integers(1,20)))
        eta=AS_OF+pd.Timedelta(days=int(rng.integers(1,10))) if state=="in_transit" else shipped_at+pd.Timedelta(days=3)
        received=eta if state=="received" else None
        sid=f"SHP-2026-{ship_counter:06d}"; ship_counter+=1
        shipment_rows.append({"shipment_id":sid,"shipment_type":"internal_transfer","order_id":None,
            "from_location_id":src,"to_location_id":dst,"sku_id":sku,"quantity":qty,"status":state,
            "shipped_at":shipped_at.isoformat(),"eta":eta.isoformat(),
            "received_at":received.isoformat() if received is not None else None})
        transfer_meta.append((sid,sku,src,dst,qty,state,shipped_at,eta))
    shipments=pd.DataFrame(shipment_rows)

    # 6. Immutable movements. Every balance is derived from movement deltas.
    rows=[]
    def add(sku,loc,typ,qty,ref_id=None,ref_type=None,reason=None,dt=None,
            d_on=0,d_res=0,d_block=0,d_in=0,d_out=0,created="system"):
        rows.append((sku,loc,typ,int(qty),ref_id,ref_type,reason,
                     (dt if dt is not None else AS_OF-pd.Timedelta(days=1)).isoformat(),
                     created,int(d_on),int(d_res),int(d_block),int(d_in),int(d_out)))
    open_dt=AS_OF-pd.Timedelta(days=180)
    for sku,loc in zip(key_skus,key_locs):
        add(sku,loc,"opening_balance",1000,None,"opening","opening_stock",open_dt,1000)
    # Order sales are explicit and linked to order IDs.
    for ctx in line_context:
        i,ln,oid,lid,sku,loc,qty,price,line_status=ctx
        if line_status=="shipped":
            add(sku,loc,"sale",qty,oid,"order","customer_fulfillment",
                order_times[i],-qty,created="ecommerce")
    # Reservation holds and releases.
    for r in reservations.itertuples(index=False):
        add(r.sku_id,r.location_id,"reservation_hold",r.quantity,r.reservation_id,"reservation","order_hold",
            pd.Timestamp(r.reserved_at),d_res=r.quantity,created="ecommerce")
        if r.status!="active":
            add(r.sku_id,r.location_id,"reservation_release",r.quantity,r.reservation_id,"reservation",
                "expiry" if r.status=="expired" else r.status,pd.Timestamp(r.released_at),d_res=-r.quantity,created="system")
    # Internal transfer events: dispatch source and inbound at destination; receipt only on received transfers.
    for sid,sku,src,dst,qty,state,shipped_at,eta in transfer_meta:
        add(sku,src,"transfer_out",qty,sid,"shipment","transfer_dispatch",shipped_at,-qty,d_out=qty,created="warehouse")
        add(sku,dst,"transfer_in",qty,sid,"shipment","in_transit_inbound",shipped_at,d_in=qty,created="warehouse")
        if state=="received":
            add(sku,dst,"transfer_receipt",qty,sid,"shipment","transfer_received",eta,qty,d_in=-qty,created="warehouse")
            add(sku,src,"transfer_out_complete",qty,sid,"shipment","transfer_completed",eta,d_out=-qty,created="warehouse")
    # Fill exact movement target with reproducible manual operational events.
    remaining=n_mov-len(rows)
    if remaining<0: raise ValueError("Scale too small for mandatory event rows")
    key_idx=rng.integers(0,n_keys,remaining)
    types=rng.choice(["receipt","return","adjustment","damage","cycle_count"],remaining,p=[.08,.08,.35,.15,.34])
    qtys=rng.integers(1,6,remaining)
    deltas=np.zeros(remaining,dtype=np.int64); blocks=np.zeros(remaining,dtype=np.int64)
    reasons=[]
    for k,t in enumerate(types):
        q=int(qtys[k])
        if t in ("receipt","return"): deltas[k]=q
        elif t=="adjustment": deltas[k]=q if rng.random()<.5 else -q
        elif t=="cycle_count": deltas[k]=q if rng.random()<.5 else -q
        elif t=="damage": blocks[k]=q
        reasons.append({"receipt":"supplier_receipt","return":"customer_return","adjustment":"operator_adjustment",
                        "damage":"damaged_goods","cycle_count":"cycle_count"}[t])
    secs=rng.integers(0,180*24*3600,remaining)
    times=AS_OF-pd.to_timedelta(secs,unit="s")
    # Supplier receipt movements reference real receipt-shipment rows; returns reference an order.
    receipt_idx=np.where(types=="receipt")[0]
    receipt_ids=np.array([f"SHP-2026-{ship_counter+i:06d}" for i in range(len(receipt_idx))],dtype=object)
    if len(receipt_idx):
        receipt_shipments=pd.DataFrame({
            "shipment_id":receipt_ids,"shipment_type":"supplier_receipt","order_id":None,
            "from_location_id":None,"to_location_id":key_locs[key_idx[receipt_idx]],
            "sku_id":key_skus[key_idx[receipt_idx]],"quantity":qtys[receipt_idx],"status":"received",
            "shipped_at":[x.isoformat() for x in times[receipt_idx]],
            "eta":[x.isoformat() for x in times[receipt_idx]],
            "received_at":[x.isoformat() for x in times[receipt_idx]]
        })
        shipments=pd.concat([shipments,receipt_shipments],ignore_index=True)
    ref_ids=np.full(remaining,None,dtype=object)
    ref_types=np.full(remaining,"manual",dtype=object)
    ref_ids[receipt_idx]=receipt_ids; ref_types[receipt_idx]="shipment"
    return_idx=np.where(types=="return")[0]
    if len(return_idx):
        ref_ids[return_idx]=rng.choice(order_ids,len(return_idx)); ref_types[return_idx]="order"
    gen_df=pd.DataFrame({
        "sku_id":key_skus[key_idx],"location_id":key_locs[key_idx],"movement_type":types,
        "quantity":qtys,"reference_id":ref_ids,"reference_type":ref_types,"reason_code":reasons,
        "occurred_at":[x.isoformat() for x in times],"created_by":"operator",
        "delta_on_hand":deltas,"delta_reserved":0,"delta_blocked":blocks,
        "delta_in_transit_in":0,"delta_in_transit_out":0
    })
    cols=["sku_id","location_id","movement_type","quantity","reference_id","reference_type",
        "reason_code","occurred_at","created_by","delta_on_hand","delta_reserved","delta_blocked","delta_in_transit_in","delta_in_transit_out"]
    mov=pd.concat([pd.DataFrame(rows,columns=cols),gen_df],ignore_index=True)
    mov["order_id_ref"]=mov["reference_id"].where(mov["reference_type"]=="order")
    mov["reservation_id_ref"]=mov["reference_id"].where(mov["reference_type"]=="reservation")
    mov["shipment_id_ref"]=mov["reference_id"].where(mov["reference_type"]=="shipment")
    mov=mov.sort_values(["occurred_at","sku_id","location_id"],kind="mergesort").reset_index(drop=True)
    mov.insert(0,"movement_id",make_ids("MOV-2026",len(mov),8))
    # derive balance snapshots exactly from ledger
    agg=mov.groupby(["sku_id","location_id"],as_index=False).agg(
        on_hand=("delta_on_hand","sum"),reserved=("delta_reserved","sum"),blocked=("delta_blocked","sum"),
        in_transit_in=("delta_in_transit_in","sum"),in_transit_out=("delta_in_transit_out","sum"))
    agg["balance_id"]=["BAL-"+s+"-"+l for s,l in zip(agg.sku_id,agg.location_id)]
    agg=agg.merge(rules[["sku_id","location_id","safety_stock_units","channel_buffer_units","inbound_policy_days"]],
                  on=["sku_id","location_id"],how="left",validate="one_to_one")
    # Only inbound transfers whose ETA is within the rule's policy horizon are ATP-approved.
    approved={}
    for sid,sku,src,dst,qty,state,shipped_at,eta in transfer_meta:
        if state=="in_transit" and (eta-AS_OF).days <= 14:
            approved[(sku,dst)]=approved.get((sku,dst),0)+qty
    agg["approved_inbound"]=[approved.get((s,l),0) for s,l in zip(agg.sku_id,agg.location_id)]
    agg["available_to_promise"]=(agg.on_hand-agg.reserved-agg.blocked-agg.safety_stock_units-
                                  agg.channel_buffer_units+agg.approved_inbound).clip(lower=0)
    # latest movement ID per balance
    last=mov.groupby(["sku_id","location_id"],sort=False).tail(1)[["sku_id","location_id","movement_id"]]
    agg=agg.merge(last,on=["sku_id","location_id"],how="left")
    agg=agg.rename(columns={"movement_id":"last_movement_id"})
    agg["as_of_ts"]=AS_OF.isoformat()
    balances=agg[["balance_id","sku_id","location_id","on_hand","reserved","blocked","in_transit_in","in_transit_out",
        "safety_stock_units","channel_buffer_units","approved_inbound","available_to_promise","last_movement_id","as_of_ts"]]
    # 7. Deliberate negative scenarios are isolated from production facts.
    first_balance=str(balances.iloc[0].balance_id)
    first_res=str(reservations.iloc[0].reservation_id)
    first_order=str(orders.iloc[0].order_id)
    transfer_ids=shipments.loc[shipments.shipment_type=="internal_transfer","shipment_id"]
    first_transfer=str(transfer_ids.iloc[0]) if len(transfer_ids) else str(shipments.iloc[0].shipment_id)
    expired_rows=reservations[reservations.status=="expired"]
    expired_id=str(expired_rows.iloc[0].reservation_id) if len(expired_rows) else first_res
    second_order=str(orders.iloc[min(1,len(orders)-1)].order_id)
    fixtures=[
      ("CASE-001","balance_mismatch","balance",first_balance,"ledger_on_hand=100;reported_on_hand=112","reject snapshot; rebuild from movement ledger","high"),
      ("CASE-002","reservation_exceeds_available","reservation",first_res,"requested_qty=999;available_qty=3","reject excess reservation or backorder remainder","high"),
      ("CASE-003","fulfilled_from_blocked","order",first_order,"allocated_qty=5;blocked_qty=5","prevent allocation from blocked stock; route to alternate location","high"),
      ("CASE-004","premature_transfer_count","shipment",first_transfer,"status=in_transit;destination_on_hand_includes_transfer=true","keep destination quantity in inbound bucket until receipt","medium"),
      ("CASE-005","overselling_attempt","order",second_order,"requested_qty=50;available_to_promise=4","reject or partially backorder; never create negative stock","high"),
      ("CASE-006","expired_reservation","reservation",expired_id,"status=active;expires_at<as_of","emit reservation_release and free reserved units","high"),
    ]
    gt=pd.DataFrame([{"scenario_id":a,"issue_type":b,"entity_type":c,"entity_id":d,"observed_condition":e,
                      "expected_action":f,"severity":g,"fixture_only":True} for a,b,c,d,e,f,g in fixtures])
    anomaly_fixtures=gt.copy()
    # Save data
    tables={"products":products,"skus":skus,"locations":locations,"inventory_balances":balances,
            "inventory_movements":mov,"orders":orders,"order_lines":order_lines,"reservations":reservations,
            "shipments":shipments,"replenishment_rules":rules,"order_events":order_events,
            "reservation_events":reservation_events,"ground_truth":gt,"anomaly_fixtures":anomaly_fixtures}
    for name,df in tables.items():
        df.to_csv(out/f"{name}.csv",index=False)
    gt.to_json(out/"ground_truth.json",orient="records",indent=2)
    counts={k:len(v) for k,v in tables.items()}
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob("*.csv"))}
    manifest={"project":"Unified Inventory Control Tower","seed":int(seed),"scale":scale,"as_of":AS_OF.isoformat(),
              "counts":counts,"sha256":hashes,"provenance":"100% synthetic; no external data",
              "business_rules":{"atp":"max(0,on_hand-reserved-blocked-safety_stock_units-channel_buffer_units+approved_inbound)",
                                "approved_inbound":"open transfer ETA within replenishment_rule.inbound_policy_days",
                                "reservation_expiry":"expired reservations are released with an immutable reservation_release movement"}}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2))
    print(json.dumps({"scale":scale,"counts":counts,"output":str(out)},indent=2))
    return manifest

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--scale",choices=["starter","standard","full"],default="starter")
    p.add_argument("--seed",type=int,default=DEFAULT_SEED)
    p.add_argument("--output-dir",default=None)
    a=p.parse_args()
    generate(a.scale,a.seed,a.output_dir)

if __name__=="__main__": main()
