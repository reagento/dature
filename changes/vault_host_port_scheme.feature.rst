:class:`VaultSource` and :class:`VaultConfig` now accept ``host``/``port``/``scheme``
fields, matching :class:`EtcdSource` and :class:`ConsulSource`. The previous ``url``
field is deprecated in favor of the three split fields and will be removed in dature 1.2.
