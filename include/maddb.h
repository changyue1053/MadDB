#ifndef MADDB_H
#define MADDB_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* ABI v1: opaque process-local tokens, not pointers. Never persist/share across
 * processes or separately loaded copies of the library. Zero is invalid.
 * Close each successful open exactly once. Stale/double-close tokens are rejected
 * and never reused in a loaded library. No calls after unloading the library.
 * Each handle serializes its operations with its own mutex. Registry lookup holds
 * a short global lock, never during SQLite operations. Close removes the token,
 * then waits for the slot lock and clears its database. A previously looked-up
 * call that wins the slot lock can finish before close; otherwise it sees the
 * cleared slot and returns INVALID_HANDLE. Calls after token removal are rejected.
 * Host still synchronizes its own buffers. Do not call from signal handlers.
 *
 * All byte strings are length-delimited, NOT NUL-terminated. Paths, namespaces and
 * keys require UTF-8; keys may contain NUL. Values are arbitrary binary bytes.
 * Null input is allowed only with length 0. Paths cannot contain NUL; open rejects
 * empty paths, :memory: and file: URIs. Use open_memory explicitly for ephemeral DB.
 *
 * Caller owns all buffers. Non-null pointers must reference live allocations of
 * stated size; outputs must be writable and naturally aligned. Output ranges
 * must not overlap inputs or each other. Invalid non-null pointers cannot be
 * detected and violate this contract (undefined behavior). Lengths/capacities
 * above PTRDIFF_MAX are rejected. Inputs are borrowed only during the call.
 *
 * out_handle is required and set to 0 on failure; successful open transfers a
 * handle requiring close. No Rust allocations are returned to the caller.
 * get requires out_len, resets it to 0 on errors/not-found, and reports required
 * size on OK/BUFFER_TOO_SMALL. No partial copy: output buffer remains unchanged
 * unless status is OK, which copies exactly out_len bytes with no terminator.
 * A null buffer and zero capacity probes size: empty -> OK/0, absent -> NOT_FOUND/0,
 * nonempty -> BUFFER_TOO_SMALL/required. Probe/copy are separate reads, not a
 * snapshot; concurrent changes may require retry or return different data.
 * remove is idempotent: missing keys return OK.
 *
 * Rust unwind panics become INTERNAL_ERROR; a poisoned handle/registry fails closed.
 * Process abort/OOM, invalid pointers, and platform faults cannot be recovered.
 * Plaintext SQLite only; this ABI does not add encryption or an app sandbox.
 */
typedef uint64_t maddb_handle;
typedef int32_t maddb_status;
#define MADDB_OK ((maddb_status)0)
#define MADDB_NOT_FOUND ((maddb_status)1)
#define MADDB_BUFFER_TOO_SMALL ((maddb_status)2)
#define MADDB_INVALID_ARGUMENT ((maddb_status)-1)
#define MADDB_INVALID_HANDLE ((maddb_status)-2)
#define MADDB_STORAGE_ERROR ((maddb_status)-3)
#define MADDB_SCHEMA_ERROR ((maddb_status)-4)
#define MADDB_INTERNAL_ERROR ((maddb_status)-5)
#define MADDB_HANDLE_EXHAUSTED ((maddb_status)-6)
uint32_t maddb_abi_version(void);
maddb_status maddb_open(const uint8_t *path, size_t path_len, const uint8_t *ns, size_t ns_len, maddb_handle *out_handle);
maddb_status maddb_open_memory(const uint8_t *ns, size_t ns_len, maddb_handle *out_handle);
maddb_status maddb_close(maddb_handle handle);
maddb_status maddb_put(maddb_handle handle, const uint8_t *key, size_t key_len, const uint8_t *value, size_t value_len);
maddb_status maddb_get(maddb_handle handle, const uint8_t *key, size_t key_len, uint8_t *buffer, size_t capacity, size_t *out_len);
maddb_status maddb_remove(maddb_handle handle, const uint8_t *key, size_t key_len);
#ifdef __cplusplus
}
#endif
#endif
