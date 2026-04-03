import sys
import json
import os
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aggregation_reporting import extract_val, evaluate_condition

DB_FILE = str(Path(__file__).resolve().parent.parent / "database" / "tenant_dev.users.json")

_DAY_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UNSUPPORTED_META_KEYS = frozenset({"sort", "sort_by", "order_by"})
_REGISTRATION_DAY_ALIASES = ("registration_day", "registration_date", "registered_at")
_LAST_LOGIN_DAY_KEY = "last_login_day"
_DISCOVERY_RETURN_FIELDS = [
    "id",
    "username",
    "email",
    "type",
    "status",
    "created_at",
    "updated_at",
    "last_login_at",
    "last_login_ip",
    "last_login_device",
]

def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r") as f:
        return json.load(f)


def _next_utc_day_start_iso(day_yyyy_mm_dd: str) -> str:
    d = datetime.strptime(day_yyyy_mm_dd, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    nxt = d + timedelta(days=1)
    return nxt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _is_calendar_date_string(s: str) -> bool:
    if not isinstance(s, str) or not _DAY_ONLY.match(s):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _coerce_field_day_range(args: dict, field: str) -> None:
    """Turn field: 'YYYY-MM-DD' into a UTC day range (BSON dates are compared as ISO strings)."""
    if field not in args:
        return
    val = args[field]
    if isinstance(val, str) and _is_calendar_date_string(val):
        args[field] = {
            "$gte": f"{val}T00:00:00.000Z",
            "$lt": _next_utc_day_start_iso(val),
        }


def _consume_registration_day_aliases(args: dict):
    """registration_day, registration_date, and registered_at are the same (YYYY-MM-DD, UTC)."""
    found = {}
    for key in _REGISTRATION_DAY_ALIASES:
        if key in args:
            found[key] = args.pop(key)
    if not found:
        return None, None
    values = list(found.values())
    if len(set(values)) > 1:
        return None, (
            "registration_day, registration_date, and registered_at must agree; pass only one "
            f"(got {found})."
        )
    return values[0], None


def _consume_last_login_day(args: dict):
    """last_login_day: YYYY-MM-DD UTC -> last_login_at range. Mutates args."""
    if _LAST_LOGIN_DAY_KEY not in args:
        return None, None
    return args.pop(_LAST_LOGIN_DAY_KEY), None


def _expand_return_fields_star(return_fields):
    if not isinstance(return_fields, list) or "*" not in return_fields:
        return return_fields
    rest = [f for f in return_fields if f != "*"]
    merged = rest + _DISCOVERY_RETURN_FIELDS if rest else list(_DISCOVERY_RETURN_FIELDS)
    out = []
    seen = set()
    for f in merged:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _record_matches_filter(record, filter_key, filter_value):
    record_value = record.get(filter_key)
    r_val = extract_val(record_value)

    if isinstance(filter_value, dict) and any(
        isinstance(k, str) and k.startswith("$") for k in filter_value
    ):
        try:
            return evaluate_condition(r_val, filter_value)
        except TypeError:
            return False

    if isinstance(r_val, str) and isinstance(filter_value, str):
        return r_val.lower() == filter_value.lower()
    return r_val == filter_value


def _build_pipe_table(rows):
    lines = ["id | username | email |"]
    for row in rows:
        rid = row.get("id", "")
        user = str(row.get("username", "")).replace("|", " ")
        em = str(row.get("email", "")).replace("|", " ")
        lines.append(f"{rid} | {user} | {em} |")
    return "\n".join(lines)


def account_lookup(args):
    args = dict(args)
    db = load_db()
    results = []

    ignored_meta = sorted(k for k in list(args.keys()) if k in _UNSUPPORTED_META_KEYS)
    for k in ignored_meta:
        args.pop(k, None)

    if "limit" in args:
        limit = args.pop("limit")
    else:
        limit = 50
    return_fields = args.pop("return_fields", [])
    random_sample = bool(args.pop("random", False))
    output_format = args.pop("output_format", "json")

    return_fields = _expand_return_fields_star(return_fields)

    registration_day, reg_err = _consume_registration_day_aliases(args)
    if reg_err:
        return {"status": "error", "message": reg_err}

    if registration_day:
        if "created_at" in args:
            return {
                "status": "error",
                "message": "Use registration_day (registration_date / registered_at) or created_at, not both.",
            }
        args["created_at"] = {
            "$gte": f"{registration_day}T00:00:00.000Z",
            "$lt": _next_utc_day_start_iso(registration_day),
        }
    else:
        _coerce_field_day_range(args, "created_at")

    last_login_day, _ = _consume_last_login_day(args)
    if last_login_day:
        if "last_login_at" in args:
            return {
                "status": "error",
                "message": "Use last_login_day or last_login_at, not both.",
            }
        if not _is_calendar_date_string(last_login_day):
            return {
                "status": "error",
                "message": "last_login_day must be a valid UTC calendar date YYYY-MM-DD.",
            }
        args["last_login_at"] = {
            "$gte": f"{last_login_day}T00:00:00.000Z",
            "$lt": _next_utc_day_start_iso(last_login_day),
        }
    else:
        _coerce_field_day_range(args, "last_login_at")

    if output_format == "pipe" and not return_fields:
        return_fields = ["id", "username", "email"]

    for record in db:
        match = True
        for key, value in args.items():
            if not _record_matches_filter(record, key, value):
                match = False
                break
        if match:
            results.append(record)

    total_matches = len(results)

    if random_sample:
        if limit is None:
            results = random.sample(results, len(results)) if results else []
        else:
            k = min(limit, len(results))
            results = random.sample(results, k) if k else []
    elif limit is not None:
        results = results[:limit]

    if return_fields and isinstance(return_fields, list):
        projected_results = []
        for res in results:
            projected = {k: res.get(k) for k in return_fields if k in res}
            projected_results.append(projected)
        results = projected_results

    response = {
        "status": "success",
        "count": len(results),
        "total_matches": total_matches,
        "data": results,
    }

    if ignored_meta:
        response["ignored_unsupported_arguments"] = ignored_meta
        response["hint"] = (
            "account_lookup does not support sort/order. Registration time is filtered via "
            "`created_at`; last activity via `last_login_at`, `last_login_ip`, `last_login_device`. "
            "For one UTC calendar day on registration use registration_day / registration_date / "
            "registered_at, or created_at: \"YYYY-MM-DD\", or $gte/$lt. For one UTC day on last login "
            "use last_login_day, or last_login_at: \"YYYY-MM-DD\", or $gte/$lt. return_fields: [\"*\"] "
            "expands to a discovery set including created_at and login telemetry fields."
        )

    if output_format == "pipe":
        response["pipe_table"] = _build_pipe_table(results)

    if limit is not None and total_matches > limit:
        response["message"] = (
            f"Found {total_matches} records, but limited output to {limit} to prevent "
            "system overload. Pass null for limit only when the user needs every row."
        )

    return response


if __name__ == "__main__":
    try:
        cli_args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
        result = account_lookup(cli_args)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
