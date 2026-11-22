# Separate opt-in target. MadDB's normal build never enters this directory.
.PHONY: test
ROOT := ../..
OUT := $(ROOT)/target/obs-adapter
# Independently supplied public MadObs header, not vendored or redistributed.
PINNED_OBSERVER_BLOB := 2fd8c8cc81b2e38569c2b2ce3cd5fec03ffcf001
test:
	@test -n "$(MADOBS_INCLUDE_DIR)"
	@test "$$(git hash-object "$(MADOBS_INCLUDE_DIR)/madobs/observer.h")" = "$(PINNED_OBSERVER_BLOB)"
	@mkdir -p $(OUT)
	$(CC) -std=c11 -Wall -Wextra -Werror -pedantic -I$(ROOT)/include -I"$(MADOBS_INCLUDE_DIR)" test_adapter.c -o $(OUT)/c-test
	@$(OUT)/c-test
	$(CXX) -x c++ -std=c++17 -Wall -Wextra -Werror -pedantic -I$(ROOT)/include -I"$(MADOBS_INCLUDE_DIR)" test_adapter.c -o $(OUT)/cpp-test
	@$(OUT)/cpp-test
	@echo 'PASS: optional adapter C11/C++17 with synthetic local sink; no SQLite/runtime transport execution'
