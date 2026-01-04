# CXL Shared Memory with MESIF Protocol - Implementation Guide

## Overview

This guide walks you through implementing a two-board CXL shared memory configuration with MESIF (Modified, Exclusive, Shared, Invalid, Forward) coherence protocol in gem5.

## Directory Structure

```
configs/cxl/
├── basic.py                 # Main configuration (updated)
├── day1_hello_world.py      # Day 1: Basic hello world test
├── day2_multi_system.py     # Day 2: Two systems setup
├── day3_cxl_switch.py       # Day 3: CXL switch with snoop filter
├── day4_with_caches.py      # Day 4: Add L1/L2 caches
├── day7_verification.py     # Day 7: Shared memory verification
└── README.md                # This file

src/mem/ruby/protocol/
├── MESIF_Two_Level.slicc    # Protocol definition
├── MESIF_Two_Level-msg.sm   # Message types
├── MESIF_Two_Level-L1cache.sm   # L1 cache state machine
├── MESIF_Two_Level-L2cache.sm   # L2 cache state machine
├── MESIF_Two_Level-dir.sm   # Directory controller
└── MESIF_Two_Level-dma.sm   # DMA controller

build_opts/
└── X86_MESIF_Two_Level      # Build configuration for MESIF
```

---

## Day-by-Day Execution Plan

### Day 1: Fix Hello World

**Goal:** Run a simple hello world using AtomicSimpleCPU to verify gem5 works.

**Commands:**
```bash
# Build gem5 (if not already built)
cd /home/ali/gem5
scons build/X86/gem5.opt -j$(nproc)

# Run Day 1 test
./build/X86/gem5.opt configs/cxl/day1_hello_world.py
```

**Expected Output:**
```
Day 1: Hello World Test
Beginning simulation...
Hello World!
Exiting @ tick XXXXX because exiting with last active thread context
SUCCESS: Hello World completed!
```

**Troubleshooting:**
- If binary not found, build test programs: `scons build/X86/gem5.opt tests/test-progs/hello`
- If using a CXL fork with modified APIs, try: `--cpu-type=AtomicSimpleCPU`

---

### Day 2: Multi-System Setup

**Goal:** Create two separate System objects under one Root.

**Commands:**
```bash
./build/X86/gem5.opt configs/cxl/day2_multi_system.py
```

**Key Concepts:**
- Both systems have independent CPUs and memory buses
- Each system has its own local memory (temporary)
- The Root object contains both systems

**Expected Output:**
```
Day 2: Multi-System Setup
System A: AtomicSimpleCPU
System B: AtomicSimpleCPU
Beginning simulation (running System A's workload)...
SUCCESS: Multi-system configuration works!
```

---

### Day 3: Address Mapping & CXL Switch

**Goal:** Connect both systems to shared memory via CXL switch.

**Commands:**
```bash
./build/X86/gem5.opt configs/cxl/day3_cxl_switch.py
```

**Key Concepts:**
- CXL Switch = `CoherentXBar` with `SnoopFilter`
- Both systems see the SAME memory address range
- `point_of_coherency=True` makes the switch handle coherence
- `SnoopFilter` tracks which caches have which lines

**Architecture:**
```
┌──────────────┐     ┌──────────────┐
│   System A   │     │   System B   │
│  ┌────────┐  │     │  ┌────────┐  │
│  │  CPU   │  │     │  │  CPU   │  │
│  └───┬────┘  │     │  └───┬────┘  │
│      │       │     │      │       │
│  ┌───┴────┐  │     │  ┌───┴────┐  │
│  │ MemBus │  │     │  │ MemBus │  │
│  └───┬────┘  │     │  └───┬────┘  │
└──────┼───────┘     └──────┼───────┘
       │                    │
       └────────┬───────────┘
                │
        ┌───────┴───────┐
        │  CXL Switch   │
        │ (CoherentXBar)│
        │ SnoopFilter   │
        └───────┬───────┘
                │
        ┌───────┴───────┐
        │ Shared Memory │
        │  (DDR4 DRAM)  │
        └───────────────┘
```

---

### Day 4: SLICC Modifications

**Goal:** Add the Forward (F) state to Ruby protocol.

**What is MESIF?**
- **M** (Modified): Only copy, dirty
- **E** (Exclusive): Only copy, clean  
- **S** (Shared): Read-only copy, NOT the responder
- **I** (Invalid): No valid copy
- **F** (Forward): Read-only copy, DESIGNATED to respond to GetS requests

**Key Benefit of F State:**
When multiple caches have shared copies, only the F holder responds to new GetS requests, preventing multiple caches from flooding the network with data.

**Files Modified:**
1. `MESIF_Two_Level-msg.sm` - Added `DATA_FORWARD` response type
2. `MESIF_Two_Level-L1cache.sm` - Added F state and transitions
3. `MESIF_Two_Level-L2cache.sm` - Added SF (Shared-Forward) state
4. `MESIF_Two_Level-dir.sm` - Directory tracks Forward holder

