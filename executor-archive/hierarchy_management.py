import sys
import json
import os

DB_FILE = "database/tenant_dev.users.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def traverse_hierarchy(args):
    target_id = args.get("target_id")
    direction = args.get("direction")
    max_depth = args.get("max_depth")

    if not target_id or not direction:
        return {"status": "error", "message": "Missing required arguments: 'target_id' and 'direction'"}

    db = load_db()
    
    # 1. Find the target node
    target_node = next((r for r in db if r.get("id") == target_id), None)
    if not target_node:
        return {"status": "error", "message": f"Account with ID {target_id} not found."}

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

    return {
        "status": "success", 
        "target": target_node.get("username", target_id),
        "direction": direction,
        "count": len(results),
        "data": results
    }

if __name__ == "__main__":
    try:
        args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
        result = traverse_hierarchy(args)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))