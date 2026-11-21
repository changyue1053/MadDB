#pragma once
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
void *ds_journal_open(const char *file);
bool ds_journal_value(void *journal, int64_t expected);
bool ds_journal_put(void *journal, int64_t value);
void ds_journal_close(void *journal);
bool ds_distinct_regular_files(const char *first, const char *second);

#ifdef __cplusplus
}
#endif
