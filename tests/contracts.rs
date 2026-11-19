use maddb::{Database, Error, Mutation};
use std::{path::PathBuf, sync::atomic::{AtomicUsize, Ordering}};
static NEXT: AtomicUsize = AtomicUsize::new(0);
struct Temp(PathBuf);
impl Temp {
    fn new() -> Self {
        let p = std::env::temp_dir().join(format!("maddb-public-{}-{}", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)));
        std::fs::create_dir(&p).unwrap();
        Self(p)
    }
    fn db(&self) -> PathBuf { self.0.join("store.sqlite") }
}
impl Drop for Temp { fn drop(&mut self) { let _ = std::fs::remove_dir_all(&self.0); } }
#[test]
fn binary_roundtrip_upsert_delete_and_sql_binding() {
    let mut db = Database::in_memory("app").unwrap();
    let key = "'; DROP TABLE maddb_kv; --\0";
    assert_eq!(db.get(key).unwrap(), None);
    db.put(key, &[0, 255, 1]).unwrap();
    assert_eq!(db.get(key).unwrap(), Some(vec![0,255,1]));
    db.put(key, b"").unwrap();
    assert_eq!(db.get(key).unwrap(), Some(vec![]));
    db.delete(key).unwrap(); db.delete(key).unwrap();
    assert_eq!(db.get(key).unwrap(), None);
}
#[test]
fn persistence_and_namespace_isolation() {
    let temp = Temp::new();
    { Database::open(temp.db(), "a").unwrap().put("same", b"A").unwrap(); }
    let mut a = Database::open(temp.db(), "a").unwrap();
    let mut b = Database::open(temp.db(), "b").unwrap();
    assert_eq!(a.get("same").unwrap(), Some(b"A".to_vec()));
    assert_eq!(b.get("same").unwrap(), None);
    b.put("same", b"B").unwrap(); a.delete("same").unwrap();
    assert_eq!(b.get("same").unwrap(), Some(b"B".to_vec()));
    assert!(std::fs::read(temp.db()).unwrap().starts_with(b"SQLite format 3\0"));
}
#[test]
fn batch_rolls_back_after_mid_batch_sql_failure() {
    let temp = Temp::new();
    let mut db = Database::open(temp.db(), "a").unwrap();
    let raw = rusqlite::Connection::open(temp.db()).unwrap();
    raw.execute_batch("CREATE TRIGGER reject_key BEFORE INSERT ON maddb_kv WHEN NEW.key='fail' BEGIN SELECT RAISE(ABORT,'test failure'); END;").unwrap();
    assert!(db.apply(&[Mutation::Put{key:"first",value:b"1"},Mutation::Put{key:"fail",value:b"2"}]).is_err());
    assert_eq!(db.get("first").unwrap(), None);
    db.put("after", b"ok").unwrap();
}
#[test]
fn ordered_batch_commits() {
    let mut db = Database::in_memory("a").unwrap();
    db.apply(&[Mutation::Put{key:"k",value:b"v"},Mutation::Delete{key:"k"},Mutation::Put{key:"k",value:b"final"}]).unwrap();
    assert_eq!(db.get("k").unwrap(), Some(b"final".to_vec()));
}
#[test]
fn invalid_namespace_does_not_create_file() {
    let temp = Temp::new();
    assert!(matches!(Database::open(temp.db(), ""), Err(Error::InvalidNamespace)));
    assert!(!temp.db().exists());
    assert!(matches!(Database::in_memory(&"a".repeat(129)), Err(Error::InvalidNamespace)));
}
#[test]
fn refuses_future_schema_without_downgrade() {
    let temp = Temp::new();
    let raw = rusqlite::Connection::open(temp.db()).unwrap();
    raw.execute_batch("PRAGMA user_version=99; PRAGMA application_id=1296122948").unwrap();
    assert!(matches!(Database::open(temp.db(), "a"), Err(Error::UnsupportedSchema(99))));
    let v: i64 = raw.query_row("PRAGMA user_version", [], |r| r.get(0)).unwrap();
    assert_eq!(v,99);
}
#[test]
fn memory_handles_are_independent() {
    let mut a = Database::in_memory("a").unwrap();
    let mut b = Database::in_memory("a").unwrap();
    a.put("k", b"v").unwrap(); assert_eq!(b.get("k").unwrap(),None);
}
#[test]
fn report_actual_sqlite_version() { println!("SQLite runtime: {}", rusqlite::version()); }
#[cfg(feature="madobs")]
#[test]
fn opt_in_metrics_contain_counts_only() {
    let mut db = Database::in_memory("a").unwrap();
    db.put("secret", b"secret").unwrap(); db.get("secret").unwrap();
    assert_eq!(db.metrics(), maddb::Metrics{reads:1,committed_batches:1});
}

#[test]
fn rejects_foreign_file_without_modifying_schema() {
    let temp = Temp::new();
    let raw = rusqlite::Connection::open(temp.db()).unwrap();
    raw.execute_batch("CREATE TABLE unrelated(value TEXT)").unwrap();
    assert!(matches!(Database::open(temp.db(), "a"), Err(Error::ForeignDatabase)));
    let count: i64 = raw.query_row("SELECT count(*) FROM sqlite_schema WHERE name='maddb_kv'", [], |r| r.get(0)).unwrap();
    assert_eq!(count, 0);
}

#[test]
fn rejects_altered_collation_or_missing_primary_key() {
    let temp = Temp::new();
    let raw = rusqlite::Connection::open(temp.db()).unwrap();
    raw.execute_batch("CREATE TABLE maddb_kv(namespace TEXT COLLATE NOCASE,key TEXT,value BLOB); PRAGMA application_id=1296122948; PRAGMA user_version=1").unwrap();
    assert!(matches!(Database::open(temp.db(), "a"), Err(Error::InvalidSchema)));
}

#[test]
fn persistent_open_rejects_temporary_memory_and_uri_paths() {
    for path in ["", ":memory:", "file::memory:?cache=shared", "file:maddb_ephemeral?mode=memory&cache=shared"] {
        assert!(matches!(Database::open(path, "a"), Err(Error::InvalidPath)), "accepted non-file path: {path:?}");
    }
}

#[test]
fn rejects_foreign_sqlitex_table_without_changing_file() {
    let temp = Temp::new();
    let raw = rusqlite::Connection::open(temp.db()).unwrap();
    raw.execute_batch("CREATE TABLE sqliteX_customer(value TEXT); INSERT INTO sqliteX_customer VALUES ('preserve')").unwrap();
    let before = std::fs::read(temp.db()).unwrap();
    assert!(matches!(Database::open(temp.db(), "a"), Err(Error::ForeignDatabase)));
    assert_eq!(std::fs::read(temp.db()).unwrap(), before);
}

#[test]
fn ordinary_path_named_memory_is_persistent() {
    let temp = Temp::new();
    let path = temp.0.join(":memory:");
    Database::open(&path, "a").unwrap().put("k", b"v").unwrap();
    assert!(path.exists());
    assert_eq!(Database::open(&path, "a").unwrap().get("k").unwrap(), Some(b"v".to_vec()));
}
