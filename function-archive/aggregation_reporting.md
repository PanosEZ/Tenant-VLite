# Tool: Aggregation & Reporting
**Function Name:** `generate_aggregation_report`

## Scope
Handles counting, grouping, rankings, comparisons, and summary statistics. Focuses on numeric summaries and distributions rather than returning individual user profiles.

## How it Works
Uses database aggregation to group records and calculate totals. It translates natural language constraints (timeframes, statuses, hierarchies) into structured query filters before aggregating.

## Arguments
* `metric` (string, required): Enum [`count`, `distribution`]. Use `distribution` for grouping/ranking (e.g., "most popular", "breakdown"), and `count` for raw totals.
* `group_by` (string, optional): The exact document field to group by (e.g., `currency`, `type`, `status`).
* `filters` (object, optional): A dictionary applying pre-aggregation filters. Supports standard MongoDB query operators (`$gte`, `$lte`, `$in`, `$ne`, `$exists`, etc.) to handle complex conditions like dynamic date ranges, exclusions, or thresholds. Map all logical constraints directly to existing document fields (e.g., `created_at`, `updated_at`).
* `target_ancestor_id` (string, optional): Restricts aggregation to the downline of a specific ID.

## Usage Guide for LLM
* **Trigger when:** The user asks for numbers, breakdowns, statistical summaries, or rankings (e.g., "how many", "which is the most/least").
* **Constraint - Schema Strictness:** Strictly map user terminology to the available document schema. Do not hallucinate external tables or metrics (e.g., "transactions", "deposits"). If a user asks about "usage" or "activity", proxy this using available fields like `created_at` or `session_expire`.
* **Constraint - Temporal & Logical Filtering:** If the user implies a time constraint (e.g., "last month", "this year") or a negative constraint (e.g., "not active"), you MUST construct the corresponding mathematical operator (e.g., `$gte` on `created_at`) inside the `filters` object.

## CRITICAL — Output Format
You MUST NOT answer the user's question yourself. You do NOT have access to any data.
Instead, output ONLY a single `<FUNCTION_CALL>` block containing the function name and arguments as valid JSON. Example:

<FUNCTION_CALL>
{"function": "generate_aggregation_report", "arguments": {"metric": "distribution", "group_by": "currency"}}
</FUNCTION_CALL>

You are free to include any text with your thoughts and reasoning before writing the final <FUNCTION_CALL> block. Do NOT fabricate results.

you are strictly allowed to write only one function call, the dev tool can not execute many commands in one go.