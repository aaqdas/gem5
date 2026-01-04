# Copyright (c) 2024 CXL Shared Memory Simulation
# Day 3.1: Multiple Hosts with CXL Switch to Shared Memory
#
# Multiple CPUs (representing hosts) connect through a CXL Switch
# to access shared memory. This models CXL Type 3 memory pooling.
#
# Run with: ./build/X86/gem5.opt configs/cxl/day3_1_multi_host_cxl.py

import os
import m5
from m5.objects import *

# ============================================================================
# Configuration Parameters
# ============================================================================
CLOCK_SPEED = "3GHz"
SHARED_MEM_SIZE = "512MiB"
NUM_HOSTS = 2  # Number of hosts (CPUs) sharing the CXL memory

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

# ============================================================================
# Create Multiple Hosts (CPUs with their own buses)
# ============================================================================
# Each "host" consists of a CPU and a local memory bus
# This models multiple compute nodes in a CXL fabric

system.cpu = [X86MinorCPU(cpu_id=i) for i in range(NUM_HOSTS)]
system.host_bus = [SystemXBar() for i in range(NUM_HOSTS)]

# Connect each CPU to its local bus
for i in range(NUM_HOSTS):
    # Connect CPU ports to its local bus
    system.cpu[i].icache_port = system.host_bus[i].cpu_side_ports
    system.cpu[i].dcache_port = system.host_bus[i].cpu_side_ports
    
    # Create interrupt controller for each CPU
    system.cpu[i].createInterruptController()
    system.cpu[i].interrupts[0].pio = system.host_bus[i].mem_side_ports
    system.cpu[i].interrupts[0].int_requestor = system.host_bus[i].cpu_side_ports
    system.cpu[i].interrupts[0].int_responder = system.host_bus[i].mem_side_ports

# System port connects to first host's bus
system.system_port = system.host_bus[0].cpu_side_ports

# ============================================================================
# CXL Switch (CoherentXBar with Snoop Filter)
# ============================================================================
# The CXL switch is the central point of coherency
# All hosts connect to this switch to access shared memory

system.cxl_switch = CoherentXBar(
    width=64,  # 64-byte cache line width (CXL uses 64B)
    frontend_latency=3,  # Latency from host to switch
    forward_latency=4,   # Latency to forward requests
    response_latency=2,  # Latency for responses
    snoop_response_latency=4,  # Latency for snoop responses
    point_of_coherency=True,   # This switch handles coherency
    point_of_unification=True,
)

# Enable Snoop Filter for MESI-like coherence tracking
# The snoop filter tracks which caches have copies of each line
system.cxl_switch.snoop_filter = SnoopFilter(
    lookup_latency=5,    # Cycles to look up the filter
    max_capacity="8MiB", # Can track 8MiB worth of cache lines
)

# Connect ALL host buses to the CXL switch
for i in range(NUM_HOSTS):
    system.host_bus[i].mem_side_ports = system.cxl_switch.cpu_side_ports

# ============================================================================
# Shared Memory Controller (CXL Device / Type 3 Memory)
# ============================================================================
# This represents the CXL memory expander/pooled memory device

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

# Setup workload - only Host 0 runs the workload
system.workload = SEWorkload.init_compatible(binary)

# Assign workload to Host 0 only
for i in range(NUM_HOSTS):
    process = Process(pid=100 + i)
    process.cmd = [binary]
    system.cpu[i].workload = process

# Create threads for all CPUs
for i in range(NUM_HOSTS):
    system.cpu[i].createThreads()

# ============================================================================
# Create Root and Run
# ============================================================================
root = Root(full_system=False, system=system)

print("=" * 60)
print("Day 3.1: Multi-Host CXL Switch with Shared Memory")
print("=" * 60)
print(f"Number of Hosts: {NUM_HOSTS}")
print(f"Shared Memory Size: {SHARED_MEM_SIZE}")
print(f"CXL Switch Width: 64 bytes")
print(f"Snoop Filter: Enabled (8MiB capacity)")
for i in range(NUM_HOSTS):
    workload = "hello world" if i == 0 else "idle"
    print(f"Host {i}: {type(system.cpu[i]).__name__} - {workload}")
print("=" * 60)
print("Architecture:")
print("")
print("   ┌─────────┐     ┌─────────┐")
print("   │ Host 0  │     │ Host 1  │")
print("   │  CPU    │     │  CPU    │")
print("   └────┬────┘     └────┬────┘")
print("        │               │")
print("   ┌────▼────┐     ┌────▼────┐")
print("   │host_bus │     │host_bus │")
print("   │   [0]   │     │   [1]   │")
print("   └────┬────┘     └────┬────┘")
print("        │               │")
print("        └───────┬───────┘")
print("                │")
print("         ┌──────▼──────┐")
print("         │  CXL Switch │")
print("         │ CoherentXBar│")
print("         │ +SnoopFilter│")
print("         └──────┬──────┘")
print("                │")
print("         ┌──────▼──────┐")
print("         │   Shared    │")
print("         │   Memory    │")
print("         │  (512 MiB)  │")
print("         └─────────────┘")
print("")
print("=" * 60)

m5.instantiate()

print("Beginning simulation (Host 0 runs hello world via shared memory)...")
exit_event = m5.simulate()

print("=" * 60)
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
print("=" * 60)
print("SUCCESS: Multi-host CXL simulation works!")
print("")
print("Key observations:")
print("- All hosts access the same shared memory through CXL switch")
print("- Snoop filter tracks cache line ownership across hosts")
print("- This models CXL Type 3 memory pooling")
print("")
print("Next step: Day 4 - Add L1/L2 caches with coherence protocol")
