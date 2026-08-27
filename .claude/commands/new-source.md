Walk me through adding a new Source type to dature step by step.

Use the following checklist. Ask me for the format name before starting, then execute each step:

**Steps:**

1. **Source class** — create `src/dature/sources/<format>_.py`
   - Subclass `FileSource` (structured format) or `FlatKeySource` (flat key=value) or `RemoteSource` (remote API)
   - Set `format_name: ClassVar[str]` and `location_label: ClassVar[str]`
   - Implement `_load_file(self, path: FileOrStream) -> JSONValue`
   - Import the optional dependency *inside* `_load_file`, not at module level
   - For `FlatKeySource` subclasses that need custom error location: override `resolve_location(self, *, field_path, file_content, nested_conflict, input_value=None)` as an **instance method** (not classmethod). Use `self._compute_line_carets(line_content, input_value=input_value, field_key=field_path[-1])` to compute per-line carets — returns `list[CaretSpan]` parallel to `line_content`. Assign to `SourceLocation.line_carets`. For format-specific caret placement, override classmethods `_caret_for_key_line` or `_find_value_in_line` (both return `CaretSpan`).

2. **Line index** (if the format supports line-number error locations) — implement in the same `src/dature/sources/<format>_.py`
   - Override `_build_line_index(self, content: str) -> dict[tuple[str, ...], LineRange] | None`
   - Return a dict mapping dotted-path tuples to `LineRange`. Return `None` if diagnostics are not available.
   - Import the parser lazily inside the method (as in `_load_file`). See `sources/yaml_.py` or `sources/toml_.py` as reference.
   - No separate class or file needed — everything lives in the Source module.

3. **Optional dependency** — add to `pyproject.toml [project.optional-dependencies]`:
   ```
   <format> = ["<package>>=<version>"]
   ```

4. **Public export** — add to `src/dature/__init__.py`:
   - Import the new source class
   - Add to `__all__`

5. **Tests** — create `tests/sources/test_<format>_.py`
   - Test happy path loading
   - Test missing optional dep via `block_import` fixture
   - Test file-not-found error
   - Mirror structure of existing `tests/sources/test_yaml12_.py` or similar
   - Test EXPECTED_ALL_TYPES/AllPythonTypesCompact unit and integration

6. **Integration tests** (if the source talks to an external service) — create `tests/integration/sources/<source>/`
   - Mirror the layout of an existing source dir (`conftest.py` with a `testcontainers Docker fixture, `test_<source>_.py`, optionally `test_examples.py`/`helpers.py`)
   - Add a matching entry to `[tool.dature.ci.integration-jobs]` in `pyproject.toml` — `.github/scripts/get_integration_jobs.py` fails the CI build if the new directory isn't declared. Set `extras` to the `[project.optional-dependencies]` section name only if the client library needs cross-major-version testing.

7. **Changelog fragment** — create `changes/+add-<format>-source.feature.md`

After completing all steps, run `/done` to verify everything passes.
