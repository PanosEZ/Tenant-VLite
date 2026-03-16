# Tool: Hierarchy Management
**Function Name:** `traverse_hierarchy`

## Scope
Handles all tree-based logic and materialized path traversal. Focuses on relationships utilizing `parent_id`, the `ancestors` array, and `depth`.

## How it Works
Takes a focal account ID and traverses the tree in the specified direction. It fetches documents based on parent-child relationships rather than flat attributes.

## Arguments
* `target_id` (string, required): The focal `id` for the query.
* `direction` (string, required): Enum [`parent`, `children`, `ancestors`, `descendants`].
* `max_depth` (integer, optional): Limits descendant traversal to a specific number of levels.

## Usage Guide for LLM
* **Trigger when:** The user asks about relationships, uplines, downlines, or hierarchy structure.
* **Example Queries:**
  * "Who is the direct parent of `user1`?"
  * "Show me the entire downline for `agent2`."
  * "Which users report directly to the EUR Currency Agent?"
* **Do NOT trigger when:** The user just wants a total count without the actual account details.

## CRITICAL — Output Format
You MUST NOT answer the user's question yourself. You do NOT have access to any data.
Instead, output ONLY a single `<FUNCTION_CALL>` block containing the function name and arguments as valid JSON. Example:

<FUNCTION_CALL>
{"function": "traverse_hierarchy", "arguments": {"target_id": "2", "direction": "children"}}
</FUNCTION_CALL>

You are free to include any text with your thoughts and reasoning before writing the final <FUNCTION_CALL> block. Do NOT fabricate results.

you are strictly allowed to write only one function call, the dev tool can not execute many commands in one go.