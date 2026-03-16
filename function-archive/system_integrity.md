# system_integrity.md

## Scope
This tool acts as a diagnostic utility to validate the structural health of the materialized path hierarchy. It looks for data corruption, logical impossibilities, or orphaned nodes.

## How it Works
It runs specific, predefined diagnostic database queries to compare field constraints (e.g., ensuring `depth` exactly equals the length of the `ancestors` array, or ensuring no account has a `parent_id` that does not exist in the database).

## Arguments
* `diagnostic_routine` (string, required): The specific check to run. Enum: 
    * `depth_mismatch` (Finds accounts where `ancestors.length != depth`).
    * `orphaned_nodes` (Finds accounts where `parent_id` is not null but points to a non-existent ID).
    * `missing_admin` (Finds accounts that do not have the Admin '1' in their ancestors).

## Usage Guide for LLM
* **Trigger when:** The user asks to "run a health check", "find broken relationships", "check for orphans", or "validate the tree structure".

## CRITICAL — Output Format
You MUST NOT answer the user's question yourself. You do NOT have access to any data.
Instead, output ONLY a single `<FUNCTION_CALL>` block containing the function name and arguments as valid JSON. Example:

<FUNCTION_CALL>
{"function": "check_system_integrity", "arguments": {"diagnostic_routine": "depth_mismatch"}}
</FUNCTION_CALL>

You are free to include any text with your thoughts and reasoning before writing the final <FUNCTION_CALL> block. Do NOT fabricate results.

you are strictly allowed to write only one function call, the dev tool can not execute many commands in one go.