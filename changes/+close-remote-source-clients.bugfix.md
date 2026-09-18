All remote sources (Vault, Consul, etcd, SSM, Secrets Manager, Azure App Configuration,
Azure Key Vault, GCP Secret Manager) now close their network client after each `_fetch()`,
including when it raises. Previously only `ZooKeeperSource` did this — the other eight built a
fresh HTTP/gRPC client on every fetch and never released it, so a background `reload=` trigger
(added in 1.4) would leak a client, and its underlying connection, on every tick for the lifetime
of the process.
