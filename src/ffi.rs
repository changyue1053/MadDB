//! Opt-in C ABI v1. See include/maddb.h for pointer and lifecycle requirements.
use crate::{Database, Error};
use std::{collections::HashMap, panic::{catch_unwind, AssertUnwindSafe}, sync::{Arc, Mutex, OnceLock}};

pub const OK: i32 = 0;
pub const NOT_FOUND: i32 = 1;
pub const BUFFER_TOO_SMALL: i32 = 2;
pub const INVALID_ARGUMENT: i32 = -1;
pub const INVALID_HANDLE: i32 = -2;
pub const STORAGE_ERROR: i32 = -3;
pub const SCHEMA_ERROR: i32 = -4;
pub const INTERNAL_ERROR: i32 = -5;
pub const HANDLE_EXHAUSTED: i32 = -6;

type Slot = Arc<Mutex<Option<Database>>>;
#[derive(Default)]
struct Registry { next: u64, databases: HashMap<u64, Slot> }
static REGISTRY: OnceLock<Mutex<Registry>> = OnceLock::new();
fn boundary(f: impl FnOnce() -> i32) -> i32 {
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(code) => code,
        Err(payload) => { std::mem::forget(payload); INTERNAL_ERROR }
    }
}
fn registry(f: impl FnOnce(&mut Registry) -> i32) -> i32 {
    match REGISTRY.get_or_init(|| Mutex::new(Registry::default())).lock() {
        Ok(mut r) => f(&mut r),
        Err(_) => INTERNAL_ERROR,
    }
}
fn lookup(handle: u64, remove: bool) -> Result<Slot, i32> {
    let mut r = REGISTRY.get_or_init(|| Mutex::new(Registry::default()))
        .lock().map_err(|_| INTERNAL_ERROR)?;
    let slot = if remove { r.databases.remove(&handle) } else { r.databases.get(&handle).cloned() };
    slot.ok_or(INVALID_HANDLE)
}
fn with_database(handle: u64, f: impl FnOnce(&mut Database) -> i32) -> i32 {
    let slot = match lookup(handle, false) { Ok(s) => s, Err(e) => return e };
    let mut guard = match slot.lock() { Ok(g) => g, Err(_) => return INTERNAL_ERROR };
    match guard.as_mut() { Some(db) => f(db), None => INVALID_HANDLE }
}
fn status(error: Error) -> i32 {
    match error {
        Error::InvalidNamespace | Error::InvalidPath => INVALID_ARGUMENT,
        Error::ForeignDatabase | Error::InvalidSchema | Error::UnsupportedSchema(_) => SCHEMA_ERROR,
        Error::Sqlite(_) => STORAGE_ERROR,
    }
}
unsafe fn bytes<'a>(ptr: *const u8, len: usize) -> Result<&'a [u8], i32> {
    if len == 0 { return Ok(&[]); }
    if ptr.is_null() || len > isize::MAX as usize { return Err(INVALID_ARGUMENT); }
    // Caller guarantees a live readable allocation for len bytes during the call.
    Ok(unsafe { std::slice::from_raw_parts(ptr, len) })
}
unsafe fn text<'a>(ptr: *const u8, len: usize) -> Result<&'a str, i32> {
    std::str::from_utf8(unsafe { bytes(ptr, len)? }).map_err(|_| INVALID_ARGUMENT)
}
fn insert(db: Database, out: *mut u64) -> i32 {
    registry(|r| {
        let Some(id) = r.next.checked_add(1) else { return HANDLE_EXHAUSTED; };
        r.next = id;
        r.databases.insert(id, Arc::new(Mutex::new(Some(db))));
        unsafe { out.write(id); }
        OK
    })
}
#[no_mangle]
pub extern "C" fn maddb_abi_version() -> u32 { 1 }

