from pathlib import Path
import json
from functools import lru_cache
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"

@lru_cache(maxsize=None)
def read(name): return pd.read_csv(DATA/f"{name}.csv",low_memory=False)

def test_acceptance_suite_has_zero_failures():
    result=json.loads((DATA/"validation_summary.json").read_text())
    assert result["failed_count"]==0
    assert result["passed_count"]>=90

def test_required_scale_seed_and_manifest():
    manifest=json.loads((DATA/"manifest.json").read_text())
    assert manifest["seed"]==20261022
    assert manifest["scale"] in {"starter","standard","full"}
    assert manifest["counts"]["inventory_movements"]==len(read("inventory_movements"))

def test_atp_formula_all_balances():
    b=read("inventory_balances")
    calc=(b.on_hand-b.reserved-b.blocked-b.safety_stock_units-b.channel_buffer_units+b.approved_inbound).clip(lower=0)
    assert (calc==b.available_to_promise).all()

def test_clean_ledger_reconciles():
    b=read("inventory_balances"); m=read("inventory_movements")
    sums=m.groupby(["sku_id","location_id"])[["delta_on_hand","delta_reserved","delta_blocked","delta_in_transit_in","delta_in_transit_out"]].sum().reset_index()
    merged=b.merge(sums,on=["sku_id","location_id"],suffixes=("_b","_m"),validate="one_to_one")
    assert (merged.on_hand==merged.delta_on_hand).all()
    assert (merged.reserved==merged.delta_reserved).all()
    assert (merged.blocked==merged.delta_blocked).all()
    assert (merged.in_transit_in==merged.delta_in_transit_in).all()
    assert (merged.in_transit_out==merged.delta_in_transit_out).all()

def test_expired_reservations_are_released():
    r=read("reservations"); m=read("inventory_movements")
    expired=r[r.status!="active"]
    releases=m[m.movement_type=="reservation_release"]
    assert set(expired.reservation_id).issubset(set(releases.reference_id))

def test_order_allocations_are_traceable():
    o=read("order_lines"); m=read("inventory_movements")
    shipped=o[o.line_status=="shipped"]
    sales=m[m.movement_type=="sale"]
    assert set(shipped.order_id).issubset(set(sales.reference_id))

def test_transfer_receipt_does_not_prematurely_add_on_hand():
    sh=read("shipments"); m=read("inventory_movements")
    transfers=sh[sh.shipment_type=="internal_transfer"]
    counts=(m[m.shipment_id_ref.isin(set(transfers.shipment_id))]
            .groupby(["shipment_id_ref","movement_type"]).size().unstack(fill_value=0))
    counts=counts.reindex(transfers.shipment_id,fill_value=0)
    received=(transfers.status.to_numpy()=="received").astype(int)
    assert (counts.transfer_out.to_numpy()==1).all()
    assert (counts.transfer_in.to_numpy()==1).all()
    assert (counts.transfer_receipt.to_numpy()==received).all()
    assert (counts.transfer_out_complete.to_numpy()==received).all()

def test_ground_truth_is_separate_and_complete():
    gt=read("ground_truth")
    assert {"balance_mismatch","reservation_exceeds_available","fulfilled_from_blocked",
            "premature_transfer_count","overselling_attempt","expired_reservation"}.issubset(set(gt.issue_type))
    assert gt.fixture_only.all()

def test_event_history_ends_at_current_state():
    oe=read("order_events"); o=read("orders")
    re=read("reservation_events"); r=read("reservations")
    o_last=oe.sort_values("event_ts").groupby("order_id").tail(1).set_index("order_id").to_status
    r_last=re.sort_values("event_ts").groupby("reservation_id").tail(1).set_index("reservation_id").to_status
    assert all(o_last[x]==y for x,y in zip(o.order_id,o.status))
    assert all(r_last[x]==y for x,y in zip(r.reservation_id,r.status))



def test_ground_truth_dashboard_schema_has_description():
    from app.data_utils import normalize_ground_truth
    gt = read("ground_truth")
    normalized = normalize_ground_truth(gt)
    assert "description" in normalized.columns
    assert normalized["description"].notna().all()
    assert normalized.loc[0, "description"] == gt.loc[0, "observed_condition"]


def test_ground_truth_normalizer_handles_missing_optional_fields():
    from app.data_utils import normalize_ground_truth
    source = pd.DataFrame([{
        "issue_type": "balance_mismatch",
        "entity_id": "BAL-001",
        "observed_condition": "reported quantity differs",
    }])
    normalized = normalize_ground_truth(source)
    assert normalized.loc[0, "description"] == "reported quantity differs"
    assert normalized.loc[0, "expected_action"] == "Not provided"
    assert normalized.loc[0, "severity"] == "Not provided"
