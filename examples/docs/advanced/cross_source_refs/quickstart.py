"""Cross-source references — quick start."""

import os
from dataclasses import dataclass
from pathlib import Path

import dature

os.environ["APP_CONFIG_PATH"] = str(
    Path(__file__).parent / "sources" / "app.json"
)


@dataclass
class AppConfig:
    host: str = "localhost"
    port: int = 8080


# Sources can be listed in any order — dature builds a dependency graph from
# ${@tag.key} patterns and loads them in topological order automatically.
# JsonSource is listed first but loaded second because it depends on EnvSource.
#
# The "env" in ${@env.config_path} is the source tag.  By default the tag
# equals the source type's format_name ("env" for EnvSource, "json" for
# JsonSource).  Set tag= explicitly when you have two sources of the same type.
cfg = dature.load(
    dature.JsonSource(file="${@env.config_path}"),
    dature.EnvSource(prefix="APP_"),
    schema=AppConfig,
)

assert cfg.host == "db.internal"
assert cfg.port == 5432
