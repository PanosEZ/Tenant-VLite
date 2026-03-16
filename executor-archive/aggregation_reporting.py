import sys
import json
import os
from collections import defaultdict

DB_FILE = "database/tenant_dev.users.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def extract_val(val):
    if isinstance(val, dict) and "$date" in val:
        return val["$date"]
    return val

def evaluate_condition(record_val, condition):
    # 1. Exact Match Logic (Case-insensitive for strings)
    if not isinstance(condition, dict):
        if isinstance(record_val, str) and isinstance(condition, str):
            return record_val.lower() == condition.lower()
        return record_val == condition 

    # 2. Advanced Operators Logic
    for op, target_val in condition.items():
        if op == "$gte" and not (record_val >= target_val): return False
        if op == "$lte" and not (record_val <= target_val): return False
        if op == "$gt" and not (record_val > target_val): return False
        if op == "$lt" and not (record_val < target_val): return False
        
        if op == "$in":
            if isinstance(record_val, str):
                # Case-insensitive $in check
                if not any(isinstance(v, str) and record_val.lower() == v.lower() for v in target_val):
                    return False
            else:
                if record_val not in target_val: return False
                
        if op == "$ne":
            if isinstance(record_val, str) and isinstance(target_val, str):
                if record_val.lower() == target_val.lower(): return False
            else:
                if record_val == target_val: return False
                
        if op == "$exists":
            exists = record_val is not None
            if exists != target_val: return False
            
    return True

def generate_aggregation_report(args):
    metric = args.get("metric")
    group_by = args.get("group_by")
    filters = args.get("filters", {})
    target_ancestor_id = args.get("target_ancestor_id")

    if not metric:
        return {"status": "error", "message": "Missing required argument 'metric'"}

    db = load_db()
    filtered_data = []

    # Apply pre-aggregation filters
    for record in db:
        if target_ancestor_id and target_ancestor_id not in record.get("ancestors", []):
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