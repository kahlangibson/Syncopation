#-----------------------------------------------------------------------------
# Copyright (c) 2020 Kahlan Gibson, Esther Roorda
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

from .misc import read_file, execute, save
import os, math
from .string_templates import header_template, request_template, request_template_dual, sdc_template, sdc_template_dual
from .verilog_processing import get_num_bits, get_num_nStates, get_states
from .settings import *

def perform_sta(verilog_file):
    project_folder = os.path.dirname(os.path.abspath(verilog_file))
    project_name = verilog_file.split(".")[0]
    out_dir = project_name+"_files"

    states_per_module = read_file(os.path.join(out_dir,"hls_statesPerModule.json"))
    drains_per_state = read_file(os.path.join(out_dir, "drainsPerState.json"))
    sources_per_state = read_file(os.path.join(out_dir, "sourcesPerState.json"))
    memory_drains_per_state = read_file(os.path.join(out_dir, "memoryDrainsPerState.json"))
    memory_sources_per_state = read_file(os.path.join(out_dir, "memorySourcesPerState.json"))
    instructions_per_state = read_file(os.path.join(out_dir, "hls_instructionsPerState.json"))

    tcl_file = os.path.join(out_dir, 'sta.tcl')
    sdc_file = project_name + '.sdc'

    lines = header_template.substitute({"sdc":sdc_file})

    for module,states in states_per_module.items():
        if module == "main": inst = "main_inst"
        else: inst = module
        path = "*|{}:{}|".format(module,inst)
        for state in states:
            sources = []
            sources.extend([path+s for s in sources_per_state[state] if 'arg_' not in s])
            sources.extend(["*|"+inst+"_"+s for s in sources_per_state[state] if 'arg_' in s])
            sources.extend(memory_sources_per_state[state])
            drains = []
            drains.extend([path+d for d in drains_per_state[state]])
            drains.extend(memory_drains_per_state[state])
            for source in sources:
                for drain in drains:
                    lines += request_template_dual.substitute({"priority":"Priority1", "to":drain+"*", "from":source+"*", "state":state})

                lines += request_template_dual.substitute({"priority":"Priority1", "to":path+"cur_state*", "from":source+"*", "state":state})
                lines += request_template_dual.substitute({"priority":"Priority1", "to":"*|top_inst|div_top_reg*", "from":source+"*", "state":state})
                lines += request_template_dual.substitute({"priority":"Priority1", "to":path+module+"_rom*", "from":source+"*", "state":state})
                lines += request_template.substitute({"priority":"Priority2", "reg":source+"*", "dir":"from", "state":state})
                lines += request_template_dual.substitute({"priority":"Priority2", "to":path+"cur_state*", "from":source+"*", "state":state})

            for drain in drains:
                lines += request_template_dual.substitute({"priority":"Priority1", "from":path+"cur_state*", "to":drain+"*", "state":state})
                if "finish" in drain or "return_val" in drain:
                    lines += request_template.substitute({"priority":"Priority1", "reg":drain+"*", "dir":"from", "state":state})
                
                lines += request_template_dual.substitute({"priority":"Priority2", "from":path+"cur_state*", "to":drain+"*", "state":state})
                lines += request_template.substitute({"priority":"Priority2", "reg":drain+"*", "dir":"to", "state":state})
            
            if 'LEGUP_0' in state:
                lines += request_template.substitute({"priority":"Priority1", "reg":path+"start*", "dir":"to", "state":state})
                lines += request_template.substitute({"priority":"Priority1", "reg":"*"+module+"_arg*", "dir":"from", "state":state})

            if len(drains) == 0 and len(sources) == 0:
                lines += request_template_dual.substitute({"priority":"Priority2", "to":path+"cur_state*", "from":path+"cur_state*", "state":state})


            lines += request_template_dual.substitute({"priority":"Priority3", "to":path+module+"_rom*", "from":path+"cur_state*", "state":state})
            lines += request_template_dual.substitute({"priority":"Priority3", "to":path+"cur_state*", "from":path+"cur_state*", "state":state})
            lines += request_template_dual.substitute({"priority":"Priority3", "to":"*|top_inst|div_top_reg*", "from":path+"cur_state*", "state":state})

    save(tcl_file, lines)

    result = execute(['quartus_sta', '-t', tcl_file], t=5000, cd=project_folder, quiet=True)
    result = result.split('\n')
    save(os.path.join(out_dir, "sta_results.log"), result)

    delay_vals_one = [line for line in result if 'Delay' in line and 'State' in line and "Priority1" in line]
    delay_vals_two = [line for line in result if 'Delay' in line and 'State' in line and "Priority2" in line]
    delay_vals_three = [line for line in result if 'Delay' in line and 'State' in line and "Priority3" in line]

    minSlackPerState = {}
    backupSlackPerState = {}
    worstcaseSlackPerState = {}
    slacksPerState = {}
    for module,states in states_per_module.items():
        for state in states:
            minSlackPerState[state] = 0
            backupSlackPerState[state] = 0
            worstcaseSlackPerState[state] = 0
            slacksPerState[state] = []

    for module,states in states_per_module.items():
        if module == "main": inst = "main_inst"
        else: inst = module
        path = "*|{}:{}|".format(module,inst)
        for state in states:
            drains = drains_per_state[state]
            sources = sources_per_state[state]
            results1 = [l for l in delay_vals_one if state in l]
            results2 = [l for l in delay_vals_two if state in l]
            results3 = [l for l in delay_vals_three if state in l]
            slacksPerState[state] = [0]
            for d in drains:
                delays = [0]
                d_path = "to "+path+d
                delays.extend([float(l.split()[-1]) for l in results1 if d_path in l])
                if min(delays) >= 0:
                    delays.extend([float(l.split()[-1]) for l in results2 if d_path in l])
                if min(delays) >= 0:
                    delays.extend([float(l.split()[-1]) for l in results3 if d_path in l])
                slacksPerState[state].append(min(delays))
            for s in sources:
                if 'arg' in s:
                    s_path = "from *|"+inst+"_"+s
                else: s_path = "from "+path+s
                delays = [0]
                delays.extend([float(l.split()[-1]) for l in results1 if s_path in l])
                if min(delays) >= 0:
                    delays.extend([float(l.split()[-1]) for l in results2 if s_path in l])
                if min(delays) >= 0:
                    delays.extend([float(l.split()[-1]) for l in results3 if s_path in l])
                slacksPerState[state].append(min(delays))
            minSlackPerState[state] = min(slacksPerState[state])

    for val in delay_vals_one:
        state = val.split(' ')[1]
        delay = float(val.split(' ')[-1])
        if delay < minSlackPerState[state]: minSlackPerState[state] = delay 
        slacksPerState[state].append(delay)

    for val in delay_vals_two:
        state = val.split(' ')[1]
        delay = float(val.split(' ')[-1])
        if delay < backupSlackPerState[state]: backupSlackPerState[state] = delay 

    for val in delay_vals_three:
        state = val.split(' ')[1]
        delay = float(val.split(' ')[-1])
        if delay < worstcaseSlackPerState[state]: worstcaseSlackPerState[state] = delay 

    for state, delay in minSlackPerState.items():
        if delay == 0:
            if backupSlackPerState[state] == 0:
                minSlackPerState[state] = worstcaseSlackPerState[state]
                slacksPerState[state].append(worstcaseSlackPerState[state])
            else:
                minSlackPerState[state] = backupSlackPerState[state]
                slacksPerState[state].append(backupSlackPerState[state])

    def convert_slack_to_MHz(slack_ns):
        # 2 because SDC is 500 MHz clock
        return 1000.0/(2-slack_ns)
    
    frequencyPerState = dict.fromkeys(minSlackPerState.keys())
    for state in frequencyPerState.keys():
        if minSlackPerState[state] != 0:
            if convert_slack_to_MHz(minSlackPerState[state]) > 500: 
                # frequencyPerState[state] = convert_slack_to_MHz(minSlackPerState[state])
                frequencyPerState[state] = 500
            else: 
                frequencyPerState[state] = convert_slack_to_MHz(minSlackPerState[state])
        else:
            frequencyPerState[state] = 500

    save(os.path.join(out_dir, "frequencyPerState.json"), frequencyPerState)

    save(os.path.join(out_dir, "minSlackPerState.json"), minSlackPerState)
    save(os.path.join(out_dir, "backupSlackPerState.json"), backupSlackPerState)
    save(os.path.join(out_dir, "worstcaseSlackPerState.json"), worstcaseSlackPerState)
    save(os.path.join(out_dir, "slacksPerState.json"), slacksPerState)

