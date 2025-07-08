// reg_file.sv
// Register File
module reg_file (
    input  logic clk, rst,
    input  logic wr_en,
    input  logic [4:0] rs1, rs2, rd,
    input  logic [31:0] wr_data,
    output logic [31:0] rd_data1, rd_data2
);

    logic [31:0] registers [0:31];

    assign rd_data1 = registers[rs1];
    assign rd_data2 = registers[rs2];

    always_ff @(posedge clk) begin
        if (rst) begin
            // Reset logic
        end else if (wr_en) begin
            registers[rd] <= wr_data;
        end
    end

endmodule