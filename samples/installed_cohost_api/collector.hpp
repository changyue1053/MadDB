#pragma once
#include <array>
#include <cstddef>
#include "madlink_c.h"
#include "maddb_obs.h"
#include "queued_observer.hpp"

namespace cohost_api {
using Link = madlink::madobs_adapter::QueuedObserver;
enum class Event { connect, connected, db_put, db_get, closed, excluded, invalid };
static_assert(MADDB_OBS_SCHEMA_ID == 0x4D444201u && MADDB_OBS_SCHEMA_VERSION == 1u);
static_assert(MADDB_OBS_GET == 1u && MADDB_OBS_PUT == 2u && MADDB_OBS_REMOVE == 3u);
static_assert(MADDB_OBS_STATUS_ATTRIBUTE == 1u);
static_assert(madlink::madobs_adapter::sdk_id == 0x4d4cu &&
              madlink::madobs_adapter::sdk_version == 1u &&
              madlink::madobs_adapter::state_event == 1u &&
              madlink::madobs_adapter::state_key == 1u);
static_assert(ML_CONNECTING == 1 && ML_CONNECTED == 2 && ML_CLOSED == 4);

inline Event classify(const madobs_event_v1 *event) {
    if (!event || event->struct_size != sizeof(*event) || event->abi_version != MADOBS_ABI_VERSION ||
        event->monotonic_ns != 0 || event->reserved != 0 || event->attribute_count != 1 ||
        event->severity != 1 || event->attributes[0].key != 1) return Event::invalid;
    for (std::size_t i=1; i<MADOBS_MAX_ATTRIBUTES; ++i)
        if (event->attributes[i].key || event->attributes[i].enum_value) return Event::invalid;
    const uint32_t value=event->attributes[0].enum_value;
    if (event->sdk_id==0x4D444201u && event->sdk_version==1 && value==0) {
        switch (event->event_id) {
            case 1: return Event::db_get;
            case 2: return Event::db_put;
            case 3: return Event::excluded;
        }
    }
    if (event->sdk_id==0x4d4cu && event->sdk_version==1 && event->event_id==1) {
        switch (value) {
            case 1: return Event::connect;
            case 2: return Event::connected;
            case 4: return Event::closed;
        }
    }
    return Event::invalid;
}

struct Collector {
    std::array<Event,6> received{};
    std::size_t count=0;
    bool excluded=false, invalid=false;
    static void record(void *context, const madobs_event_v1 *event) noexcept {
        auto &self=*static_cast<Collector *>(context);
        const auto type=classify(event);
        if (type==Event::excluded) {
            self.invalid |= self.excluded || self.count!=self.received.size();
            self.excluded=true;
        } else if (type==Event::invalid || self.count==self.received.size()) {
            self.invalid=true;
        } else {
            self.received[self.count++]=type;
        }
    }
    madobs_observer_v1 port() noexcept {
        return {sizeof(madobs_observer_v1),MADOBS_ABI_VERSION,this,&record};
    }
    bool exact() const noexcept {
        constexpr std::array<Event,6> expected{Event::connect,Event::connected,Event::db_put,
                                              Event::db_get,Event::closed,Event::db_get};
        return !invalid && excluded && count==expected.size() && received==expected;
    }
};
}
