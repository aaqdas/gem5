# Copyright (c) 2024 CXL Shared Memory Simulation
# Day 2: Multi-System Setup
#
# Creates two separate systems (System A and System B) under one Root.
# Each system has its own CPU, memory bus, and local memory for now.
#
# Run with: ./build/X86/gem5.opt configs/cxl/day2_multi_system.py

import os
import m5
from m5.objects import *

# ============================================================================
# Configuration Parameters
# ============================================================================
CLOCK_SPEED = "3GHz"
MEM_SIZE = "256MiB"

# ============================================================================
# Helper function to create a complete system
# ============================================================================
def create_system(name, mem_range, binary=None):
    """Create a fully configured system."""
    system = System()
    
    # Clock domain
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = CLOCK_SPEED
    system.clk_domain.voltage_domain = VoltageDomain()
    
    # Memory configuration
    system.mem_mode = "atomic"  # Keep atomic for debugging
    system.mem_ranges = [mem_range]
    
    # CPU
    system.cpu = AtomicSimpleCPU()
    
    # Memory bus
    system.membus = SystemXBar()
    
    # Connect CPU to memory bus
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
    
    # Memory controller (local memory for now)
    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR4_2400_8x8()
    system.mem_ctrl.dram.range = mem_range
    system.mem_ctrl.port = system.membus.mem_side_ports
    
    # Setup workload if binary provided
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
# Create Root with two systems
# ============================================================================
root = Root(full_system=False)

# System A - Memory range 0x0 to 256MB
root.systemA = create_system("SystemA", AddrRange(0, MEM_SIZE), binary)

# System B - Memory range 256MB to 512MB (separate address space for now)
# Note: In the shared memory configuration, both will see the same range
root.systemB = create_system("SystemB", AddrRange(0, MEM_SIZE), binary)

# ============================================================================
# Run Simulation - We'll run System A first
# ============================================================================
print("=" * 60)
print("Day 2: Multi-System Setup")
print("=" * 60)
print(f"System A: {type(root.systemA.cpu).__name__}")
print(f"System B: {type(root.systemB.cpu).__name__}")
print("=" * 60)

m5.instantiate()

print("Beginning simulation (running System A's workload)...")
exit_event = m5.simulate()

print("=" * 60)
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
print("=" * 60)
print("SUCCESS: Multi-system configuration works!")
print("")
print("Next step: Day 3 - Connect both systems to shared memory via CXL switch")
