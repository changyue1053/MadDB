#include "maddb.h"
#include "madlink_c.h"
#if COHOST_OBS
#include "maddb_obs.h"
#include "queued_observer.hpp"
#include "madobs/private.h"
#include <atomic>
#endif

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>

#define CHECK(expr) do { if (!(expr)) { std::fprintf(stderr,"FAIL: cohost assertion %d\n",__LINE__); std::exit(1); } } while (0)
struct Transport {
    uint64_t generation=0;
    bool connected_event=false;
    unsigned writes=0;
};
static constexpr uint8_t link_byte=23;
static void connect_link(void* context, const char*, uint64_t generation) {
    auto& t=*static_cast<Transport*>(context); t.generation=generation; t.connected_event=true;
}
static void close_link(void*) {}
static int32_t poll_link(void* context, ml_wire_event_v1* event) {
    auto& t=*static_cast<Transport*>(context);
    if (!t.connected_event) return 0;
    t.connected_event=false; event->kind=ML_WIRE_CONNECTED; event->generation=t.generation;
    return 1;
}
static int32_t write_link(void* context, const uint8_t* data, uint64_t size) {
    auto& t=*static_cast<Transport*>(context);
    CHECK(size==1 && data && data[0]==link_byte);
    ++t.writes; return ML_WRITE_ACCEPTED;
}
static uint64_t zero(void*) { return 0; }

#if COHOST_OBS
using LinkObserver=madlink::madobs_adapter::QueuedObserver;
struct Obs {
    const madobs_privacy_policy_v1* policy;
    madobs_private_handle_t handle=0;
    unsigned db=0, link=0, rejected=0, unexpected=0;
    std::atomic<unsigned> safe_batches{0}, unsafe_batches{0};
};
static void forward(void* context, const madobs_event_v1* event) {
    auto& o=*static_cast<Obs*>(context);
    if (!event) { ++o.unexpected; return; }
    auto status=madobs_private_emit(o.handle,event);
    if (status==MADOBS_E_SCHEMA_REJECTED) { ++o.rejected; return; }
    if (status!=MADOBS_OK || event->monotonic_ns || event->attribute_count!=1) {
        ++o.unexpected; return;
    }
    if (event->sdk_id==MADDB_OBS_SCHEMA_ID) ++o.db;
    else if (event->sdk_id==madlink::madobs_adapter::sdk_id) ++o.link;
    else ++o.unexpected;
}
static void local_sink(void* context, uint8_t, uint64_t, const uint8_t* bytes, size_t size,
                       madobs_send_done_fn done, void* dc) {
    auto& o=*static_cast<Obs*>(context);
    const auto safe=size<=2*1024*1024 &&
                    madobs_check_private_batch(bytes,size,o.policy)==MADOBS_PRIVATE_BATCH_OK;
    done(dc,safe);
    (safe ? o.safe_batches : o.unsafe_batches).fetch_add(1);
}
static madobs_event_rule_v1 db_rule(uint32_t id) {
    madobs_event_rule_v1 r{};
    r.sdk_id=MADDB_OBS_SCHEMA_ID; r.sdk_version=MADDB_OBS_SCHEMA_VERSION;
    r.event_id=id; r.max_severity=1; r.attribute_count=1;
    r.attributes[0].key=MADDB_OBS_STATUS_ATTRIBUTE;
    r.attributes[0].value_count=1; r.attributes[0].values[0]=0; // successful operations only
    return r;
}
#endif