/// # Safety
/// All non-null pointers must satisfy include/maddb.h's lifetime, size and alias rules.
#[no_mangle]
pub unsafe extern "C" fn maddb_open(path: *const u8, path_len: usize, namespace: *const u8, namespace_len: usize, out: *mut u64) -> i32 {
    boundary(|| {
        if out.is_null() { return INVALID_ARGUMENT; }
        unsafe { out.write(0); }
        let path = match unsafe { text(path, path_len) } { Ok(x) => x, Err(e) => return e };
        let namespace = match unsafe { text(namespace, namespace_len) } { Ok(x) => x, Err(e) => return e };
        if path.as_bytes().contains(&0) { return INVALID_ARGUMENT; }
        match Database::open(path, namespace) { Ok(db) => insert(db, out), Err(e) => status(e) }
    })
}
/// # Safety
/// Same pointer requirements as maddb_open; creates real ephemeral SQLite.
#[no_mangle]
pub unsafe extern "C" fn maddb_open_memory(namespace: *const u8, namespace_len: usize, out: *mut u64) -> i32 {
    boundary(|| {
        if out.is_null() { return INVALID_ARGUMENT; }
        unsafe { out.write(0); }
        let namespace = match unsafe { text(namespace, namespace_len) } { Ok(x) => x, Err(e) => return e };
        match Database::in_memory(namespace) { Ok(db) => insert(db, out), Err(e) => status(e) }
    })
}
#[no_mangle]
pub extern "C" fn maddb_close(handle: u64) -> i32 {
    boundary(|| {
        let slot = match lookup(handle, true) { Ok(s) => s, Err(e) => return e };
        let mut guard = match slot.lock() { Ok(g) => g, Err(_) => return INTERNAL_ERROR };
        guard.take();
        OK
    })
}
/// # Safety
/// Read buffers must be valid for their lengths; see include/maddb.h.
#[no_mangle]
pub unsafe extern "C" fn maddb_put(handle: u64, key: *const u8, key_len: usize, value: *const u8, value_len: usize) -> i32 {
    boundary(|| {
        let key = match unsafe { text(key, key_len) } { Ok(x) => x, Err(e) => return e };
        let value = match unsafe { bytes(value, value_len) } { Ok(x) => x, Err(e) => return e };
        with_database(handle, |db| db.put(key, value).map_or_else(status, |_| OK))
    })
}
/// # Safety
/// Output length and buffer must be valid, aligned where needed, and disjoint
/// from each other and input ranges. Null buffer requires zero capacity.
#[no_mangle]
pub unsafe extern "C" fn maddb_get(handle: u64, key: *const u8, key_len: usize, buffer: *mut u8, capacity: usize, out_len: *mut usize) -> i32 {
    boundary(|| {
        if out_len.is_null() { return INVALID_ARGUMENT; }
        unsafe { out_len.write(0); }
        if (buffer.is_null() && capacity != 0) || capacity > isize::MAX as usize { return INVALID_ARGUMENT; }
        let key = match unsafe { text(key, key_len) } { Ok(x) => x, Err(e) => return e };
        with_database(handle, |db| {
            let value = match db.get(key) { Ok(Some(v)) => v, Ok(None) => return NOT_FOUND, Err(e) => return status(e) };
            unsafe { out_len.write(value.len()); }
            if capacity < value.len() { return BUFFER_TOO_SMALL; }
            if !value.is_empty() { unsafe { std::ptr::copy_nonoverlapping(value.as_ptr(), buffer, value.len()); } }
            OK
        })
    })
}
/// # Safety
/// Key must be valid UTF-8 in a live read buffer, or null with zero length.
#[no_mangle]
pub unsafe extern "C" fn maddb_remove(handle: u64, key: *const u8, key_len: usize) -> i32 {
    boundary(|| {
        let key = match unsafe { text(key, key_len) } { Ok(x) => x, Err(e) => return e };
        with_database(handle, |db| db.delete(key).map_or_else(status, |_| OK))
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn panic_is_contained() {
        assert_eq!(boundary(|| panic!("contained test panic")), INTERNAL_ERROR);
    }
    #[test]
    fn separate_handles_do_not_share_operation_lock() {
        let (mut a, mut b) = (0, 0);
        unsafe {
            assert_eq!(maddb_open_memory(b"a".as_ptr(), 1, &mut a), OK);
            assert_eq!(maddb_open_memory(b"b".as_ptr(), 1, &mut b), OK);
        }
        let slot = lookup(a, false).unwrap();
        let guard = slot.lock().unwrap();
        assert_eq!(with_database(b, |_| OK), OK);
        drop(guard);
        assert_eq!(maddb_close(a), OK);
        assert_eq!(maddb_close(b), OK);
    }
}
