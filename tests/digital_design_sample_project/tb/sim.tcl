# sim.tcl
# Basic Tcl script for running a simulation in a tool like ModelSim/QuestaSim

# Compile the source files
vlog -sv rtl/*.sv
vlog -sv tb/tb_top_processor.sv

# Start the simulation
vsim -novopt tb_top_processor

# Add waves for key signals
add wave -divider "Pipeline IF/ID"
add wave sim:/tb_top_processor/dut/if_id_ir
add wave sim:/tb_top_processor/dut/if_id_pc

add wave -divider "Pipeline ID/EX"
# ... more waves ...

# Run the simulation
run -all