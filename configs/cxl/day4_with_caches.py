# Copyright (c) 2024 CXL Shared Memory Simulation
# Day 4: Add L1/L2 Caches for Coherence
#
# This configuration adds private L1/L2 caches to each system.
# The caches will participate in coherence via the CXL switch's snoop filter.
#
# Run with: ./build/X86/gem5.opt configs/cxl/day4_with_caches.py

import os
import m5
from m5.objects import *

# ============================================================================
# Configuration Parameters
# ============================================================================
CLOCK_SPEED = "3GHz"
SHARED_MEM_SIZE = "512MiB"

# ============================================================================
# Cache Configuration Classes
# ============================================================================
class L1ICache(Cache):
    """L1 Instruction Cache"""
    size = '32kB'
    assoc = 8
    tag_latency = 1
    data_latency = 1
    response_latency = 1
    mshrs = 4
    tgts_per_mshr = 20

class L1DCache(Cache):
    """L1 Data Cache"""
    size = '32kB'
    assoc = 8
    tag_latency = 1
    data_latency = 1
    response_latency = 1
    mshrs = 4
    tgts_per_mshr = 20

class L2Cache(Cache):
    """Shared L2 Cache (per system)"""
    size = '256kB'
    assoc = 16
    tag_latency = 10
    data_latency = 10
    response_latency = 1
    mshrs = 20
    tgts_per_mshr = 12

# ============================================================================
# L2 Crossbar (connects L1 caches to L2)
# ============================================================================
class L2XBar(CoherentXBar):
    """Crossbar connecting L1 caches to L2"""
    width = 32
    frontend_latency = 1
    forward_latency = 0
    response_latency = 1
    snoop_response_latency = 1
    snoop_filter = SnoopFilter(lookup_latency=0)
    point_of_unification = True

# ============================================================================
# Helper function to create a system with caches
# ============================================================================
def create_system_with_caches(name, mem_range, binary=None):
    """Create a system with L1 and L2 caches."""
    system = System()
    
    # Clock domain
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = CLOCK_SPEED
    system.clk_domain.voltage_domain = VoltageDomain()
    
    # Memory configuration
    system.mem_mode = "timing"
    system.mem_ranges = [mem_range]
    
    # CPU
    system.cpu = TimingSimpleCPU()
    
    # L1 Caches
    system.cpu.icache = L1ICache()
    system.cpu.dcache = L1DCache()
    
    # Connect CPU to L1 caches
    system.cpu.icache_port = system.cpu.icache.cpu_side
    system.cpu.dcache_port = system.cpu.dcache.cpu_side
    
    # L2 Crossbar (connects L1s to L2)
    system.l2bus = L2XBar()
    
    # Connect L1 caches to L2 bus
    system.cpu.icache.mem_side = system.l2bus.cpu_side_ports
    system.cpu.dcache.mem_side = system.l2bus.cpu_side_ports
    
    # L2 Cache
    system.l2cache = L2Cache()
    system.l2bus.mem_side_ports = system.l2cache.cpu_side
    
    # System bus (connects L2 to external memory/CXL switch)
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
    
    # System port
    system.system_port = system.membus.cpu_side_ports
    
    # Setup workload
    if binary and os.path.exists(binary):
        system.workload = SEWorkload.init_compatible(binary)
        process = Process()
        process.cmd = [binary]
        system.cpu.workload = process
        system.cpu.createThreads()
    
    return system

# ============================================================================
# Find binary
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

# Create both systems with caches
root.systemA = create_system_with_caches("SystemA", shared_mem_range, binary)
root.systemB = create_system_with_caches("SystemB", shared_mem_range, None)

# ============================================================================
# CXL Switch (CoherentXBar with Snoop Filter)
# ============================================================================
root.cxl_switch = CoherentXBar(
    width=64,
    frontend_latency=3,
    forward_latency=4,
    response_latency=2,
    snoop_response_latency=4,
    point_of_coherency=True,
    point_of_unification=True,
)

root.cxl_switch.snoop_filter = SnoopFilter(
    lookup_latency=1,
    max_capacity="8MiB",
)

# Connect both systems to CXL switch
root.systemA.membus.mem_side_ports = root.cxl_switch.cpu_side_ports
root.systemB.membus.mem_side_ports = root.cxl_switch.cpu_side_ports

# ============================================================================
# Shared Memory Controller
# ============================================================================
root.shared_mem_ctrl = MemCtrl()
root.shared_mem_ctrl.dram = DDR4_2400_8x8()
root.shared_mem_ctrl.dram.range = shared_mem_range
root.shared_mem_ctrl.port = root.cxl_switch.mem_side_ports

# ============================================================================
# Run Simulation
# ============================================================================
print("=" * 60)
print("Day 4: CXL with L1/L2 Caches")
print("=" * 60)
print(f"System A: L1I=32kB, L1D=32kB, L2=256kB")
print(f"System B: L1I=32kB, L1D=32kB, L2=256kB")
print(f"CXL Switch: 64B width, Snoop Filter enabled")
print(f"Shared Memory: {SHARED_MEM_SIZE}")
print("=" * 60)

m5.instantiate()

print("Beginning simulation...")
exit_event = m5.simulate()

print("=" * 60)
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
print("=" * 60)
print("SUCCESS: CXL with caches works!")
print("")
print("Next step: Day 5 - Build with MESIF Ruby protocol")
