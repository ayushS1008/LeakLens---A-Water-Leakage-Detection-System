"""Ticket lifecycle and a conservative comparison of equal follow-up windows."""
from datetime import datetime, timezone
import hashlib
import pandas as pd


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def build_ticket(analysis, incident, description):
    identity = f"{analysis['analysis_id']}:{incident['incident_id']}"
    now = utc_now()
    return {
        "ticket_id": "ticket-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
        "analysis_id": analysis["analysis_id"],
        "household_id": analysis["household_id"],
        "incident_id": incident["incident_id"],
        "first_alert_at": incident["first_alert_at"],
        "last_alert_at": incident["last_alert_at"],
        "description": description,
        "status": "open",
        "created_at": now,
        "updated_at": now,
        "repaired_at": None,
        "verification": None,
        "finding": None,
        "explanation": incident.get("explanation"),
        "revision": 0,
        "history": [{"at": now, "action": "created", "note": description}],
    }


def change_ticket(ticket, status, repaired_at, note):
    if status == "investigating" and ticket["status"] not in ["open", "investigating"]:
        raise ValueError("A reported repair cannot be moved back to investigating.")
    if status == "repaired":
        if repaired_at is None or repaired_at.tzinfo is None or repaired_at.utcoffset() is None:
            raise ValueError("Supply a repair time with an explicit timezone.")
        repaired_at = repaired_at.astimezone(timezone.utc)
        if repaired_at.minute % 15 or repaired_at.second or repaired_at.microsecond:
            raise ValueError("Repair time must be on a 15-minute boundary.")
        if repaired_at < datetime.fromisoformat(ticket["first_alert_at"]):
            raise ValueError("Repair time must be at or after the first alert.")
        if repaired_at > datetime.now(timezone.utc):
            raise ValueError("Repair time cannot be in the future.")
        ticket["repaired_at"] = repaired_at.isoformat()
        ticket["verification"] = None
    ticket["status"] = status
    ticket["revision"] += 1
    ticket["updated_at"] = utc_now()
    ticket["history"] = (ticket["history"] + [{"at": ticket["updated_at"], "action": status, "note": note}])[-50:]
    return ticket


def record_finding(ticket, outcome, note):
    if outcome not in ['confirmed_leak', 'normal_activity', 'undetermined']:
        raise ValueError('Choose a supported investigation outcome.')
    if not note.strip():
        raise ValueError('Add a note describing the evidence for this finding.')
    now = utc_now()
    ticket['finding'] = {'outcome': outcome, 'note': note.strip(), 'recorded_at': now, 'source': 'user_reported'}
    ticket['revision'] += 1
    ticket['updated_at'] = now
    ticket['history'] = (ticket['history'] + [{'at': now, 'action': 'finding_recorded', 'note': f"{outcome}: {note.strip()}"}])[-50:]
    return ticket


def compare_repair(ticket, source, followup):
    if ticket["status"] != "repaired" or not ticket["repaired_at"]:
        raise ValueError("Record the repair and its time before checking follow-up readings.")
    if source["household_id"] == "unspecified" or followup["household_id"] == "unspecified":
        raise ValueError("Both uploads need an explicit household_id for a follow-up comparison.")
    if source["household_id"] != followup["household_id"]:
        raise ValueError("Follow-up data must belong to the same household.")
    if source["model_fingerprint"] != followup["model_fingerprint"]:
        raise ValueError("Use the same model and settings for the before/after comparison.")
    repair = pd.Timestamp(ticket["repaired_at"])
    before_grid = pd.date_range(repair - pd.Timedelta(hours=24) + pd.Timedelta(minutes=15), repair, freq="15min")
    after_grid = pd.date_range(repair + pd.Timedelta(minutes=15), repair + pd.Timedelta(hours=24), freq="15min")

    def window(analysis, grid):
        frame = pd.DataFrame(analysis["readings"])
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frame = frame.set_index("timestamp").reindex(grid)
        known = frame["litres_used"].notna()
        scored = frame["anomaly_score"].notna()
        complete = bool((known & scored).all())
        return {"expected_intervals": 96, "valid_intervals": int(known.sum()), "scored_intervals": int(scored.sum()), "recorded_litres": float(frame["litres_used"].sum()), "alert_intervals": int(frame["is_alert"].eq(True).sum()), "complete": complete}

    before = window(source, before_grid)
    after = window(followup, after_grid)
    if not before["complete"] or not after["complete"]:
        outcome = "insufficient_data"
        message = "Need 24 hours of valid, scored readings on both sides of the repair. Include one hour of preceding context in each upload."
    elif after["alert_intervals"] > 0:
        outcome = "alerts_persist"
        message = "Alerts remain in the 24 hours after the reported repair. Investigate further."
    elif before["alert_intervals"] == 0:
        outcome = "inconclusive"
        message = "There were no alerts in the comparison window before repair, so disappearance cannot be demonstrated."
    else:
        outcome = "improved"
        message = "Alerts were present before the reported repair and absent in the following 24 hours. This indicates improvement in the readings, not proof of a repaired leak."
    change = None
    if before["complete"] and after["complete"] and before["recorded_litres"] > 0:
        change = round(100 * (after["recorded_litres"] - before["recorded_litres"]) / before["recorded_litres"], 1)
    return {"outcome": outcome, "message": message, "checked_at": utc_now(), "window_hours": 24, "repaired_at": ticket["repaired_at"], "followup_analysis_id": followup["analysis_id"], "before": before, "after": after, "consumption_change_percent": change, "limitation": "Occupancy and ordinary usage can change consumption. No measured water-saving claim is made."}
