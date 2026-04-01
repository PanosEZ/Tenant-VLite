# Tool: Compliance Verification
**Function Name:** `check_compliance`

## Scope
Handles account verification and regulatory-style checks. Focused on compliance state — email verification, phone verification, terms acceptance, and identifying accounts missing required confirmations.

## How it Works
Scans accounts for missing or incomplete compliance fields and returns which accounts fail the specified check.

## Arguments
* `check_type` (string, required): The specific compliance check to run. Enum:
  * `email_unverified`: Finds accounts where `email_verified` is false.
  * `phone_unverified`: Finds accounts where `phone_verified` is false.
  * `terms_not_accepted`: Finds accounts with no `terms_accepted_version`.
  * `full_audit`: Runs all checks and returns a combined report.
* `scope_filter` (object, optional): Narrow the check to a subset of accounts. Only **direct fields** on the user record are matched (same key → same value). Example: `{"type": "AGENT"}` to only check agents. There is no `user_ids` filter; use `limit` on a broad query instead.
* `limit` (integer, optional): Maximum number of failing accounts returned **per check** (or per bucket in `full_audit`). Omit for no cap (full list — can be very large). Use this to stay within tool output size limits when scanning many accounts (e.g. `{"type": "AGENT"}`).
* `random` (boolean, optional, default `false`): If `true`, the `limit` failures are chosen uniformly at random from all failures in scope. If `false`, the first `limit` failures in scan order are returned (faster). **`limit` is required when `random` is `true`.**
* `email` (boolean, optional, default `false`): If `true`, each returned account entry includes the user’s `email` field (with `id`, `username`, and `type`). Use this when the user needs email in the same response as compliance results, so you do not need a separate `account_lookup` per row.

## Response notes
* When `limit` is set, the response includes `total_failed`: the full count of failures in scope, even if only `limit` rows are listed. A `message` is added when `total_failed` exceeds `limit`.
* For `full_audit` with `limit`, each of `email_unverified`, `phone_unverified`, and `terms_not_accepted` is capped separately; `report_totals` gives the full counts per bucket.

## Usage Guide for LLM
* **Trigger when:** The user asks about verification status, compliance gaps, or unverified accounts.
* **Example Queries:**
  * "Are there any agents who haven't verified their email?"
  * "Which accounts haven't accepted the terms of service?"
  * "Run a full compliance audit on all USER accounts."
* **Do NOT trigger when:** The user asks about hierarchy structure, counts, or data retrieval.

## CRITICAL — Output Format
You MUST NOT answer the user's question yourself. You do NOT have access to any data.
Instead, output ONLY a single `<FUNCTION_CALL>` block containing the function name and arguments as valid JSON. Example:

<FUNCTION_CALL>
{"function": "check_compliance", "arguments": {"check_type": "email_unverified", "scope_filter": {"type": "AGENT"}}}
</FUNCTION_CALL>

* **Sample up to N non-compliant agents (stable order):** Prefer one call with `limit` instead of looping via `account_lookup`. Example:

<FUNCTION_CALL>
{"function": "check_compliance", "arguments": {"check_type": "terms_not_accepted", "scope_filter": {"type": "AGENT"}, "limit": 5}}
</FUNCTION_CALL>

* **Sample N random non-compliant agents in scope:** Use `random: true` with `limit` (requires scanning all failures in scope, then sampling).

<FUNCTION_CALL>
{"function": "check_compliance", "arguments": {"check_type": "terms_not_accepted", "scope_filter": {"type": "AGENT"}, "limit": 5, "random": true}}
</FUNCTION_CALL>

* **ID, username, and email in one call:** Set `email: true` (e.g. random sample of users with unverified phone including addresses):

<FUNCTION_CALL>
{"function": "check_compliance", "arguments": {"check_type": "phone_unverified", "limit": 5, "random": true, "email": true}}
</FUNCTION_CALL>

You are free to include any text with your thoughts and reasoning before writing the final <FUNCTION_CALL> block. Do NOT fabricate results.

you are strictly allowed to write only one function call, the dev tool can not execute many commands in one go.
--- END OF FILE compliance_verification.md ---