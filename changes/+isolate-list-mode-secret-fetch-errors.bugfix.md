`GcpSecretManagerSource` and `AzureKeyVaultSource` list mode (`name="*"`) fetches every listed
secret one by one after the initial listing call. If a secret was deleted or became inaccessible
in the window between listing and fetching, the "secret not found" error aborted the whole load,
even though every other secret fetched fine.

Fetching an individual secret in list mode now catches that not-found error, logs a warning
naming the skipped secret, and continues with the rest — a single missing secret no longer fails
the entire source. Fetching still happens sequentially (no added concurrency); auth failures and
other errors from the listing call itself still abort the load as before.
