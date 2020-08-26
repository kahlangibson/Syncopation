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

File: dynamic_clock.v

Integer divider clock
**/
module dynamic_clock
    #( 
        parameter M = 4,
        parameter [M-1:0] init = 2
    )(
        valid,
        frequency_setting_request,
        clk_fast,
        clk
    );

    input valid;
    input [M-1:0] frequency_setting_request;
    input clk_fast;
    wire clk_d;
    output reg clk;

    wire zero_n;
    reg [M-1:0] count;
    reg [M-1:0] frequency_setting;
    reg [M-1:0] fs;
    initial frequency_setting = {(M){1'b0}}+init;

    reg [3:0] next_count;
    always @(*) begin 
        if (~zero_n) next_count = {M{1'b0}};
        else next_count = count + 1'b1;
    end 

    always @(posedge clk_fast) begin 
        count = next_count;
    end

    assign zero_n = (count < fs - 1'b1) ? 1'b1 : 1'b0;
    assign clk_d = (count < {1'b0, fs[M-1:1]}) ? 1'b1 : 1'b0;
    always @(posedge clk_fast) clk = clk_d; // register to prevent glitches

    always @(posedge clk_fast) begin  
        if (valid) frequency_setting = frequency_setting_request;
        else frequency_setting = frequency_setting;
        fs = frequency_setting;
    end

endmodule