package require cmdline

set to [lindex $argv 0]
set from [lindex $argv 1]

puts to 
puts from

project_open top
create_timing_netlist
read_sdc
update_timing_netlist

set tuple [report_timing -detail summary -from_clock { dyn_clk } -to_clock { dyn_clk } -to $to -from $from -setup -npaths 1 -nworst 1 -pairs_only]
set num [lindex $tuple 0]
set result [lindex $tuple 1]

puts "Slack: $result"

delete_timing_netlist
project_close