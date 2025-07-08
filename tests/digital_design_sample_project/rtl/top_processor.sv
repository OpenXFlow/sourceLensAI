// top_processor.sv
// Top-level module connecting the 5 pipeline stages.
module top_processor (
    input logic clk,
    input logic rst
);

// Pipeline registers and inter-stage signals
logic [31:0] if_id_ir, if_id_pc;
logic [31:0] id_ex_ir, id_ex_pc, id_ex_rs1_data, id_ex_rs2_data;
logic [31:0] ex_mem_alu_result, ex_mem_write_data;
logic [4:0]  ex_mem_rd;
logic        ex_mem_wb_en;
logic [31:0] mem_wb_mem_data, mem_wb_alu_result;
logic [4:0]  mem_wb_rd;
logic        mem_wb_wb_en;

// Instantiate Pipeline Stages
pipeline_stage_if u_if_stage (.*);
pipeline_stage_id u_id_stage (.*);
pipeline_stage_ex u_ex_stage (.*);
pipeline_stage_mem u_mem_stage (.*);
pipeline_stage_wb u_wb_stage (.*);

endmodule