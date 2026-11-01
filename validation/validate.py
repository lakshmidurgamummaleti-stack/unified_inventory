#!/usr/bin/env python3
"""Independent acceptance validator for the Unified Inventory Control Tower."""
from pathlib import Path
import json, re, sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
def load(n): return pd.read_csv(DATA/f"{n}.csv",low_memory=False)
def validate(data_dir=DATA, write_summary=True):
    global DATA
    DATA=Path(data_dir)
    names=["products","skus","locations","inventory_balances","inventory_movements","orders",
           "order_lines","reservations","shipments","replenishment_rules","order_events","reservation_events",
           "ground_truth","anomaly_fixtures"]
    d={n:pd.read_csv(DATA/f"{n}.csv",low_memory=False) for n in names}
    p,s,l,b,m,o,ol,r,sh,rr,oe,re,gt,fx=[d[n] for n in names]
    manifest=json.loads((DATA/"manifest.json").read_text())
    passed=[]; failed=[]
    def check(label, condition, detail=""):
        (passed if bool(condition) else failed).append({"test":label,"detail":detail})
    # PKs
    pk={"products":"product_id","skus":"sku_id","locations":"location_id","inventory_balances":"balance_id",
        "inventory_movements":"movement_id","orders":"order_id","order_lines":"order_line_id",
        "reservations":"reservation_id","shipments":"shipment_id","replenishment_rules":"rule_id"}
    for n,c in pk.items(): check(f"PK unique: {n}.{c}",d[n][c].notna().all() and not d[n][c].duplicated().any())
    # FK integrity
    def subset(child,col,parent,pcol):
        return child[col].dropna().isin(set(parent[pcol])).all()
    fks=[
      ("SKU product FK",s,"product_id",p,"product_id"),
      ("Location parent FK",l,"parent_location_id",l,"location_id"),
      ("Balance SKU FK",b,"sku_id",s,"sku_id"),("Balance location FK",b,"location_id",l,"location_id"),
      ("Movement SKU FK",m,"sku_id",s,"sku_id"),("Movement location FK",m,"location_id",l,"location_id"),
      ("Order fulfillment location FK",o,"fulfillment_location_id",l,"location_id"),
      ("OrderLine order FK",ol,"order_id",o,"order_id"),("OrderLine SKU FK",ol,"sku_id",s,"sku_id"),
      ("OrderLine allocated location FK",ol,"allocated_location_id",l,"location_id"),
      ("Reservation order FK",r,"order_id",o,"order_id"),("Reservation line FK",r,"order_line_id",ol,"order_line_id"),
      ("Reservation SKU FK",r,"sku_id",s,"sku_id"),("Reservation location FK",r,"location_id",l,"location_id"),
      ("Shipment order FK",sh,"order_id",o,"order_id"),("Shipment source location FK",sh,"from_location_id",l,"location_id"),
      ("Shipment destination location FK",sh,"to_location_id",l,"location_id"),("Shipment SKU FK",sh,"sku_id",s,"sku_id"),
      ("Rule SKU FK",rr,"sku_id",s,"sku_id"),("Rule location FK",rr,"location_id",l,"location_id")]
    for label,ch,c,pa,pc in fks: check(label,subset(ch,c,pa,pc))
    # enums and formats
    check("SKU nomenclature",s.sku_id.str.fullmatch(r"SKU-\d{6}").all())
    check("Location nomenclature",l.location_id.str.fullmatch(r"LOC-\d{6}").all())
    check("Order nomenclature",o.order_id.str.fullmatch(r"ORD-2026-\d{6}").all())
    check("Movement nomenclature",m.movement_id.str.fullmatch(r"MOV-2026-\d{8}").all())
    check("Shipment nomenclature",sh.shipment_id.str.fullmatch(r"SHP-2026-\d{6}").all())
    check("Movement enums",set(m.movement_type).issubset({"opening_balance","receipt","sale","return","transfer_out","transfer_in",
      "transfer_receipt","transfer_out_complete","adjustment","damage","cycle_count","reservation_hold","reservation_release"}))
    check("Reservation lifecycle enums",set(r.status).issubset({"active","expired","fulfilled","cancelled","released"}))
    check("Order lifecycle enums",set(o.status).issubset({"pending","confirmed","reserved","allocated","shipped","delivered","cancelled","backordered"}))
    check("Shipment lifecycle enums",set(sh.status).issubset({"planned","in_transit","received","delivered"}))
    check("Shipment type enums",set(sh.shipment_type).issubset({"customer_order","internal_transfer","supplier_receipt"}))
    check("Supplier receipts have destination and receipt timestamp",
          ((sh.shipment_type!="supplier_receipt") | (sh.to_location_id.notna() & sh.received_at.notna())).all())
    check("Location enums",set(l.location_type).issubset({"store","warehouse","dc","online_virtual"}))
    # Cardinality / unique composites
    check("One balance per SKU-location",not b.duplicated(["sku_id","location_id"]).any())
    check("One replenishment rule per SKU-location",not rr.duplicated(["sku_id","location_id"]).any())
    check("Rule coverage for every balance",set(zip(b.sku_id,b.location_id))==set(zip(rr.sku_id,rr.location_id)))
    check("Every order has at least one line",set(o.order_id)==set(ol.order_id))
    # Arithmetic and dates
    line_totals=ol.assign(line_total=ol.quantity*ol.unit_price).groupby("order_id").line_total.sum()
    order_totals=o.set_index("order_id").total_amount
    check("Order totals equal order-line sums",((line_totals-order_totals).abs()<0.011).all())
    rrsv=r.merge(ol[["order_line_id","order_id","sku_id","quantity","allocated_location_id"]],on="order_line_id",suffixes=("_res","_line"))
    check("Reservation parent attributes agree",((rrsv.order_id_res==rrsv.order_id_line)&(rrsv.sku_id_res==rrsv.sku_id_line)&
         (rrsv.quantity_res==rrsv.quantity_line)&(rrsv.location_id==rrsv.allocated_location_id)).all() if len(rrsv) else True)
    rt=pd.to_datetime(r.reserved_at,utc=True); et=pd.to_datetime(r.expires_at,utc=True)
    check("Reservation expiry after reservation creation",(et>rt).all())
    check("Active reservations have future expiry",((r.status!="active") | (et>pd.Timestamp(manifest["as_of"],tz="UTC") if pd.Timestamp(manifest["as_of"]).tzinfo is None else et>pd.Timestamp(manifest["as_of"]))).all())
    # Movement references
    for typ,frame,key,refcol in [("order",o,"order_id","order_id_ref"),("reservation",r,"reservation_id","reservation_id_ref"),("shipment",sh,"shipment_id","shipment_id_ref")]:
        subsetm=m[m.reference_type==typ]
        check(f"Movement {typ} references resolve",subsetm.reference_id.notna().all() and subsetm.reference_id.isin(set(frame[key])).all())
        check(f"Movement {typ} FK column resolves",m[refcol].dropna().isin(set(frame[key])).all())
        check(f"Movement {typ} FK column populated",m.loc[m.reference_type==typ,refcol].notna().all())
    receipt_moves=m[(m.movement_type=="receipt") & (m.reference_type=="shipment")][["reference_id","quantity"]]
    receipt_ship=sh[sh.shipment_type=="supplier_receipt"][["shipment_id","quantity"]]
    receipt_check=receipt_moves.merge(receipt_ship,left_on="reference_id",right_on="shipment_id",suffixes=("_movement","_shipment"),how="outer",indicator=True)
    check("Receipt movements trace to supplier receipt shipments",
          (receipt_check._merge=="both").all() and
          (receipt_check.quantity_movement==receipt_check.quantity_shipment).all())
    check("Opening balances represented by opening events",(m[m.movement_type=="opening_balance"].delta_on_hand>0).all())
    # Ledger reconciliation (all four inventory dimensions)
    agg=m.groupby(["sku_id","location_id"],as_index=False).agg(
      on_hand=("delta_on_hand","sum"),reserved=("delta_reserved","sum"),blocked=("delta_blocked","sum"),
      in_transit_in=("delta_in_transit_in","sum"),in_transit_out=("delta_in_transit_out","sum"))
    chk=b.merge(agg,on=["sku_id","location_id"],suffixes=("_b","_m"),how="outer",indicator=True)
    check("All balance keys represented in movement ledger",(chk._merge=="both").all())
    for col in ["on_hand","reserved","blocked","in_transit_in","in_transit_out"]:
        check(f"Ledger reconciliation: {col}",(chk[f"{col}_b"]==chk[f"{col}_m"]).all())
    check("No negative physical stock",(b.on_hand>=0).all())
    check("No negative reserved/blocked/inbound",(b[["reserved","blocked","in_transit_in","in_transit_out"]]>=0).all().all())
    check("Blocked stock does not exceed on-hand",(b.blocked<=b.on_hand).all())
    # Reservation hold/release lifecycle exactly matches rows
    holds=m[m.movement_type=="reservation_hold"].groupby("reference_id").delta_reserved.sum()
    releases=m[m.movement_type=="reservation_release"].groupby("reference_id").delta_reserved.sum()
    check("Every reservation has one hold movement",set(r.reservation_id)==set(holds.index))
    check("Reservation hold quantities match rows",all(holds.get(x,0)==q for x,q in zip(r.reservation_id,r.quantity)))
    check("Released reservations have release movement",set(r.loc[r.status!="active","reservation_id"]).issubset(set(releases.index)))
    check("Active reservations have no release movement",not set(r.loc[r.status=="active","reservation_id"]).intersection(set(releases.index)))
    # Shipped order lines map to matching sale events
    sales=m[m.movement_type=="sale"]
    expected=ol[ol.line_status=="shipped"].groupby(["order_id","sku_id","allocated_location_id"]).quantity.sum()
    actual=sales.groupby(["reference_id","sku_id","location_id"]).quantity.sum()
    expected.index.names=["reference_id","sku_id","location_id"]
    check("Shipped order lines trace to sale movements",expected.sort_index().equals(actual.sort_index()))
    # Shipment transfer logic
    tr=sh[sh.shipment_type=="internal_transfer"]
    check("Internal transfers have distinct locations",(tr.from_location_id!=tr.to_location_id).all())
    transfer_counts=(m[m.shipment_id_ref.isin(set(tr.shipment_id))]
        .groupby(["shipment_id_ref","movement_type"]).size().unstack(fill_value=0))
    transfer_counts=transfer_counts.reindex(tr.shipment_id,fill_value=0)
    received_mask=tr.status.to_numpy()=="received"
    required_ok=((transfer_counts.get("transfer_out",0).to_numpy()==1) &
                 (transfer_counts.get("transfer_in",0).to_numpy()==1) &
                 (transfer_counts.get("transfer_receipt",0).to_numpy()==received_mask.astype(int)) &
                 (transfer_counts.get("transfer_out_complete",0).to_numpy()==received_mask.astype(int)))
    check("Transfer dispatch/receipt lifecycle events",required_ok.all())
    # Inbound approval + ATP
    inbound={}
    for row in tr[tr.status=="in_transit"].itertuples(index=False):
        eta=pd.to_datetime(row.eta,utc=True)
        asof=pd.to_datetime(manifest["as_of"],utc=True)
        if (eta-asof).days<=14:
            inbound[(row.sku_id,row.to_location_id)]=inbound.get((row.sku_id,row.to_location_id),0)+row.quantity
    approved=[inbound.get((s0,l0),0) for s0,l0 in zip(b.sku_id,b.location_id)]
    check("Approved inbound matches open transfer policy",list(b.approved_inbound)==approved)
    expected_atp=(b.on_hand-b.reserved-b.blocked-b.safety_stock_units-b.channel_buffer_units+b.approved_inbound).clip(lower=0)
    check("ATP formula exact",list(b.available_to_promise)==list(expected_atp))
    # Explicit state-transition history must resolve to its parent entities.
    check("Order event FK",oe.order_id.isin(set(o.order_id)).all())
    check("Reservation event FK",re.reservation_id.isin(set(r.reservation_id)).all())
    check("Every order has event history",set(o.order_id)==set(oe.order_id))
    check("Every reservation has event history",set(r.reservation_id)==set(re.reservation_id))
    final_order_events=oe.sort_values("event_ts").groupby("order_id").tail(1).set_index("order_id").to_status
    check("Order event history ends at current status",all(final_order_events.get(x)==y for x,y in zip(o.order_id,o.status)))
    final_res_events=re.sort_values("event_ts").groupby("reservation_id").tail(1).set_index("reservation_id").to_status
    check("Reservation event history ends at current status",all(final_res_events.get(x)==y for x,y in zip(r.reservation_id,r.status)))
    # Ground truth is separate and fixture-only
    required={"balance_mismatch","reservation_exceeds_available","fulfilled_from_blocked","premature_transfer_count"}
    check("Required edge cases labelled",required.issubset(set(gt.issue_type)))
    check("Ground truth separate from operational features","issue_type" not in m.columns and "issue_type" not in b.columns)
    check("Fixture labels not injected into clean balances",len(fx)==len(gt) and fx.scenario_id.is_unique)
    check("Overselling and expired-reservation cases included",{"overselling_attempt","expired_reservation"}.issubset(set(gt.issue_type)))
    # Date / relationship sanity
    check("Shipment dates ordered",((pd.to_datetime(sh.shipped_at,utc=True)<=pd.to_datetime(sh.eta,utc=True)) | sh.eta.isna()).all())
    check("Received shipments have received_at",((sh.status!="received")|sh.received_at.notna()).all())
    check("No duplicate order lines",not ol.duplicated(["order_id","order_line_id"]).any())
    # Scale acceptance
    scale=manifest["scale"]
    if scale=="full":
        check("Full-scale SKU target",len(s)==5000)
        check("Full-scale location target",len(l)==100)
        check("Full-scale movement target",len(m)==1000000)
        check("Full-scale order target",len(o)==50000)
    check("Manifest row counts match files",all(manifest["counts"].get(n)==len(d[n]) for n in names))
    check("Manifest checksum matches CSV files",all(__import__("hashlib").sha256((DATA/f"{n}.csv").read_bytes()).hexdigest()==manifest["sha256"].get(f"{n}.csv") for n in names))
    result={"passed":passed,"failed":failed,"passed_count":len(passed),"failed_count":len(failed),
            "total_count":len(passed)+len(failed),"pass_rate_pct":round(100*len(passed)/max(1,len(passed)+len(failed)),2),
            "scale":scale,"seed":manifest["seed"],"counts":manifest["counts"]}
    if write_summary: (DATA/"validation_summary.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    return result
if __name__=="__main__":
    result=validate()
    sys.exit(1 if result["failed"] else 0)
