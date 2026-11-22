#include "maddb_obs.h"
#include <assert.h>
#include <string.h>
/* ABI stubs for wrapper contract tests only. They do not implement SQLite. */
static unsigned wrapper_testing, abi_calls, returned_phase;
static maddb_status stub_status;
static const uint8_t fixture_key[] = {0, 7};
static const uint8_t fixture_value[] = {3, 0, 8};
static uint8_t fixture_buffer[3];
static size_t fixture_len;
maddb_status maddb_put(maddb_handle h, const uint8_t *k, size_t kl, const uint8_t *v, size_t vl) {
  assert(h == 41 && k == fixture_key && kl == 2 && v == fixture_value && vl == 3);
  ++abi_calls; returned_phase = 1; return stub_status;
}
maddb_status maddb_get(maddb_handle h, const uint8_t *k, size_t kl, uint8_t *b, size_t cap, size_t *len) {
  assert(h == 41 && k == fixture_key && kl == 2 && b == fixture_buffer && cap == 3 && len == &fixture_len);
  ++abi_calls;
  if (stub_status == MADDB_OK) { memcpy(b, fixture_value, 3); *len = 3; }
  else { *len = 0; }
  returned_phase = 1; return stub_status;
}
struct recording { unsigned calls; madobs_event_v1 event; };
static void record(void *ctx, const madobs_event_v1 *event) {
  struct recording *r = (struct recording *)ctx;
  if (wrapper_testing) assert(returned_phase == 1);
  ++r->calls; r->event = *event; /* Copy only within callback lifetime. */
}
int main(void) {
  struct recording r;
  memset(&r, 0, sizeof(r));
  madobs_observer_v1 observer = {sizeof(observer), MADOBS_ABI_VERSION, &r, record};
  const maddb_status statuses[] = {MADDB_OK, MADDB_NOT_FOUND, MADDB_BUFFER_TOO_SMALL,
    MADDB_INVALID_ARGUMENT, MADDB_INVALID_HANDLE, MADDB_STORAGE_ERROR,
    MADDB_SCHEMA_ERROR, MADDB_INTERNAL_ERROR, MADDB_HANDLE_EXHAUSTED};
  unsigned i, slot;
  for (i = 0; i < sizeof(statuses)/sizeof(statuses[0]); ++i) {
    assert(maddb_obs_report_result(&observer, MADDB_OBS_GET, statuses[i]) == MADOBS_EMITTED);
    assert(r.event.struct_size == sizeof(r.event) && r.event.abi_version == MADOBS_ABI_VERSION);
    assert(r.event.sdk_id == MADDB_OBS_SCHEMA_ID && r.event.sdk_version == 1);
    assert(r.event.event_id == MADDB_OBS_GET && r.event.attribute_count == 1);
    assert(r.event.attributes[0].key == 1 && r.event.attributes[0].enum_value == i);
    assert(r.event.severity == (statuses[i] < 0 ? 3u : 1u));
    assert(r.event.monotonic_ns == 0 && r.event.reserved == 0);
    for (slot = 1; slot < MADOBS_MAX_ATTRIBUTES; ++slot)
      assert(r.event.attributes[slot].key == 0 && r.event.attributes[slot].enum_value == 0);
  }
  assert(maddb_obs_report_result(&observer, MADDB_OBS_PUT, MADDB_OK) == MADOBS_EMITTED);
  assert(maddb_obs_report_result(&observer, MADDB_OBS_REMOVE, MADDB_OK) == MADOBS_EMITTED);
  unsigned before = r.calls;
  assert(maddb_obs_report_result(&observer, 99, MADDB_OK) == MADOBS_INVALID);
  assert(maddb_obs_report_result(&observer, MADDB_OBS_GET, 99) == MADOBS_INVALID);
  assert(maddb_obs_report_result(&observer, MADDB_OBS_PUT, MADDB_NOT_FOUND) == MADOBS_INVALID);
  assert(maddb_obs_report_result(&observer, MADDB_OBS_REMOVE, MADDB_BUFFER_TOO_SMALL) == MADOBS_INVALID);
  assert(maddb_obs_report_result(NULL, MADDB_OBS_GET, MADDB_OK) == MADOBS_NOOP);
  madobs_observer_v1 noop = madobs_noop_observer();
  assert(maddb_obs_report_result(&noop, MADDB_OBS_GET, MADDB_OK) == MADOBS_NOOP);
  observer.abi_version = 999;
  assert(maddb_obs_report_result(&observer, MADDB_OBS_GET, MADDB_OK) == MADOBS_INVALID);
  assert(r.calls == before);
  observer.abi_version = MADOBS_ABI_VERSION;
  wrapper_testing = 1;
  for (i = 0; i < sizeof(statuses)/sizeof(statuses[0]); ++i) {
    stub_status = statuses[i]; returned_phase = 0;
    unsigned calls = abi_calls;
    assert(maddb_obs_get(&observer, 41, fixture_key, 2, fixture_buffer, 3, &fixture_len) == stub_status);
    assert(abi_calls == calls + 1 && returned_phase == 1);
    assert(fixture_len == (stub_status == MADDB_OK ? 3u : 0u));
    if (stub_status == MADDB_OK) assert(memcmp(fixture_buffer, fixture_value, 3) == 0);
  }
  stub_status = MADDB_STORAGE_ERROR; returned_phase = 0;
  assert(maddb_obs_put(&observer, 41, fixture_key, 2, fixture_value, 3) == MADDB_STORAGE_ERROR);
  observer.abi_version = 999; stub_status = MADDB_OK; returned_phase = 0;
  /* Invalid observer cannot turn a committed success into a database failure. */
  assert(maddb_obs_put(&observer, 41, fixture_key, 2, fixture_value, 3) == MADDB_OK);
  assert(maddb_obs_put(NULL, 41, fixture_key, 2, fixture_value, 3) == MADDB_OK);
  return 0;
}
