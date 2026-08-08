Migrated :class:`EtcdSource`, :class:`ConsulSource`, and :class:`VaultSource` from the
removed imperative ``check_invariants()`` hook to declarative validation: single-field
rules use ``Annotated[..., V ...]`` predicates, ``Literal``-typed fields are checked
automatically, and cross-field rules use the ``Source.root_validators`` ``ClassVar``
(renamed from ``source_invariants``). Note this is distinct from ``load()``'s
``root_validators=`` parameter, which validates the merged schema instance rather than
the source itself.