def get_dynamic_timing(verilog_file, enhanced_synthesis):
    project_folder = os.path.dirname(verilog_file)
    project_name = verilog_file.split(".")[0]
    out_dir = project_name+"_files"

    states_per_module = read_file(os.path.join(out_dir,"hls_statesPerModule.json"))
    drains_per_state = read_file(os.path.join(out_dir, "drainsPerState.json"))
    sources_per_state = read_file(os.path.join(out_dir, "sourcesPerState.json"))
    memory_drains_per_state = read_file(os.path.join(out_dir, "memoryDrainsPerState.json"))
    memory_sources_per_state = read_file(os.path.join(out_dir, "memorySourcesPerState.json"))
    instructions_per_state = read_file(os.path.join(out_dir, "hls_instructionsPerState.json"))

    # First, figure out what the clock period is for each state:
    if not enhanced_synthesis:
        newFreqPerState = read_file(os.path.join(out_dir, "frequencyPerState.json"))
    else:
        newFreqPerState = read_file(os.path.join(out_dir, "correctedFrequencyPerState.json"))

    optimisticFreqPerState = {k: (lambda x: PLL_CLOCK/math.floor(PLL_CLOCK/x))(v)
                                for k,v in newFreqPerState.items()}
    pessimisticFreqPerState = {k: (lambda x: PLL_CLOCK/math.ceil(PLL_CLOCK/x))(v)
                                for k,v in newFreqPerState.items()}
    optimisticPeriodPerState = {k: (lambda x: 1000/x)(v) for k, v in optimisticFreqPerState.items()}
    pessimisticPeriodPerState = {k: (lambda x: 1000/x)(v) for k, v in pessimisticFreqPerState.items()}        
     
    save(os.path.join(out_dir, "optimistic_freqs.json"), optimisticFreqPerState)
    save(os.path.join(out_dir, "optimistic_periods.json"), optimisticPeriodPerState)
    save(os.path.join(out_dir, "pessimistic_freqs.json"), pessimisticFreqPerState)
    save(os.path.join(out_dir, "pessimistic_periods.json"), pessimisticPeriodPerState)

    # choose period per state
    chosenPeriodPerState = {}
    for state in optimisticPeriodPerState:
        if enhanced_synthesis:
            chosenPeriodPerState[state] = optimisticPeriodPerState[state]
        else:
            chosenPeriodPerState[state] = pessimisticPeriodPerState[state]

    save(os.path.join(out_dir, "chosen_periods.json"), chosenPeriodPerState)

    # Now generate an SDC constraining delays based on the new freqs
    if not enhanced_synthesis:
        sdc_file = os.path.join(project_folder, "sdc", "path_delays_debug.sdc")
    else: 
        sdc_file = os.path.join(project_folder, "sdc", "path_delays.sdc")


    # to bound all modules
    if enhanced_synthesis:
        lines = ""
        module_sdc = os.path.join(project_folder, "sdc", "path_delays_debug.sdc")

        fmax_per_module = read_file(os.path.join(out_dir, "max_freq_per_module.json"))
        instances_per_module = read_file(os.path.join(out_dir,"instancesPerModule.json"))

        optimisticFreqPerModule = {k: (lambda x: PLL_CLOCK/math.floor(PLL_CLOCK/x))(v) 
                                    for k,v in fmax_per_module.items()}
        optimisticPeriodPerModule = {k: (lambda x: 1000/x)(v) for k, v in optimisticFreqPerModule.items()}

        # choose period per module
        chosenPeriodPerModule = {}
        for state in optimisticPeriodPerModule:
            chosenPeriodPerModule[state] = optimisticPeriodPerModule[state]

        for module in instances_per_module.keys():
            if module == "top": path = "*"
            else:
                if module == "main": inst = "main_inst"
                else: inst = module
                path = "*|{}:{}|*".format(module,inst)

            chosen_period = "{:.3f}".format(chosenPeriodPerModule[module])
            lines += sdc_template_dual.substitute({"from":path,  "to":path, "freq":chosen_period})

        save(os.path.join(project_folder, "sdc", "fmax_delay.sdc"), lines)

    lines = ""
    delay_per_source = {}
    delay_per_drain = {}

    if not enhanced_synthesis:
        for module,states in states_per_module.items():
            if module == "main": inst = "main_inst"
            else: inst = module
            path = "*|{}:{}|".format(module,inst)

            # Go through these delays from low frequency (large period) to high frequency (small period) so that the delay
            # ends up set to the smallest possible value.
            sorted_states = sorted(states, key=lambda x:chosenPeriodPerState[x], reverse=True) 
            for state in sorted_states:
                chosen_period = "{:.3f}".format(chosenPeriodPerState[state])
                if path+"cur_state*" not in delay_per_drain.keys():
                    delay_per_drain[path+"cur_state*"] = []
                delay_per_drain[path+"cur_state*"].append(chosen_period)

                if 'function_call' in state:
                    callee = [r for r in drains_per_state[state] if 'start' in r][0]
                    callee = callee.split('_start')[0]
                    lines += sdc_template_dual.substitute({"from":path+callee+":"+callee+"|return_val*", "to":path+callee+"_return_val_reg", "freq":chosen_period})
                    lines += sdc_template_dual.substitute({"from":path+callee+":"+callee+"|finish*", "to":path+callee+"_finish_reg*", "freq":chosen_period})

                if "*|top_inst|div_top_reg*" not in delay_per_drain.keys():
                    delay_per_drain["*|top_inst|div_top_reg*"] = []
                delay_per_drain["*|top_inst|div_top_reg*"].append(chosen_period)

                if path+module+"_rom:"+module+"_rom_INST|*" not in delay_per_drain.keys():
                    delay_per_drain[path+module+"_rom:"+module+"_rom_INST|*"] = []
                delay_per_drain[path+module+"_rom:"+module+"_rom_INST|*"].append(chosen_period)
                
                for drain in memory_drains_per_state[state]:
                    if "main_LEGUP_0" in state:
                        lines += sdc_template.substitute({"reg":drain+"*",  "dir":"to", "freq":chosen_period})
                    lines += sdc_template_dual.substitute({"to":drain+"*", "from":path+"cur_state*", "freq":chosen_period})
                    for source in memory_sources_per_state[state]:
                        lines += sdc_template_dual.substitute({"from":source+"*", "to":drain+"*", "freq":chosen_period})
                    for source in sources_per_state[state]:
                        if 'arg_' in source:
                            lines += sdc_template_dual.substitute({"from":"*|"+inst+"_"+source+"*", "to":drain+"*", "freq":chosen_period})
                        else:
                            lines += sdc_template_dual.substitute({"from":path+source+"*", "to":drain+"*", "freq":chosen_period})

                for source in memory_sources_per_state[state]:
                    if "main_LEGUP_0" in state:
                        lines += sdc_template.substitute({"reg":source+"*",  "dir":"from", "freq":chosen_period})
                    lines += sdc_template_dual.substitute({"from":source+"*", "to":path+"cur_state*", "freq":chosen_period})
                    for drain in drains_per_state[state]:
                        lines += sdc_template_dual.substitute({"from":source+"*", "to":path+drain+"*", "freq":chosen_period})
                
                for drain in drains_per_state[state]:
                    if "main_LEGUP_0" in state:
                        lines += sdc_template.substitute({"reg":path+drain+"*",  "dir":"to", "freq":chosen_period})
                    if 'finish' in drain and 'main_inst' in inst:
                        if "*return_val_reg*" not in delay_per_drain.keys():
                            delay_per_drain["*return_val_reg*"] = []
                        delay_per_drain["*return_val_reg*"].append(chosen_period)
                        if "*return_val_reg*" not in delay_per_source.keys():
                            delay_per_source["*return_val_reg*"] = []
                        delay_per_source["*return_val_reg*"].append(chosen_period)
                        if path+"finish*" not in delay_per_source.keys():
                            delay_per_source[path+"finish*"] = []
                        delay_per_source[path+"finish*"].append(chosen_period)
                        if path+"finish*" not in delay_per_drain.keys():
                            delay_per_drain[path+"finish*"] = []
                        delay_per_drain[path+"finish*"].append(chosen_period)

                    if path+"cur_state*" not in delay_per_source.keys():
                        delay_per_source[path+"cur_state*"] = []
                    delay_per_source[path+"cur_state*"].append(chosen_period)

                    lines += sdc_template_dual.substitute({"to":path+drain+"*",  "from":path+"cur_state*", "freq":chosen_period})
                    for source in sources_per_state[state]:
                        if 'arg_' in source:
                            lines += sdc_template_dual.substitute({"from":"*|"+inst+"_"+source+"*", "to":path+drain+"*", "freq":chosen_period})
                        else:
                            lines += sdc_template_dual.substitute({"from":path+source+"*", "to":path+drain+"*", "freq":chosen_period})
                
                for source in sources_per_state[state]:
                    if "main_LEGUP_0" in state:
                        lines += sdc_template.substitute({"reg":path+source+"*",  "dir":"from", "freq":chosen_period})
                    if "arg_" in source:
                        lines += sdc_template_dual.substitute({"from":"*|"+inst+"_"+source+"*",  "to":path+"cur_state*", "freq":chosen_period})
                        lines += sdc_template_dual.substitute({"from":"*|"+inst+"_"+source+"*",  "to":"*|top_inst|div_top_reg*", "freq":chosen_period})
                        lines += sdc_template_dual.substitute({"from":"*|"+inst+"_"+source+"*",  "to":path+module+"_rom:"+module+"_rom_INST|*", "freq":chosen_period})
                    else:
                        lines += sdc_template_dual.substitute({"from":path+source+"*", "to":path+"cur_state*", "freq":chosen_period})
                        lines += sdc_template_dual.substitute({"from":path+source+"*", "to":"*|top_inst|div_top_reg*", "freq":chosen_period})
                        lines += sdc_template_dual.substitute({"from":path+source+"*", "to":path+module+"_rom:"+module+"_rom_INST|*", "freq":chosen_period})
                        
                if len(drains_per_state[state]) == 0 and len(sources_per_state[state]) == 0 and len(memory_sources_per_state[state]) == 0 and len(memory_drains_per_state[state]) == 0:
                    lines += sdc_template.substitute({"reg":path+module+"_rom*", "dir":"to",  "freq":chosen_period})
                    lines += sdc_template.substitute({"reg":"*|top_inst|div_top_reg*", "dir":"to",  "freq":chosen_period})

        for source, delays in delay_per_source.items():
            lines += sdc_template.substitute({"reg":source, "dir":"from",  "freq":max([float(d) for d in delays])})
        for drain,delays in delay_per_drain.items():
            lines += sdc_template.substitute({"reg":drain,  "dir":"to", "freq":max([float(d) for d in delays])})
    
    else: # enhanced synthesis
        for module,states in states_per_module.items():
            if module == "main": inst = "main_inst"
            else: inst = module
            path = "*|{}:{}|".format(module,inst)

            # Go through these delays from low frequency (large period) to high frequency (small period) so that the delay
            # ends up set to the smallest possible value.
            sorted_states = sorted(states, key=lambda x:chosenPeriodPerState[x], reverse=True) 
            for state in sorted_states:
                chosen_period = "{:.3f}".format(chosenPeriodPerState[state])
                
                for drain in memory_drains_per_state[state]:
                    lines += sdc_template.substitute({"reg":drain+"*", "dir":"to", "freq":chosen_period})

                for source in memory_sources_per_state[state]:
                    lines += sdc_template.substitute({"reg":source+"*", "dir":"from", "freq":chosen_period})
                
                for drain in drains_per_state[state]:
                    lines += sdc_template.substitute({"reg":path+drain+"*",  "dir":"to", "freq":chosen_period})
                
                for source in sources_per_state[state]:
                    if "arg_" in source:
                        lines += sdc_template.substitute({"reg":"*|"+inst+"_"+source+"*", "dir":"from", "freq":chosen_period})
                    else:
                        lines += sdc_template.substitute({"reg":path+source+"*", "dir":"from", "freq":chosen_period})

    save(sdc_file, lines)