**Key Transitions:**
```
# When a cache in F state receives a GetS:
F + Fwd_GETS → S  (send data to requester, requester becomes new F)

# When fetching shared data:
I + Load → IS → F  (first sharer becomes Forward holder)

# When F holder is evicted:
F → F_I → I  (transfer Forward token to another sharer)
```

---

### Day 5: Protocol Compiling

**Goal:** Build gem5 with the new MESIF protocol.

**Commands:**
```bash
# Build with MESIF protocol
cd /home/ali/gem5
scons build/X86_MESIF_Two_Level/gem5.opt -j$(nproc)
```

**If you encounter SLICC errors:**
1. Check syntax in .sm files
2. Ensure all states have transitions for all events
3. Look at existing MESI files for reference

**Common Errors:**
- "Undefined state" - Add missing state to state_declaration
- "Undefined event" - Add missing event to enumeration
- "No transition" - Add transition(OldState, Event, NewState) block

---

### Day 6: CXL Header Latency

**Goal:** Add realistic CXL protocol latency (~100ns).

**In your configuration:**
```python
# CXL adds approximately 100ns latency
CXL_HEADER_LATENCY_NS = 100
CLOCK_FREQ_GHZ = 3
CXL_LATENCY_CYCLES = int(CXL_HEADER_LATENCY_NS * CLOCK_FREQ_GHZ)

root.cxl_switch.frontend_latency = CXL_LATENCY_CYCLES
```

**CXL Protocol Types:**
- **CXL.io**: PCIe-based I/O (not cache coherent)
- **CXL.cache**: Device caches host memory (requires coherence)
- **CXL.mem**: Host accesses device memory (our focus)

---

### Day 7: Verification

**Goal:** Verify shared memory works with m5 ops.

**Test Scenario:**
1. System A writes value X to shared address
2. System B reads from same address
3. Verify System B sees value X

**Commands:**
```bash
./build/X86_MESIF_Two_Level/gem5.opt configs/cxl/day7_verification.py
```

**Using m5 ops:**
```c
// In your test program
#include <gem5/m5ops.h>

// Write from System A
volatile int *shared_addr = (int *)0x10000000;
*shared_addr = 42;
m5_work_end(0, 0);  // Signal completion

// Read from System B
int value = *shared_addr;
assert(value == 42);  // Should see System A's write
```

---

## Quick Reference

### Build Commands

```bash
# Standard X86 build (no Ruby)
scons build/X86/gem5.opt -j$(nproc)

# X86 with MESI Two Level protocol
scons build/X86_MESI_Two_Level/gem5.opt -j$(nproc)

# X86 with MESIF Two Level protocol (after adding files)
scons build/X86_MESIF_Two_Level/gem5.opt -j$(nproc)
```

### Run Commands

```bash
# Basic simulation
./build/X86/gem5.opt configs/cxl/basic.py

# With Ruby network options
./build/X86_MESI_Two_Level/gem5.opt configs/cxl/basic.py \
    --ruby --network=simple --topology=Crossbar
```

### Debug Flags

```bash
# Enable coherence debugging
./build/X86/gem5.opt --debug-flags=RubyCache,SnoopFilter configs/cxl/basic.py

# Enable memory debugging
./build/X86/gem5.opt --debug-flags=MemoryAccess,DRAM configs/cxl/basic.py
```

---

## Troubleshooting

### "Hello World" Still Failing

1. **Use AtomicSimpleCPU first:**
   ```python
   system.cpu = AtomicSimpleCPU()
   system.mem_mode = "atomic"
   ```

2. **Check if using CXL fork APIs:**
   - Look for custom System or Root classes
   - Check for required parameters in the fork

3. **Try minimal configuration:**
   - Use `day1_hello_world.py` which has no Ruby/caches

### SLICC Compilation Errors

1. **Missing transitions:**
   - Every (State, Event) pair needs a transition
   - Add `transition(State, Event) { /* stall */ }` for unhandled cases

2. **Type mismatches:**
   - Ensure message types match between sender and receiver
   - Check `MessageSizeType` is correct

### Snoop Filter Panics

```
panic: panic condition snoopMaskSize > maxCapacity
```

**Solution:** Increase snoop filter capacity:
```python
root.cxl_switch.snoop_filter = SnoopFilter(
    lookup_latency=1,
    max_capacity="16MiB"  # Increase from default
)
```

---

## Next Steps

After completing this implementation:

1. **Add more CPUs per system** - Test with multi-core
2. **Implement CXL.cache** - Device caches host memory
3. **Add performance counters** - Track cache misses, coherence traffic
4. **Benchmark with real workloads** - SPLASH2, PARSEC

## References

- gem5 Ruby Documentation: https://www.gem5.org/documentation/general_docs/ruby/
- SLICC Tutorial: https://www.gem5.org/documentation/learning_gem5/part3/
- CXL Specification: https://www.computeexpresslink.org/
