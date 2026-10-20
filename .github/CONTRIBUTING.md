# Contributing to dature

Thanks for your interest in improving dature!

## Setup

```bash
git clone https://github.com/reagento/dature.git
cd dature
uv sync --all-extras --all-groups
```

## Workflow

1. Open an issue first for anything non-trivial (new feature, public API change).
2. Create a branch whose prefix matches the change type — the PR labeler uses it:
   `fix/`, `bugfix/`, `bug/`, `feat/`, `feature/`, `docs/`, `refactor/`, `test/`, `chore/`, `ci/`, `removal/`, `deps/`.
3. Make the change. Rules of thumb:
   - Zero required dependencies; optional ones live behind extras and are imported inside the function that needs them.
   - Type hints everywhere; the package ships `py.typed`.
   - Do not break the public API (`src/dature/__init__.py` is the contract) without discussion.
   - Errors must be human-readable and name the field path.
   - Google-style docstrings in English.
4. Add tests:
   - Every bugfix needs a regression test.
   - Tests that differ only in data use `@pytest.mark.parametrize`.
5. Run the checks:

   ```bash
   uv run prek run --all-files   # ruff + mypy
   uv run pytest -q
   ```

6. Add a [towncrier](https://towncrier.readthedocs.io/) fragment to `changes/` for every change under `src/`.

## Changelog fragments

Format: `changes/<issue-or-pr-number>.<type>`, for example:

```bash
echo "Added support for YAML anchors." > changes/42.feature
```

| Type | Description |
|------|-------------|
| `feature` | New features |
| `bugfix` | Bug fixes |
| `doc` | Documentation improvements |
| `refactor` | Refactoring |
| `removal` | Deprecations and removals |
| `misc` | Other changes |

For changes without a linked issue use `+<description>`:

```bash
echo "Fixed typo in error message." > changes/+fix-typo.bugfix.md
```

## Documentation

```bash
uv run mkdocs serve
```

Examples under `docs/examples/` and `examples/` are executed by `tests/examples/test_examples.py`.
A script with a neighbouring `.stderr` file must fail with exactly that output;
a script with a `.stdout` file must print exactly that.

## Security

Please do not report vulnerabilities in public issues — see [SECURITY.md](../SECURITY.md).
