# Tool: Hierarchy Management
**Function Name:** `traverse_hierarchy`

## Scope
Handles all tree-based logic and materialized path traversal. Focuses on relationships utilizing `parent_id`, the `ancestors` array, and `depth`.

## How it Works
Takes a focal account ID and traverses the tree in the specified direction. It fetches documents based on parent-child relationships rather than flat attributes.

## Arguments
* `target_id` (string, optional): The focal `id` for the query. Provide this if you know the account's numeric ID.
* `target_username` (string, optional): The focal `username` for the query. Provide this if the user refers to an account by name (e.g., "steven_065"). The tool resolves the username to an ID internally.
* **One of `target_id` or `target_username` is required.** If you have both, prefer `target_id`.
* `direction` (string, required): Enum [`parent`, `children`, `ancestors`, `descendants`].
* `limit` (integer, optional): Maximum number of records to return. Default is 50. Use this when the user asks for a specific number of results (e.g., "give me 5 users").
* `max_depth` (integer, optional): Limits descendant traversal to a specific number of levels.
* `return_fields` (list of strings, optional): Specify EXACTLY which fields to return per record (e.g., `["username", "id"]`). Use this to keep the response small. If the user only needs names, only request names. When omitted, full documents are returned.

## Usage Guide for LLM
* **Trigger when:** The user asks about relationships, uplines, downlines, or hierarchy structure.
* **Example Queries:**
  * "Who is the direct parent of `user1`?" -> Use `target_username: "user1"`.
  * "Show me the entire downline for `agent2`." -> Use `target_username: "agent2"`.
  * "Give me 5 users under `steven_065`." -> Use `target_username: "steven_065"`, `direction: "children"`, `limit: 5`, `return_fields: ["username", "id"]`.
  * "Which users report directly to the EUR Currency Agent?"
* **Do NOT trigger when:** The user just wants a total count without the actual account details.

## CRITICAL — Output Format
You MUST NOT answer the user's question yourself. You do NOT have access to any data.
Instead, output ONLY a single `<FUNCTION_CALL>` block containing the function name and arguments as valid JSON. Example:

<FUNCTION_CALL>
{"function": "traverse_hierarchy", "arguments": {"target_username": "agent2", "direction": "children", "return_fields": ["username", "id"]}}
</FUNCTION_CALL>

You are free to include any text with your thoughts and reasoning before writing the final <FUNCTION_CALL> block. Do NOT fabricate results.

you are strictly allowed to write only one function call, the dev tool can not execute many commands in one go.
--- END OF FILE hierarchy_management.md ---