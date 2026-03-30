import sys
import json
import os

DB_FILE = "database/tenant_dev.users.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def account_lookup(args):
    db = load_db()
    results = []

    # 1. Extract special control arguments BEFORE filtering the database
    # Default limit is 50 to prevent catastrophic token overflow
    limit = args.pop("limit", 50) 
    return_fields = args.pop("return_fields", [])

    # 2. Filter the database based on the remaining args
    for record in db:
        match = True
        for key, value in args.items():
            record_value = record.get(key)
            
            # Case-insensitive match if both are strings
            if isinstance(record_value, str) and isinstance(value, str):
                if record_value.lower() != value.lower():
                    match = False
                    break
            # Otherwise, exact match
            elif record_value != value:
                match = False
                break
        
        if match:
            results.append(record)

    total_matches = len(results)

    # 3. Apply the limit (Pagination)
    results = results[:limit]

    # 4. Apply the projection (Return Fields)
    if return_fields and isinstance(return_fields, list):
        projected_results = []
        for res in results:
            # Only keep the keys the LLM explicitly asked for
            projected = {k: res.get(k) for k in return_fields if k in res}
            projected_results.append(projected)
        results = projected_results

    # 5. Format the final output
    response = {
        "status": "success", 
        "count": len(results), 
        "total_matches": total_matches,
        "data": results
    }

    # Add a warning message if we hit the limit, so the LLM knows there is more data
    if total_matches > limit:
        response["message"] = f"Found {total_matches} records, but limited output to {limit} to prevent system overload. Ask user to narrow search."

    return response

if __name__ == "__main__":
    try:
        args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
        result = account_lookup(args)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
