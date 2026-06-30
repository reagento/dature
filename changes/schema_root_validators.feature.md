Root validators are now schema-level: pass them via `root_validators=` on `load()`, `Loader`, and `configure()` instead of on the source. They run once on the final merged dataclass instance.

```python
# before
load(JsonSource(file=..., root_validators=(V.root(check),)), schema=Config)

# after
load(JsonSource(file=...), schema=Config, root_validators=(V.root(check),))
```
