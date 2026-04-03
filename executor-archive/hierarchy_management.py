import sys
import json
import os
from pathlib import Path

DB_FILE = str(Path(__file__).resolve().parent.parent / "database" / "tenant_dev.users.json")


def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def resolve_target(db, target_id=None, target_username=None):
    if target_id:
        return next((r for r in db if r.get("id") == target_id), None)
    if target_username:
        return next((r for r in db if isinstance(r.get("username"), str) and r["username"].lower() == target_username.lower()), None)
    return None

def traverse_hierarchy(args):
    target_id = args.get("target_id")
    target_username = args.get("target_username")
    direction = args.get("direction")
    max_depth = args.get("max_depth")
    limit = args.get("limit", 50)
    return_fields = args.get("return_fields")

    if (not target_id and not target_username) or not direction:
        return {"status": "error", "message": "Missing required arguments: ('target_id' or 'target_username') and 'direction'"}

    db = load_db()
    
    target_node = resolve_target(db, target_id, target_username)
    if not target_node:
        identifier = target_id or target_username
        return {"status": "error", "message": f"Account '{identifier}' not found."}

    target_id = target_node.get("id")

    results = []

    # 2. Process based on direction
    if direction == "parent":
        parent_id = target_node.get("parent_id")
        if parent_id:
            parent_node = next((r for r in db if r.get("id") == parent_id), None)
            if parent_node: results.append(parent_node)

    elif direction == "children":
        results = [r for r in db if r.get("parent_id") == target_id]

    elif direction == "ancestors":
        ancestor_ids = target_node.get("ancestors", [])
        results = [r for r in db if r.get("id") in ancestor_ids]
        # Sort ancestors by depth (top level to immediate parent)
        results.sort(key=lambda x: x.get("depth", 0))

    elif direction == "descendants":
        target_depth = target_node.get("depth", 0)
        for record in db:
            if target_id in record.get("ancestors", []):
                # Apply max_depth constraint if provided
                if max_depth is not None:
                    if record.get("depth", 0) > (target_depth + max_depth):
                        continue
                results.append(record)

    else:
        return {"status": "error", "message": f"Invalid direction: {direction}"}

    total_matches = len(results)
    results = results[:limit]

    if return_fields:
        results = [{k: r.get(k) for k in return_fields if k in r} for r in results]

    response = {
        "status": "success", 
        "target": target_node.get("username", target_id),
        "direction": direction,
        "count": len(results),
        "total_matches": total_matches,
        "data": results
    }

    if total_matches > limit:
        response["message"] = f"Found {total_matches} records, but limited output to {limit} to prevent system overload. Ask user to narrow search."

    return response

if __name__ == "__main__":
    try:
        args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
        result = traverse_hierarchy(args)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))