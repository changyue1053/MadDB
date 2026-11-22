#include <maddb.h>
#include <stdio.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) return 1; } while (0)
static const uint8_t ns[] = "same.namespace", key[] = "same-key";
static const uint8_t value[] = {0, 65, 255}, replacement[] = {0, 67, 254};
static const uint8_t refused[] = {0, 68, 253};

static int has_value(maddb_handle handle, const uint8_t *expected) {
    uint8_t buffer[sizeof value] = {0};
    size_t len = 0;
    return maddb_get(handle, key, sizeof key-1, buffer, sizeof buffer, &len) == MADDB_OK
        && len == sizeof buffer && memcmp(buffer, expected, sizeof buffer) == 0;
}

static int handshake(const char *signal, const char *command) {
    char line[16] = {0};
    return puts(signal) >= 0 && fflush(stdout) == 0
        && fgets(line, sizeof line, stdin) && strcmp(line, command) == 0;
}

static int lock_recovery(maddb_handle handle) {
    size_t len = 1;
    CHECK(maddb_get(handle, key, sizeof key-1, NULL, 0, &len) == MADDB_NOT_FOUND && len == 0);
    CHECK(maddb_put(handle, key, sizeof key-1, value, sizeof value) == MADDB_OK);
    CHECK(handshake("ready", "locked\n"));
    CHECK(has_value(handle, value));
    CHECK(maddb_put(handle, key, sizeof key-1, refused, sizeof refused) == MADDB_STORAGE_ERROR);
    CHECK(has_value(handle, value));
    CHECK(handshake("rejected", "released\n"));
    CHECK(has_value(handle, value));
    CHECK(maddb_put(handle, key, sizeof key-1, replacement, sizeof replacement) == MADDB_OK);
    CHECK(has_value(handle, replacement));
    return 0;
}

int main(int argc, char **argv) {
    uint8_t buffer[sizeof value] = {0};
    size_t len = 0;
    maddb_handle handle = 0;
    CHECK(argc == 3 && maddb_abi_version() == 1);
    CHECK(maddb_open((const uint8_t*)argv[1], strlen(argv[1]), ns, sizeof ns-1, &handle) == MADDB_OK);
    int result = 0;
    if (strcmp(argv[2], "write") == 0) {
        CHECK(maddb_get(handle, key, sizeof key-1, buffer, sizeof buffer, &len) == MADDB_NOT_FOUND && len == 0);
        CHECK(maddb_put(handle, key, sizeof key-1, value, sizeof value) == MADDB_OK);
    } else if (strcmp(argv[2], "lock-recovery") == 0) {
        result = lock_recovery(handle);
    } else if (strcmp(argv[2], "read-replacement") == 0) {
        result = has_value(handle, replacement) ? 0 : 1;
    } else {
        CHECK(strcmp(argv[2], "read") == 0);
        CHECK(maddb_get(handle, key, sizeof key-1, buffer, sizeof buffer, &len) == MADDB_OK);
        CHECK(len == sizeof value);
        if (memcmp(buffer, value, sizeof value) != 0) result = 2;
    }
    CHECK(maddb_close(handle) == MADDB_OK);
    return result;
}
