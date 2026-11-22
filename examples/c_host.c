#include "maddb.h"
#include <assert.h>
#include <string.h>

int main(int argc, char **argv) {
    assert(argc == 2); /* Test runner supplies a fresh temporary file path. */
    const uint8_t ns[] = "c-host";
    const uint8_t key[] = {'k', 0, 'x'};
    const uint8_t value[] = {0, 255, 128, 42};
    maddb_handle h = 0;
    size_t n = 99;
    uint8_t out[6] = {7,7,7,7,7,7};
    assert(maddb_abi_version() == 1);
    assert(maddb_open((const uint8_t *)argv[1], strlen(argv[1]), ns, sizeof(ns)-1, &h) == MADDB_OK);
    assert(h != 0);
    assert(maddb_get(h, key, sizeof(key), NULL, 0, &n) == MADDB_NOT_FOUND && n == 0);
    assert(maddb_put(h, key, sizeof(key), value, sizeof(value)) == MADDB_OK);
    assert(maddb_close(h) == MADDB_OK);
    assert(maddb_close(h) == MADDB_INVALID_HANDLE);
    assert(maddb_open((const uint8_t *)argv[1], strlen(argv[1]), ns, sizeof(ns)-1, &h) == MADDB_OK);
    assert(maddb_get(h, key, sizeof(key), NULL, 0, &n) == MADDB_BUFFER_TOO_SMALL && n == 4);
    assert(maddb_get(h, key, sizeof(key), out, 3, &n) == MADDB_BUFFER_TOO_SMALL && n == 4);
    for (size_t i = 0; i < sizeof(out); ++i) assert(out[i] == 7);
    assert(maddb_get(h, key, sizeof(key), out, sizeof(out), &n) == MADDB_OK && n == 4);
    assert(memcmp(value, out, 4) == 0 && out[4] == 7 && out[5] == 7);
    assert(maddb_put(h, key, sizeof(key), NULL, 0) == MADDB_OK);
    assert(maddb_get(h, key, sizeof(key), NULL, 0, &n) == MADDB_OK && n == 0);
    assert(maddb_remove(h, key, sizeof(key)) == MADDB_OK);
    assert(maddb_remove(h, key, sizeof(key)) == MADDB_OK);
    assert(maddb_get(h, key, sizeof(key), NULL, 0, &n) == MADDB_NOT_FOUND && n == 0);
    assert(maddb_close(h) == MADDB_OK);
    assert(maddb_remove(h, key, sizeof(key)) == MADDB_INVALID_HANDLE);
    h = 99;
    assert(maddb_open_memory(NULL, 1, &h) == MADDB_INVALID_ARGUMENT && h == 0);
    assert(maddb_open_memory(ns, sizeof(ns)-1, &h) == MADDB_OK);
    assert(maddb_close(h) == MADDB_OK);
    return 0;
}
