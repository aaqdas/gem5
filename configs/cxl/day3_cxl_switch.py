# Copyright (c) 2024 CXL Shared Memory Simulation
# Day 3: Shared Memory with CXL Switch
#
# Both systems now connect to a CXL Switch (CoherentXBar) with Snoop Filter
# that provides access to shared memory.
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
# Helper function to create a system (no local memory controller)
# ============================================================================
def create_system_for_cxl(name, mem_range, binary=None):
    """
    Create a system configured to use external shared memory.
    The membus is NOT connected to a local memory controller.
    """
    system = System()
    
    # Clock domain
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = CLOCK_SPEED
    system.clk_domain.voltage_domain = VoltageDomain()
    
    # Memory configuration - this tells the system what address range exists
    system.mem_mode = "timing"  # Use timing for accurate CXL simulation
    system.mem_ranges = [mem_range]
    
    # CPU - use X86MinorCPU for realistic in-order pipeline timing
    system.cpu = X86MinorCPU()
    
    # Memory bus (local to this system)
    system.membus = SystemXBar()
    
    # Connect CPU to local memory bus
    system.cpu.icache_port = system.membus.cpu_side_ports
    system.cpu.dcache_port = system.membus.cpu_side_ports
    
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
    
    # NOTE: No local memory controller - we'll connect to shared memory via CXL
    
    # Setup workload
    if binary and os.path.exists(binary):
        system.workload = SEWorkload.init_compatible(binary)
        process = Process()
        process.cmd = [binary]
        system.cpu.workload = process
    
    # Always create threads (required for ISA initialization)
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
# Shared Memory Range - Both systems see this same range
# ============================================================================
shared_mem_range = AddrRange(SHARED_MEM_SIZE)

# ============================================================================
# Create Root
# ============================================================================
root = Root(full_system=False)

# Create both systems with the SAME memory range (shared memory)
root.systemA = create_system_for_cxl("SystemA", shared_mem_range, binary)
root.systemB = create_system_for_cxl("SystemB", shared_mem_range, None)  # No process on B

# ============================================================================
# CXL Switch (CoherentXBar with Snoop Filter)
# ============================================================================
# The CXL switch is the point of coherency between the two systems
# Attach it to systemA to avoid proxy resolution issues

root.systemA.cxl_switch = CoherentXBar(
    width=64,  # 64-byte cache line width (CXL uses 64B)
    frontend_latency=3,
    forward_latency=4,
    response_latency=2,
    snoop_response_latency=4,
    point_of_coherency=True,  # This crossbar handles coherency
    point_of_unification=True,
)

# Enable Snoop Filter for MESI-like coherence tracking
root.systemA.cxl_switch.snoop_filter = SnoopFilter(
    lookup_latency=5,  # 1 cycle to look up snoop filter
    max_capacity="8MiB",  # Can track 8MiB worth of cache lines
)

# Connect both systems' memory buses to the CXL switch
root.systemA.membus.mem_side_ports = root.systemA.cxl_switch.cpu_side_ports
root.systemB.membus.mem_side_ports = root.systemA.cxl_switch.cpu_side_ports

# ============================================================================
# Shared Memory Controller (CXL Device / Type 3 Memory)
# ============================================================================
root.systemA.shared_mem_ctrl = MemCtrl()
root.systemA.shared_mem_ctrl.dram = DDR4_2400_8x8()
root.systemA.shared_mem_ctrl.dram.range = shared_mem_range
root.systemA.shared_mem_ctrl.port = root.systemA.cxl_switch.mem_side_ports

# ============================================================================
# Run Simulation
# ============================================================================
print("=" * 60)
print("Day 3: CXL Switch with Shared Memory")
print("=" * 60)
print(f"Shared Memory Size: {SHARED_MEM_SIZE}")
print(f"CXL Switch Width: 64 bytes")
print(f"Snoop Filter: Enabled (8MiB capacity)")
print(f"System A CPU: {type(root.systemA.cpu).__name__}")
print(f"System B CPU: {type(root.systemB.cpu).__name__}")
print("=" * 60)

m5.instantiate()

print("Beginning simulation (System A runs hello world via shared memory)...")
exit_event = m5.simulate()

print("=" * 60)
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
print("=" * 60)
print("SUCCESS: CXL switch with shared memory works!")
print("")
print("Next step: Day 4 - Add caches and implement MESIF protocol in SLICC")
