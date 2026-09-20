`ConsulSource`, `EtcdSource`, `ZookeeperSource`, and `AwsSsmSource` shared an identical
`match self.decode: case "raw"/"utf-8"/"json"` block in `format_loaders()`, copied byte for byte
across all four. Extracted into `RemoteSource._decode_mode_loaders()`. Fixing the duplication
surfaced an unexplained gap: `AwsSsmSource` only supported `"utf-8"`/`"json"`, missing the `"raw"`
mode the other three had. `AwsSsmSource` now also accepts `decode="raw"` for parity — a
backward-compatible addition, existing behavior for `"utf-8"`/`"json"` is unchanged.
