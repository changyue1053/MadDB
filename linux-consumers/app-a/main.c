#include <maddb.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) return 1; } while (0)
int main(int argc, char **argv) {
    const uint8_t ns[] = "same.namespace", key[] = "same-key", value[] = {0, 65, 255};
    uint8_t buffer[sizeof value] = {0};
    size_t len = 0;
    maddb_handle handle = 0;
    CHECK(argc == 3 && maddb_abi_version() == 1);
    CHECK(maddb_open((const uint8_t*)argv[1], strlen(argv[1]), ns, sizeof ns-1, &handle) == MADDB_OK);
    int result = 0;
    if (strcmp(argv[2], "write") == 0) {
        CHECK(maddb_get(handle, key, sizeof key-1, buffer, sizeof buffer, &len) == MADDB_NOT_FOUND && len == 0);
        CHECK(maddb_put(handle, key, sizeof key-1, value, sizeof value) == MADDB_OK);
    } else {
        CHECK(strcmp(argv[2], "read") == 0);
        CHECK(maddb_get(handle, key, sizeof key-1, buffer, sizeof buffer, &len) == MADDB_OK);
        CHECK(len == sizeof value);
        if (memcmp(buffer, value, sizeof value) != 0) result = 2;
    }
    CHECK(maddb_close(handle) == MADDB_OK);
    return result;
}
