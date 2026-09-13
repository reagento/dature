A missing environment variable inside a `${VAR:-fallback}` fallback (e.g. `${A:-$B}` with both
`A` and `B` unset) in `"strict"` mode used to raise immediately from a throwaway sub-expander
instead of being collected like every other missing variable. This meant `expand_string_collect`
raised despite its documented "without raising" contract, `field_path` on the resulting error was
lost (rendered as `[<root>]` instead of the actual field), sibling fields with their own missing
variables were never reported, and `config_dirs` entries using this fallback shape (e.g. the
default `${XDG_CONFIG_HOME:-$HOME/.config}`) could crash `find_config` instead of being skipped
with a warning as documented. The fallback is now resolved by the same expander as the rest of the
string, so its errors are collected and attributed correctly.
