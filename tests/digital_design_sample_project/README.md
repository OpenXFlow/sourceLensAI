# Simple 5-Stage RISC-V Processor Core

This project contains the SystemVerilog implementation of a basic 5-stage pipelined processor based on a subset of the RISC-V instruction set architecture (ISA).

## Key Features:
- 5-stage pipeline: Instruction Fetch (IF), Instruction Decode (ID), Execute (EX), Memory Access (MEM), Write Back (WB).
- Basic integer instructions (add, sub, and, or, lw, sw, beq).
- Separate modules for each pipeline stage and key hardware components (ALU, Register File).

## Directory Structure:
- `rtl/`: Contains all synthesizable SystemVerilog source files for the processor core.
- `tb/`: Contains the testbench and simulation scripts.
- `constraints/`: Contains timing and physical constraints for synthesis.