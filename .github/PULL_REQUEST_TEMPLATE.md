## What and why

<!-- Short description of the change and the motivation. Link the issue: Closes #123 -->

## Checklist

- [ ] Changelog fragment added to `changes/` (`<number>.<type>` or `+<description>.<type>.md`) — required for any change under `src/`
- [ ] Tests added; a bugfix includes a regression test; tests differing only in data use `@pytest.mark.parametrize`
- [ ] `uv run prek run --all-files` passes
- [ ] `uv run pytest -q` passes
- [ ] Docs and examples updated if behaviour or public API changed
- [ ] Public API (`src/dature/__init__.py`) is unchanged, or the change is discussed in an issue
