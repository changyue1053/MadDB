#![cfg(feature = "c-api")]
use maddb::ffi::*;
use std::ptr::{null, null_mut};

#[test]
fn binary_copy_empty_missing_and_lifecycle() { unsafe {
    assert_eq!(maddb_abi_version(), 1);
    let mut h = 0;
    assert_eq!(maddb_open_memory(b"app".as_ptr(), 3, &mut h), OK);
    assert_ne!(h, 0);
    let key = b"k\0x";
    let mut n = 99;
    assert_eq!(maddb_get(h, key.as_ptr(), key.len(), null_mut(), 0, &mut n), NOT_FOUND);
    assert_eq!(n, 0);
    let value = [0, 255, 128, 1];
    assert_eq!(maddb_put(h, key.as_ptr(), key.len(), value.as_ptr(), value.len()), OK);
    assert_eq!(maddb_get(h, key.as_ptr(), key.len(), null_mut(), 0, &mut n), BUFFER_TOO_SMALL);
    assert_eq!(n, 4);
    let mut output = [77; 6];
    assert_eq!(maddb_get(h, key.as_ptr(), key.len(), output.as_mut_ptr(), 3, &mut n), BUFFER_TOO_SMALL);
    assert_eq!(output, [77; 6]);
    assert_eq!(maddb_get(h, key.as_ptr(), key.len(), output.as_mut_ptr(), output.len(), &mut n), OK);
    assert_eq!(output, [0,255,128,1,77,77]);
    assert_eq!(maddb_put(h, key.as_ptr(), key.len(), null(), 0), OK);
    assert_eq!(maddb_get(h, key.as_ptr(), key.len(), null_mut(), 0, &mut n), OK);
    assert_eq!(n, 0);
    assert_eq!(maddb_remove(h, key.as_ptr(), key.len()), OK);
    assert_eq!(maddb_remove(h, key.as_ptr(), key.len()), OK);
    assert_eq!(maddb_close(h), OK);
    assert_eq!(maddb_close(h), INVALID_HANDLE);
    assert_eq!(maddb_get(h, null(), 0, null_mut(), 0, &mut n), INVALID_HANDLE);
    let mut other = 0;
    assert_eq!(maddb_open_memory(b"app".as_ptr(), 3, &mut other), OK);
    assert_ne!(h, other);
    assert_eq!(maddb_close(other), OK);
} }

#[test]
fn argument_failures_reset_outputs() { unsafe {
    let mut h = 99;
    assert_eq!(maddb_open_memory(null(), 1, &mut h), INVALID_ARGUMENT);
    assert_eq!(h, 0);
    assert_eq!(maddb_open_memory(b"app".as_ptr(), 3, null_mut()), INVALID_ARGUMENT);
    assert_eq!(maddb_open(b":memory:".as_ptr(), 8, b"app".as_ptr(), 3, &mut h), INVALID_ARGUMENT);
    assert_eq!(maddb_open(b"a\0b".as_ptr(), 3, b"app".as_ptr(), 3, &mut h), INVALID_ARGUMENT);
    assert_eq!(maddb_open_memory(b"app".as_ptr(), 3, &mut h), OK);
    let invalid = [255];
    assert_eq!(maddb_put(h, invalid.as_ptr(), 1, null(), 0), INVALID_ARGUMENT);
    assert_eq!(maddb_put(h, null(), 0, null(), 1), INVALID_ARGUMENT);
    assert_eq!(maddb_put(h, b"k".as_ptr(), usize::MAX, null(), 0), INVALID_ARGUMENT);
    let mut n = 99;
    assert_eq!(maddb_get(h, null(), 0, null_mut(), 1, &mut n), INVALID_ARGUMENT);
    assert_eq!(n, 0);
    assert_eq!(maddb_get(h, null(), 0, null_mut(), 0, null_mut()), INVALID_ARGUMENT);
    assert_eq!(maddb_close(h), OK);
} }

#[test]
fn concurrent_close_and_calls_are_serialized() { unsafe {
    let mut h = 0;
    assert_eq!(maddb_open_memory(b"app".as_ptr(), 3, &mut h), OK);
    let worker = std::thread::spawn(move || {
        for _ in 0..64 {
            let code = maddb_put(h, b"k".as_ptr(), 1, b"v".as_ptr(), 1);
            assert!(code == OK || code == INVALID_HANDLE);
        }
    });
    assert_eq!(maddb_close(h), OK);
    worker.join().unwrap();
    assert_eq!(maddb_remove(h, null(), 0), INVALID_HANDLE);
} }
