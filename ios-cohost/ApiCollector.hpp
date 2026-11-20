#pragma once
#include <array>
#include <cstddef>
#include <madobs/privacy.h>

namespace cohost_api {
inline constexpr uint32_t db_sdk=0x43444201, link_sdk=0x434c4b01;
enum class Item { connecting,connected,put,get,reopen,closed,invalid };
struct Collector {
    madobs_event_rule_v1 rules[2]{};
    madobs_privacy_policy_v1 policy{sizeof(policy),MADOBS_ABI_VERSION,2,rules};
    std::array<Item,6> receipt{};
    std::size_t count=0;
    bool excluded=false, invalid=false;
    Collector() {
        configure(rules[0],db_sdk,{1,2,3});
        configure(rules[1],link_sdk,{1,2,4});
    }
    Collector(const Collector&)=delete;
    Collector& operator=(const Collector&)=delete;

    static void configure(madobs_event_rule_v1 &r,uint32_t sdk,const uint32_t (&values)[3]) {
        r.sdk_id=sdk;r.sdk_version=1;r.event_id=1;r.max_severity=1;
        r.attribute_count=1;r.attributes[0].key=1;r.attributes[0].value_count=3;
        for (unsigned i=0;i<3;++i) r.attributes[0].values[i]=values[i];
    }
    static bool canonical(const madobs_event_v1 &e) {
        if (e.struct_size!=sizeof(e) || e.abi_version!=MADOBS_ABI_VERSION ||
            e.sdk_version!=1 || e.severity!=1 || e.monotonic_ns || e.reserved ||
            e.attribute_count!=1 || e.attributes[0].key!=1) return false;
        for (unsigned i=1;i<MADOBS_MAX_ATTRIBUTES;++i)
            if (e.attributes[i].key || e.attributes[i].enum_value) return false;
        return true;
    }
    static Item classify(const madobs_event_v1 &e) {
        if (!canonical(e) || e.event_id!=1) return Item::invalid;
        const auto value=e.attributes[0].enum_value;
        if (e.sdk_id==db_sdk) {
            if (value==1) return Item::put;
            if (value==2) return Item::get;
            if (value==3) return Item::reopen;
        }
        if (e.sdk_id==link_sdk) {
            if (value==1) return Item::connecting;
            if (value==2) return Item::connected;
            if (value==4) return Item::closed;
        }
        return Item::invalid;
    }
    static void record(void *context,const madobs_event_v1 *event) noexcept {
        auto &self=*static_cast<Collector*>(context);
        const auto id=event?classify(*event):Item::invalid;
        if (id==Item::invalid || self.count==self.receipt.size()) {
            self.invalid=true;return;
        }
        self.receipt[self.count++]=id;
    }
    bool report(uint32_t sdk,uint32_t id,uint32_t value) {
        madobs_event_v1 e{},safe{};
        e.struct_size=sizeof(e);e.abi_version=MADOBS_ABI_VERSION;
        e.sdk_id=sdk;e.sdk_version=1;e.event_id=id;e.severity=1;e.attribute_count=1;
        e.attributes[0]={1,value};
        const auto admission=madobs_sanitize_event(&policy,&e,&safe);
        if (sdk==db_sdk && id==2 && value==4) {
            // A legitimate remove is excluded. Never call local sink on rejection.
            if (admission!=MADOBS_INVALID || excluded || count!=receipt.size()) {
                invalid=true;return false;
            }
            excluded=true;return true;
        }
        if (admission!=MADOBS_EMITTED || classify(e)==Item::invalid ||
            classify(e)!=classify(safe) || excluded) {invalid=true;return false;}
        const madobs_observer_v1 observer{sizeof(observer),MADOBS_ABI_VERSION,this,record};
        const auto before=count;
        return madobs_observer_emit(&observer,&safe)==MADOBS_EMITTED && !invalid && count==before+1;
    }
    bool exact() const {
        constexpr std::array<Item,6> expected{Item::connecting,Item::connected,
                                             Item::put,Item::get,Item::closed,Item::reopen};
        return !invalid && excluded && count==expected.size() && receipt==expected;
    }
};
}
