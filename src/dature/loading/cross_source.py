"""Cross-source reference orchestration.

Validates ``${@tag.key}`` dependency graph eagerly at ``Loader.__init__`` time:
  1. Detect which tags each source's init-field strings reference.
  2. Kahn's algorithm over the dependency graph → topological order.
  3. If nodes remain after Kahn's pass, extract a cycle with DFS and raise.

Tag collision (two sources with the same ``resolved_tag``) is detected upfront
before the graph is built.

Actual interpolation happens lazily inside ``LoadCtx.load`` — each source's
``load_raw()`` is called exactly once, with cross-ref substitution applied to
its init-fields immediately before that call.
"""

import dataclasses
from collections import deque
from dataclasses import dataclass

from dature.conditions import Condition
from dature.errors.exceptions import DatureError
from dature.expansion.cross_source import expand_cross_refs, find_refs, needs_cross_ref_expansion
from dature.expansion.env_expand import expand_string_default
from dature.sources.base import Source, clone_source
from dature.types import JSONValue


def _init_string_fields(source: Source) -> dict[str, str]:
    """Return {field_name: value} for all init string fields of a source."""
    d = vars(source)
    return {
        field.name: value
        for field in dataclasses.fields(source)
        if field.init and isinstance(value := d[field.name], str)
    }


def when_has_cross_refs(source: Source) -> bool:
    """Return True if source.when contains any ${@tag.key} cross-ref."""
    return source.when is not None and source.when.has_cross_refs()


def _extract_ref_tags(source: Source) -> set[str]:
    """Return all tag names referenced in this source's init string fields and when keys."""
    tags: set[str] = set()
    for value in _init_string_fields(source).values():
        for tag, _ in find_refs(value):
            tags.add(tag)
    if source.when is not None:
        tags |= source.when.ref_tags()
    return tags


def evaluate_when_eager(when: "Condition | None") -> bool:
    """Return True if when is None or all conditions pass using env-var expansion only.

    Called at the start of each ``.load()`` before any sources are fetched.
    Cross-source refs are left unexpanded here; the caller's ``when_has_cross_refs``
    short-circuit defers such sources to lazy evaluation.
    """
    if when is None:
        return True
    return when.evaluate(expand_string_default)


def _lazy_expand(s: str, context: dict[str, dict[str, JSONValue]]) -> str:
    expanded = expand_string_default(s)
    if needs_cross_ref_expansion(expanded):
        expanded = expand_cross_refs(expanded, context=context)
    return expanded


def evaluate_when_lazy(
    when: "Condition | None",
    context: dict[str, dict[str, JSONValue]],
) -> bool:
    """Return True if when is None or all conditions pass using env-var + cross-source expansion.

    Called inside ``LoadCtx._prepare_source`` when the source's dependency context
    is already available.
    """
    if when is None:
        return True
    return when.evaluate(lambda s: _lazy_expand(s, context))


def clone_with_interpolation(
    source: Source,
    context: dict[str, dict[str, JSONValue]],
) -> Source:
    """Return a shallow copy of *source* with cross-refs in init fields expanded.

    Uses ``copy.copy`` + ``vars().update()`` — the same pattern as
    ``apply_source_init_params`` — to avoid re-running ``__post_init__``
    on already-processed fields.
    """
    overrides: dict[str, object] = {}
    for name, value in _init_string_fields(source).items():
        if needs_cross_ref_expansion(value):
            expanded = expand_cross_refs(value, context=context)
            if expanded != value:
                overrides[name] = expanded

    if not overrides:
        return source

    return clone_source(source, overrides)


def _find_cycle(start: int, deps: list[list[int]]) -> list[int]:
    """DFS from *start* to find a cycle. Returns cycle as list of indices."""
    visited: set[int] = set()
    stack: list[int] = []
    stack_set: set[int] = set()

    def _dfs(node: int) -> bool:
        if node in visited:
            return False
        if node in stack_set:
            idx = stack.index(node)
            stack.append(node)
            del stack[:idx]  # keep only from cycle start
            return True
        stack.append(node)
        stack_set.add(node)
        for neighbor in deps[node]:
            if _dfs(neighbor):
                return True
        stack.pop()
        stack_set.discard(node)
        visited.add(node)
        return False

    _dfs(start)
    return stack


def _format_cycle_error(
    cycle: list[int],
    sources: tuple[Source, ...],
    deps: list[list[int]],
) -> str:
    """Format a human-readable cycle error message."""
    lines = ["Cross-source reference cycle detected:"]
    cycle_set = set(cycle)
    nodes = cycle[:-1] if len(cycle) > 1 and cycle[-1] == cycle[0] else cycle
    for source_idx in nodes:
        source = sources[source_idx]
        cycle_dep_tags = {sources[dep_idx].resolved_tag for dep_idx in deps[source_idx] if dep_idx in cycle_set}
        example_refs = [
            f"${{@{tag}.{key}}}"
            for value in _init_string_fields(source).values()
            for tag, key in find_refs(value)
            if tag in cycle_dep_tags
        ]
        ref_str = ", ".join(example_refs) if example_refs else "?"
        lines.append(f"  {type(source).__name__}(tag='{source.resolved_tag}')  →  references {ref_str}")
    if cycle:
        closing = sources[cycle[-1]]
        lines.append(f"  closes back to {type(closing).__name__}(tag='{closing.resolved_tag}')")
    lines.append("")
    lines.append(
        "Sources cannot reference each other's data in a cycle. "
        "Break the cycle by hardcoding one side or parsing one source imperatively."
    )
    return "\n".join(lines)


