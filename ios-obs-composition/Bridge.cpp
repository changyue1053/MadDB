#include "Bridge.h"
#include <madobs/runtime.h>
#include <atomic>
#include <new>

struct State {
  madobs_event_rule_v1 rules[2]{};
  madobs_privacy_policy_v1 policy{};
  madobs_handle_t runtime{};
  madobs_observer_binding_v1 binding{};
  madobs_observer_v1 observer{};
  std::atomic<unsigned> batches{0}, rejected{0};
};
static constexpr uint32_t sdk = 0x4D444201;
static void consume(void *ctx, uint8_t, uint64_t, const uint8_t *bytes, size_t size,
                    madobs_send_done_fn done, void *done_ctx) {
  auto &s = *static_cast<State *>(ctx);
  unsigned attempt = s.batches.fetch_add(1);
  bool safe = attempt < 16 && size <= 1024*1024 &&
      madobs_check_private_batch(bytes, size, &s.policy) == MADOBS_PRIVATE_BATCH_OK;
  if (!safe) ++s.rejected;
  done(done_ctx, safe ? 1 : 0);
}
extern "C" void *maddb_test_obs_begin(const char *path) {
  auto *s = new (std::nothrow) State;
  if (!s) return nullptr;
  for (unsigned i=0;i<2;++i) {
    auto &r = s->rules[i]; r.sdk_id=sdk; r.sdk_version=1;
    r.event_id=i+1; r.max_severity=1; r.attribute_count=1;
    r.attributes[0].key=1; r.attributes[0].value_count=i==0?2:1;
    r.attributes[0].values[0]=0; r.attributes[0].values[1]=1;
  }
  s->policy={sizeof(s->policy),MADOBS_ABI_VERSION,2,s->rules};
  if (!madobs_privacy_policy_valid(&s->policy)) { delete s; return nullptr; }
  s->runtime=madobs_create(path,consume,s);
  if (!s->runtime) { delete s; return nullptr; }
  if (madobs_start(s->runtime)!=MADOBS_OK || madobs_observer_for_runtime(s->runtime,&s->binding,&s->observer)!=MADOBS_OK) {
    if (madobs_stop(s->runtime)==MADOBS_OK && madobs_destroy(s->runtime)==MADOBS_OK) delete s;
    return nullptr;
  }
  return s;
}
extern "C" int32_t maddb_test_obs_report(void *state,uint32_t outcome) {
  if (!state || outcome<1 || outcome>3) return 0;
  auto &s=*static_cast<State *>(state);
  madobs_event_v1 event{};
  event.struct_size=sizeof(event); event.abi_version=MADOBS_ABI_VERSION;
  event.sdk_id=sdk; event.sdk_version=1; event.event_id=outcome==1?2:1;
  event.severity=1; event.attribute_count=1;
  event.attributes[0].key=1; event.attributes[0].enum_value=outcome==3?1:0;
  return madobs_observer_emit(&s.observer,&event)==MADOBS_EMITTED;
}
extern "C" int32_t maddb_test_obs_finish(void *state) {
  if (!state) return 0;
  auto *s=static_cast<State *>(state);
  if (madobs_stop(s->runtime)!=MADOBS_OK) return 0; // Keep callback state live on failure.
  madobs_generic_stats_v1 stats{};
  bool ok=madobs_get_generic_stats(s->runtime,&stats)==MADOBS_OK &&
      stats.enqueued==3 && stats.drained==3 && stats.queue_dropped==0 && stats.wal_dropped==0 &&
      s->batches.load()>0 && s->batches.load()<=16 && s->rejected.load()==0;
  if (madobs_destroy(s->runtime)!=MADOBS_OK) return 0;
  delete s; return ok?1:0;
}
