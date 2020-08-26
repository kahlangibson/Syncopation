/**
#-----------------------------------------------------------------------------
# Copyright (c) 2020 Kahlan Gibson
# kahlangibson<at>ece.ubc.ca
#
# Permission to use, copy, and modify this software and its documentation is
# hereby granted only under the following terms and conditions. Both the
# above copyright notice and this permission notice must appear in all copies
# of the software, derivative works or modified versions, and any portions
# thereof, and both notices must appear in supporting documentation.
# This software may be distributed (but not offered for sale or transferred
# for compensation) to third parties, provided such third parties agree to
# abide by the terms and conditions of this notice.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHORS, AS WELL AS THE UNIVERSITY
# OF BRITISH COLUMBIA DISCLAIM ALL WARRANTIES WITH REGARD TO THIS SOFTWARE,
# INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO 
# EVENT SHALL THE AUTHORS OR THE UNIVERSITY OF BRITISH COLUMBIA BE LIABLE
# FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR
# IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#---------------------------------------------------------------------------

File: syncopation_top.v

This top-level module connects the I/O on the DE1-SoC board
to a legup-generated top level module, driven by a dynamic
clock.
**/

module connect_top #(parameter DIV_W, parameter NUM_INST, parameter ADDR_W) (
	CLOCK_50,
	KEY,
	SW,
	HEX0,
	HEX1,
	HEX2,
	HEX3,
	HEX4,
	HEX5,
	LEDR
	);

	input CLOCK_50;
	input [3:0] KEY;
	input [9:0] SW;
	output [6:0] HEX0, HEX1, HEX2, HEX3, HEX4, HEX5;
	reg [6:0] hex0, hex1, hex2, hex3, hex4, hex5;
	output [9:0] LEDR;

	wire go = ~KEY[1]; // press KEY1 to begin
	wire reset = ~KEY[0]; // press KEY0 to reset
	wire pll_reset = ~KEY[3];

	// PLL for clk_fast
	wire clk_fast, locked;
	pll PLL_INST (
		.refclk(CLOCK_50),
		.rst(pll_reset),
		.outclk_0(clk_fast),
		.locked(locked)
	);	

	// dynamic_clock to generate clk
	wire clk;
	reg valid;
	initial valid = 1'b0;
	reg [DIV_W-1:0] div_in;
	dynamic_clock #(.M(DIV_W), .init({DIV_W{1'b1}})) CLOCK_GEN (
		.valid(valid),
		.frequency_setting_request(div_in),
		.clk_fast(clk_fast),
		.clk(clk)
	);

	// top_inst
	wire [DIV_W-1:0] div;
	wire [31:0] return_val;
	wire start, finish;
	top top_inst (
		.div_top_reg(div),
		.clk(clk),
		.reset(reset),
		.finish(finish),
		.return_val(return_val),
		.start(start)
	);

	// controller
	parameter s_WAIT=3'b000, s_START=3'b001, s_EXE=3'b010, s_DONE=3'b011, s_EXE1=3'b101;
	reg [3:0] c_state, n_state; // current and next state

	assign start = (c_state == s_START);

	// next state logic
	always @* begin 
		case (c_state)
			s_WAIT: if (go) n_state = s_START; else n_state = s_WAIT; 
			s_START: n_state = s_EXE1;
			s_EXE1:  if (!finish) n_state = s_EXE; else n_state = s_DONE; // this state we still have 0xF divisor
			s_EXE:   if (!finish) n_state = s_EXE; else n_state = s_DONE;
			s_DONE:  n_state = s_DONE;
			default: n_state = 3'bxxx;
		endcase
	end 

	// synchronous reset logic
	always @(posedge clk) begin 
		if (reset) c_state <= s_WAIT;
		else c_state <= n_state;
	end

	// clock div valid signal logic 
	always @* begin 
		case (c_state)
			s_EXE1,s_EXE: valid <= 1'b1;
			default: if (reset) valid <= 1'b1; else valid <= 1'b0;
		endcase
	end
	
	// clock div signal logic 
	parameter minimum = 2;
	always @* begin 
        case (c_state) 
            s_WAIT,s_DONE,s_START: div_in <= {DIV_W{1'b1}};
            s_EXE1,s_EXE: if (finish) div_in <= {DIV_W{1'b1}};
					else if (div < minimum) div_in <= {DIV_W{1'b1}};
				   else div_in <= div;
            default: div_in <= {DIV_W{1'b1}};
        endcase 
	end 

	reg [31:0] return_val_reg;
	always @(posedge clk) begin
		if (((c_state == s_EXE)||(c_state == s_EXE1)) && finish) begin
			return_val_reg <= return_val;
		end else if (c_state == s_WAIT) begin
			return_val_reg <= 0;
		end else begin
			return_val_reg <= return_val_reg;
		end
	end 

	// hex display (ls 24 b)
	always @(*) begin 
		hex5 <= return_val_reg[23:20]|return_val_reg[31:28];
		hex4 <= return_val_reg[19:16]|return_val_reg[27:24];
		hex3 <= return_val_reg[15:12];
		hex2 <= return_val_reg[11:8];
		hex1 <= return_val_reg[7:4];
		hex0 <= return_val_reg[3:0];
	end

 	hex_digits h5( .x(hex5), .hex_LEDs(HEX5));
 	hex_digits h4( .x(hex4), .hex_LEDs(HEX4));
  	hex_digits h3( .x(hex3), .hex_LEDs(HEX3));
   	hex_digits h2( .x(hex2), .hex_LEDs(HEX2));
   	hex_digits h1( .x(hex1), .hex_LEDs(HEX1));
   	hex_digits h0( .x(hex0), .hex_LEDs(HEX0));

endmodule