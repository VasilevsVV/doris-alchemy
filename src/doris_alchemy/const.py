from typing import TypeAlias


TABLE_PROPERTIES_SORT_TUPLES = [
    ("UNIQUE_KEY", "PARTITION_BY"),
    ("AGGREGATE_KEY", "PARTITION_BY"),
    ("DUPLICATE_KEY", "PARTITION_BY"),
    ("UNIQUE_KEY",    "DISTRIBUTED_BY"),
    ("AGGREGATE_KEY", "DISTRIBUTED_BY"),
    ("DUPLICATE_KEY", "DISTRIBUTED_BY"),
    ("PARTITION_BY", "DISTRIBUTED_BY"),
    ("DISTRIBUTED_BY", "PROPERTIES"),
    ("UNIQUE_KEY", "COMMENT"),
    ("AGGREGATE_KEY", "COMMENT"),
    ("DUPLICATE_KEY", "COMMENT"),
    ('COMMENT', 'PARTITION_BY'),
    ('COMMENT', 'DISTRIBUTED_BY')
]

TABLE_KEY_OPTIONS = (
    "UNIQUE KEY",
    "AGGREGATE KEY",
    "DUPLICATE KEY",
)