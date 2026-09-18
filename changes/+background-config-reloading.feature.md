Added `reload=` — a background trigger that periodically reloads a config in place and keeps
the cache up to date, without restarting the process. Two triggers ship out of the box:
`FixedIntervalTrigger` (unconditional reload on a fixed cadence) and `FileWatchTrigger` (reload
when a watched file changes, requiring the optional `watchdog` package). Both accept `scheduler=`
to run on a dedicated thread instead of the shared process-wide default.
`on_reload=`/`on_error=` callbacks observe successful and failed reloads; a failed reload never
replaces the currently cached config (see `stale_on_error`). `reload=` is mutually exclusive with
`cache=timedelta(...)` and has no effect in function mode (`dature.load(...)` without a `Loader`
kept around) — both raise `ValueError`. Custom triggers can be written directly against
`ReloadTriggerProtocol` without subclassing anything. See the new "Background Reloading" docs page.
