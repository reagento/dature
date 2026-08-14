Added a load-level ``masking_mode`` parameter (``load()``, ``Loader``, the ``--masking-mode`` CLI
flag, ``MergeConfig``) mirroring ``MaskingConfig.masking_mode``, so masking aggressiveness can be
overridden per call, not just globally via ``configure()``.

Deprecated ``mask_secrets`` (``load()``/``Loader``/``configure(masking={...})``/
``DATURE_MASKING__MASK_SECRETS``/``--mask-secrets``) in favor of ``masking_mode``: ``True`` maps to
``masking_mode="secrets_only"``, ``False`` maps to ``masking_mode="none"``. Using ``mask_secrets`` emits
a ``DeprecationWarning`` and will be removed in dature 1.3. If both ``mask_secrets`` and
``masking_mode`` are set at the same time, ``masking_mode`` wins — this is not an error.
