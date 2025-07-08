// tb_top_processor.sv
// Testbench for the top-level processor module.
`timescale 1ns/1ps

module tb_top_processor;
    logic clk;
    logic rst;

    // Instantiate the DUT
    top_processor dut (
        .clk(clk),
        .rst(rst)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    // Test sequence
    initial begin
        rst = 1;
        #20;
        rst = 0;
        
        // Here you would load a program into the instruction memory
        // and check the results in the register file or data memory.
        
        #500;
        $finish;
    end

endmodule