#include "maddb.h"
#include "madlink_c.h"
#include "collector.hpp"

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

int main(int argc, char** argv) {
    CHECK(argc==2);
    cohost_api::Collector obs;
    const auto port=obs.port();
    cohost_api::Link queue(port);
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
        const auto rc=observe ? maddb_obs_get(&port,db,key,sizeof(key),result,sizeof(result),&size)
                              : maddb_get(db,key,sizeof(key),result,sizeof(result),&size);
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
            queue.enqueue_state(event.state);
        }
        CHECK(rc==ML_EMPTY && got==count);
        CHECK(queue.drain(count)==count && !queue.pending());
    };
    const uint32_t ready[]={ML_CONNECTING,ML_CONNECTED};
    read_states(ready,2);
    CHECK(maddb_obs_put(&port,db,key,sizeof(key),value,sizeof(value))==MADDB_OK);
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

    // Business removal of the absent fixture key succeeds; observation is excluded locally.
    const uint8_t missing[]={8};
    const auto removed=maddb_remove(db,missing,sizeof(missing));
    CHECK(removed==MADDB_OK);
    CHECK(maddb_obs_report_result(&port,MADDB_OBS_REMOVE,removed)==MADOBS_EMITTED);
    CHECK(obs.exact());
    const auto q=queue.stats();
    CHECK(q.enqueued==3 && q.callback_invoked==3 && !q.overflow && !q.rejected &&
          !q.callback_error && !q.invalid_state && !q.reentrant && !q.noop);
    uint8_t untouched=77; size_t size=99;
    CHECK(maddb_get(db,missing,sizeof(missing),&untouched,1,&size)==MADDB_NOT_FOUND &&
          untouched==77 && size==0);
    CHECK(maddb_close(db)==MADDB_OK);
    open_db(); get(false); CHECK(maddb_close(db)==MADDB_OK);
    std::puts("PASS: API-only cohost synthetic operations and exact local 3+3");
}
