# Tool: Account Lookup
**Function Name:** `account_lookup`

## Scope
Handles all single-entity and flat-filtered queries. This function is for direct retrieval of user profiles based on specific identifiers or categorical fields. It does not perform any tree-based or hierarchical reasoning.

## How it Works
Queries the database for direct document matches. To protect the system from memory overloads, you MUST use `return_fields` to request only the specific data needed to answer the user's question.

## Arguments
* `return_fields` (list of strings, optional): Field names to return, or include **`"*"`** for the discovery preset: `id`, `username`, `email`, `type`, `status`, `created_at`, `updated_at`, `last_login_at`, `last_login_ip`, `last_login_device`. When `output_format` is `pipe`, if omitted or empty, defaults to `["id", "username", "email"]`.
* `limit` (integer or null, optional): Maximum number of records to return. Default is 50. Use `null` only when the user needs every matching row (e.g. all accounts registered on one day); warn them if the result could be huge.
* `output_format` (string, optional): `json` (default) or `pipe`. With `pipe`, the tool adds `pipe_table`: plain text lines `id | username | email |` (header plus one row per record).
* `registration_day` (string, optional): UTC calendar day `YYYY-MM-DD`; expands to a range on the document field **`created_at`**. Do not pass `created_at` in the same call.
* `registration_date` (string, optional): Same as `registration_day` (alias only; not a stored column name).
* `registered_at` (string, optional): Same as `registration_day` (alias only; not a stored column name).
* `last_login_day` (string, optional): UTC calendar day `YYYY-MM-DD`; expands to a range on the document field **`last_login_at`**. Do not pass `last_login_at` in the same call. You may also filter or return `last_login_ip` and `last_login_device` like any other document field.
* `created_at` (optional): Filter registration time. For one UTC day you can pass a plain `"YYYY-MM-DD"` string (expanded to a range), a `$gte` / `$lt` object, or use `registration_day` / `registration_date` / `registered_at` instead of this key.
* `last_login_at` (optional): Filter last login time. For one UTC day use a plain `"YYYY-MM-DD"` string, a `$gte` / `$lt` object, or `last_login_day` instead of this key.
* `random` (boolean, optional): If `true`, draw up to `limit` records uniformly at random from all matches (without replacement). If `false` or omitted, results keep a stable order (first matches in storage order). Use for requests like "a random agent" or "10 random users". If `limit` is `null` and `random` is true, all matches are returned in random order.
* `id` (string, optional): Exact `id` (e.g., "1", "7").
* `username` (string, optional): Exact username (e.g., "admin", "agent1"). (note: if the user is asking for the admin of the app, just see how many admins are there or if there is only one or few just respond accordingly)
* `email` (string, optional): Exact email address.
* `type` (string, optional): Enum [`ADMIN`, `CURRENCY_AGENT`, `AGENT`, `USER`].
* `status` (string, optional): Enum [`ACTIVE`, etc.].
* `currency` (string, optional): Enum [`EUR`, `TRY`, `USD`,`GBP`].
* `is_test_account` (boolean, optional): Filter for test accounts.
* `is_system_account` (boolean, optional): Filter for system accounts.
* **Any other document field** (optional): Any other filter key must match a real column on the stored document and must not duplicate a dedicated parameter above. Do not invent extra “registration” or “login” field names.

## Usage Guide for LLM
* **Trigger when:** The user asks to find specific accounts, check field values, or list accounts matching basic filters.
* **Example Queries:** 
  * "What is the email for account ID 10?" -> Request only `["email"]`.
  * "Can you tell me the name of each agent?" -> Request `type: AGENT`, and `return_fields: ["username", "id"]`.
  * "Give me 5 random agents" -> `type: AGENT`, `limit: 5`, `random: true`, plus needed `return_fields`.
  * "List all users who registered on 23 January 2026" -> `type: USER`, `registration_day: "2026-01-23"`, `limit: null`, `output_format: "pipe"`. Read `pipe_table` from the tool output and present it to the user (UTC calendar day).
  * "Who logged in on 1 April 2026?" -> `last_login_day: "2026-04-01"` and `return_fields` for identifiers plus `last_login_at` / `last_login_ip` as needed.
* **Do NOT trigger when:** The user asks about downlines, parents, or aggregate counts.

## CRITICAL — Output Format
You MUST NOT answer the user's question yourself. You do NOT have access to any data.
Instead, output ONLY a single `<FUNCTION_CALL>` block containing the function name and arguments as valid JSON. 

You are strictly allowed to write ONLY ONE function call. The dev tool cannot execute many commands in one go.

Example:
<FUNCTION_CALL>
{"function": "account_lookup", "arguments": {"type": "AGENT", "return_fields": ["username", "id"], "limit": 10}}
</FUNCTION_CALL>

For a random subset of matches, include `"random": true` in `arguments` (e.g. with `"limit": 5`).

<FUNCTION_CALL>
{"function": "account_lookup", "arguments": {"type": "USER", "registration_day": "2026-01-23", "limit": null, "output_format": "pipe"}}
</FUNCTION_CALL>

You are free to include any text with your thoughts and reasoning before writing the final <FUNCTION_CALL> block. Do NOT fabricate results.
--- END OF FILE account_lookup.md ---