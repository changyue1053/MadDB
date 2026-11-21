#include "JournalBridge.h"
#include "core/journal/journal.h"
#include <TargetConditionals.h>
#include <sys/stat.h>

#if !TARGET_OS_IOS || !TARGET_OS_SIMULATOR || !defined(__arm64__)
#error "Requires ARM64 iOS Simulator"
#endif

using immd::Journal;
static constexpr char key[] = "fixed";

void *ds_journal_open(const char *file) {
    if (!file) return nullptr;
    auto opened = Journal::open(file, immd::JournalDurability::Full);
    return opened.ok() ? opened.value().release() : nullptr;
}
bool ds_journal_value(void *journal, int64_t expected) {
    if (!journal) return false;
    auto rows = static_cast<Journal *>(journal)->load_all();
    return rows.ok() && rows.value().size() == 1 && rows.value()[0].task_id == key &&
        rows.value()[0].kind == immd::TaskKind::Upload &&
        rows.value()[0].state == immd::TaskState::Queued && rows.value()[0].bytes_done == expected;
}
bool ds_journal_put(void *journal, int64_t value) {
    if (!journal) return false;
    immd::TaskRecord row{};
    row.task_id = key;
    row.kind = immd::TaskKind::Upload;
    row.state = immd::TaskState::Queued;
    row.bytes_done = value;
    return !static_cast<Journal *>(journal)->save(row);
}
void ds_journal_close(void *journal) {
    delete static_cast<Journal *>(journal);
}
bool ds_distinct_regular_files(const char *first, const char *second) {
    struct stat a{}, b{};
    return first && second && lstat(first, &a) == 0 && lstat(second, &b) == 0 &&
        S_ISREG(a.st_mode) && S_ISREG(b.st_mode) &&
        (a.st_dev != b.st_dev || a.st_ino != b.st_ino);
}
