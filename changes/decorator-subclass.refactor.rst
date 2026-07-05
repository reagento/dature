Decorator mode now creates a true subclass of the target dataclass instead of
patching ``__init__`` and ``__post_init__`` in-place. The original class is
completely untouched after decoration; ``isinstance(Config(), OriginalConfig)``
continues to work. Root-validator errors now include source-file location info
(same as field-level errors). Internal: root validators are folded back into
the final adaptix retort (``final_retort``) via ``ConstructorOverrideProvider``,
eliminating the separate ``coerce_and_construct`` step; ``RetortCache`` gained a
public ``prewarm()`` method; the defunct ``root_retort()`` variant was removed.
