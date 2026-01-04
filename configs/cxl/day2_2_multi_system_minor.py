# Copyright (c) 2024 CXL Shared Memory Simulation
# Day 2.2: Multi-System with X86MinorCPU
#
# Two independent systems, each with their own MinorCPU and local memory.
# This demonstrates multi-system simulation before adding shared memory.
#
# Run with: ./build/X86/gem5.opt configs/cxl/day2_2_multi_system_minor.py

import os
import m5
from m5.objects import *
# from sim import Root

# ============================================================================
# Configuration Parameters
# ============================================================================
CLOCK_SPEED = "3GHz"
MEM_SIZE_PER_SYSTEM = "256MiB"

# ============================================================================
# Helper function to create a standalone system
# ============================================================================
def create_standalone_system(name, mem_start, mem_size, binary=None):
    """
    Create a complete standalone system with its own CPU and local memory.
    """
    system = System()
    
    # Clock domain
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = CLOCK_SPEED
    system.clk_domain.voltage_domain = VoltageDomain()
    
    # Memory configuration - each system has its own address range
    mem_range = AddrRange(mem_start, size=mem_size)
    system.mem_mode = "timing"
    system.mem_ranges = [mem_range]
    
    # CPU - X86MinorCPU provides a 4-stage in-order pipeline
    system.cpu = X86MinorCPU()
    
    # Memory bus
    system.membus = SystemXBar()
    
    # Connect CPU to memory bus
    system.cpu.icache_port = system.membus.cpu_side_ports
    system.cpu.dcache_port = system.membus.cpu_side_ports
    
    # Interrupt controller (required for X86)
    system.cpu.createInterruptController()
    system.cpu.interrupts[0].pio = system.membus.mem_side_ports
    system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
    system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports
    
    # System port
    system.system_port = system.membus.cpu_side_ports
    
    # Local memory controller
    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR4_2400_8x8()
    system.mem_ctrl.dram.range = mem_range
    system.mem_ctrl.port = system.membus.mem_side_ports
    
    # Setup workload
    if binary and os.path.exists(binary):
        system.workload = SEWorkload.init_compatible(binary)
        process = Process()
        process.cmd = [binary]
        system.cpu.workload = process
    
    # Always create threads for ISA initialization
    system.cpu.createThreads()
    
    return system

# ============================================================================
# Find Binary
# ============================================================================
thispath = os.path.dirname(os.path.realpath(__file__))
gem5_root = os.path.join(thispath, "../..")
binary = os.path.join(gem5_root, "tests/test-progs/hello/bin/x86/linux/hello")

if not os.path.exists(binary):
    print(f"ERROR: Binary not found at {binary}")
    exit(1)

print(f"Using binary: {binary}")

# ============================================================================
# Create Root with Two Systems
# ============================================================================
systemA = create_standalone_system(
    "SystemA", 
    "0x00000000", 
    MEM_SIZE_PER_SYSTEM, 
    binary  # Run hello world on System A
)
systemB = create_standalone_system(
    "SystemB", 
    "0x10000000", 
    MEM_SIZE_PER_SYSTEM, 
    binary  # System B is idle
)
root = Root(full_system=False, system=[systemA, systemB])

# Create two independent systems with separate memory regions
# System A: 0x00000000 - 0x10000000 (256 MiB)
# System B: 0x10000000 - 0x20000000 (256 MiB)
# root.systemA = create_standalone_system(
#     "SystemA", 
#     "0x00000000", 
#     MEM_SIZE_PER_SYSTEM, 
#     binary  # Run hello world on System A
# )

# root.systemB = create_standalone_system(
#     "SystemB", 
#     "0x10000000", 
#     MEM_SIZE_PER_SYSTEM, 
#     None  # System B is idle
# )

print(root)

# ============================================================================
# Run Simulation
# ============================================================================
# print("=" * 60)
# print("Day 2.2: Multi-System with X86MinorCPU")
# print("=" * 60)
# print(f"System A:")
# print(f"  CPU: {type(root.systemA.cpu).__name__}")
# print(f"  Memory: {MEM_SIZE_PER_SYSTEM} @ 0x00000000")
# print(f"  Workload: hello world")
# print(f"System B:")
# print(f"  CPU: {type(root.systemB.cpu).__name__}")
# print(f"  Memory: {MEM_SIZE_PER_SYSTEM} @ 0x10000000")
# print(f"  Workload: idle")
# print("=" * 60)

m5.instantiate()

print("Beginning simulation (System A runs hello world)...")
exit_event = m5.simulate()

print("=" * 60)
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
print("=" * 60)

if "exiting with last active thread context" in exit_event.getCause():
    print("SUCCESS: Multi-system simulation completed!")
else:
    print(f"Note: Exit reason was: {exit_event.getCause()}")

print("")
print("Architecture:")
print("  ┌─────────────┐    ┌─────────────┐")
print("  │  System A   │    │  System B   │")
print("  │ X86MinorCPU │    │ X86MinorCPU │")
print("  │      │      │    │      │      │")
print("  │  [membus]   │    │  [membus]   │")
print("  │      │      │    │      │      │")
print("  │  [DDR4]     │    │  [DDR4]     │")
print("  │  256 MiB    │    │  256 MiB    │")
print("  └─────────────┘    └─────────────┘")
print("   (independent)      (independent)")
print("")
print("Next step: Day 3 - Connect systems via CXL Switch with shared memory")
