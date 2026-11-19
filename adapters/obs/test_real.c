/* Real SQLite dispatch test: no madDB ABI stubs or replacement implementation. */
#include "maddb_obs.h"
#include <assert.h>
#include <string.h>
struct sink { unsigned count; madobs_event_v1 last; };
static void record(void *ctx, const madobs_event_v1 *event) {
  struct sink *sink = (struct sink *)ctx;
  ++sink->count; sink->last = *event;
}
static void expect(struct sink *s, unsigned count, uint32_t operation, uint32_t status) {
  assert(s->count == count && s->last.event_id == operation);
  assert(s->last.sdk_id == MADDB_OBS_SCHEMA_ID && s->last.attribute_count == 1);
  assert(s->last.attributes[0].key == 1 && s->last.attributes[0].enum_value == status);
  assert(s->last.monotonic_ns == 0);
}
int main(void) {
  struct sink sink = {0};
  madobs_observer_v1 observer = {sizeof(observer), MADOBS_ABI_VERSION, &sink, record};
  maddb_handle handle = 0;
  const uint8_t ns[] = "synthetic", key[] = "key", empty[] = "empty", missing[] = "absent";
  const uint8_t value[] = {0, 255, 7};
  uint8_t buffer[3] = {42, 42, 42};
  size_t len = 999;
  assert(maddb_abi_version() == 1);
  assert(maddb_open_memory(ns, sizeof(ns)-1, &handle) == MADDB_OK && handle != 0);
  assert(maddb_obs_put(&observer, handle, key, sizeof(key)-1, value, sizeof(value)) == MADDB_OK);
  expect(&sink, 1, MADDB_OBS_PUT, 0);
  assert(maddb_obs_get(&observer, handle, key, sizeof(key)-1, NULL, 0, &len) == MADDB_BUFFER_TOO_SMALL && len == 3);
  expect(&sink, 2, MADDB_OBS_GET, 2);
  assert(maddb_obs_get(&observer, handle, key, sizeof(key)-1, buffer, 2, &len) == MADDB_BUFFER_TOO_SMALL && len == 3);
  assert(buffer[0] == 42 && buffer[1] == 42 && buffer[2] == 42);
  expect(&sink, 3, MADDB_OBS_GET, 2);
  assert(maddb_obs_get(&observer, handle, key, sizeof(key)-1, buffer, sizeof(buffer), &len) == MADDB_OK);
  assert(len == 3 && memcmp(buffer, value, 3) == 0);
  expect(&sink, 4, MADDB_OBS_GET, 0);
  assert(maddb_obs_get(&observer, handle, missing, sizeof(missing)-1, buffer, 3, &len) == MADDB_NOT_FOUND && len == 0);
  expect(&sink, 5, MADDB_OBS_GET, 1);
  assert(maddb_obs_put(&observer, handle, empty, sizeof(empty)-1, NULL, 0) == MADDB_OK);
  expect(&sink, 6, MADDB_OBS_PUT, 0);
  assert(maddb_obs_get(&observer, handle, empty, sizeof(empty)-1, NULL, 0, &len) == MADDB_OK && len == 0);
  expect(&sink, 7, MADDB_OBS_GET, 0);
  /* Invalid observer must not change successful DB mutation or returned data. */
  observer.abi_version = 999;
  assert(maddb_obs_put(&observer, handle, key, sizeof(key)-1, NULL, 0) == MADDB_OK);
  assert(sink.count == 7);
  assert(maddb_get(handle, key, sizeof(key)-1, NULL, 0, &len) == MADDB_OK && len == 0);
  assert(maddb_remove(handle, key, sizeof(key)-1) == MADDB_OK);
  observer.abi_version = MADOBS_ABI_VERSION;
  assert(maddb_obs_get(&observer, handle, key, sizeof(key)-1, buffer, 3, &len) == MADDB_NOT_FOUND && len == 0);
  expect(&sink, 8, MADDB_OBS_GET, 1);
  assert(maddb_close(handle) == MADDB_OK);
  assert(maddb_obs_get(&observer, handle, key, sizeof(key)-1, buffer, 3, &len) == MADDB_INVALID_HANDLE && len == 0);
  expect(&sink, 9, MADDB_OBS_GET, 4);
  return 0;
}
