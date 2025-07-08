# processor.xdc
# Example timing constraints for a Xilinx FPGA

# Create a 100MHz clock
create_clock -period 10.000 -name clk [get_ports clk]

# Reset should be asynchronous
set_property ASYNC_REG TRUE [get_cells -hierarchical -filter {NAME =~ *rst*}]