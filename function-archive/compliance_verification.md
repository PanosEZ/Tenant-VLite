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
* `scope_filter` (object, optional): Narrow the check to a subset of accounts. Example: `{"type": "AGENT"}` to only check agents.

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

You are free to include any text with your thoughts and reasoning before writing the final <FUNCTION_CALL> block. Do NOT fabricate results.

you are strictly allowed to write only one function call, the dev tool can not execute many commands in one go.
--- END OF FILE compliance_verification.md ---