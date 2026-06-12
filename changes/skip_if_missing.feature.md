New `skip_if_missing` parameter on `load()`, `Loader`, and `Source` — silently skips a source whose file does not exist, independently of `skip_if_broken` (parse errors).

```python
# global flag
load(JsonSource(file="local.json"), EnvSource(), schema=Config, skip_if_missing=True)

# per-source override
load(
    JsonSource(file="required.json"),
    JsonSource(file="optional.json", skip_if_missing=True),  # only this source is optional
    schema=Config,
)
```
