// pipeline_stage_if.sv
// Instruction Fetch Stage
module pipeline_stage_if (
    input  logic clk,
    input  logic rst,
    output logic [31:0] if_id_ir,
    output logic [31:0] if_id_pc
);

    logic [31:0] pc_reg;
    // Simplified instruction memory model
    logic [31:0] instr_mem [0:255]; 

    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            pc_reg <= 32'h0;
        end else begin
            pc_reg <= pc_reg + 4;
        end
    end

    assign if_id_ir = instr_mem[pc_reg >> 2];
    assign if_id_pc = pc_reg;

endmodule