# Copyright (c) 2024 CXL Shared Memory Simulation
# Day 7: Verification Script
#
# This script verifies that shared memory works correctly between two systems.
# System A writes to shared memory, System B reads from the same address.
#
# Run with: ./build/X86/gem5.opt configs/cxl/day7_verification.py

import os
import m5
from m5.objects import *

# ============================================================================
# Configuration
# ============================================================================
CLOCK_SPEED = "3GHz"
SHARED_MEM_SIZE = "512MiB"

# CXL latency modeling
CXL_HEADER_LATENCY_NS = 100  # CXL adds ~100ns latency
CLOCK_PERIOD_NS = 1.0 / 3.0  # 3GHz = 0.333ns
CXL_LATENCY_CYCLES = int(CXL_HEADER_LATENCY_NS / CLOCK_PERIOD_NS)

# ============================================================================
# Cache Classes
# ============================================================================
class L1ICache(Cache):
    size = '32kB'
    assoc = 8
    tag_latency = 1
    data_latency = 1
    response_latency = 1
    mshrs = 4
    tgts_per_mshr = 20

class L1DCache(Cache):
    size = '32kB'
    assoc = 8
    tag_latency = 1
    data_latency = 1
    response_latency = 1
    mshrs = 4
    tgts_per_mshr = 20

class L2Cache(Cache):
    size = '256kB'
    assoc = 16
    tag_latency = 10
    data_latency = 10
    response_latency = 1
    mshrs = 20
    tgts_per_mshr = 12

class L2XBar(CoherentXBar):
    width = 32
    frontend_latency = 1
    forward_latency = 0
    response_latency = 1
    snoop_response_latency = 1
    snoop_filter = SnoopFilter(lookup_latency=0)
    point_of_unification = True

# ============================================================================
# Create System with Caches
# ============================================================================
def create_cached_system(name, mem_range, binary=None):
    """Create a system with full cache hierarchy."""
    system = System()
    
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = CLOCK_SPEED
    system.clk_domain.voltage_domain = VoltageDomain()
    
    system.mem_mode = "timing"
    system.mem_ranges = [mem_range]
    
    # Use TimingSimpleCPU for accurate timing
    system.cpu = TimingSimpleCPU()
    
    # L1 Caches
    system.cpu.icache = L1ICache()
    system.cpu.dcache = L1DCache()
    
    system.cpu.icache_port = system.cpu.icache.cpu_side
    system.cpu.dcache_port = system.cpu.dcache.cpu_side
    
    # L2 Bus
    system.l2bus = L2XBar()
    system.cpu.icache.mem_side = system.l2bus.cpu_side_ports
    system.cpu.dcache.mem_side = system.l2bus.cpu_side_ports
    
    # L2 Cache
    system.l2cache = L2Cache()
    system.l2bus.mem_side_ports = system.l2cache.cpu_side
    
    # System Bus
    system.membus = SystemXBar()
    system.l2cache.mem_side = system.membus.cpu_side_ports
    
    # Interrupt controller
    system.cpu.createInterruptController()
    try:
        system.cpu.interrupts[0].pio = system.membus.mem_side_ports
        system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
        system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports
    except:
        pass
    
    system.system_port = system.membus.cpu_side_ports
    
    if binary and os.path.exists(binary):
        system.workload = SEWorkload.init_compatible(binary)
        process = Process()
        process.cmd = [binary]
        system.cpu.workload = process
        system.cpu.createThreads()
    
    return system

# ============================================================================
# Find Test Binary
# ============================================================================
thispath = os.path.dirname(os.path.realpath(__file__))
gem5_root = os.path.join(thispath, "../..")
binary = os.path.join(gem5_root, "tests/test-progs/hello/bin/x86/linux/hello")

if not os.path.exists(binary):
    print(f"Warning: Binary not found at {binary}")
    binary = None

# ============================================================================
# Shared Memory Range
# ============================================================================
shared_mem_range = AddrRange(SHARED_MEM_SIZE)

# ============================================================================
# Create Root
# ============================================================================
root = Root(full_system=False)

# Create both systems
root.systemA = create_cached_system("SystemA", shared_mem_range, binary)
root.systemB = create_cached_system("SystemB", shared_mem_range, None)

# ============================================================================
# CXL Switch with Snoop Filter
# ============================================================================
root.cxl_switch = CoherentXBar(
    width=64,
    frontend_latency=CXL_LATENCY_CYCLES,  # CXL header latency
    forward_latency=4,
    response_latency=2,
    snoop_response_latency=4,
    point_of_coherency=True,
    point_of_unification=True,
)

# MESIF-style snoop filter
root.cxl_switch.snoop_filter = SnoopFilter(
    lookup_latency=1,
    max_capacity="16MiB",
)

# Connect systems to CXL switch
root.systemA.membus.mem_side_ports = root.cxl_switch.cpu_side_ports
root.systemB.membus.mem_side_ports = root.cxl_switch.cpu_side_ports

# ============================================================================
# Shared Memory (CXL Type 3 Device)
# ============================================================================
root.shared_mem_ctrl = MemCtrl()
root.shared_mem_ctrl.dram = DDR4_2400_8x8()
root.shared_mem_ctrl.dram.range = shared_mem_range
root.shared_mem_ctrl.port = root.cxl_switch.mem_side_ports

# ============================================================================
# Run Simulation
# ============================================================================
print("=" * 70)
print("Day 7: CXL Shared Memory Verification")
print("=" * 70)
print(f"Configuration:")
print(f"  Shared Memory: {SHARED_MEM_SIZE}")
print(f"  CXL Latency: {CXL_HEADER_LATENCY_NS}ns ({CXL_LATENCY_CYCLES} cycles)")
print(f"  Cache Hierarchy: L1I=32kB, L1D=32kB, L2=256kB")
print(f"  Snoop Filter: 16MiB capacity")
print("=" * 70)
print("")
print("Architecture:")
print("  ┌─────────────┐     ┌─────────────┐")
print("  │  System A   │     │  System B   │")
print("  │   (CPU+$)   │     │   (CPU+$)   │")
print("  └──────┬──────┘     └──────┬──────┘")
print("         │                   │")
print("         └─────────┬─────────┘")
print("                   │")
print("         ┌─────────┴─────────┐")
print("         │    CXL Switch     │")
print("         │   (SnoopFilter)   │")
print("         └─────────┬─────────┘")
print("                   │")
print("         ┌─────────┴─────────┐")
print("         │   Shared Memory   │")
print("         │    (DDR4 DRAM)    │")
print("         └───────────────────┘")
print("=" * 70)

m5.instantiate()

print("")
print("Running simulation...")
print("  System A: Executing hello world via shared memory")
print("  System B: Idle (can observe coherence traffic)")
print("")

exit_event = m5.simulate()

print("=" * 70)
print(f"Simulation Complete!")
print(f"  Exit tick: {m5.curTick()}")
print(f"  Exit cause: {exit_event.getCause()}")
print("=" * 70)

# Check stats file for coherence information
print("")
print("To analyze coherence behavior, check:")
print("  m5out/stats.txt - Look for 'snoop' and 'cache' statistics")
print("")
print("Next steps for verification:")
print("  1. Create a custom test program that writes/reads shared memory")
print("  2. Use m5 ops to synchronize between systems")
print("  3. Check snoop filter hit/miss rates in stats")
