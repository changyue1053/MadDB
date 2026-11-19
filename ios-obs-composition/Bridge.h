#ifndef MADDB_TEST_OBS_BRIDGE_H
#define MADDB_TEST_OBS_BRIDGE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Test-only pointer. Single producer; finish after all Swift operations. */
void *maddb_test_obs_begin(const char *fresh_wal);
/* Only typed synthetic outcomes: 1 put-success, 2 get-present, 3 get-missing.
 * No DB handle/key/value/path/SQL crosses this reporting boundary. */
int32_t maddb_test_obs_report(void *state, uint32_t outcome);
int32_t maddb_test_obs_finish(void *state);
#ifdef __cplusplus
}
#endif
#endif
