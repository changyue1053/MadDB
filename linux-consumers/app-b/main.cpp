#include <maddb.h>
#include <array>
#include <cstring>
#include <string_view>

int main(int argc, char **argv) {
    if (argc != 3 || maddb_abi_version() != 1) return 1;
    constexpr uint8_t ns[] = "same.namespace", key[] = "same-key";
    constexpr std::array<uint8_t, 3> value{0, 66, 128};
    std::array<uint8_t, value.size()> buffer{};
    size_t len = 0;
    maddb_handle handle = 0;
    if (maddb_open(reinterpret_cast<const uint8_t*>(argv[1]), std::strlen(argv[1]),
                   ns, sizeof ns-1, &handle) != MADDB_OK) return 1;
    const std::string_view phase(argv[2]);
    int result = 1;
    if (phase == "write") {
        if (maddb_get(handle, key, sizeof key-1, buffer.data(), buffer.size(), &len) == MADDB_NOT_FOUND
            && len == 0 && maddb_put(handle, key, sizeof key-1, value.data(), value.size()) == MADDB_OK) result = 0;
    } else if (phase == "read") {
        if (maddb_get(handle, key, sizeof key-1, buffer.data(), buffer.size(), &len) == MADDB_OK
            && len == value.size()) result = buffer == value ? 0 : 2;
    }
    return maddb_close(handle) == MADDB_OK ? result : 1;
}
