`deep_merge_last_wins` and `deep_merge_first_wins` (`merging/deep_merge.py`) differed only in their
base case (`return override` vs. `return base`). Merged into a single `_deep_merge` helper
parameterized by `last_wins`, so a future change to the recursive merge logic (e.g. list handling)
can't be applied to one copy and forgotten in the other. Also documented in the new helper's
docstring that lists are always replaced wholesale by `override`, never merged element-wise — that
was true before and remains unchanged. No observable behavior change.
