<!-- unisoft-mcp-guidance:start -->
# UniSoft MCP Workflow

Claude MUST use the UniSoft MCP tools before editing. Code changes must be grounded in project context, prior decisions, indexed knowledge, and remembered experience.

## Default Workflow

1. Classify the user request before touching files.
2. Before editing any code, Claude MUST call the highest-level context tool that matches the work:
   - Feature work: `build_feature_context`
   - Bugfix work: `build_bugfix_context`
   - Refactoring work: `build_refactoring_context`
   - General or unclear work: `build_context`
3. Claude MUST review the returned symbols, dependencies, documentation, business rules, database knowledge, architecture notes, and experience memories.
4. Claude MUST use the retrieved context to guide code changes. High-level context tools take priority over low-level searches.
5. Implement the change.
6. Run the relevant tests or validation commands before reporting completion.
7. After the work is complete and validated, Claude MUST call `record_outcome`.

Claude MUST NOT skip the high-level context step for feature, bugfix, refactor, or unclear work. Low-level tools are only allowed for targeted lookup, debugging, indexing, or direct memory management after the high-level context tool has been considered.

## Recording Outcomes

Claude MUST call `record_outcome` after completing implementation and validation.

Put the reusable lesson in `outcome`. It MUST be a clean, reusable summary that would help a future agent make a better decision. Do not put raw command output, stack traces, or full logs in `outcome`.

Put execution details in `metadata`. Metadata MUST include the fields that are available from the work:

- `original_task`
- `goal`
- `files_changed`
- `commands_run`
- `tests_run`
- `git_diff_summary`
- `errors`
- `agent`
- `model`
- `source = external_mcp`
- Important decisions

## Preferred Tools

Claude MUST use these high-level workflow tools for the normal task lifecycle:

- `build_feature_context`
- `build_bugfix_context`
- `build_refactoring_context`
- `build_context`
- `record_outcome`
- `learn_from_feedback`

Targeted retrieval tools include knowledge search, architecture lookup, discovery/project file lookup, experience search, and memory search tools. Use them only when the context package points to an area that needs deeper investigation.

Administrative and indexing tools include project creation, repository scanning, ingestion, and project-file extraction tools. Use them to set up or refresh indexed knowledge. They are not a substitute for context before editing.

Low-level helper tools include raw memory CRUD, raw extraction, and ranking-related helpers. Use them only when direct management or debugging is needed.

## Examples

Feature workflow:

```txt
User asks: Add semantic retrieval for experience memories.
Claude MUST:
1. call build_feature_context
2. implement using returned symbols, dependencies, docs, business rules, database knowledge, and memories
3. run tests
4. call record_outcome
```

Bugfix workflow:

```txt
User asks: Fix duplicate records returned by hybrid retrieval.
Claude MUST:
1. call build_bugfix_context
2. inspect previous fixes, known pitfalls, relevant symbols, dependencies, docs, and database knowledge
3. fix
4. run focused regression tests
5. call record_outcome
```

Refactor workflow:

```txt
User asks: Refactor context package creation to share validation.
Claude MUST:
1. call build_refactoring_context
2. inspect dependencies, impact, business rules, and prior lessons
3. refactor safely in behavior-preserving steps
4. run tests
5. call record_outcome
```

Feedback workflow:

```txt
User says: That result was wrong, or that fix was good.
Claude MUST:
1. call learn_from_feedback for the relevant experience memory or prior outcome
2. capture whether the feedback indicates success or failure
3. include concise metadata about the task, agent, model, and source = external_mcp
```

General workflow:

```txt
User asks: Explain how project scanning works and make any needed cleanup.
Claude MUST:
1. call build_context
2. inspect returned project files, symbols, docs, business rules, database knowledge, and memories
3. make only context-supported changes
4. run validation
5. call record_outcome if code or durable project knowledge changed
```
<!-- unisoft-mcp-guidance:end -->
