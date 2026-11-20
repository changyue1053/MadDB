#ifndef MADDB_COHOST_BRIDGE_H
#define MADDB_COHOST_BRIDGE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Sample-only owner-thread API. No user input, SDK object or telemetry bytes. */
void *mco_open(const char *scratch);
int32_t mco_send(void *state, uint32_t expected_total);
int32_t mco_close_link(void *state);
int32_t mco_db_report(void *state, uint32_t operation);
int32_t mco_finish(void *state, int32_t verify);
#ifdef __cplusplus
}
#endif
#endif
