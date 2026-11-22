//! Small synchronous, plaintext SQLite SDK. No network or required MadObs service.
use rusqlite::{params, Connection, OpenFlags, OptionalExtension, TransactionBehavior};
use std::{fmt, path::Path, time::Duration};

#[derive(Debug)]
pub enum Error {
    Sqlite(rusqlite::Error),
    InvalidNamespace,
    InvalidPath,
    ForeignDatabase,
    InvalidSchema,
    UnsupportedSchema(i64),
}
impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Sqlite(e) => write!(f, "SQLite: {e}"),
            Self::InvalidPath => f.write_str("open requires a nonempty filesystem path, not a SQLite URI or :memory:"),
            Self::InvalidSchema => f.write_str("MadDB schema does not match version 1"),
            Self::ForeignDatabase => f.write_str("file is not a dedicated MadDB database"),
            Self::InvalidNamespace => f.write_str("namespace must contain 1..=128 bytes"),
            Self::UnsupportedSchema(v) => write!(f, "unsupported schema version: {v}"),
        }
    }
}
impl std::error::Error for Error {}
impl From<rusqlite::Error> for Error {
    fn from(value: rusqlite::Error) -> Self { Self::Sqlite(value) }
}
pub type Result<T> = std::result::Result<T, Error>;

pub enum Mutation<'a> {
    Put { key: &'a str, value: &'a [u8] },
    Delete { key: &'a str },
}

/// Opt-in counters only: no keys, values, SQL, paths, or outbound transport.
#[cfg(feature = "madobs")]
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Metrics { pub reads: u64, pub committed_batches: u64 }

pub struct Database {
    connection: Connection,
    namespace: String,
    #[cfg(feature = "madobs")]
    metrics: Metrics,
}
impl Database {
    /// Opens a dedicated MadDB file. Empty paths, `:memory:`, and SQLite URIs are rejected.
    /// The host controls directory creation and permissions. Use `in_memory` for ephemeral data.
    pub fn open(path: impl AsRef<Path>, namespace: &str) -> Result<Self> {
        Self::validate(namespace)?;
        let path = path.as_ref();
        if path.as_os_str().is_empty()
            || path == Path::new(":memory:")
            || path.as_os_str().as_encoded_bytes().starts_with(b"file:")
        {
            return Err(Error::InvalidPath);
        }
        // Do not opt into URI interpretation (rusqlite's default flags do).
        let flags = OpenFlags::SQLITE_OPEN_READ_WRITE
            | OpenFlags::SQLITE_OPEN_CREATE
            | OpenFlags::SQLITE_OPEN_NO_MUTEX;
        Self::initialize(Connection::open_with_flags(path, flags)?, namespace)
    }
    /// Real SQLite in-memory database, not a HashMap/mock. Contents die on drop.
    pub fn in_memory(namespace: &str) -> Result<Self> {
        Self::validate(namespace)?;
        Self::initialize(Connection::open_in_memory()?, namespace)
    }
    fn validate(namespace: &str) -> Result<()> {
        if namespace.is_empty() || namespace.len() > 128 { return Err(Error::InvalidNamespace); }
        Ok(())
    }
    fn initialize(mut connection: Connection, namespace: &str) -> Result<Self> {
        connection.busy_timeout(Duration::from_secs(5))?;
        let tx = connection.transaction_with_behavior(TransactionBehavior::Immediate)?;
        let version: i64 = tx.query_row("PRAGMA user_version", [], |r| r.get(0))?;
        let app_id: i64 = tx.query_row("PRAGMA application_id", [], |r| r.get(0))?;
        const APP_ID: i64 = 0x4D414444;
        if (version != 0 && app_id != APP_ID) || (version == 0 && app_id != 0) {
            return Err(Error::ForeignDatabase);
        }
        match version {
            0 => {
                let objects: i64 = tx.query_row(
                    "SELECT count(*) FROM sqlite_schema WHERE name NOT GLOB 'sqlite_*'", [], |r| r.get(0))?;
                if objects != 0 { return Err(Error::ForeignDatabase); }
                tx.execute_batch(include_str!("schema.sql"))?;
            },
            1 => {},
            other => return Err(Error::UnsupportedSchema(other)),
        }
        // Version 1 has one canonical table definition. Fail closed on altered keys/collations.
        let definition: Option<String> = tx.query_row(
            "SELECT sql FROM sqlite_schema WHERE type='table' AND name='maddb_kv'", [], |r| r.get(0)).optional()?;
        let expected = include_str!("schema.sql").split(';').next().unwrap().trim();
        if definition.as_deref() != Some(expected) { return Err(Error::InvalidSchema); }
        tx.commit()?;
        Ok(Self { connection, namespace: namespace.to_owned(),
            #[cfg(feature = "madobs")]
            metrics: Metrics::default(),
        })
    }
    pub fn get(&mut self, key: &str) -> Result<Option<Vec<u8>>> {
        let result = self.connection.query_row(
            "SELECT value FROM maddb_kv WHERE namespace = ?1 AND key = ?2",
            params![self.namespace, key], |r| r.get(0)).optional()?;
        #[cfg(feature = "madobs")]
        { self.metrics.reads = self.metrics.reads.saturating_add(1); }
        Ok(result)
    }
    pub fn put(&mut self, key: &str, value: &[u8]) -> Result<()> {
        self.apply(&[Mutation::Put { key, value }])
    }
    pub fn delete(&mut self, key: &str) -> Result<()> {
        self.apply(&[Mutation::Delete { key }])
    }
    /// Entire batch commits, or all mutations are rolled back on failure.
    pub fn apply(&mut self, mutations: &[Mutation<'_>]) -> Result<()> {
        let tx = self.connection.transaction_with_behavior(TransactionBehavior::Immediate)?;
        for mutation in mutations {
            match mutation {
                Mutation::Put { key, value } => {
                    tx.execute("INSERT INTO maddb_kv(namespace,key,value) VALUES (?1,?2,?3) ON CONFLICT(namespace,key) DO UPDATE SET value=excluded.value", params![self.namespace, key, value])?;
                }
                Mutation::Delete { key } => {
                    tx.execute("DELETE FROM maddb_kv WHERE namespace=?1 AND key=?2", params![self.namespace, key])?;
                }
            }
        }
        tx.commit()?;
        #[cfg(feature = "madobs")]
        { self.metrics.committed_batches = self.metrics.committed_batches.saturating_add(1); }
        Ok(())
    }
    #[cfg(feature = "madobs")]
    pub fn metrics(&self) -> Metrics { self.metrics }
}

#[cfg(feature = "c-api")]
pub mod ffi;
