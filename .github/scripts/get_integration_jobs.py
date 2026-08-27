"""Compute the integration-tests job matrix for CI from [tool.dature.ci.integration-jobs].

See pyproject.toml for the table format and .github/workflows/ci.yml::get-integration-jobs
for how the output is consumed.
"""

import json
import os
import sys
import tomllib
import urllib.request
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version


def _validate_job_table(job_table: dict) -> None:
    """Every tests/integration/sources/ dir must be declared in exactly one job."""
    sources_root = Path("tests/integration/sources")
    on_disk = {p.name for p in sources_root.iterdir() if p.is_dir() and (p / "__init__.py").exists()}

    declared = [d for job in job_table.values() for d in job["dirs"]]
    duplicates = {d for d in declared if declared.count(d) > 1}
    if duplicates:
        sys.exit(f"::error::integration test dirs declared in more than one job: {sorted(duplicates)}")

    declared_set = set(declared)
    missing_on_disk = declared_set - on_disk
    if missing_on_disk:
        sys.exit(f"::error::integration-jobs declares dirs that don't exist: {sorted(missing_on_disk)}")

    undeclared = on_disk - declared_set
    if undeclared:
        sys.exit(
            f"::error::integration test dirs not declared in [tool.dature.ci.integration-jobs]: {sorted(undeclared)}"
        )


def _latest_per_major(lib_name: str, spec: SpecifierSet) -> dict[int, Version]:
    """Latest non-yanked stable release per major version matching ``spec``."""
    with urllib.request.urlopen(f"https://pypi.org/pypi/{lib_name}/json") as resp:
        data = json.loads(resp.read())

    by_major: dict[int, Version] = {}
    for v_str, files in data["releases"].items():
        if not files or any(f.get("yanked") for f in files):
            continue
        try:
            v = Version(v_str)
        except InvalidVersion:
            continue
        if v.is_prerelease or v not in spec:
            continue
        if v.major not in by_major or v > by_major[v.major]:
            by_major[v.major] = v
    return by_major


def _matrix_entries_for_job(job_name: str, job: dict, extras: dict) -> list[dict]:
    paths = " ".join(f"tests/integration/sources/{d}" for d in job["dirs"])
    extras_name = job.get("extras")
    if extras_name is None:
        return [{"name": job_name, "paths": paths, "flags": ""}]

    req = Requirement(extras[extras_name][0])
    lib_name = req.name
    by_major = _latest_per_major(lib_name, req.specifier)
    if not by_major:
        sys.exit(f"::error::No versions of {lib_name} match constraint {req.specifier}")

    return [
        {
            "name": f"{job_name}-{lib_name}{major}",
            "paths": paths,
            "flags": f"--upgrade-package {lib_name}=={by_major[major]}",
        }
        for major in sorted(by_major)
    ]


def main() -> None:
    with Path("pyproject.toml").open("rb") as f:
        pyproject = tomllib.load(f)
    job_table = pyproject["tool"]["dature"]["ci"]["integration-jobs"]
    extras = pyproject["project"]["optional-dependencies"]

    _validate_job_table(job_table)

    jobs = [entry for job_name, job in job_table.items() for entry in _matrix_entries_for_job(job_name, job, extras)]

    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as f:
        f.write(f"jobs={json.dumps(jobs)}\n")


if __name__ == "__main__":
    main()
