`dature.get_load_report` is renamed to `dature.load_report`.
The underlying module is also renamed from `dature.load_report` to `dature.report`:

```python
# before
from dature import get_load_report
from dature.load_report import LoadReport

# after
from dature import load_report
from dature.report import LoadReport
```