def _format_tag_collision_error(tag: str, sources: list[Source]) -> str:
    names = "\n".join(f"  {source!r}" for source in sources)
    return (
        f"Tag collision: multiple sources share resolved_tag={tag!r}:\n"
        f"{names}\n"
        "Set an explicit tag= on at least one of them."
    )


def _build_dep_graph(sources: tuple[Source, ...]) -> list[list[int]]:
    """Return dependency graph: deps[i] = indices of sources that source i depends on.

    Raises DatureError on tag collision or reference to unknown tag.
    """
    refs_per_source = [_extract_ref_tags(source) for source in sources]
    referenced_tags: set[str] = set().union(*refs_per_source) if refs_per_source else set()

    by_tag: dict[str, int] = {}
    collisions: dict[str, list[int]] = {}
    for source_idx, source in enumerate(sources):
        tag = source.resolved_tag
        if tag in by_tag:
            collisions.setdefault(tag, [by_tag[tag]]).append(source_idx)
        else:
            by_tag[tag] = source_idx

    active_collisions = {
        tag: idxs
        for tag, idxs in collisions.items()
        if tag in referenced_tags or any(sources[i].tag is not None for i in idxs)
    }
    if active_collisions:
        msgs = [
            _format_tag_collision_error(tag, [sources[idx] for idx in idxs]) for tag, idxs in active_collisions.items()
        ]
        msg = "\n\n".join(msgs)
        raise DatureError(msg)

    known_tags = ", ".join(f"'{tag}'" for tag in sorted(by_tag) if tag not in collisions)
    deps: list[list[int]] = [[] for _ in sources]
    for source_idx, source in enumerate(sources):
        for ref_tag in refs_per_source[source_idx]:
            if ref_tag not in by_tag:
                msg = (
                    f"{type(source).__name__}(tag='{source.resolved_tag}') references unknown tag '{ref_tag}'. "
                    f"Known tags: {known_tags or 'none'}. "
                    "Ensure a source with that tag is listed in the same load() call."
                )
                raise DatureError(msg)
            dep_idx = by_tag[ref_tag]
            if dep_idx != source_idx and dep_idx not in deps[source_idx]:
                deps[source_idx].append(dep_idx)

    return deps


def _topological_sort(sources: tuple[Source, ...], deps: list[list[int]]) -> list[int]:
    """Return source indices in topological order (dependencies before dependents).

    Raises DatureError if a cycle is detected.
    """
    in_degree = [len(dep_list) for dep_list in deps]
    reverse_deps: list[list[int]] = [[] for _ in sources]
    for source_idx, dep_list in enumerate(deps):
        for dep_idx in dep_list:
            reverse_deps[dep_idx].append(source_idx)

    queue: deque[int] = deque(source_idx for source_idx, degree in enumerate(in_degree) if degree == 0)
    topo_order: list[int] = []
    while queue:
        source_idx = queue.popleft()
        topo_order.append(source_idx)
        for dependent_idx in reverse_deps[source_idx]:
            in_degree[dependent_idx] -= 1
            if in_degree[dependent_idx] == 0:
                queue.append(dependent_idx)

    remaining = set(range(len(sources))) - set(topo_order)
    if remaining:
        cycle = _find_cycle(next(iter(remaining)), deps)
        raise DatureError(_format_cycle_error(cycle, sources, deps))

    return topo_order


@dataclass(frozen=True, slots=True)
class CrossRefPlan:
    """Precomputed dependency graph for lazy cross-ref interpolation.

    ``deps[i]`` is the list of source indices that source ``i`` depends on
    (i.e. sources whose data must be loaded first so their values can be
    substituted into source ``i``'s init fields).
    """

    deps: tuple[tuple[int, ...], ...]


def build_cross_ref_plan(sources: tuple[Source, ...]) -> CrossRefPlan | None:
    """Eagerly validate the cross-ref dependency graph and return a plan.

    Raises ``DatureError`` on tag collision, unknown tag reference, or cycle.
    Returns ``None`` when there are no cross-ref edges (fast path for interpolation;
    collision validation still runs via ``_build_dep_graph``).
    """
    deps = _build_dep_graph(sources)
    if not any(deps):
        return None
    _topological_sort(sources, deps)
    return CrossRefPlan(deps=tuple(tuple(d) for d in deps))
