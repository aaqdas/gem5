# Copyright (c) 2024 CXL Shared Memory Simulation
# Day 3: Shared Memory with CXL Switch
#
# A system with CXL switch connecting CPU to shared memory.
# This demonstrates CXL-style memory access with snoop filtering.
#
# Run with: ./build/X86/gem5.opt configs/cxl/day3_cxl_switch.py

import os
import m5
from m5.objects import *

# ============================================================================
# Configuration Parameters
# ============================================================================
CLOCK_SPEED = "3GHz"
SHARED_MEM_SIZE = "512MiB"

# ============================================================================
# Create the System
# ============================================================================
system = System()

# Clock domain
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = CLOCK_SPEED
system.clk_domain.voltage_domain = VoltageDomain()

# Memory configuration
system.mem_mode = "timing"
system.mem_ranges = [AddrRange(SHARED_MEM_SIZE)]

# CPU - use X86MinorCPU for realistic in-order pipeline timing
system.cpu = X86MinorCPU()

# ============================================================================
# Local Memory Bus (CPU side)
# ============================================================================
system.membus = SystemXBar()

# Connect CPU to local memory bus
system.cpu.icache_port = system.membus.cpu_side_ports
system.cpu.dcache_port = system.membus.cpu_side_ports

# Interrupt controller
system.cpu.createInterruptController()
system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports

# System port
system.system_port = system.membus.cpu_side_ports

# ============================================================================
# CXL Switch (CoherentXBar with Snoop Filter)
# ============================================================================
system.cxl_switch = CoherentXBar(
    width=64,  # 64-byte cache line width (CXL uses 64B)
    frontend_latency=3,
    forward_latency=4,
    response_latency=2,
    snoop_response_latency=4,
    point_of_coherency=True,
    point_of_unification=True,
)

# Enable Snoop Filter for MESI-like coherence tracking
system.cxl_switch.snoop_filter = SnoopFilter(
    lookup_latency=5,
    max_capacity="8MiB",
)

# Connect local membus to CXL switch
system.membus.mem_side_ports = system.cxl_switch.cpu_side_ports

# ============================================================================
# Shared Memory Controller (CXL Device / Type 3 Memory)
# ============================================================================
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR4_2400_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.cxl_switch.mem_side_ports

# ============================================================================
# Find and Load Binary
# ============================================================================
thispath = os.path.dirname(os.path.realpath(__file__))
gem5_root = os.path.join(thispath, "../..")
binary = os.path.join(gem5_root, "tests/test-progs/hello/bin/x86/linux/hello")

if not os.path.exists(binary):
    print(f"ERROR: Binary not found at {binary}")
    exit(1)

print(f"Using binary: {binary}")

# Setup workload
system.workload = SEWorkload.init_compatible(binary)
process = Process()
process.cmd = [binary]
system.cpu.workload = process
system.cpu.createThreads()

# ============================================================================
# Create Root and Run
# ============================================================================
root = Root(full_system=False, system=system)

print("=" * 60)
print("Day 3: CXL Switch with Shared Memory")
print("=" * 60)
print(f"Shared Memory Size: {SHARED_MEM_SIZE}")
print(f"CXL Switch Width: 64 bytes")
print(f"Snoop Filter: Enabled (8MiB capacity)")
print(f"CPU: {type(system.cpu).__name__}")
print("=" * 60)
print("Architecture:")
print("  CPU -> membus -> CXL Switch -> Shared Memory (DDR4)")
print("=" * 60)

m5.instantiate()

print("Beginning simulation...")
exit_event = m5.simulate()

print("=" * 60)
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
print("=" * 60)
print("SUCCESS: CXL switch simulation works!")
print("")
print("Next step: Day 4 - Add caches and implement MESIF protocol")
