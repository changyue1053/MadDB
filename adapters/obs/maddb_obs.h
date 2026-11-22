#ifndef MADDB_OBS_H
#define MADDB_OBS_H
#include "maddb.h"
#include "madobs/observer.h"
/* Optional host-side adapter, no MadDB hooks, allocation, queue or network.
 * Call AFTER the database operation returns, outside all host/database locks.
 * Never use the observation result as a database-operation result or retry cause.
 * Host owns observer/context and serializes unregister with all producer calls.
 * Callback must not block, retain event pointers, throw or reenter the host's
 * operation/report loop. Observer invocation is NOT delivery/persistence proof.
 * No handle, key, value, namespace, path, SQL, size, duration or clock is accepted.
 * Probe/copy reads are separate calls; report only what the host intends to count.
 * Numeric SDK identity is a preview schema constant, not a global registration.
 */
#define MADDB_OBS_SCHEMA_ID UINT32_C(0x4D444201)
#define MADDB_OBS_SCHEMA_VERSION 1u
#define MADDB_OBS_GET 1u
#define MADDB_OBS_PUT 2u
#define MADDB_OBS_REMOVE 3u
#define MADDB_OBS_STATUS_ATTRIBUTE 1u
static inline madobs_emit_result maddb_obs_report_result(
    const madobs_observer_v1 *observer, uint32_t operation, maddb_status status) {
  uint32_t result;
  if (operation != MADDB_OBS_GET && operation != MADDB_OBS_PUT &&
      operation != MADDB_OBS_REMOVE) return MADOBS_INVALID;
  switch (status) {
    case MADDB_OK: result = 0; break;
    case MADDB_NOT_FOUND: result = 1; break;
    case MADDB_BUFFER_TOO_SMALL: result = 2; break;
    case MADDB_INVALID_ARGUMENT: result = 3; break;
    case MADDB_INVALID_HANDLE: result = 4; break;
    case MADDB_STORAGE_ERROR: result = 5; break;
    case MADDB_SCHEMA_ERROR: result = 6; break;
    case MADDB_INTERNAL_ERROR: result = 7; break;
    case MADDB_HANDLE_EXHAUSTED: result = 8; break;
    default: return MADOBS_INVALID;
  }
  if (operation != MADDB_OBS_GET && (status == MADDB_NOT_FOUND || status == MADDB_BUFFER_TOO_SMALL))
    return MADOBS_INVALID;
#ifdef __cplusplus
  madobs_event_v1 event{};
#else
  madobs_event_v1 event = {0};
#endif
  event.struct_size = sizeof(event);
  event.abi_version = MADOBS_ABI_VERSION;
  event.sdk_id = MADDB_OBS_SCHEMA_ID;
  event.sdk_version = MADDB_OBS_SCHEMA_VERSION;
  event.event_id = operation;
  event.severity = status < 0 ? 3u : 1u;
  event.attribute_count = 1;
  event.attributes[0].key = MADDB_OBS_STATUS_ATTRIBUTE;
  event.attributes[0].enum_value = result;
  return madobs_observer_emit(observer, &event);
}
/* Opt-in wrappers preserve the DB return code and all original pointer/ownership
 * contracts. They report only AFTER the actual ABI call returns. Observation
 * failure is deliberately not substituted for the completed database result.
 * Observer callbacks still obey the lifetime/nonreentrancy contract above. */
static inline maddb_status maddb_obs_put(const madobs_observer_v1 *observer,
    maddb_handle handle, const uint8_t *key, size_t key_len,
    const uint8_t *value, size_t value_len) {
  maddb_status status = maddb_put(handle, key, key_len, value, value_len);
  (void)maddb_obs_report_result(observer, MADDB_OBS_PUT, status);
  return status;
}
static inline maddb_status maddb_obs_get(const madobs_observer_v1 *observer,
    maddb_handle handle, const uint8_t *key, size_t key_len,
    uint8_t *buffer, size_t capacity, size_t *out_len) {
  maddb_status status = maddb_get(handle, key, key_len, buffer, capacity, out_len);
  (void)maddb_obs_report_result(observer, MADDB_OBS_GET, status);
  return status;
}
#endif
