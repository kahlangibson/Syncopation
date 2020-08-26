package require cmdline

project_open top
create_timing_netlist
read_sdc
update_timing_netlist

set clk [report_clock_fmax_summary]
puts $clk

delete_timing_netlist
project_close