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

from string import Template 

rom_file_template = Template("""
`timescale 1 ps / 1 ps
// synopsys translate_on
module ${module}_rom (
	address_a,
	address_b,
	clock,
	q_a,
	q_b);

	input	[${addr_w}-1:0]  address_a;
	input	[${addr_w}-1:0]  address_b;
	input	  clock;
	output	[${data_w}-1:0]  q_a;
	output	[${data_w}-1:0]  q_b;
`ifndef ALTERA_RESERVED_QIS
// synopsys translate_off
`endif
	tri1	  clock;
`ifndef ALTERA_RESERVED_QIS
// synopsys translate_on
`endif

	wire [${data_w}-1:0] sub_wire0;
	wire [${data_w}-1:0] sub_wire1;
	wire [${data_w}-1:0] sub_wire2 = ${data_w}'b0;
	wire  sub_wire3 = 1'h0;
	wire [${data_w}-1:0] q_a = sub_wire0[${data_w}-1:0];
	wire [${data_w}-1:0] q_b = sub_wire1[${data_w}-1:0];

	altsyncram	altsyncram_component (
				.address_a (address_a),
				.address_b (address_b),
				.clock0 (clock),
				.data_a (sub_wire2),
				.data_b (sub_wire2),
				.wren_a (sub_wire3),
				.wren_b (sub_wire3),
				.q_a (sub_wire0),
				.q_b (sub_wire1)
				// synopsys translate_off
				,
				.aclr0 (),
				.aclr1 (),
				.addressstall_a (),
				.addressstall_b (),
				.byteena_a (),
				.byteena_b (),
				.clock1 (),
				.clocken0 (),
				.clocken1 (),
				.clocken2 (),
				.clocken3 (),
				.eccstatus (),
				.rden_a (),
				.rden_b ()
				// synopsys translate_on
				);
	defparam
		altsyncram_component.address_reg_b = "CLOCK0",
		altsyncram_component.clock_enable_input_a = "BYPASS",
		altsyncram_component.clock_enable_input_b = "BYPASS",
		altsyncram_component.clock_enable_output_a = "BYPASS",
		altsyncram_component.clock_enable_output_b = "BYPASS",
		altsyncram_component.indata_reg_b = "CLOCK0",
		altsyncram_component.init_file = "${mif_file}",
		altsyncram_component.intended_device_family = "Cyclone V",
		altsyncram_component.lpm_type = "altsyncram",
		altsyncram_component.numwords_a = ${depth},
		altsyncram_component.numwords_b = ${depth},
		altsyncram_component.operation_mode = "BIDIR_DUAL_PORT",
		altsyncram_component.outdata_aclr_a = "NONE",
		altsyncram_component.outdata_aclr_b = "NONE",
		altsyncram_component.outdata_reg_a = "UNREGISTERED",
		altsyncram_component.outdata_reg_b = "UNREGISTERED",
		altsyncram_component.power_up_uninitialized = "FALSE",
		altsyncram_component.ram_block_type = "M10K",
		altsyncram_component.widthad_a = ${addr_w},
		altsyncram_component.widthad_b = ${addr_w},
		altsyncram_component.width_a = ${data_w},
		altsyncram_component.width_b = ${data_w},
		altsyncram_component.width_byteena_a = 1,
		altsyncram_component.width_byteena_b = 1,
		altsyncram_component.wrcontrol_wraddress_reg_b = "CLOCK0";


endmodule
""")

qip_file_template = Template("""set_global_assignment -name IP_TOOL_NAME "ROM: 1-PORT"
set_global_assignment -name IP_TOOL_VERSION "15.0"
set_global_assignment -name IP_GENERATED_DEVICE_FAMILY "{Cyclone V}"
set_global_assignment -name VERILOG_FILE [file join $::quartus(qip_path) "${module}.v"]
""")

top_template = Template("""`define NUM_INST ${num_inst}
`define ADDR_W ${addr_w}
`define DIV_W ${div_w}

module board_top (CLOCK_50,KEY,SW,HEX0,HEX1,HEX2,HEX3,HEX4,HEX5,LEDR);
input CLOCK_50;
input [3:0] KEY;
input [9:0] SW;
output [6:0] HEX5,HEX4,HEX3,HEX2,HEX1,HEX0;
output [9:0] LEDR;

connect_top #(.DIV_W(`DIV_W),.NUM_INST(`NUM_INST),.ADDR_W(`ADDR_W)) connect_top_INST
(.CLOCK_50(CLOCK_50),.KEY(KEY),.SW(SW),.HEX0(HEX0),.HEX1(HEX1),.HEX2(HEX2),.HEX3(HEX3),.HEX4(HEX4),.HEX5(HEX5),.LEDR(LEDR));
endmodule
""")

header_template =Template("""package require cmdline 
set project_sdc "${sdc}"
project_open top
create_timing_netlist
read_sdc $$project_sdc
update_timing_netlist

""")
request_template = Template("""puts "report_timing -from_clock { dyn_clk } -to_clock { dyn_clk } -setup -${dir} ${reg} -nworst 1"
set tuple [report_timing -from_clock { dyn_clk } -to_clock { dyn_clk } -setup -${dir} ${reg} -nworst 1]
set num [lindex $$tuple 0]
set result [lindex $$tuple 1]
puts "State ${state} ${dir} ${reg} $priority Delay $$result"
""") # dir = to/from, Type = Drain/Source

request_template_dual = Template("""puts "report_timing -from_clock { dyn_clk } -to_clock { dyn_clk } -setup -to ${to} -from ${from} -nworst 1"
set tuple [report_timing -from_clock { dyn_clk } -to_clock { dyn_clk } -setup -to ${to} -from ${from} -nworst 1]
set num [lindex $$tuple 0]
set result [lindex $$tuple 1]
puts "State ${state} from $from to $to $priority Delay $$result"
""") 

sdc_template = Template("""
set_max_delay -${dir} ${reg} ${freq}
""")

sdc_template_dual = Template("""
set_max_delay -from ${from} -to ${to} ${freq}
""")