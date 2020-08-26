# to run:
# quartus_sh -t setup_sync_proj.tcl

project_open top

set_global_assignment -name SDC_FILE sdc/fmax_delay.sdc
set_global_assignment -name SDC_FILE sdc/path_delays.sdc
set_global_assignment -name SDC_FILE sdc/path_delays_debug.sdc
set_global_assignment -name ALLOW_REGISTER_RETIMING OFF
set_global_assignment -name SOURCE_FILE board_top.v
set_global_assignment -name TOP_LEVEL_ENTITY board_top
set_global_assignment -name SOURCE_FILE connect_top.v
set_global_assignment -name SOURCE_FILE pll/pll/pll_0002.v
set_global_assignment -name SOURCE_FILE pll/pll/pll_0002.qip
set_global_assignment -name SOURCE_FILE pll/pll.v
set_global_assignment -name SOURCE_FILE pll/pll.qip
set_global_assignment -name SOURCE_FILE dynamic_clock.v
project_close

# EOF
