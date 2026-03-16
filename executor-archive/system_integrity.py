import sys
import json
import os

DB_FILE = "database/tenant_dev.users.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def extract_summary(record):
    return {"id": record.get("id"), "username": record.get("username"), "type": record.get("type")}

def check_system_integrity(args):
    routine = args.get("diagnostic_routine")
    if not routine:
        return {"status": "error", "message": "Missing required argument 'diagnostic_routine'"}

    db = load_db()
    all_ids = {r.get("id") for r in db if r.get("id")}
    issues_found = []

    for record in db:
        record_id = record.get("id")
        parent_id = record.get("parent_id")
        ancestors = record.get("ancestors", [])
        depth = record.get("depth", 0)

        if routine == "depth_mismatch":
            if len(ancestors) != depth:
                issue = extract_summary(record)
                issue["details"] = f"Depth is {depth} but ancestors array length is {len(ancestors)}"
                issues_found.append(issue)

        elif routine == "orphaned_nodes":
            # Parent is not null/empty AND the parent_id doesn't exist in the DB anymore
            if parent_id and parent_id not in all_ids:
                issue = extract_summary(record)
                issue["details"] = f"Points to non-existent parent_id: {parent_id}"
                issues_found.append(issue)

        elif routine == "missing_admin":
            # Everyone except the Admin (ID: 1) should have '1' in their ancestors
            if record_id != "1" and "1" not in ancestors:
                issue = extract_summary(record)
                issue["details"] = "Missing Admin ID '1' in ancestors tree"
                issues_found.append(issue)
                
        else:
            return {"status": "error", "message": f"Unknown diagnostic routine: {routine}"}

    return {
        "status": "success",
        "diagnostic_routine": routine,
        "issues_found_count": len(issues_found),
        "anomalies": issues_found
    }

if __name__ == "__main__":
    try:
        args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
        result = check_system_integrity(args)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))