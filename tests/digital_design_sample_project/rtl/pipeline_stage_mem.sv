// pipeline_stage_mem.sv
// Memory Access Stage
module pipeline_stage_mem (
    input  logic        clk, rst,
    input  logic [31:0] ex_mem_alu_result, // Address
    input  logic [31:0] ex_mem_write_data, // Data to write
    input  logic        mem_write_en,
    output logic [31:0] mem_wb_mem_data
);

    // Simplified data memory model
    logic [31:0] data_mem [0:255];

    assign mem_wb_mem_data = data_mem[ex_mem_alu_result >> 2];

    always_ff @(posedge clk) begin
        if (mem_write_en) begin
            data_mem[ex_mem_alu_result >> 2] <= ex_mem_write_data;
        end
    end

endmodule