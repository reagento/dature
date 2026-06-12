`skip_broken_sources` parameter of `load()` and `Loader` is renamed to `skip_if_broken` and now covers **only parse/config errors** (invalid syntax, malformed files). It no longer silently skips missing files.

```python
# before
load(..., skip_broken_sources=True)

# after
load(..., skip_if_broken=True)  # parse errors only
load(..., skip_if_missing=True)  # missing files only
load(..., skip_if_broken=True, skip_if_missing=True)  # both
```
