"""Data schema compatibility helpers for the inventory dashboard."""

import pandas as pd

def normalize_ground_truth(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a display-safe ground-truth frame across supported CSV schemas.

    Older datasets call the anomaly explanation ``observed_condition`` while
    the dashboard historically expected ``description``. Keep both names so
    downstream display code and exports remain compatible.
    """
    frame = frame.copy()
    aliases = {
        "description": ("observed_condition", "details", "condition"),
        "expected_action": ("recommended_action", "action"),
        "severity": ("priority",),
        "issue_type": ("anomaly_type", "exception_type"),
        "entity_type": ("entity",),
        "entity_id": ("record_id", "reference_id"),
    }
    for target, candidates in aliases.items():
        if target not in frame.columns:
            source = next((name for name in candidates if name in frame.columns), None)
            frame[target] = frame[source] if source else "Not provided"
    for column in ("scenario_id", "issue_type", "entity_type", "entity_id",
                   "description", "expected_action", "severity"):
        if column not in frame.columns:
            frame[column] = "Not provided"
        frame[column] = frame[column].fillna("Not provided").astype(str)
    return frame