def get_timing_constraints(verilog_file):
    project_folder = os.path.dirname(os.path.abspath(verilog_file))
    project_name = verilog_file.split(".")[0]
    out_dir = project_name+"_files"
    instances_per_module = read_file(os.path.join(out_dir,"instancesPerModule.json"))
    fmax_per_module = dict.fromkeys(instances_per_module)

    result = execute(['quartus_sta', '-t', os.path.join(TOOL_PATH, 'tcl','report_longest.tcl')], cd=project_folder, quiet=True)
    lines = result.split('\n')
    slack = [l for l in lines if "Slack: "  in l]
    slack = float(slack[0].split()[-1])
    max_frequency = 1000.0/(2-slack)
    if DEBUG:
        from_node = [l.strip().split(" ")[-1].strip() for l in lines if "From Node" in l]
        to_node = [l.strip().split(" ")[-1].strip() for l in lines if "To Node" in l]
        if len(from_node) > 0 and len(to_node) > 0:
            print("DEBUG: Max Frequency Path from ")
            print("\t"+from_node[0])
            print("\t"+" to node ")
            print("\t"+to_node[0])
            print("\t"+" :  "+str(max_frequency)+"  (Slack "+str(slack)+")")
        else: print(result)
    
    modules = list(instances_per_module.keys())
    def num_submodules(module):
        return len(instances_per_module[module])
    modules.sort(key=num_submodules)

    not_processed = list(instances_per_module.keys())
    not_processed.remove("top")
    sdc_lines = []
    while len(not_processed) > 0:
        def get_next_module(not_processed, instances_per_module):
            for module in not_processed:
                if len(instances_per_module[module]) == 0: # leaf
                    return module 
                elif all([bool(m not in not_processed) for m in instances_per_module[module]]): # all instances processed, leaf
                    return module
        leaf_module = get_next_module(not_processed, instances_per_module)
        not_processed.remove(leaf_module)
        
        if leaf_module == "main": inst = "main_inst"
        else: inst = leaf_module
        path = "*|{}:{}|*".format(leaf_module,inst)

        # get timing
        result = execute(['quartus_sta', '-t', os.path.join(TOOL_PATH, 'tcl', 'report_longest_custom.tcl'), path, path], cd=project_folder, quiet=True)
        lines = result.split('\n')
        slack = [l for l in lines if "Slack: "  in l]
        slack = float(slack[0].split()[-1])
        if slack > 0:
            max_frequency = 500.0
        else:
            max_frequency = 1000.0/(2-slack)
        fmax_per_module[leaf_module] = max_frequency
        if DEBUG:
            from_node = [l.strip().split(" ")[-1].strip() for l in lines if "From Node" in l]
            to_node = [l.strip().split(" ")[-1].strip() for l in lines if "To Node" in l]
            if len(from_node) > 0 and len(to_node) > 0:
                print("DEBUG: Path from ")
                print("\t"+from_node[0])
                print("\t"+" to node ")
                print("\t"+to_node[0])
                print("\t"+" :  "+str(max_frequency)+"  (Slack "+str(slack)+")")
            else: print(result)

        max_delay = 1000.0/(PLL_CLOCK/math.ceil(PLL_CLOCK/max_frequency)) # bin frequency for simplicity

        sdc_lines = [sdc_template_dual.substitute({"to":path,  "from":path, "freq":max_delay})] + sdc_lines
        with open(os.path.join('sdc', 'fmax_delay.sdc'), 'w') as outf:
            for line in sdc_lines:
                outf.write(line)

    result = execute(['quartus_sta', '-t', os.path.join(TOOL_PATH, 'tcl','report_longest.tcl')], cd=project_folder, quiet=True)
    lines = result.split('\n')
    slack = [l for l in lines if "Slack: "  in l]
    slack = float(slack[0].split()[-1])
    if slack > 0:
        max_frequency = 500.0
    else:
        max_frequency = 1000.0/(2-slack)
    if DEBUG:
        from_node = [l.strip().split(" ")[-1].strip() for l in lines if "From Node" in l]
        to_node = [l.strip().split(" ")[-1].strip() for l in lines if "To Node" in l]
        if len(from_node) > 0 and len(to_node) > 0:
            print("DEBUG: Max Frequency Path post-analysis from ")
            print("\t"+from_node[0])
            print("\t"+" to node ")
            print("\t"+to_node[0])
            print("\t"+" :  "+str(max_frequency)+"  (Slack "+str(slack)+")")
        else: print(result)

    fmax_per_module["top"] = max_frequency
    
    print(fmax_per_module)

    save(os.path.join(out_dir, "max_freq_per_module.json"), fmax_per_module)

    return fmax_per_module

