# Tool: Account Lookup
**Function Name:** `account_lookup`

## If the user asked: “who registered a specific date?”
Use **one** call (UTC calendar day). **Do not** invent field names `registration_date` or `registered_at` **as database columns** — they are **only** supported as **filter aliases** below. The stored field is **`created_at`**.

## Scope
Handles all single-entity and flat-filtered queries. This function is for direct retrieval of user profiles based on specific identifiers or categorical fields. It does not perform any tree-based or hierarchical reasoning.

## How it Works
Queries the database for direct document matches. To protect the system from memory overloads, you MUST use `return_fields` to request only the specific data needed to answer the user's question.

## Arguments
* `return_fields` (list of strings, optional): Field names to return, or include **`"*"`** for the discovery preset (see above). When `output_format` is `pipe`, if omitted or empty, defaults to `["id", "username", "email"]`.
* `limit` (integer or null, optional): Maximum number of records to return. Default is 50. Use `null` only when the user needs every matching row (e.g. all accounts registered on one day); warn them if the result could be huge.
* `output_format` (string, optional): `json` (default) or `pipe`. With `pipe`, the tool adds `pipe_table`: plain text lines `id | username | email |` (header plus one row per record).
* `registration_day` (string, optional): Calendar day in UTC as `YYYY-MM-DD`. Expands to a `created_at` range for that whole day. Do not combine with a `created_at` argument.
* `registration_date` (string, optional): **Alias** of `registration_day`.
* `registered_at` (string, optional): **Alias** of `registration_day` (same `YYYY-MM-DD`). **Not** a document field — only this filter parameter.
* `random` (boolean, optional): If `true`, draw up to `limit` records uniformly at random from all matches (without replacement). If `false` or omitted, results keep a stable order (first matches in storage order). Use for requests like "a random agent" or "10 random users". If `limit` is `null` and `random` is true, all matches are returned in random order.
* `id` (string, optional): Exact `id` (e.g., "1", "7").
* `username` (string, optional): Exact username (e.g., "admin", "agent1"). (note: if the user is asking for the admin of the app, just see how many admins are there or if there is only one or few just respond accordingly)
* `email` (string, optional): Exact email address.
* `type` (string, optional): Enum [`ADMIN`, `CURRENCY_AGENT`, `AGENT`, `USER`].
* `status` (string, optional): Enum [`ACTIVE`, etc.].
* `currency` (string, optional): Enum [`EUR`, `TRY`, `USD`,`GBP`].
* `is_test_account` (boolean, optional): Filter for test accounts.
* `is_system_account` (boolean, optional): Filter for system accounts.
* **Any other document field** (optional): Filter by fields that exist on documents. For **one UTC calendar day** on `created_at`, use a **plain date string** `created_at: "2026-01-12"` (expanded to a range) or operator object. Prefer **`registration_day`**, **`registration_date`**, or **`registered_at`** when the user names a single day.

## Usage Guide for LLM
* **Trigger when:** The user asks to find specific accounts, check field values, or list accounts matching basic filters.
* **Example Queries:** 
  * "What is the email for account ID 10?" -> Request only `["email"]`.
  * "Can you tell me the name of each agent?" -> Request `type: AGENT`, and `return_fields: ["username", "id"]`.
  * "Give me 5 random agents" -> `type: AGENT`, `limit: 5`, `random: true`, plus needed `return_fields`.
  * "List all users who registered on 23 January 2026" -> `type: USER`, `registration_day: "2026-01-23"`, `limit: null`, `output_format: "pipe"`. Read `pipe_table` from the tool output and present it to the user (UTC calendar day).
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

Registration-day listing (pipe table):

<FUNCTION_CALL>
{"function": "account_lookup", "arguments": {"type": "USER", "registration_day": "2026-01-23", "limit": null, "output_format": "pipe"}}
</FUNCTION_CALL>

You are free to include any text with your thoughts and reasoning before writing the final <FUNCTION_CALL> block. Do NOT fabricate results.
--- END OF FILE account_lookup.md ---