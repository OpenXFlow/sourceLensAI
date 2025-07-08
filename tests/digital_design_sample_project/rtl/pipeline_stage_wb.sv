// pipeline_stage_wb.sv
// Write Back Stage
module pipeline_stage_wb (
    input logic clk, rst,
    input logic mem_wb_wb_en,
    input logic [4:0] mem_wb_rd,
    input logic [31:0] mem_wb_mem_data,
    input logic [31:0] mem_wb_alu_result
    // Connected to reg_file write port
);
    // This stage selects which result to write back
    // to the register file, but the actual write
    // is handled by the reg_file module.
endmodule