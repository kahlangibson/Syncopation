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

from .verilog_processing import get_rtl_data, get_modules, generate_roms, pull_out_state, get_num_bits, generate_temp_mif
from .schedule_processing import get_hls_data
from .string_templates import top_template
from .misc import read_file, save
import os
from .settings import *

def add_synthesis_directives(verilog_file):
    """
    Insert synthesis directives into RTL
    """
    modules = get_modules(verilog_file)
    modules = list(modules) + ['top']

    verilog = read_file(verilog_file)

    module = ''
    for idx in range(len(verilog)):
        line = verilog[idx]
        if "module" in line: module = line.split(' ')[-1]
        if module in modules: 
            if 'reg' == line[0:3] and '_reg;' == line[-5::] and 'stage0' not in line:
                verilog[idx] = line[0:-1] + ' /* synthesis noprune */ /* synthesis preserve */;'
            elif 'reg' == line[0:3] and '_reg;' == line[-5::] and 'stage0' in line:
                verilog[idx] = line[0:-1] + ' /* synthesis preserve */;'

    with open(verilog_file, 'w') as out_f:
        for line in verilog:
            out_f.write(line+'\n')

def profile_rtl(verilog_file):
    """
    Get data from RTL
    """
    project_folder = os.path.dirname(verilog_file)
    project_name = verilog_file.split(".")[0]
    out_dir = project_name+"_files"
    
    get_hls_data(verilog_file)
    get_rtl_data(verilog_file)

    # generate resources
    states_per_module = read_file(os.path.join(out_dir, "hls_statesPerModule.json"))
    hls_instructions_per_state = read_file(os.path.join(out_dir, "hls_instructionsPerState.json"))
    hls_instructions_per_module = read_file(os.path.join(out_dir, "hls_instructionsPerModule.json"))
    hls_drains_per_instruction = read_file(os.path.join(out_dir, "hls_drainsPerInstruction.json"))
    hls_sources_per_instruction = read_file(os.path.join(out_dir, "hls_sourcesPerInstruction.json"))
    start_per_instruction = read_file(os.path.join(out_dir, "hls_startStatesPerInstruction.json"))
    finish_per_instruction = read_file(os.path.join(out_dir, "hls_finishStatesPerInstruction.json"))
    hls_regs_per_module = read_file(os.path.join(out_dir, "hls_regsPerModule.json"))
    alloca_per_module = read_file(os.path.join(out_dir, "hls_allocaPerModule.json"))
    basic_blocks_per_module = read_file(os.path.join(out_dir, "hls_basicBlocksPerModule.json"))
    
    rtl_drains_per_state = read_file(os.path.join(out_dir, "rtl_regsPerState.json"))
    rtl_drains_per_instruction = read_file(os.path.join(out_dir, "rtl_regsPerInstruction.json"))
    constant_phi_per_state = read_file(os.path.join(out_dir, "rtl_constantPhiPerState.json"))
    rtl_nodes_per_module = read_file(os.path.join(out_dir, "rtl_nodesPerModule.json"))
    rtl_registers_per_module = read_file(os.path.join(out_dir, "rtl_regsPerModule.json"))

    memory_per_instruction = read_file(os.path.join(out_dir, "rtl_memoriesPerInstruction.json"))
    memory_instances = read_file(os.path.join(out_dir, "rtl_memoryInstances.json"))
    memory_modules = read_file(os.path.join(out_dir, "rtl_memoryModules.json"))
    
    def rtl_reg_match(hls_reg, registers):
        # remove extra punctuation
        hls_reg = hls_reg.replace('.','').replace('-','')
        matches = []
        # look for module/hls reg match in rtl registers
        for reg in registers:
            if '_{}_reg'.format(hls_reg) in reg:
                matches.append(reg)
            if '_{}_var'.format(hls_reg) in reg and '_reg' in reg:
                matches.append(reg)
            if 'arg_{}'.format(hls_reg) in reg:
                matches.append(reg)
        return list(dict.fromkeys(matches))

    drains_per_state = {}
    sources_per_state = {}
    memory_drains_per_state = {}
    memory_sources_per_state = {}
    name_map = {}
    sdiv_regs = {}
    rescheduled = {}
    rescheduled_hls = {}

    # for module,states in states_per_module.items():
    rs = []
    for module,states in states_per_module.items():
        rescheduled[module] = {}
        rescheduled_hls[module] = {}
        name_map[module] = {}
        sdiv_regs[module] = []
        for state in states_per_module[module]:
            memory_drains_per_state[state] = []
            memory_sources_per_state[state] = []
            drains_per_state[state] = []
            sources_per_state[state] = []

            for instruction in hls_instructions_per_state[state]:

                finishes = False
                starts = False
                if state in start_per_instruction[instruction]: starts = True
                if state in finish_per_instruction[instruction]: finishes = True

                for hls in hls_drains_per_instruction[instruction]:
                    if 'stage0' in hls and starts:
                        matches = [d for d in rtl_reg_match(hls, rtl_drains_per_state['']) if module in d]
                        if len(matches) > 0:
                            if len(matches) > 1 and DEBUG: print(module, instruction, hls,matches)
                            assert(len(matches) == 1)
                            if state not in drains_per_state.keys():
                                drains_per_state[state] = []
                            for match in matches:
                                drains_per_state[state].append(match)
                                if hls not in name_map[module].keys():
                                    name_map[module][hls] = []
                                name_map[module][hls].append(match)
                                name_map[module][hls] = list(dict.fromkeys(name_map[module][hls]))
                    elif finishes:
                        if 'sdiv' in instruction or 'udiv' in instruction: 
                            matches = rtl_drains_per_instruction[instruction]
                            assert(len(matches) == 1)
                            if state not in drains_per_state.keys():
                                drains_per_state[state] = []
                            for match in matches:
                                drains_per_state[state].append(match)
                                if hls not in name_map[module].keys():
                                    name_map[module][hls] = []
                                name_map[module][hls].append(match)
                                name_map[module][hls] = list(dict.fromkeys(name_map[module][hls]))
                        else:
                            matches = [d for d in rtl_reg_match(hls, rtl_drains_per_state[state]) if module in d]
                            if len(matches) > 0:
                                if len(matches) > 1 and DEBUG: print(module, instruction, hls,matches)
                                assert(len(matches) == 1)
                                if state not in drains_per_state.keys():
                                    drains_per_state[state] = []
                                for match in matches:
                                    drains_per_state[state].append(match)
                                    if hls not in name_map[module].keys():
                                        name_map[module][hls] = []
                                    name_map[module][hls].append(match)
                                    name_map[module][hls] = list(dict.fromkeys(name_map[module][hls]))
                            else: #rescheduled
                                # if 'sdiv' in instruction:
                                #     sdiv_regs[module].append(hls)
                                # else:
                                if state not in rescheduled[module].keys():
                                    rescheduled[module][state] = {instruction:[]}
                                else: rescheduled[module][state][instruction] = []
                                if state not in rescheduled_hls[module].keys():
                                    rescheduled_hls[module][state] = {instruction:hls}
                                else: rescheduled_hls[module][state][instruction] = hls

                if ' load ' in instruction or 'store ' in instruction:
                    if instruction not in memory_per_instruction.keys():
                        if DEBUG: print("DEBUG: No memory for {}".format(instruction))
                    else:
                        memory = memory_per_instruction[instruction][0]
                        inst = memory_modules[memory]
                        if inst == "main" or inst == "top":
                            inst = inst + "_inst"
                        if 'load' in instruction and starts:
                            memory_drains_per_state[state].append("*|{}|{}|".format(inst, memory_instances[memory]))
                        if 'store' in instruction and starts:
                            memory_drains_per_state[state].append("*|{}|{}|".format(inst, memory_instances[memory]))
                        if 'load' in instruction and finishes:
                            memory_sources_per_state[state].append("*|{}|{}|".format(inst, memory_instances[memory]))

    for module in rescheduled_hls.keys():
        for from_state in rescheduled_hls[module].keys():
            for instruction in rescheduled_hls[module][from_state].keys():
                hls = rescheduled_hls[module][from_state][instruction]
                for state in states_per_module[module]:
                    matches = rtl_reg_match(hls, rtl_drains_per_state[state])
                    assert(len(matches) <= 1)
                    for match in matches:
                        if state not in drains_per_state.keys():
                            drains_per_state[state] = []
                        drains_per_state[state].append(match)
                        if hls not in name_map[module].keys():
                            name_map[module][hls] = []
                        name_map[module][hls].append(match)
                        name_map[module][hls] = list(dict.fromkeys(name_map[module][hls]))
                        rescheduled[module][from_state][instruction].append(state)
                    
    for module in states_per_module.keys():
        for state in states_per_module[module]:
            for instruction in hls_instructions_per_state[state]:
                hls_sources = [s for s in hls_sources_per_instruction[instruction] if s not in basic_blocks_per_module[module]]

                finishes = False
                starts = False
                if state in start_per_instruction[instruction]: starts = True
                if state in finish_per_instruction[instruction]: finishes = True
                
                if starts:
                    constant_source = False
                    if state in constant_phi_per_state.keys():
                        if instruction in constant_phi_per_state[state]:
                            constant_source = True

                    if not constant_source:
                        if state in rescheduled[module].keys() and instruction in rescheduled[module][state].keys():
                            for hls in hls_sources:
                                for dest_state in rescheduled[module][state][instruction]:
                                    if hls in name_map[module].keys():
                                        matches = name_map[module][hls]
                                    else:
                                        matches = rtl_reg_match(hls, rtl_registers_per_module[module])

                                    if len(matches) > 0:
                                        if dest_state not in sources_per_state.keys():
                                            sources_per_state[dest_state] = []
                                        for match in matches:
                                            sources_per_state[dest_state].append(match)
                                    else:
                                        if DEBUG: print("DEBUG: could not resched find source {} to {} {} {}".format(state, dest_state, instruction, hls))

                        else:
                            for hls in hls_sources:
                                if hls in name_map[module].keys():
                                    matches = name_map[module][hls]
                                else:
                                    matches = rtl_reg_match(hls, rtl_registers_per_module[module])
                                
                                if len(matches) > 0:
                                    if state not in sources_per_state.keys():
                                        sources_per_state[state] = []
                                    for match in matches:
                                        if starts: sources_per_state[state].append(match)
                                elif hls in alloca_per_module[module]: pass
                                else:
                                    if DEBUG: print("DEBUG: could not find source {} {} {}".format(state, instruction, hls))


    for module in states_per_module.keys():
        for hls_reg in hls_regs_per_module[module]:
            if hls_reg not in name_map[module].keys():
                if hls_reg in alloca_per_module[module]:
                    pass 
                elif hls_reg in basic_blocks_per_module[module]:
                    pass
                # elif hls_reg in sdiv_regs[module]:
                #     pass
                else:
                    if DEBUG: print("DEBUG: HLS reg {} from module {} not matched".format(hls_reg, module))
        for rtl_reg in rtl_registers_per_module[module]:
            found = False 
            for hls_reg in name_map[module].keys():
                if rtl_reg in name_map[module][hls_reg]:
                    found = True 
            if not found:
                found = []
                for state,regs in rtl_drains_per_state.items():
                    if rtl_reg in regs and module in state:
                        found.append(state)
                if found: 
                    for state in found: 
                        if state != '':
                            drains_per_state[state].append(rtl_reg)
                else: 
                    if DEBUG: print("DEBUG: RTL reg {} from module {} not matched".format(rtl_reg, module))

    for module in states_per_module.keys():
        for instruction in hls_instructions_per_module[module]:
            if ' = mul' in instruction:
                starts = [s for s in start_per_instruction[instruction] if module in s]
                finishes = [f for f in finish_per_instruction[instruction] if module in f]
                # print(starts, finishes)
                assert(len(starts) == 1)
                assert(len(finishes) == 1)
                start = starts[0]
                finish = finishes[0]
                hls_stage_0_reg = [d for d in hls_drains_per_instruction[instruction] if 'stage0' in d]
                hls_reg = [d for d in hls_drains_per_instruction[instruction] if 'stage0' not in d]
                assert(len(hls_stage_0_reg) == 1)
                hls_stage_0_reg = hls_stage_0_reg[0]
                hls_reg = hls_reg[0]
                rtl_stage_0_reg = name_map[module][hls_stage_0_reg]
                rtl_reg = name_map[module][hls_reg]
                assert(len(rtl_stage_0_reg) == 1)
                rtl_stage_0_reg = rtl_stage_0_reg[0]
                rtl_reg = rtl_reg[0]

                sources_per_state[start].append(rtl_stage_0_reg)
                sources_per_state[finish].append(rtl_stage_0_reg)
                drains_per_state[start].append(rtl_reg)
                sources_per_state[finish].append(rtl_reg)
                drains_per_state[start].append("lpm_mult")
                sources_per_state[finish].append("lpm_mult")
                drains_per_state[start].append("Mult")
                sources_per_state[finish].append("Mult")

            if 'sdiv' in instruction or 'udiv' in instruction:
                starts = [s for s in start_per_instruction[instruction] if module in s]
                finishes = [f for f in finish_per_instruction[instruction] if module in f]
                assert(len(starts) == 1)
                assert(len(finishes) == 1)
                start = starts[0]
                finish = finishes[0]
                hls_reg = [d for d in hls_drains_per_instruction[instruction]]
                assert(len(hls_reg) == 1)
                hls_reg = hls_reg[0]
                rtl_reg = name_map[module][hls_reg]
                drains_per_state[start].append("lpm_divide")
                sources_per_state[finish].append("lpm_divide")

    count = 0
    for k,v in sources_per_state.items(): 
        sources_per_state[k] = list(dict.fromkeys(v))
        count += len(v)
    save(os.path.join(out_dir, "sourcesPerState.json"), sources_per_state)
    count = 0
    for k,v in drains_per_state.items(): 
        drains_per_state[k] = list(dict.fromkeys(v))
        count += len(v)

    for module, states in states_per_module.items():
        for state in states:
            if len(drains_per_state[state]) == 0 and len(sources_per_state[state]) == 0 and len(memory_drains_per_state[state]) == 0 and len(memory_sources_per_state[state]) == 0:
                for instruction in hls_instructions_per_state[state]:
                    finish = finish_per_instruction[instruction] 
                    if 'store' in instruction and state == finish[0]:
                        pass
                    else:
                        if state not in rescheduled[module].keys():
                            should_have_reg = [] 
                            if len(hls_drains_per_instruction[instruction]) > 0:
                                should_have_reg.extend(hls_drains_per_instruction[instruction])
                            for source in hls_sources_per_instruction[instruction]:
                                if source not in basic_blocks_per_module[module]:
                                    should_have_reg.append(source)
                            if len(should_have_reg) > 0 and DEBUG:
                                print("DEBUG: State {} has no sources, drains - but should have instruction {}: {}".format(state,instruction,should_have_reg))
                        elif state in rescheduled[module].keys() and instruction not in rescheduled[module][state].keys():
                            if DEBUG: print("DEBUG: State {} has no sources, drains - but should have instruction {}".format(state,instruction))

    save(os.path.join(out_dir, "drainsPerState.json"), drains_per_state)
    save(os.path.join(out_dir, "rescheduled.json"), rescheduled)
    save(os.path.join(out_dir, "name_map.json"), name_map)

    for k,v in memory_sources_per_state.items(): memory_sources_per_state[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir, "memorySourcesPerState.json"), memory_sources_per_state)
    for k,v in memory_drains_per_state.items(): memory_drains_per_state[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir, "memoryDrainsPerState.json"), memory_drains_per_state)

def insert_syncoption_hardware(pipeline, verilog_file):
    """
    Inserts Syncopation hardware into Verilog RTL file generated by LEGUP
    """
    # insert hardware into rtl
    verilog = pull_out_state(pipeline, verilog_file) 
    # save back to file
    with open(verilog_file, 'w') as out_f:
        for line in verilog:
            out_f.write(line+'\n')

    generate_roms(verilog_file)
    generate_temp_mif(verilog_file)

def generate_top_module(no_sync_hardware, pipeline, verilog_file):
    """
    Generate top-level module to instantiate specified hardware.
    """
    project_name = verilog_file.split(".")[0]
    project_folder = os.path.dirname(os.path.abspath(verilog_file))
    out_dir = project_name+"_files"
    top_file = os.path.join(project_folder,'board_top.v')

    num_bits = get_num_bits(verilog_file)
    max_addr_w = max([n for m,n in num_bits.items()])
    modules = get_modules(verilog_file)
    num_instances = len(modules)
    top_template_dict = {'addr_w':max_addr_w, 'num_inst':num_instances, 'div_w':COUNTER_BITS}

    with open(top_file,'w+') as outf:
        outf.write(top_template.substitute(top_template_dict))