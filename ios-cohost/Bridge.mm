#include "Bridge.h"
#include <MadLink/madlink_c.h>
#include <new>
#if COHOST_OBS
#include <atomic>
#include <madobs/runtime.h>
#elif COHOST_OBS_API
#include "ApiCollector.hpp"
static_assert(ML_CONNECTING==1 && ML_CONNECTED==2 && ML_CLOSED==4);
#endif

namespace {
constexpr uint8_t wire_byte=19;
struct Session {
    ml_client *link=nullptr;
    uint64_t generation=0;
    bool ready=false;
    unsigned writes=0;
#if COHOST_OBS
    madobs_handle_t observer=0;
    unsigned db=0, link_states=0, rejected=0;
    std::atomic<unsigned> batches{0}, unsafe{0};
    madobs_event_rule_v1 rules[2]{};
    madobs_privacy_policy_v1 policy{sizeof(policy),MADOBS_ABI_VERSION,2,rules};
#elif COHOST_OBS_API
    cohost_api::Collector collector;
#endif
};
void begin(void *ctx,const char*,uint64_t generation) {
    auto &s=*static_cast<Session*>(ctx);s.generation=generation;s.ready=true;
}
void close_wire(void*) {}
int32_t poll(void *ctx,ml_wire_event_v1 *event) {
    auto &s=*static_cast<Session*>(ctx);
    if (!s.ready) return 0;
    s.ready=false;event->generation=s.generation;event->kind=ML_WIRE_CONNECTED;return 1;
}
int32_t write(void *ctx,const uint8_t *bytes,uint64_t length) {
    auto &s=*static_cast<Session*>(ctx);
    if (length!=1 || !bytes || bytes[0]!=wire_byte) return ML_WRITE_FAILED;
    ++s.writes;return ML_WRITE_ACCEPTED;
}
uint64_t zero(void*) { return 0; }
#if COHOST_OBS
constexpr uint32_t db_sdk=0x43444201, link_sdk=0x434c4b01;
void rule(madobs_event_rule_v1 &r,uint32_t sdk,const uint32_t (&values)[3]) {
    r.sdk_id=sdk;r.sdk_version=1;r.event_id=1;r.max_severity=1;
    r.attribute_count=1;r.attributes[0].key=1;r.attributes[0].value_count=3;
    for (unsigned i=0;i<3;++i) r.attributes[0].values[i]=values[i];
}
void discard(void *ctx,uint8_t priority,uint64_t,const uint8_t *data,size_t size,
             madobs_send_done_fn done,void *dc) {
    auto &s=*static_cast<Session*>(ctx);
    const bool valid=s.batches.fetch_add(1)<16 && priority<=2 && data && size && size<=1024*1024 &&
        madobs_check_private_batch(data,size,&s.policy)==MADOBS_PRIVATE_BATCH_OK;
    if (!valid) ++s.unsafe;
    done(dc,valid?1:0);
}
bool observe(Session &s,uint32_t sdk,uint32_t event_id,uint32_t value) {
    madobs_event_v1 event{},clean{};
    event.struct_size=sizeof(event);event.abi_version=MADOBS_ABI_VERSION;
    event.sdk_id=sdk;event.sdk_version=1;event.event_id=event_id;event.severity=1;
    event.attribute_count=1;event.attributes[0]={1,value};
    if (madobs_sanitize_event(&s.policy,&event,&clean)!=MADOBS_EMITTED) {
        if (sdk!=db_sdk || event_id!=2) return false;
        ++s.rejected;return true; // no admission call after sanitizer rejection
    }
    // The raw runtime is not the privacy boundary. Fail if sanitization removed
    // any field this adapter expected to be in its fixed allowlist.
    if (event_id!=1 || clean.attribute_count!=1 || clean.monotonic_ns ||
        clean.attributes[0].key!=1 || clean.attributes[0].enum_value!=value ||
        madobs_emit_generic_event(s.observer,&clean)!=MADOBS_OK) return false;
    if (sdk==db_sdk) ++s.db; else ++s.link_states;
    return true;
}
#endif
bool states(Session &s,const uint32_t *expected,unsigned count) {
    ml_event_v1 event{};event.struct_size=sizeof(event);event.abi_version=ML_ABI_V1;
    unsigned got=0;
    for (unsigned read=0;read<9;++read) {
        auto rc=ml_next_event_v1(s.link,&event);
        if (rc==ML_EMPTY) return got==count;
        if (rc!=ML_OK) return false;
        if (event.kind!=ML_EVENT_STATE) continue;
        if (got>=count || event.state!=expected[got++]) return false;
#if COHOST_OBS
        if (!observe(s,link_sdk,1,event.state)) return false;
#elif COHOST_OBS_API
        if (!s.collector.report(cohost_api::link_sdk,1,event.state)) return false;
#endif
    }
    return false;
}
bool dispose(Session *s,bool verify) {
    if (s->link) { ml_destroy_v1(s->link);s->link=nullptr; }
#if COHOST_OBS
    if (s->observer) {
        // Stop/destroy failure retains callback state until app process exit.
        if (madobs_stop(s->observer)!=MADOBS_OK) return false;
        madobs_generic_stats_v1 totals{};
        verify=!verify || (s->db==3 && s->link_states==3 && s->rejected==1 &&
            madobs_get_generic_stats(s->observer,&totals)==MADOBS_OK && totals.enqueued==6 &&
            totals.drained==6 && !totals.queue_dropped && !totals.wal_dropped &&
            s->batches && s->batches<=16 && !s->unsafe);
        if (madobs_destroy(s->observer)!=MADOBS_OK) return false;
    }
#elif COHOST_OBS_API
    verify=!verify || s->collector.exact();
#else
    (void)verify;verify=true;
#endif
    delete s;return verify;
}
}
extern "C" void *mco_open(const char *directory) {
    auto *s=new(std::nothrow) Session;
    if (!s) return nullptr;
#if COHOST_OBS
    rule(s->rules[0],db_sdk,{1,2,3});rule(s->rules[1],link_sdk,{ML_CONNECTING,ML_CONNECTED,ML_CLOSED});
    if (!directory || !madobs_privacy_policy_valid(&s->policy) ||
        !(s->observer=madobs_create(directory,discard,s)) || madobs_start(s->observer)!=MADOBS_OK) {
        (void)dispose(s,false);return nullptr;
    }
#else
    (void)directory;
#endif
    const ml_config_v1 cfg={sizeof(cfg),ML_ABI_V1,4,16,8,100,10,20,1};
    const ml_host_v1 host={sizeof(host),ML_ABI_V1,s,begin,close_wire,poll,write,zero,zero};
    const uint32_t expected[]={ML_CONNECTING,ML_CONNECTED};
    if (ml_create_tracked_v1(&cfg,&host,1,&s->link)==ML_OK && s->link &&
        ml_connect_v1(s->link,"synthetic")==ML_OK && ml_tick_v1(s->link)==ML_OK && states(*s,expected,2)) return s;
    (void)dispose(s,false);return nullptr;
}
extern "C" int32_t mco_send(void *context,uint32_t expected) {
    auto &s=*static_cast<Session*>(context);
    uint64_t id=0;
    ml_completion_v1 out={sizeof(out),ML_ABI_V1,0,0,0};
    return s.link && ml_send_tracked_v1(s.link,&wire_byte,1,100,&id)==ML_OK && id &&
        ml_tick_v1(s.link)==ML_OK && s.writes==expected &&
        ml_next_completion_v1(s.link,&out)==ML_OK && out.operation==id &&
        out.outcome==ML_COMPLETION_LOCAL_ACCEPTED && ml_next_completion_v1(s.link,&out)==ML_EMPTY;
}
extern "C" int32_t mco_close_link(void *context) {
    auto &s=*static_cast<Session*>(context);
    if (!s.link) return 0;
    const uint32_t expected[]={ML_CLOSED};
    const bool ok=ml_close_v1(s.link)==ML_OK && states(s,expected,1);
    ml_destroy_v1(s.link);s.link=nullptr;return ok;
}
extern "C" int32_t mco_db_report(void *context,uint32_t operation) {
#if COHOST_OBS
    if (operation<1 || operation>4) return 0;
    auto &s=*static_cast<Session*>(context);
    return observe(s,db_sdk,operation==4?2:1,operation);
#elif COHOST_OBS_API
    if (operation<1 || operation>4) return 0;
    auto &s=*static_cast<Session*>(context);
    return s.collector.report(cohost_api::db_sdk,operation==4?2:1,operation);
#else
    (void)context;(void)operation;return 0;
#endif
}
extern "C" int32_t mco_finish(void *context,int32_t verify) {
    return dispose(static_cast<Session*>(context),verify!=0);
}
