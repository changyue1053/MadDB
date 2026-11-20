#include "ApiCollector.hpp"
#include <cstdlib>
using namespace cohost_api;
#define CHECK(expr) do { if (!(expr)) std::exit(1); } while (0)
static bool sequence(Collector &c) {
    return c.report(link_sdk,1,1) && c.report(link_sdk,1,2) &&
           c.report(db_sdk,1,1) && c.report(db_sdk,1,2) &&
           c.report(link_sdk,1,4) && c.report(db_sdk,1,3);
}
int main() {
    Collector c;
    CHECK(sequence(c) && !c.exact());
    CHECK(c.report(db_sdk,2,4) && c.exact() && c.count==6);
    CHECK(!c.report(db_sdk,2,4) && !c.exact());

    Collector early;
    CHECK(!early.report(db_sdk,2,4) && !early.exact() && early.count==0);
    Collector bad;
    CHECK(!bad.report(db_sdk,1,4) && !bad.exact() && bad.count==0);
    Collector overflow;
    CHECK(sequence(overflow) && !overflow.report(db_sdk,1,3) && overflow.count==6);

    madobs_event_v1 draft{};
    draft.struct_size=sizeof(draft);draft.abi_version=MADOBS_ABI_VERSION;
    draft.sdk_id=db_sdk;draft.sdk_version=1;draft.event_id=1;draft.severity=1;
    draft.attribute_count=1;draft.attributes[0]={1,1};
    CHECK(Collector::classify(draft)==Item::put);
    draft.monotonic_ns=1;
    CHECK(Collector::classify(draft)==Item::invalid);
    draft.monotonic_ns=0;draft.attributes[7].key=1;
    CHECK(Collector::classify(draft)==Item::invalid);
    return 0;
}
