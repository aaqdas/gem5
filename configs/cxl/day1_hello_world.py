# Copyright (c) 2024 CXL Shared Memory Simulation
# Day 1: Hello World Test with AtomicSimpleCPU
#
# This is a minimal configuration to verify gem5 is working.
# Run with: ./build/X86/gem5.opt configs/cxl/day1_hello_world.py

import os
import m5
from m5.objects import *

# Create the system
system = System()

# Clock domain
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "1GHz"
system.clk_domain.voltage_domain = VoltageDomain()

# Memory configuration
system.mem_mode = "atomic"  # Use atomic for fastest simulation
system.mem_ranges = [AddrRange("512MiB")]

# CPU - AtomicSimpleCPU bypasses complex timing issues
system.cpu = AtomicSimpleCPU()

# Memory bus
system.membus = SystemXBar()

# Connect CPU to memory bus
system.cpu.icache_port = system.membus.cpu_side_ports
system.cpu.dcache_port = system.membus.cpu_side_ports

# Create interrupt controller
system.cpu.createInterruptController()

# For X86, connect interrupt controller to memory bus
try:
    system.cpu.interrupts[0].pio = system.membus.mem_side_ports
    system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
    system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports
except:
    pass  # Non-X86 architectures don't need this

# System port
system.system_port = system.membus.cpu_side_ports

# Memory controller
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR4_2400_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

# Find the hello world binary
thispath = os.path.dirname(os.path.realpath(__file__))
gem5_root = os.path.join(thispath, "../..")

# Try different binary locations
binary_paths = [
    os.path.join(gem5_root, "tests/test-progs/hello/bin/x86/linux/hello"),
    os.path.join(gem5_root, "tests/test-progs/hello/bin/arm/linux/hello"),
    os.path.join(gem5_root, "tests/test-progs/hello/bin/riscv/linux/hello"),
]

binary = None
for path in binary_paths:
    if os.path.exists(path):
        binary = path
        break

if binary is None:
    print("ERROR: No hello world binary found!")
    print("Please provide a binary path or build test programs")
    print("Tried:")
    for path in binary_paths:
        print(f"  - {path}")
    exit(1)

print(f"Using binary: {binary}")

# Setup workload
system.workload = SEWorkload.init_compatible(binary)

process = Process()
process.cmd = [binary]
system.cpu.workload = process
system.cpu.createThreads()

# Create root and run
root = Root(full_system=False, system=system)
m5.instantiate()

print("=" * 60)
print("Day 1: Hello World Test")
print("=" * 60)
print("Beginning simulation...")

exit_event = m5.simulate()

print("=" * 60)
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
print("=" * 60)

if "exiting with last active thread context" in exit_event.getCause():
    print("SUCCESS: Hello World completed!")
else:
    print(f"Note: Exit reason was: {exit_event.getCause()}")
