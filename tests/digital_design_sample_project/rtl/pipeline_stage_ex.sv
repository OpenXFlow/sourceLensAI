// pipeline_stage_ex.sv
// Execute Stage
module pipeline_stage_ex (
    input  logic [31:0] id_ex_rs1_data,
    input  logic [31:0] id_ex_rs2_data,
    // ... other inputs
    output logic [31:0] ex_mem_alu_result
);

    alu u_alu (
        .a(id_ex_rs1_data),
        .b(id_ex_rs2_data),
        // ... control inputs
        .result(ex_mem_alu_result)
    );

endmodule