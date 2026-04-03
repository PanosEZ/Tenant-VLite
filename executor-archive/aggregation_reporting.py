import sys
import json
import os
from collections import defaultdict
from pathlib import Path

DB_FILE = str(Path(__file__).resolve().parent.parent / "database" / "tenant_dev.users.json")


def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r") as f:
        return json.load(f)

def extract_val(val):
    if isinstance(val, dict) and "$date" in val:
        return val["$date"]
    return val


def unwrap_filter_scalar(val):
    """Match Mongo extended JSON date literals used inside filter values."""
    if isinstance(val, dict) and "$date" in val:
        return val["$date"]
    return val


def evaluate_condition(record_val, condition):
    if isinstance(condition, dict) and len(condition) == 1 and "$date" in condition:
        return evaluate_condition(record_val, condition["$date"])

    # 1. Exact Match Logic (Case-insensitive for strings)
    if not isinstance(condition, dict):
        condition = unwrap_filter_scalar(condition)
        if isinstance(record_val, str) and isinstance(condition, str):
            return record_val.lower() == condition.lower()
        return record_val == condition

    # 2. Advanced Operators Logic
    for op, target_val in condition.items():
        target_val = unwrap_filter_scalar(target_val)
        if op == "$gte" and not (record_val >= target_val):
            return False
        if op == "$lte" and not (record_val <= target_val):
            return False
        if op == "$gt" and not (record_val > target_val):
            return False
        if op == "$lt" and not (record_val < target_val):
            return False

        if op == "$in":
            unwrapped_in = [unwrap_filter_scalar(v) for v in target_val]
            if isinstance(record_val, str):
                if not any(
                    isinstance(v, str) and record_val.lower() == v.lower() for v in unwrapped_in
                ):
                    return False
            else:
                if record_val not in unwrapped_in:
                    return False

        if op == "$ne":
            if isinstance(record_val, str) and isinstance(target_val, str):
                if record_val.lower() == target_val.lower():
                    return False
            else:
                if record_val == target_val:
                    return False

        if op == "$exists":
            exists = record_val is not None
            if exists != target_val:
                return False

    return True

def resolve_id_by_username(db, username):
    match = next((r for r in db if isinstance(r.get("username"), str) and r["username"].lower() == username.lower()), None)
    return match.get("id") if match else None

def generate_aggregation_report(args):
    metric = args.get("metric")
    group_by = args.get("group_by")
    filters = args.get("filters", {})
    target_ancestor_id = args.get("target_ancestor_id")
    target_ancestor_username = args.get("target_ancestor_username")
    target_parent_id = args.get("target_parent_id")
    target_parent_username = args.get("target_parent_username")

    if not metric:
        return {"status": "error", "message": "Missing required argument 'metric'"}

    db = load_db()

    if not target_ancestor_id and target_ancestor_username:
        target_ancestor_id = resolve_id_by_username(db, target_ancestor_username)
        if not target_ancestor_id:
            return {"status": "error", "message": f"Account with username '{target_ancestor_username}' not found."}

    if not target_parent_id and target_parent_username:
        target_parent_id = resolve_id_by_username(db, target_parent_username)
        if not target_parent_id:
            return {"status": "error", "message": f"Account with username '{target_parent_username}' not found."}

    filtered_data = []

    for record in db:
        if target_ancestor_id and target_ancestor_id not in record.get("ancestors", []):
            continue

        if target_parent_id and record.get("parent_id") != target_parent_id:
            continue
            
        passes_filters = True
        for f_key, f_val in filters.items():
            r_val = extract_val(record.get(f_key))
            if not evaluate_condition(r_val, f_val):
                passes_filters = False
                break
        
        if passes_filters:
            filtered_data.append(record)

    # Execute Aggregation
    if metric == "count":
        return {"status": "success", "metric": "count", "result": len(filtered_data)}

    elif metric == "distribution":
        if not group_by:
            return {"status": "error", "message": "Distribution metric requires 'group_by' field"}
        
        counts = defaultdict(int)
        for record in filtered_data:
            val = record.get(group_by, "UNKNOWN/NULL")
            counts[str(val)] += 1
        
        sorted_dist = dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))
        return {
            "status": "success", 
            "metric": "distribution", 
            "group_by": group_by,
            "total_records_processed": len(filtered_data),
            "result": sorted_dist
        }

if __name__ == "__main__":
    try:
        args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
        result = generate_aggregation_report(args)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))