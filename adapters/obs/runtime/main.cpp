#include "maddb_obs.h"
#include <madobs/runtime.h>
#include <atomic>
#include <cassert>
#include <cstring>

struct Capture {
  const madobs_privacy_policy_v1 *policy;
  std::atomic<unsigned> batches{0}, rejected{0};
};
// Bounded local discard sink. No sockets, exported data or retained byte pointers.
static void consume(void *ctx, uint8_t, uint64_t, const uint8_t *bytes, size_t size,
                    madobs_send_done_fn done, void *done_ctx) {
  auto &capture = *static_cast<Capture *>(ctx);
  unsigned attempt = capture.batches.fetch_add(1);
  bool safe = attempt < 16 && size <= 1024*1024 &&
      madobs_check_private_batch(bytes, size, capture.policy) == MADOBS_PRIVATE_BATCH_OK;
  if (!safe) ++capture.rejected;
  done(done_ctx, safe ? 1 : 0); // Local discard acknowledgment, NOT remote delivery.
}
int main(int argc, char **argv) {
  assert(argc == 2); // Fresh synthetic WAL directory supplied by the driver.
  madobs_event_rule_v1 rules[2]{};
  for (unsigned i=0; i<2; ++i) {
    rules[i].sdk_id=MADDB_OBS_SCHEMA_ID; rules[i].sdk_version=1;
    rules[i].event_id=i+1; rules[i].max_severity=3; rules[i].attribute_count=1;
    rules[i].attributes[0].key=1; rules[i].attributes[0].value_count=9;
    for (unsigned j=0;j<9;++j) rules[i].attributes[0].values[j]=j;
  }
  madobs_privacy_policy_v1 policy{sizeof(policy), MADOBS_ABI_VERSION, 2, rules};
  assert(madobs_privacy_policy_valid(&policy));
  Capture capture{&policy};
  madobs_handle_t runtime=madobs_create(argv[1],consume,&capture);
  assert(runtime && madobs_start(runtime)==MADOBS_OK);
  madobs_observer_binding_v1 binding{}; madobs_observer_v1 observer{};
  assert(madobs_observer_for_runtime(runtime,&binding,&observer)==MADOBS_OK);
  maddb_handle db=0;
  const uint8_t ns[]="synthetic", key[]="k", missing[]="absent", value[]={0,7,255};
  uint8_t output[3]{};size_t len=0;
  assert(maddb_open_memory(ns,sizeof(ns)-1,&db)==MADDB_OK);
  assert(maddb_obs_put(&observer,db,key,1,value,3)==MADDB_OK);
  assert(maddb_obs_get(&observer,db,key,1,output,3,&len)==MADDB_OK);
  assert(len==3 && std::memcmp(output,value,3)==0);
  assert(maddb_obs_get(&observer,db,missing,sizeof(missing)-1,output,3,&len)==MADDB_NOT_FOUND && len==0);
  assert(maddb_close(db)==MADDB_OK); // No producers remain after this point.
  madobs_generic_stats_v1 stats{};
  assert(madobs_get_generic_stats(runtime,&stats)==MADOBS_OK && stats.enqueued==3);
  assert(madobs_stop(runtime)==MADOBS_OK);
  assert(madobs_get_generic_stats(runtime,&stats)==MADOBS_OK);
  assert(stats.enqueued==3 && stats.drained==3 && stats.queue_dropped==0 && stats.wal_dropped==0);
  assert(capture.batches.load()>0 && capture.batches.load()<=16 && capture.rejected.load()==0);
  assert(madobs_destroy(runtime)==MADOBS_OK);
  return 0;
}