def generate_clock_settings(verilog_file, pipeline):
    project_name = verilog_file.split(".")[0]
    out_dir = project_name+"_files"

    minSlackPerState = read_file(os.path.join(out_dir, "minSlackPerState.json"))
    statesPerModule = read_file(os.path.join(out_dir,"hls_statesPerModule.json"))
    
    def convert_slack_to_MHz(slack_ns, period=2):
        return 1000.0/(period-slack_ns)

    fmax_per_module = read_file(os.path.join(out_dir, "max_freq_per_module.json"))

    correctedFrequencyPerState = dict.fromkeys(minSlackPerState.keys())
    for module, states in statesPerModule.items():
        max_frequency = fmax_per_module[module]
        if max_frequency > fmax_per_module['top']: max_frequency = fmax_per_module['top']
        for state in states:
            if minSlackPerState[state] != 0:
                if convert_slack_to_MHz(minSlackPerState[state]) > max_frequency: 
                    correctedFrequencyPerState[state] = max_frequency
                else: 
                    correctedFrequencyPerState[state] = convert_slack_to_MHz(minSlackPerState[state])
            else:
                correctedFrequencyPerState[state] = max_frequency

    save(os.path.join(out_dir, "correctedFrequencyPerState.json"), correctedFrequencyPerState)

