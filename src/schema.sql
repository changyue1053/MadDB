CREATE TABLE maddb_kv (
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    value BLOB NOT NULL,
    PRIMARY KEY (namespace, key)
) WITHOUT ROWID;
PRAGMA user_version = 1;
PRAGMA application_id = 1296122948;
