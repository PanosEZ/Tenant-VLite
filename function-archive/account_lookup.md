# Tool: Account Lookup
**Function Name:** `account_lookup`

## Scope
Handles all single-entity and flat-filtered queries. This function is for direct retrieval of user profiles based on specific identifiers or categorical fields. It does not perform any tree-based or hierarchical reasoning.

## How it Works
Queries the database for direct document matches. To protect the system from memory overloads, you MUST use `return_fields` to request only the specific data needed to answer the user's question.

## Arguments
* `return_fields` (list of strings, optional): Specify EXACTLY which fields to return (e.g., `["username", "id"]`). If the user only asks for names, only request names.
* `limit` (integer, optional): Maximum number of records to return. Default is 50.
* `id` (string, optional): Exact `id` (e.g., "1", "7").
* `username` (string, optional): Exact username (e.g., "admin", "agent1"). (note: if the user is asking for the admin of the app, just see how many admins are there or if there is only one or few just respond accordingly)
* `email` (string, optional): Exact email address.
* `type` (string, optional): Enum [`ADMIN`, `CURRENCY_AGENT`, `AGENT`, `USER`].
* `status` (string, optional): Enum [`ACTIVE`, etc.].
* `currency` (string, optional): Enum [`EUR`, `TRY`, `USD`,`GBP`].
* `is_test_account` (boolean, optional): Filter for test accounts.
* `is_system_account` (boolean, optional): Filter for system accounts.
* **Any other document field** (optional): You may also filter by ANY field that exists in the database documents.

## Usage Guide for LLM
* **Trigger when:** The user asks to find specific accounts, check field values, or list accounts matching basic filters.
* **Example Queries:** 
  * "What is the email for account ID 10?" -> Request only `["email"]`.
  * "Can you tell me the name of each agent?" -> Request `type: AGENT`, and `return_fields: ["username", "id"]`.
* **Do NOT trigger when:** The user asks about downlines, parents, or aggregate counts.

## CRITICAL — Output Format
You MUST NOT answer the user's question yourself. You do NOT have access to any data.
Instead, output ONLY a single `<FUNCTION_CALL>` block containing the function name and arguments as valid JSON. 

You are strictly allowed to write ONLY ONE function call. The dev tool cannot execute many commands in one go.

Example:
<FUNCTION_CALL>
{"function": "account_lookup", "arguments": {"type": "AGENT", "return_fields": ["username", "id"], "limit": 10}}
</FUNCTION_CALL>

You are free to include any text with your thoughts and reasoning before writing the final <FUNCTION_CALL> block. Do NOT fabricate results.
--- END OF FILE account_lookup.md ---