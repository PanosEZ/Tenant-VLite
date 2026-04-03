import sys
import json
import os
import random
from pathlib import Path

DB_FILE = str(Path(__file__).resolve().parent.parent / "database" / "tenant_dev.users.json")


def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def extract_summary(record, include_email=False):
    out = {
        "id": record.get("id"),
        "username": record.get("username"),
        "type": record.get("type"),
    }
    if include_email:
        out["email"] = record.get("email")
    return out

def _in_scope(record, scope_filter):
    for k, v in scope_filter.items():
        if record.get(k) != v:
            return False
    return True

def _finalize_list(items, limit, random_sample):
    """Trim or sample `items`; returns (output, total_before_trim)."""
    total = len(items)
    if limit is None:
        return items, total
    if random_sample:
        k = min(limit, total)
        out = random.sample(items, k) if k else []
        return out, total
    return items[:limit], total

def check_compliance(args):
    check_type = args.get("check_type")
    scope_filter = args.get("scope_filter", {})
    limit = args.get("limit")
    random_sample = bool(args.get("random", False))
    include_email = bool(args.get("email", False))

    if not check_type:
        return {"status": "error", "message": "Missing required argument 'check_type'"}

    if limit is not None:
        if not isinstance(limit, int) or limit < 0:
            return {"status": "error", "message": "Argument 'limit' must be a non-negative integer"}

    if random_sample and limit is None:
        return {"status": "error", "message": "Argument 'limit' is required when 'random' is true"}

    db = load_db()

    def maybe_message(total_failed):
        if limit is not None and total_failed > limit:
            return (
                f"Found {total_failed} failing accounts, but limited output to {limit} "
                "to prevent system overload. Narrow scope_filter or paginate if needed."
            )
        return None

    if check_type == "full_audit":
        if limit is not None and random_sample:
            report = {"email_unverified": [], "phone_unverified": [], "terms_not_accepted": []}
            for record in db:
                if not _in_scope(record, scope_filter):
                    continue
                if not record.get("email_verified", False):
                    report["email_unverified"].append(
                        extract_summary(record, include_email)
                    )
                if not record.get("phone_verified", False):
                    report["phone_unverified"].append(
                        extract_summary(record, include_email)
                    )
                if not record.get("terms_accepted_version", "").strip():
                    report["terms_not_accepted"].append(
                        extract_summary(record, include_email)
                    )
            totals = {k: len(v) for k, v in report.items()}
            out_report = {}
            messages = []
            for key, items in report.items():
                trimmed, tf = _finalize_list(items, limit, random_sample)
                out_report[key] = trimmed
                if limit is not None:
                    msg = maybe_message(tf)
                    if msg:
                        messages.append(f"{key}: {msg}")
            resp = {"status": "success", "check_type": "full_audit", "report": out_report}
            if limit is not None:
                resp["report_totals"] = totals
            if messages:
                resp["message"] = " ".join(messages)
            return resp

        # full_audit: unlimited, or limited first-N (single pass)
        report = {"email_unverified": [], "phone_unverified": [], "terms_not_accepted": []}
        totals = {"email_unverified": 0, "phone_unverified": 0, "terms_not_accepted": 0}
        for record in db:
            if not _in_scope(record, scope_filter):
                continue
            if not record.get("email_verified", False):
                totals["email_unverified"] += 1
                if limit is None or len(report["email_unverified"]) < limit:
                    report["email_unverified"].append(
                        extract_summary(record, include_email)
                    )
            if not record.get("phone_verified", False):
                totals["phone_unverified"] += 1
                if limit is None or len(report["phone_unverified"]) < limit:
                    report["phone_unverified"].append(
                        extract_summary(record, include_email)
                    )
            if not record.get("terms_accepted_version", "").strip():
                totals["terms_not_accepted"] += 1
                if limit is None or len(report["terms_not_accepted"]) < limit:
                    report["terms_not_accepted"].append(
                        extract_summary(record, include_email)
                    )
        resp = {"status": "success", "check_type": "full_audit", "report": report}
        if limit is not None:
            resp["report_totals"] = totals
            msgs = []
            for key in totals:
                m = maybe_message(totals[key])
                if m:
                    msgs.append(f"{key}: {m}")
            if msgs:
                resp["message"] = " ".join(msgs)
        return resp

    # Single check types
    key_map = {
        "email_unverified": lambda r: not r.get("email_verified", False),
        "phone_unverified": lambda r: not r.get("phone_verified", False),
        "terms_not_accepted": lambda r: not r.get("terms_accepted_version", "").strip(),
    }
    if check_type not in key_map:
        return {"status": "error", "message": f"Unknown check_type: {check_type}"}
    fails_predicate = key_map[check_type]

    if limit is not None and not random_sample:
        failed_accounts = []
        total_failed = 0
        for record in db:
            if not _in_scope(record, scope_filter):
                continue
            if fails_predicate(record):
                total_failed += 1
                if len(failed_accounts) < limit:
                    failed_accounts.append(
                        extract_summary(record, include_email)
                    )
    else:
        failed_accounts = []
        for record in db:
            if not _in_scope(record, scope_filter):
                continue
            if fails_predicate(record):
                failed_accounts.append(
                    extract_summary(record, include_email)
                )
        total_failed = len(failed_accounts)
        if limit is not None:
            failed_accounts, total_failed = _finalize_list(
                failed_accounts, limit, random_sample
            )

    response = {
        "status": "success",
        "check_type": check_type,
        "failed_accounts": failed_accounts,
    }
    if limit is not None:
        response["total_failed"] = total_failed
    msg = maybe_message(total_failed)
    if msg:
        response["message"] = msg
    return response

if __name__ == "__main__":
    try:
        args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
        result = check_compliance(args)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