int main(int argc, char** argv) {
#if COHOST_OBS
    CHECK(argc==3);
    const madobs_event_rule_v1 rules[]={
        db_rule(MADDB_OBS_GET), db_rule(MADDB_OBS_PUT), *LinkObserver::policy().events
    };
    const madobs_privacy_policy_v1 policy={sizeof(policy),MADOBS_ABI_VERSION,3,rules};
    CHECK(madobs_privacy_policy_valid(&policy));
    Obs obs{&policy};
    madobs_private_open_result open=MADOBS_PRIVATE_OPEN_INTERNAL;
    obs.handle=madobs_private_open_ex(argv[2],local_sink,&obs,&policy,&open);
    CHECK(obs.handle && open==MADOBS_PRIVATE_OPEN_OK);
    const madobs_observer_v1 port={sizeof(port),MADOBS_ABI_VERSION,&obs,forward};
    LinkObserver queue(port);
#else
    CHECK(argc==2);
#endif
    const auto* path=reinterpret_cast<const uint8_t*>(argv[1]);
    const auto path_size=std::strlen(argv[1]);
    const uint8_t space[]={65}, key[]={7}, value[]={0,42,255};
    maddb_handle db=0;
    auto open_db=[&] {
        CHECK(maddb_open(path,path_size,space,sizeof(space),&db)==MADDB_OK && db);
    };
    auto get=[&](bool observe) {
        uint8_t result[sizeof(value)]{};
        size_t size=0;
#if COHOST_OBS
        const auto rc=observe ? maddb_obs_get(&port,db,key,sizeof(key),result,sizeof(result),&size)
                              : maddb_get(db,key,sizeof(key),result,sizeof(result),&size);
#else
        (void)observe;
        const auto rc=maddb_get(db,key,sizeof(key),result,sizeof(result),&size);
#endif
        CHECK(rc==MADDB_OK && size==sizeof(value) && std::memcmp(result,value,size)==0);
    };
    open_db();
    Transport t;
    const ml_config_v1 config={sizeof(config),ML_ABI_V1,4,16,8,100,10,20,1};
    const ml_host_v1 host={sizeof(host),ML_ABI_V1,&t,connect_link,close_link,poll_link,write_link,zero,zero};
    ml_client* link=nullptr;
    CHECK(ml_create_tracked_v1(&config,&host,2,&link)==ML_OK && link);
    CHECK(ml_connect_v1(link,"synthetic")==ML_OK && ml_tick_v1(link)==ML_OK);
    auto read_states=[&](const uint32_t* expected,unsigned count) {
        ml_event_v1 event{}; event.struct_size=sizeof(event); event.abi_version=ML_ABI_V1;
        unsigned got=0;
        ml_status rc;
        while ((rc=ml_next_event_v1(link,&event))==ML_OK) {
            if (event.kind!=ML_EVENT_STATE) continue;
            CHECK(got<count && event.state==expected[got++]);
#if COHOST_OBS
            queue.enqueue_state(event.state);
#endif
        }
        CHECK(rc==ML_EMPTY && got==count);
#if COHOST_OBS
        CHECK(queue.drain(count)==count && !queue.pending());
#endif
    };
    const uint32_t ready[]={ML_CONNECTING,ML_CONNECTED};
    read_states(ready,2);
#if COHOST_OBS
    CHECK(maddb_obs_put(&port,db,key,sizeof(key),value,sizeof(value))==MADDB_OK);
#else
    CHECK(maddb_put(db,key,sizeof(key),value,sizeof(value))==MADDB_OK);
#endif
    get(true);

    auto send=[&](unsigned count) {
        uint64_t id=0;
        CHECK(ml_send_tracked_v1(link,&link_byte,sizeof(link_byte),100,&id)==ML_OK && id);
        CHECK(ml_tick_v1(link)==ML_OK && t.writes==count);
        ml_completion_v1 receipt{sizeof(receipt),ML_ABI_V1,0,0,0};
        CHECK(ml_next_completion_v1(link,&receipt)==ML_OK && receipt.operation==id &&
              receipt.outcome==ML_COMPLETION_LOCAL_ACCEPTED);
        CHECK(ml_next_completion_v1(link,&receipt)==ML_EMPTY);
    };
    send(1);
    CHECK(maddb_close(db)==MADDB_OK);
    send(2); // Link progresses with DB closed.
    open_db();
    CHECK(ml_close_v1(link)==ML_OK);
    const uint32_t closing[]={ML_CLOSED};
    read_states(closing,1);
    ml_destroy_v1(link);
    get(true); // DB still works after Link's destruction.

#if COHOST_OBS
    // Policy excludes REMOVE entirely. The real DB operation still returns OK.
    const uint8_t missing[]={8};
    const auto removed=maddb_remove(db,missing,sizeof(missing));
    CHECK(removed==MADDB_OK);
    CHECK(maddb_obs_report_result(&port,MADDB_OBS_REMOVE,removed)==MADOBS_EMITTED);
    CHECK(obs.rejected==1 && obs.db==3 && obs.link==3 && !obs.unexpected);
    const auto q=queue.stats();
    CHECK(q.enqueued==3 && q.callback_invoked==3 && !q.overflow && !q.rejected && !q.callback_error);
#endif
    CHECK(maddb_close(db)==MADDB_OK);
#if COHOST_OBS
    // Both producer paths stop before the sole runtime, while context is live.
    CHECK(madobs_private_stop(obs.handle)==MADOBS_OK);
    madobs_generic_stats_v1 stats{};
    madobs_private_gate_stats_v1 gate{};
    CHECK(madobs_private_get_stats(obs.handle,&stats,sizeof(stats))==MADOBS_OK);
    CHECK(stats.enqueued==6 && stats.drained==6 && !stats.queue_dropped && !stats.wal_dropped);
    CHECK(madobs_private_get_gate_stats(obs.handle,&gate,sizeof(gate))==MADOBS_OK && !gate.rejected_attempts);
    CHECK(obs.safe_batches.load()>0 && !obs.unsafe_batches.load());
    CHECK(madobs_private_destroy(obs.handle)==MADOBS_OK);
#endif
    open_db(); get(false); CHECK(maddb_close(db)==MADDB_OK);
    std::puts("PASS: installed cohost synthetic operations");
}
