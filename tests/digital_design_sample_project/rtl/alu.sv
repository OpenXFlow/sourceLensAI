// alu.sv
// Arithmetic Logic Unit
module alu (
    input  logic [31:0] a, b,
    input  logic [3:0]  alu_op,
    output logic [31:0] result
);

    always_comb begin
        case (alu_op)
            4'b0001: result = a + b;  // ADD
            4'b0010: result = a - b;  // SUB
            4'b0011: result = a & b;  // AND
            4'b0100: result = a | b;  // OR
            default: result = 32'h0;
        endcase
    end

endmodule