def generate_mif_files(verilog_file, pipeline):
    project_name = verilog_file.split(".")[0]
    out_dir = project_name+"_files"

    frequencyPerState = bin_frequencies_per_state(out_dir)
    statesPerModule = read_file(os.path.join(out_dir,"hls_statesPerModule.json"))
    valuePerState = get_value_per_state(out_dir, verilog_file)
    bits = get_num_bits(verilog_file)

    divPerState = {}
    for state, frequency in frequencyPerState.items():
        divPerState[state] = get_frequency_div(frequency)

    nstatesPerState = read_file(os.path.join(out_dir, 'hls_nstatesPerState.json'))
    num_nStates = get_num_nStates(out_dir)
    dataPerState = {}

    for module,states in statesPerModule.items():
        addr_w = bits[module]
        for state in states:
            nstates = nstatesPerState[state]
            divs = {}
            for nstate in nstates:
                if pipeline:
                    nnstates = nstatesPerState[nstate]
                    divs[nstate] = max([divPerState[nnstate] for nnstate in nnstates])
                else:
                    divs[nstate] = divPerState[nstate]
            tags = 0
            data = 0
            for nstate in nstates:
                tags = tags << int(addr_w)
                data = data << COUNTER_BITS
                tags = tags + int(valuePerState[nstate])
                data = data + int(divs[nstate])
            dataPerState[state] = data + (tags << (COUNTER_BITS*num_nStates[module]))

    save(os.path.join(out_dir, "lookupDivPerState.json"), divPerState)

    for module,states in statesPerModule.items():
        addr_w = bits[module]
        depth = 2**addr_w
        data_w = num_nStates[module] * COUNTER_BITS + num_nStates[module] *addr_w
        data = [2**COUNTER_BITS-1] * (int(depth))
        for state in states:
            address = int(valuePerState[state])
            data[address] = dataPerState[state]

        mif_file = os.path.join(out_dir, "rom", "{}_rom.mif".format(module))
        with open(mif_file, "w+") as outf:
            outf.write("-- ROM Initialization file\n")
            outf.write("WIDTH = {};\n".format(data_w))
            outf.write("DEPTH = {};\n".format(depth)) 
            outf.write("ADDRESS_RADIX = HEX;\n")
            outf.write("DATA_RADIX = HEX;\n")
            outf.write("CONTENT\nBEGIN\n")
            for address in range(0,int(depth)):
                outf.write("\t{:x} : {:x};\n".format(address,data[address]))
            outf.write("END\n")

