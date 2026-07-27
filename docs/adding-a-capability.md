# Adding a capability

A capability is a self-contained VidXP feature with its own operations,
schemas, runtime dependencies, and optional indexing or CLI integration.
Chroma collections are storage details; do not call capability packages
“collections.”

## Required shape

Create `src/vidxp/capabilities/<name>/` with only the files the feature needs:

```text
<name>/
├── __init__.py
├── definition.py
├── config.py           # Pydantic settings owned by the capability
├── operations.py
├── schemas.py          # omit when shared schemas are sufficient
├── requirements.txt
├── indexing.py         # only for an indexable capability
└── cli.py              # only for specialized commands
```

`definition.py` exports one `CapabilityDefinition` named `DEFINITION`.
Register it explicitly in `src/vidxp/capabilities/registry.py`. The registry is
the only central file that should change for ordinary runtime registration.

## Contracts

Every public operation declares:

- a Pydantic input model;
- a Pydantic output model;
- a transport-neutral handler;
- whether it requires an active index.

Handlers receive `CapabilityContext`. Use `context.require_config()` only for
operations that declare `requires_index=True`. Do not import Typer, Streamlit,
FastAPI, or an MCP implementation into operation modules.

An indexable capability also declares its collection names, indexing handler,
and index stage. The generic runner groups capabilities that reference the same
indexing handler, allowing related capabilities to share work without adding a
name switch to the runner. A capability joining a shared decoder also supplies
its own prepare/process/finalize processor through its definition; the shared
handler must not import individual capabilities. Capability-specific settings belong in
`IndexConfig.capability_options` and are read with
`config.options_for("<name>")`. Validate them through the capability's
Pydantic settings model; do not add feature-specific fields to `IndexConfig`
or the runner.

Operation-only capabilities leave the indexing fields unset. They do not need
dummy collections or index handlers.

## Dependencies and installation

Put direct runtime requirements in the capability's `requirements.txt`.
Declare matching `RuntimeDependency` checks in `definition.py`, then expose the
requirements file as an optional dependency in `pyproject.toml`:

```toml
[tool.setuptools.dynamic.optional-dependencies]
example = { file = ["src/vidxp/capabilities/example/requirements.txt"] }
```

Add runtime capabilities to the `all` file list. Do not add benchmark,
frontend, or development dependencies to `all`. Imports of optional libraries
must stay inside the functions that use them so `import vidxp` and
`vidxp --help` work in a base-only installation.

## CLI integration

Generic commands obtain capability names and operations from the registry.
Only add `cli.py` when the capability needs specialized human interaction that
does not fit a generic command. Expose it through `cli_name` and `cli_factory`
on the definition; keep business logic in operations.

## Tests

Add focused tests under `tests/`. At minimum, cover:

1. Pydantic input and output validation.
2. Operation dispatch through `VidXPService.execute`.
3. Dependency selection without importing unrelated capabilities.
4. Index grouping and collection behavior when indexing is supported.
5. CLI behavior when specialized commands are provided.
6. Successful package metadata generation and a base-only import smoke test.

Adding a normal capability must not require edits to
`src/vidxp/application.py`, `src/vidxp/core/runner.py`, or
`src/vidxp/core/storage.py`.
