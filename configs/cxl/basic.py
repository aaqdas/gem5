# Copyright (c) 2024 CXL Shared Memory Simulation
# All rights reserved.
#
# Multi-Board CXL Shared Memory Configuration
# Two systems sharing memory through a CXL Switch with Snoop Filter

import os
import m5
from m5.objects import *
from m5.util import addToPath

# ============================================================================
# PHASE 1: Multi-Board Python Configuration
# ============================================================================
# This configuration creates two systems that share a single memory address
# space. In gem5, this is achieved by placing two System objects under one Root.

# Define the shared memory range that both systems will access
SHARED_MEM_SIZE = "512MiB"  # Start smaller for testing
SHARED_MEM_RANGE = AddrRange(SHARED_MEM_SIZE)

# ============================================================================
# Helper function to create a complete system
# ============================================================================
def create_system(system_name, mem_range, binary_path=None):
    """
    Create a fully configured system with CPU, caches, and memory bus.
    
    Args:
        system_name: Name identifier for the system
        mem_range: Address range for memory
        binary_path: Path to the binary to run (optional)
    
    Returns:
        Configured System object
    """
    system = System()
    
    # Clock domain setup
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = "3GHz"
    system.clk_domain.voltage_domain = VoltageDomain()
    
    # Memory configuration
    system.mem_mode = "timing"  # Use timing mode for accurate simulation
    system.mem_ranges = [mem_range]
    
    # CPU selection - Start with AtomicSimpleCPU for debugging
    # Switch to TimingSimpleCPU once basic functionality works
    system.cpu = AtomicSimpleCPU()  # Day 1: Use Atomic to bypass timing errors
    # system.cpu = TimingSimpleCPU()  # Use this later for accurate timing
    
    # Memory bus (system interconnect)
    system.membus = SystemXBar()
    
    # Connect CPU to memory bus
    system.cpu.icache_port = system.membus.cpu_side_ports
    system.cpu.dcache_port = system.membus.cpu_side_ports
    
    # Create interrupt controller (required for X86)
    system.cpu.createInterruptController()
    
    # For X86, connect interrupt controller to memory bus
    if m5.defines.buildEnv['USE_X86_ISA']:
        system.cpu.interrupts[0].pio = system.membus.mem_side_ports
        system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
        system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports
    
    # System port for functional access
    system.system_port = system.membus.cpu_side_ports
    
    # Setup workload if binary is provided
    if binary_path and os.path.exists(binary_path):
        system.workload = SEWorkload.init_compatible(binary_path)
        process = Process()
        process.cmd = [binary_path]
        system.cpu.workload = process
        system.cpu.createThreads()
    
    return system


# ============================================================================
# Day 1: Simple Hello World Test (AtomicSimpleCPU)
# ============================================================================
# First, let's get a basic single-system hello world working

# Path to test binary - adjust based on your gem5 build
thispath = os.path.dirname(os.path.realpath(__file__))
gem5_root = os.path.join(thispath, "../..")

# Try to find hello world binary
hello_binary = os.path.join(gem5_root, "tests/test-progs/hello/bin/x86/linux/hello")

# Fallback: Check if binary exists
if not os.path.exists(hello_binary):
    print(f"Warning: Hello binary not found at {hello_binary}")
    print("You may need to build test programs or provide your own binary")
    hello_binary = None

# ============================================================================
# Create the Root with Single System (Day 1 testing)
# ============================================================================
# For Day 1, start with a single system to verify basic functionality

root = Root(full_system=False)

# Create System A
root.systemA = create_system("SystemA", SHARED_MEM_RANGE, hello_binary)

# ============================================================================
# Memory Controller for System A (local memory for now)
# ============================================================================
root.systemA.mem_ctrl = MemCtrl()
root.systemA.mem_ctrl.dram = DDR4_2400_8x8()
root.systemA.mem_ctrl.dram.range = root.systemA.mem_ranges[0]
root.systemA.mem_ctrl.port = root.systemA.membus.mem_side_ports

# ============================================================================
# Day 2: Add System B (uncomment when Day 1 works)
# ============================================================================
# root.systemB = create_system("SystemB", SHARED_MEM_RANGE, hello_binary)
# 
# # Local memory for System B (temporary - will be replaced by shared memory)
# root.systemB.mem_ctrl = MemCtrl()
# root.systemB.mem_ctrl.dram = DDR4_2400_8x8()
# root.systemB.mem_ctrl.dram.range = root.systemB.mem_ranges[0]
# root.systemB.mem_ctrl.port = root.systemB.membus.mem_side_ports

# ============================================================================
# Day 3-4: CXL Switch with Snoop Filter (uncomment when Day 2 works)
# ============================================================================
# The CXL Switch is implemented as a CoherentXBar with Snoop Filter
# This enables cache coherence across the two systems

# # Create the CXL Switch (CoherentXBar with Snoop Filter)
# root.cxl_switch = CoherentXBar(
#     width=64,  # 64-byte cache line width
#     frontend_latency=3,
#     forward_latency=4,
#     response_latency=2,
#     snoop_response_latency=4,
#     point_of_coherency=True,  # This is the coherence point
#     point_of_unification=True,
# )
# 
# # Enable MESIF-style snoop filter
# root.cxl_switch.snoop_filter = SnoopFilter(
#     lookup_latency=1,  # 1 cycle lookup
#     max_capacity="8MiB",  # Track up to 8MiB of cache lines
# )
# 
# # Connect both systems to the CXL switch
# root.systemA.membus.mem_side_ports = root.cxl_switch.cpu_side_ports
# root.systemB.membus.mem_side_ports = root.cxl_switch.cpu_side_ports
# 
# # Shared Memory Controller (The CXL Device)
# root.shared_mem_ctrl = MemCtrl()
# root.shared_mem_ctrl.dram = DDR4_2400_8x8()
# root.shared_mem_ctrl.dram.range = SHARED_MEM_RANGE
# root.shared_mem_ctrl.port = root.cxl_switch.mem_side_ports

# ============================================================================
# Day 6: CXL Header Latency (uncomment for CXL-accurate timing)
# ============================================================================
# CXL adds approximately 100ns latency for the protocol header
# This can be modeled by adding extra latency to the crossbar

# CXL_HEADER_LATENCY_NS = 100  # nanoseconds
# CXL_CLOCK_PERIOD_NS = 1 / 3  # 3GHz = ~0.333ns per cycle
# CXL_HEADER_LATENCY_CYCLES = int(CXL_HEADER_LATENCY_NS / CXL_CLOCK_PERIOD_NS)
# 
# root.cxl_switch.frontend_latency = CXL_HEADER_LATENCY_CYCLES

# ============================================================================
# Instantiate and Run Simulation
# ============================================================================
print("=" * 60)
print("CXL Shared Memory Simulation")
print("=" * 60)
print(f"Memory Range: {SHARED_MEM_SIZE}")
print(f"CPU Type: {type(root.systemA.cpu).__name__}")
if hello_binary:
    print(f"Binary: {hello_binary}")
print("=" * 60)

# Instantiate the simulation
m5.instantiate()

print("Beginning simulation...")
exit_event = m5.simulate()
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")