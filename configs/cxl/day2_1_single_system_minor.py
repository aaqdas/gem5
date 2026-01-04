# Copyright (c) 2024 CXL Shared Memory Simulation
# Day 2.1: Single System with X86MinorCPU
#
# A single system with an in-order MinorCPU pipeline.
# This provides realistic timing with a 4-stage pipeline.
#
# Run with: ./build/X86/gem5.opt configs/cxl/day2_1_single_system_minor.py

import os
import m5
from m5.objects import *

# ============================================================================
# Configuration Parameters
# ============================================================================
CLOCK_SPEED = "3GHz"
MEM_SIZE = "512MiB"

# ============================================================================
# Create the System
# ============================================================================
system = System()

# Clock domain
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = CLOCK_SPEED
system.clk_domain.voltage_domain = VoltageDomain()

# Memory configuration
system.mem_mode = "timing"  # Required for MinorCPU
system.mem_ranges = [AddrRange(MEM_SIZE)]

# CPU - X86MinorCPU provides a 4-stage in-order pipeline
# Stages: Fetch1 -> Fetch2 -> Execute -> Commit
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

# Memory controller
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR4_2400_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

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
# Create Root and Run Simulation
# ============================================================================
root = Root(full_system=False, system=system)

print("=" * 60)
print("Day 2.1: Single System with X86MinorCPU")
print("=" * 60)
print(f"CPU: X86MinorCPU (4-stage in-order pipeline)")
print(f"Clock: {CLOCK_SPEED}")
print(f"Memory: {MEM_SIZE}")
print(f"Memory Mode: timing")
print("=" * 60)

m5.instantiate()

print("Beginning simulation...")
exit_event = m5.simulate()

print("=" * 60)
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
print("=" * 60)

if "exiting with last active thread context" in exit_event.getCause():
    print("SUCCESS: Hello World completed with MinorCPU!")
else:
    print(f"Note: Exit reason was: {exit_event.getCause()}")

print("")
print("Next step: Day 2.2 - Multi-System with MinorCPU")
