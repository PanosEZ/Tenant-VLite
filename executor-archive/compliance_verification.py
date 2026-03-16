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
    return {
        "id": record.get("id"),
        "username": record.get("username"),
        "type": record.get("type")
    }

def check_compliance(args):
    check_type = args.get("check_type")
    scope_filter = args.get("scope_filter", {})
    
    if not check_type:
        return {"status": "error", "message": "Missing required argument 'check_type'"}

    db = load_db()
    results = {"email_unverified": [], "phone_unverified": [], "terms_not_accepted": []}

    for record in db:
        # Apply scope filtering first (e.g. {"type": "AGENT"})
        in_scope = True
        for k, v in scope_filter.items():
            if record.get(k) != v:
                in_scope = False
                break
        if not in_scope:
            continue

        # Check conditions
        if check_type in ["email_unverified", "full_audit"] and not record.get("email_verified", False):
            results["email_unverified"].append(extract_summary(record))
            
        if check_type in ["phone_unverified", "full_audit"] and not record.get("phone_verified", False):
            results["phone_unverified"].append(extract_summary(record))
            
        if check_type in ["terms_not_accepted", "full_audit"]:
            # Terms are considered unaccepted if the string is empty or missing entirely
            if not record.get("terms_accepted_version", "").strip():
                results["terms_not_accepted"].append(extract_summary(record))

    if check_type != "full_audit":
        return {"status": "success", "check_type": check_type, "failed_accounts": results[check_type]}
    
    return {"status": "success", "check_type": "full_audit", "report": results}

if __name__ == "__main__":
    try:
        args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
        result = check_compliance(args)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))