def bin_frequencies_per_state(out_dir):
    frequencyPerState = read_file(os.path.join(out_dir,"correctedFrequencyPerState.json"))
    binnedFrequencyPerState = {}
    for state, frequency in frequencyPerState.items():
        binnedFrequencyPerState[state] = float(PLL_CLOCK) / float(get_frequency_div(frequency))

    save(os.path.join(out_dir, "binnedFrequencyPerState.json"), binnedFrequencyPerState)
    return frequencyPerState

def get_frequency_div(f):
    div = 2
    while (float(PLL_CLOCK) / float(div)) > float(f) and div < 2**COUNTER_BITS:
        div += 1
    assert (div != 2**COUNTER_BITS)

    return div

def get_value_per_state(out_dir, verilog_file):
    lines = get_states(verilog_file)
    valuePerState = {}
    for line in lines:
        state = line[0]
        value = line[1][1]
        valuePerState[state] = value 
    save(os.path.join(out_dir, "valuePerState.json"), valuePerState)
    return valuePerState

def get_simulation_performance(verilog_file, pipeline, log_file=None):
    project_folder = os.path.dirname(verilog_file)
    project_name = verilog_file.split(".")[0]
    out_dir = project_name+"_files"
    subroutine_calls = read_file(os.path.join(out_dir,"subroutine_calls.json"))

    if log_file == None:
        results = read_file(os.path.join(out_dir,"modelsim.log"))
    else:
        results = read_file(log_file)
    if DEBUG: print("DEBUG: measuring performance using log file "+log_file)

    modules = read_file(log_file)
    results = [l.split('STATE')[-1].strip() for l in results if 'STATE' in l]
    instances = []
    activeStates = {}
    for l in results:
        line = l.split()
        i = 0
        while i < len(line)-1:
            inst = line[i]
            state = line[i+1]
            if inst not in instances:
                instances.append(inst)
                activeStates[inst] = []
            if state.isdigit():
                activeStates[inst].append(int(state))
            i += 2

    sim_state_counts = []
    for _,v in activeStates.items():
        sim_state_counts.append(len(v))

    assert(all([x==sim_state_counts[0] for x in sim_state_counts]))
    sim_state_count = sim_state_counts[0]
    save(os.path.join(out_dir, "transition_count.csv"), [sim_state_count])

    # dict to translate state integer value to state name as a string
    statesPerModule = read_file(os.path.join(out_dir,"hls_statesPerModule.json"))
    valuePerState = read_file(os.path.join(out_dir, "valuePerState.json"))
    stateTranslator = {}
    for m in statesPerModule.keys():
        stateTranslator[m] = {}
        for state in statesPerModule[m]:
            stateTranslator[m][valuePerState[state]] = state
    save(os.path.join(out_dir, "stateTranslator.json"), stateTranslator)

    # convert list of values of active states for each instance to lists of string names of active states
    activeStateNames = {}
    for instance in instances:
        activeStateNames[instance] = []
        module = instance.split('.')[-1]
        if module == 'main_inst': module = 'main'
        for stateNum in activeStates[instance]:
            activeStateNames[instance].append(stateTranslator[module][str(stateNum)])
    save(os.path.join(out_dir, "activeStateNames.json"), activeStateNames)

    # corrected frequencies are the optimum without binning, determined precisely
    correctedFrequencyPerState = read_file(os.path.join(out_dir, "correctedFrequencyPerState.json"))
    correctedActiveStateFrequencies = {}
    for instance in instances:
        correctedActiveStateFrequencies[instance] = []
        for state in activeStateNames[instance]:
            correctedActiveStateFrequencies[instance].append(correctedFrequencyPerState[state])
    counts = []
    for instance in instances:
        counts.append(len(correctedActiveStateFrequencies[instance]))
    if all([x==counts[0] and x==sim_state_count for x in counts]): transition_count = counts[0]
    else: 
        print("Error: mismatching state transitions among modules.")
        assert(0)

    correctedFrequencySchedule = []
    for cycle in range(transition_count):
        freqs = []
        instance = "main_inst"
        state = activeStateNames[instance][cycle]
        if cycle+1 < transition_count: next_state = activeStateNames[instance][cycle+1]
        else: next_state = activeStateNames[instance][0]
        instance_base = "main"
        if not (state in subroutine_calls[instance_base].keys() and next_state in subroutine_calls[instance_base].keys()):
            freqs.append(correctedActiveStateFrequencies[instance][cycle])
        while state in subroutine_calls[instance_base].keys():
            instance = instance + '.' + subroutine_calls[instance_base][state]
            freqs.append(correctedActiveStateFrequencies[instance][cycle])
            state = activeStateNames[instance][cycle]
            if cycle+1 < transition_count: next_state = activeStateNames[instance][cycle+1]
            else: next_state = activeStateNames[instance][0]
            instance_base = instance.split('.')[-1]
            if not (state in subroutine_calls[instance_base].keys() and next_state in subroutine_calls[instance_base].keys()):
                freqs.append(correctedActiveStateFrequencies[instance][cycle])

        # for instance in instances:
        #     freqs.append(correctedActiveStateFrequencies[instance][cycle])
        correctedFrequencySchedule.append(min(freqs))

    # now do the same with the binned frequencies. 
    # 'Skips' are for when a sub-routine is being called - the caller frequency 
    # does not limit the frequency of the callee in this implementation
    # also, in pipelined implementation, the frequency cannot be determined precisely
    # it is determined as a min(frequency[previous_state])
    binnedFrequencyPerState = read_file(os.path.join(out_dir, "binnedFrequencyPerState.json"))

    # takes two cycles to set dynamic clock for the first time - it's saturated (min frequency) for conservativeness
    hwFrequencySchedule = [PLL_CLOCK/((2**COUNTER_BITS)-1),PLL_CLOCK/((2**COUNTER_BITS)-1)]
    hwFreqcounter = {}
    time = 1.0/(PLL_CLOCK/((2**COUNTER_BITS)-1))+1.0/(PLL_CLOCK/((2**COUNTER_BITS)-1))
    ideal_time = 0
    for cycle in range(transition_count):
        freqs = []
        instance = "main_inst"
        state = activeStateNames[instance][cycle]
        if cycle+1 < transition_count: next_state = activeStateNames[instance][cycle+1]
        else: next_state = activeStateNames[instance][0]
        instance_base = "main"
        if not(state in subroutine_calls[instance_base].keys() and next_state in subroutine_calls[instance_base].keys()):
            freqs.append(correctedFrequencyPerState[state])
        while state in subroutine_calls[instance_base].keys():
            instance = instance + '.' + subroutine_calls[instance_base][state]
            state = activeStateNames[instance][cycle]
            if cycle+1 < transition_count: next_state = activeStateNames[instance][cycle+1]
            else: next_state = activeStateNames[instance][0]
            instance_base = instance.split('.')[-1]
            if not (state in subroutine_calls[instance_base].keys() and next_state in subroutine_calls[instance_base].keys()):
                freqs.append(correctedFrequencyPerState[state])
        ideal_time += 1.0/(min(freqs))

    if pipeline:
        precise_time = 1.0/(PLL_CLOCK/((2**COUNTER_BITS)-1))+1.0/(PLL_CLOCK/((2**COUNTER_BITS)-1))
        nextStatesPerState = read_file(os.path.join(out_dir, "hls_nstatesPerState.json"))

        for cycle in range(2, transition_count):
            freqs = []
            precise_freqs = []

            instance = "main_inst"
            state = activeStateNames[instance][cycle]
            if cycle+1 < transition_count: next_state = activeStateNames[instance][cycle+1]
            else: next_state = activeStateNames[instance][0]
            instance_base = "main"
            if not(state in subroutine_calls[instance_base].keys() and next_state in subroutine_calls[instance_base].keys()):
                previous_state = activeStateNames[instance][cycle-1] 
                current_state_candidates = nextStatesPerState[previous_state]
                freqs.append(min([binnedFrequencyPerState[s] for s in current_state_candidates]))
                precise_freqs.append(binnedFrequencyPerState[state])

            while state in subroutine_calls[instance_base].keys():
                instance = instance + '.' + subroutine_calls[instance_base][state]
                state = activeStateNames[instance][cycle]
                if cycle+1 < transition_count: next_state = activeStateNames[instance][cycle+1]
                else: next_state = activeStateNames[instance][0]
                instance_base = instance.split('.')[-1]
                if not (state in subroutine_calls[instance_base].keys() and next_state in subroutine_calls[instance_base].keys()):
                    previous_state = activeStateNames[instance][cycle-1] 
                    current_state_candidates = nextStatesPerState[previous_state]
                    freqs.append(min([binnedFrequencyPerState[s] for s in current_state_candidates]))
                    precise_freqs.append(binnedFrequencyPerState[state])

            hwFrequencySchedule.append(min(freqs))
            if min(freqs) not in hwFreqcounter.keys(): hwFreqcounter[min(freqs)] = 0
            hwFreqcounter[min(freqs)] += 1
            time += 1.0/(min(freqs))
            precise_time += 1.0/min(precise_freqs)

        print("PRECISE SIMULATION LATENCY ",precise_time)
        print("PRECISE SIMULATION EFFECTIVE FREQUENCY ",float(len(hwFrequencySchedule))/precise_time)
    else: 
        for cycle in range(2, transition_count):
            freqs = []
            instance = "main_inst"
            state = activeStateNames[instance][cycle]
            if cycle+1 < transition_count: next_state = activeStateNames[instance][cycle+1]
            else: next_state = activeStateNames[instance][0]
            instance_base = "main"
            if not(state in subroutine_calls[instance_base].keys() and next_state in subroutine_calls[instance_base].keys()):
                freqs.append(binnedFrequencyPerState[state])
            while state in subroutine_calls[instance_base].keys():
                instance = instance + '.' + subroutine_calls[instance_base][state]
                state = activeStateNames[instance][cycle]
                if cycle+1 < transition_count: next_state = activeStateNames[instance][cycle+1]
                else: next_state = activeStateNames[instance][0]
                instance_base = instance.split('.')[-1]
                if not (state in subroutine_calls[instance_base].keys() and next_state in subroutine_calls[instance_base].keys()):
                    freqs.append(binnedFrequencyPerState[state])

            hwFrequencySchedule.append(min(freqs))
            if min(freqs) not in hwFreqcounter.keys(): hwFreqcounter[min(freqs)] = 0
            hwFreqcounter[min(freqs)] += 1
            time += 1.0/(min(freqs))

    save(os.path.join(out_dir, "correctedFrequencySchedule.csv"), correctedFrequencySchedule)
    save(os.path.join(out_dir, "hwFrequencySchedule.csv"), hwFrequencySchedule)
    save(os.path.join(out_dir, "hwFreqCounter.json"), hwFreqcounter)
    save(os.path.join(out_dir, "hwTime.csv"), [time])
    save(os.path.join(out_dir, "instances.csv"), instances)

    print("SIMULATION LATENCY ",time)
    print("SIMULATION HYPOTHETICAL FMAX ",float(len(hwFrequencySchedule))/ideal_time)
    print("SIMULATION EFFECTIVE FREQUENCY ",float(len(hwFrequencySchedule))/time)


