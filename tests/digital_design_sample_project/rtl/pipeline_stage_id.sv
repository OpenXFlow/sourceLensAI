// pipeline_stage_id.sv
// Instruction Decode Stage
module pipeline_stage_id (
    input  logic        clk,
    input  logic        rst,
    input  logic [31:0] if_id_ir,
    input  logic [31:0] if_id_pc,
    output logic [31:0] id_ex_rs1_data,
    output logic [31:0] id_ex_rs2_data
    // ... other outputs for control signals
);
    logic [4:0] rs1, rs2;
    assign rs1 = if_id_ir[19:15];
    assign rs2 = if_id_ir[24:20];

    reg_file u_reg_file (
        .clk(clk),
        .rst(rst),
        .rs1(rs1),
        .rs2(rs2),
        .rd_data1(id_ex_rs1_data),
        .rd_data2(id_ex_rs2_data)
        // ... other connections
    );

endmodule