#include "collector.hpp"
#include <cstdlib>
using cohost_api::Collector;
using cohost_api::Event;
#define CHECK(x) do { if (!(x)) std::exit(1); } while (0)

static madobs_event_v1 event(uint32_t sdk,uint32_t id,uint32_t result) {
    madobs_event_v1 out{};
    out.struct_size=sizeof(out);out.abi_version=MADOBS_ABI_VERSION;
    out.sdk_id=sdk;out.sdk_version=1;out.event_id=id;out.severity=1;
    out.attribute_count=1;out.attributes[0]={1,result};
    return out;
}
int main() {
    auto connecting=event(0x4d4c,1,1), connected=event(0x4d4c,1,2), closed=event(0x4d4c,1,4);
    auto put=event(0x4D444201,2,0), get=event(0x4D444201,1,0), remove=event(0x4D444201,3,0);
    Collector c;
    const auto port=c.port();
    for (const auto *e : {&connecting,&connected,&put,&get,&closed,&get})
        CHECK(madobs_observer_emit(&port,e)==MADOBS_EMITTED);
    CHECK(!c.exact());
    CHECK(madobs_observer_emit(&port,&remove)==MADOBS_EMITTED);
    CHECK(c.exact() && c.count==6);
    CHECK(madobs_observer_emit(&port,&get)==MADOBS_EMITTED && !c.exact() && c.count==6);
    Collector duplicate;
    Collector::record(&duplicate,&remove); Collector::record(&duplicate,&remove);
    CHECK(duplicate.invalid && duplicate.count==0);
    for (unsigned kind=0;kind<9;++kind) {
        auto bad=get;
        switch (kind) {
            case 0: bad.struct_size--; break;
            case 1: bad.abi_version++; break;
            case 2: bad.monotonic_ns=1; break;
            case 3: bad.severity=3; break;
            case 4: bad.reserved=1; break;
            case 5: bad.attributes[0].enum_value=1; break;
            case 6: bad.attributes[7].key=1; break;
            case 7: bad.sdk_version=2; break;
            case 8: bad.attributes[0].key=2; break;
        }
        CHECK(cohost_api::classify(&bad)==Event::invalid);
    }
    CHECK(cohost_api::classify(nullptr)==Event::invalid);
    return 0;
}
