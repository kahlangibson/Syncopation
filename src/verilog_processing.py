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

from .misc import read_file, save
from .string_templates import rom_file_template, qip_file_template
from .settings import *
import os
from string import Template

def get_modules(verilog_file):
    """ Return list of module names """
    project_name = verilog_file.split(".")[0]
    project_folder = os.path.dirname(verilog_file)
    schedule_file = os.path.join(project_folder,"scheduling.legup.rpt")
    modules_file = os.path.join(project_name+"_files","hls_modules.csv")

    def extract_modules(verilog_file, modules_file):
        lines = read_file(schedule_file)    
        modules = []
        currentLine = ""
        currentModule = ""
        
        def module_name(currentLine):
            if "Start Function" in currentLine: 
                return currentLine.split(':')[1].strip()
            else: return None

        for line in lines:
            currentLine = line
            module = module_name(currentLine)
            if bool(module):
                currentModule = module
                if currentModule not in modules:
                    modules.append(currentModule)

        save(modules_file, modules)
        return modules

    if not os.path.exists(modules_file):
        modules = extract_modules(verilog_file, modules_file)
    else:
        modules = read_file(modules_file)

    return modules

def get_states(verilog_file):
    """ Return list of module names """
    project_name = verilog_file.split(".")[0]
    states_file = os.path.join(project_name+"_files","states.csv")

    def extract_state(verilog_file, modules_file):
        lines = read_file(verilog_file)    
        states = []
        modules = []
        currentLine = ""
        currentModule = ""

        def module_name(currentLine):
            if "module " == currentLine[:7]:
                return currentLine[7::].split('(')[0].strip()
            else: return None
        
        def state_name(currentModule, currentLine):
            if "parameter" in currentLine and "LEGUP" in currentLine:
                return (currentModule+'_'+currentLine.split(']')[1].split('=')[0].strip(), currentLine.split(']')[1].split('=')[1].strip(" ;").split("'d"))
            else: return None

        for line in lines:
            currentLine = line
            module = module_name(currentLine)
            state = state_name(currentModule, currentLine)

            if bool(module):
                currentModule = module
                if currentModule not in modules:
                    modules.append(currentModule)

            if bool(state):
                if state not in states: 
                    states.append(state)

        save(states_file, states)
        return states

    if not os.path.exists(states_file):
        states = extract_state(verilog_file, states_file)
    else:
        lines = read_file(states_file)
        # extract into tuples
        states = []
        for line in lines:
            s = line.split(',')[0].split('(')[1].strip("'")
            v = [l.strip("' ") for l in line.split('[')[1].split(']')[0].split(',')]
            states.append((s, v))

    return states

def get_rtl_data(verilog_file):
    """
    Extract States, Registers, and Modules from Verilog File
    """
    project_name = verilog_file.split(".")[0]
    out_dir = project_name+"_files"

    lines = read_file(verilog_file)
    # open unedited verilog file 
    nodes_per_module = {}

    states = []
    registers = [] 
    instructions = [] 
    modules = []
    registers_per_state = {'':[]}
    states_per_module = {}
    registers_per_instruction = {}
    registers_per_module = {}
    instructions_per_module = {'':[]} 
    phi_constant_source_per_state = {}
    memory_modules = {"memory_controller":"top"}
    memory_instances = {"memory_controller":"memory_controller_inst"}
    memory_per_instruction = {}
    start_sigs_per_instruction = {}
    function_call_values = {}

    previousLine = ""
    prePreviousLine = ""
    currentLine = ""
    currentModule = ""
    currentInstruction = ""
    currentState = ""

    def extract_start(currentLine, previousLine, prePreviousLine):
        if 'tail call' in prePreviousLine and "_start <= 1'd1;" in currentLine:
            instruction = prePreviousLine[prePreviousLine.find("*")+1:prePreviousLine.rfind("*")].strip()
            start_signal = currentLine.split("<=")[0].strip()
            return [instruction, start_signal]
        else: return [None,None]

    def extract_arg(currentLine):
        if 'input' in currentLine and 'arg_' in currentLine:
            return currentLine.split(';')[0].split()[-1].strip()
        else: return None

    def extract_module(currentLine):
        if "module " == currentLine[:7]:
            return currentLine[7::].split('(')[0].strip()
        else: return None

    def extract_state(currentModule, currentLine):
        if "parameter" in currentLine and "LEGUP" in currentLine:
            return currentModule+'_'+currentLine.split(']')[1].split('=')[0].strip()
        else: return None

    def extract_instruction(currentLine, previousLine, prePreviousLine):
        if "always @(posedge clk) begin" in prePreviousLine and "/*" in previousLine:
            return currentLine[currentLine.find("*")+1:currentLine.rfind("*")].strip()
        else:
            return None

    def extract_always_clock(currentLine, previousLine, prePreviousLine):
        if "always @(posedge clk) begin" in prePreviousLine and "/*" not in previousLine:
            return True
        else:
            return None

    def extract_instruction_change(currentLine, previousLine):
        if '/*' in currentLine and '/*' in previousLine:
            return currentLine[currentLine.find("*")+1:currentLine.rfind("*")].strip()
        else: return None

    def extract_state_change(currentModule, currentLine):
        if "if (" and "(cur_state == LEGUP" in currentLine: 
            currentState = currentLine.split('==')[1]
            currentState = currentState.split(')')[0].strip()
            return currentModule+'_'+currentState
        else: return None

    def extract_register(currentLine):
        if " <= " in currentLine and "if (" not in currentLine:
            return currentLine[:currentLine.find("<=")-1].strip()
        else: return None

    def extract_divisor(currentLine, previousLine, prePreviousLine):
        if " <= " in currentLine and ("sdiv" in prePreviousLine or "udiv" in prePreviousLine):
            return currentLine[currentLine.find("<=")+1:currentLine.find(";")].strip()
        else: return None

    def extract_phi(currentLine, previousLine, prePreviousLine):
        if "always @(*) begin" in prePreviousLine and "/*" in previousLine and "phi" in currentLine:
            return currentLine[currentLine.find("*")+1:currentLine.rfind("*")].strip()
        else:
            return None
    
    def extract_node(currentLine):
        if "reg " == currentLine.strip()[0:4]:
            return currentLine.split(';')[0].split(' ')[-1]
        else: return None
    
    def extract_memory(currentLine, previousLine):
        if " = alloca " in previousLine or " = internal " in previousLine:
            if "ram_dual_port" in currentLine or "rom_dual_port" in currentLine:
                name = previousLine.split("//")[-1].split("=")[0].strip()
                if "%" in name: name = name.strip("%")
                if "@" in name: name = name.strip("@")
                return [name,currentLine.split('(')[0].split()[-1]]
        return [None,None]

    def extract_function_call(currentLine,currentModule):
        if "parameter" in currentLine and "function_call" in currentLine:
            state = currentModule+'_'+currentLine.split()[2].strip()
            value = currentLine.split()[-1].split(';')[0]
            return [state,value]
        else: return [None, None]

    def extract_load_store_mem(currentLine, previousLine, prePreviousLine, memory_modules, currentModule):
        if "load" in prePreviousLine or "store" in prePreviousLine:
            for mem in memory_modules.keys():
                if "cur_state" in previousLine:
                    if mem.replace('.','') in currentLine:
                        return [mem,prePreviousLine[prePreviousLine.find("*")+1:prePreviousLine.rfind("*")].strip()]
                else:
                    if mem.replace('.','') in previousLine:
                        return [mem,prePreviousLine[prePreviousLine.find("*")+1:prePreviousLine.rfind("*")].strip()]
            if 'memory_controller' in currentLine:
                return ['memory_controller',prePreviousLine[prePreviousLine.find("*")+1:prePreviousLine.rfind("*")].strip()]
            if DEBUG: print("DEBUG: Can't find memory for {} : {}".format(prePreviousLine, memory_modules.keys()))
        elif "printf" not in prePreviousLine and "getelementptr" in prePreviousLine:
            for mem in memory_modules.keys():
                if "cur_state" in previousLine:
                    if mem.replace('.','') in currentLine:
                        return [mem,prePreviousLine[prePreviousLine.find("*")+1:prePreviousLine.rfind("*")].strip()]
                else:
                    if mem.replace('.','') in previousLine:
                        return [mem,prePreviousLine[prePreviousLine.find("*")+1:prePreviousLine.rfind("*")].strip()]
        return [None,None]


    idx = 0
    while idx < len(lines):
        currentLine = lines[idx]
        module = extract_module(currentLine)
        state = extract_state(currentModule, currentLine)
        instruction = extract_instruction(currentLine, previousLine, prePreviousLine)
        phi = extract_phi(currentLine, previousLine, prePreviousLine)
        node = extract_node(currentLine)
        [memory_name, memory_instance] = extract_memory(currentLine, previousLine)
        [ls_memory,ls_instruction] = extract_load_store_mem(currentLine, previousLine, prePreviousLine, memory_modules, currentModule)
        always_clock = extract_always_clock(currentLine, previousLine, prePreviousLine)
        # divisor_reg = extract_divisor(currentInstruction,previousLine, prePreviousLine)
        arg = extract_arg(currentLine)
        [tail_call,start_sig] = extract_start(currentLine, previousLine, prePreviousLine) 
        [function_call_state,function_call_value] = extract_function_call(currentLine,currentModule)

        if bool(function_call_state):
            function_call_values[function_call_state] = function_call_value

        if bool(arg):
            registers_per_module[currentModule].append(arg)
        
        if bool(ls_memory):
            memory_per_instruction[ls_instruction] = [ls_memory]

        if bool(memory_name):
            memory_modules[memory_name] = currentModule
            memory_instances[memory_name] = memory_instance

        if bool(node):
            nodes_per_module[currentModule].append(node)

        if bool(module):
            currentModule = module
            if currentModule not in modules:
                modules.append(currentModule)
                instructions_per_module[currentModule] = []
                states_per_module[currentModule] = []
                registers_per_module[currentModule] = []
                nodes_per_module[currentModule] = []
            else:
                if DEBUG: print("DEBUG: RTL Module {} detected multiple times on line {}".format(currentModule, idx+1))

        if bool(state):
            currentState = state 
            if state not in states: 
                states.append(currentState)
                registers_per_state[currentState] = []
                states_per_module[currentModule].append(currentState)
            else:
                if DEBUG: print("DEBUG: RTL State {} detected multiple times on line {}".format(currentState, idx+1))

        if bool(instruction) or bool(always_clock):
            if bool(instruction):
                currentInstruction = instruction 
                if currentInstruction not in instructions:
                    instructions.append(currentInstruction)
                    registers_per_instruction[currentInstruction] = []
                    instructions_per_module[currentModule].append(currentInstruction)
            else: 
                state = extract_state_change(currentModule, previousLine)
                if bool(state): currentState = state
                currentInstruction = ""
                if currentInstruction not in instructions:
                    registers_per_instruction[currentInstruction] = []

            # now parse the rest of the block
            begins = 0
            if 'begin' in prePreviousLine: begins += 1
            if 'begin' in previousLine: begins += 1
            if 'begin' in currentLine: begins += 1
            if 'end' in prePreviousLine: begins -= 1
            if 'end' in previousLine: begins -= 1
            if 'end' in currentLine: begins -= 1

            while begins > 0:
                idx += 1
                prePreviousLine = previousLine
                previousLine = currentLine
                currentLine = lines[idx]

                if 'begin' in currentLine: begins += 1
                if 'end' in currentLine: begins -= 1
                if begins == 0: break

                instruction = extract_instruction_change(currentLine, previousLine)
                state = extract_state_change(currentModule, currentLine)
                register = extract_register(currentLine)
                # divisor_reg = extract_divisor(currentInstruction,previousLine, prePreviousLine)
                [tail_call,start_sig] = extract_start(currentLine, previousLine, prePreviousLine) 

                if bool(instruction):
                    currentInstruction = instruction
                    if currentInstruction not in instructions:
                        instructions.append(currentInstruction)
                        registers_per_instruction[instruction] = []
                        instructions_per_module[currentModule].append(currentInstruction)
                
                if bool(state):
                    currentState = state 
                    if currentState not in states:
                        if DEBUG: print("DEBUG: Found state {} for the first time not in parameter list.".format(currentState))
                        states.append(currentState)
                        registers_per_state[currentState] = []
                        states_per_module[currentModule].append(currentState)
                
                if bool(register):
                    # if 'sdiv' in currentInstruction or 'udiv' in currentInstruction:
                    #     print(currentInstruction,register)
                    # if register != "return_val_reg":
                    if register != "cur_state":
                        registers.append(register)
                        registers_per_instruction[currentInstruction].append(register)
                        registers_per_module[currentModule].append(register)
                        registers_per_state[currentState].append(register)

                # if bool(divisor_reg):
                #     registers.append(divisor_reg) 
                #     registers_per_instruction(instruction).append(divisor_reg) 
                #     register_per_module[currentModule].append(divisor_reg)
                #     registers_per_state[currentState].append(divisor_reg)

                if bool(tail_call):
                    if start_sig not in start_sigs_per_instruction.keys():
                        start_sigs_per_instruction[start_sig] = []
                    start_sigs_per_instruction[start_sig].append(tail_call)


            # at the end of a block, clear state - it doesn't carry over
            currentState = ""

        if bool(phi):
            # we have a phi instruction, so extract the state in which the result is a constant
            begins = 1 
            while begins > 0:
                idx += 1
                prePreviousLine = previousLine
                previousLine = currentLine 
                currentLine = lines[idx] 

                if 'begin' in currentLine: begins += 1
                if 'end' in currentLine: begins -= 1
                if begins == 0: break

                state = extract_state_change(currentModule, currentLine)
                if bool(state): currentState = state

                if " = 32'" in currentLine:
                    if currentState not in phi_constant_source_per_state.keys(): 
                        phi_constant_source_per_state[currentState] = []
                    phi_constant_source_per_state[currentState].append(phi)

            currentState = ""
                
        idx += 1
        prePreviousLine = previousLine
        previousLine = currentLine


    save(os.path.join(out_dir,"rtl_instructions.csv"), instructions)
    save(os.path.join(out_dir,"rtl_states.csv"), states)
    save(os.path.join(out_dir,"rtl_modules.csv"), modules)
    save(os.path.join(out_dir,"rtl_registers.csv"), registers)

    save(os.path.join(out_dir,"rtl_memoryInstances.json"), memory_instances)
    save(os.path.join(out_dir,"rtl_memoryModules.json"), memory_modules)

    for k,v in memory_per_instruction.items(): memory_per_instruction[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"rtl_memoriesPerInstruction.json"), memory_per_instruction)

    for k,v in registers_per_state.items(): registers_per_state[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"rtl_regsPerState.json"), registers_per_state)

    for k,v in states_per_module.items(): states_per_module[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"rtl_statesPerModule.json"), states_per_module)

    for k,v in registers_per_instruction.items(): registers_per_instruction[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"rtl_regsPerInstruction.json"), registers_per_instruction)

    for k,v in registers_per_module.items(): registers_per_module[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"rtl_regsPerModule.json"), registers_per_module)

    for k,v in instructions_per_module.items(): instructions_per_module[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"rtl_instructionsPerModule.json"), instructions_per_module)

    for k,v in nodes_per_module.items(): nodes_per_module[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"rtl_nodesPerModule.json"), nodes_per_module)

    for k,v in phi_constant_source_per_state.items(): phi_constant_source_per_state[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"rtl_constantPhiPerState.json"), phi_constant_source_per_state)

    save(os.path.join(out_dir,"rtl_startsPerInstruction.json"), start_sigs_per_instruction)
    save(os.path.join(out_dir,"rtl_functionCallValues.json"), function_call_values)

def generate_roms(verilog_file):
    project_name = verilog_file.split(".")[0]
    out_dir = project_name+"_files"
    bmark = os.path.basename(verilog_file).split(".")[0]

    modules = get_modules(verilog_file)
    num_bits = get_num_bits(verilog_file)
    num_nStates = get_num_nStates(out_dir) 
    
    for module in modules:
        addr_w = num_bits[module]
        depth = 2**addr_w
        data_w = num_nStates[module] * 4 + num_nStates[module] * addr_w

        mif_file = os.path.join(out_dir, "rom", "{}_rom.mif".format(module))
        vlog_dict = dict({
            "addr_w":str(addr_w), 
            "data_w":str(data_w), 
            "mif_file":mif_file, 
            "depth":depth,
            "module":module})
        v_file = os.path.join(out_dir, "rom", "{}_rom.v".format(module))
        if not os.path.exists(os.path.join(out_dir, "rom")):
            os.makedirs(os.path.join(out_dir, "rom"))
        with open(v_file, "w+") as outf:
            outf.write(rom_file_template.substitute(vlog_dict))

        qip_file = os.path.join(out_dir, "rom", "{}_rom.qip".format(module))
        qip_dict = dict({"bmark":bmark,"module":module})

        if not os.path.exists(os.path.join(out_dir, "rom")):
            os.makedirs(os.path.join(out_dir, "rom"))
        with open(qip_file, "w+") as outf:
            outf.write(qip_file_template.safe_substitute(qip_dict))

def generate_temp_mif(verilog_file):
    project_name = verilog_file.split(".")[0]
    out_dir = project_name+"_files"

    modules = get_modules(verilog_file)
    num_bits = get_num_bits(verilog_file)
    num_nStates = get_num_nStates(out_dir) 

    for module in modules:
        addr_w = num_bits[module]
        data_w = num_nStates[module]*COUNTER_BITS + num_nStates[module]*addr_w
        depth = 2**addr_w
        tags_per_address = get_tags_per_address(out_dir, verilog_file, module)

        mif_file = os.path.join(out_dir, "rom", "{}_rom.mif".format(module))
        if not os.path.exists(os.path.dirname(mif_file)):
            os.makedirs(os.path.dirname(mif_file))
        with open(mif_file, "w+") as outf:
            outf.write("-- ROM Initialization file\n")
            outf.write("WIDTH = {};\n".format(data_w))
            outf.write("DEPTH = {};\n".format(depth)) 
            outf.write("ADDRESS_RADIX = HEX;\n")
            outf.write("DATA_RADIX = HEX;\n")
            outf.write("CONTENT\nBEGIN\n")
            for address in range(0,depth):
                tag = 0 
                data = 0
                for i in range(num_nStates[module]):
                    tag = tag << addr_w 
                    data = data << COUNTER_BITS
                    if address in tags_per_address.keys():
                        if i < len(tags_per_address[address]):
                            tag = tag + tags_per_address[address][i]
                            data = data + 2**COUNTER_BITS-1
                        else:
                            tag = tag + 0 
                            data = data + 2**COUNTER_BITS-1 # shouldn't be chosen but max (safest) if it is
                    else:
                        tag = tag + 0 
                        data = data + 2**COUNTER_BITS-1
                output = data + (tag << COUNTER_BITS*num_nStates[module])
                outf.write("\t{:x} : {:x};\n".format(address,output))
            outf.write("END\n")

def pull_out_state(pipeline, verilog_file):
    project_name = verilog_file.split(".")[0]
    out_dir = project_name+"_files"
    modules = get_modules(verilog_file)
    verilog = read_file(verilog_file)

    modules = modules + ['top']

    instructions_per_start_sig = read_file(os.path.join(out_dir,"rtl_startsPerInstruction.json"))
    value_per_state = read_file(os.path.join(out_dir,"rtl_functionCallValues.json"))
    instructions_per_state = read_file(os.path.join(out_dir,"hls_instructionsPerState.json"))
    nstatesPerModule = get_num_nStates(out_dir)
    
    module_formats = {}
    module_lengths = {}
    length_valid = {}
    module_instances = dict.fromkeys(modules)
    instance_count_per_module = dict.fromkeys(modules)
    for module in modules:
        module_formats[module] = ""
        module_lengths[module] = 0
        length_valid[module] = False
        instance_count_per_module[module] = 0
        module_instances[module] = dict.fromkeys(modules)
        for k in module_instances[module].keys():
            module_instances[module][k] = 0

    subroutine_calls = {}
    subroutine_states = {}

    idx = 0
    for module in modules:
        if module != 'top': verilog.insert(0,'`include "{}_files/rom/{}_rom.v"'.format(project_name, module))
    instance_per_module = {}
    instance_names_per_module = {'top':['top_inst']}
    while idx < len(verilog):
        line = verilog[idx]
        if 'module main_tb' in line:
            while '.return_val (return_val)' not in line:
                idx += 1
                line = verilog[idx]
            verilog.insert(idx, '.div_top_reg(),')
            idx += 4
            line = verilog[idx]

        if 'module' in line.split() and line.split()[1] in modules:
            # process this module
            module = line.split()[1]
            if module not in instance_per_module.keys():
                instance_per_module[module] = []
            if module not in instance_names_per_module.keys():
                instance_names_per_module[module] = []
            if module not in subroutine_calls.keys():
                subroutine_calls[module] = {}
            if module not in subroutine_states.keys():
                subroutine_states[module] = []

            # add port connection to declaration
            idx += 2
            if module == "top": verilog.insert(idx, 'div_{}_reg,'.format(module))
            else: verilog.insert(idx, 'div_{},'.format(module))
            idx += 1
            line = verilog[idx] 
            while ');' not in line:
                idx += 1
                line = verilog[idx]
            idx += 1
            if module == "top":
                verilog.insert(idx,"output reg [3:0] div_"+module+'_reg;')
                verilog.insert(idx,"reg [3:0] div_"+module+';')
                verilog.insert(idx,"reg [4*(${"+module+"_count_instances})-1:0] divs;")
            else:
                verilog.insert(idx,"output reg [3:0] div_"+module+';')
                verilog.insert(idx,"reg [4*(${"+module+"_num_nstates}+${"+module+"_count_instances})-1:0] divs;")
            idx += 3
            if module != 'top':
                lines = [
                    "reg [3:0] mem_div_out;",
                    "wire [${"+module+"_addr_w}*${"+module+"_num_nstates}-1:0] mem_tags;",
                    "wire [4*${"+module+"_num_nstates}-1:0] mem_divs;",
                    module+"_rom "+module+"_rom_INST("
                ]
                if pipeline:
                    lines += [".address_a(cur_state),"]
                else:
                    lines += [".address_a((memory_controller_waitrequest == 1'b1) ? cur_state : next_state),"]
                lines += [ 
                    ".address_b(),",
                    ".clock(clk),",
                    ".q_a({{mem_tags,mem_divs}}),",
                    ".q_b());"
                ]
                if pipeline:
                    lines += [
                        "genvar k;",
                        # "reg [3:0] mem_div_out;",
                        "generate for (k=0; k<${"+module+"_num_nstates}; k=k+1) begin : K",
                        "always @* begin ",
                        "if (mem_tags[(k+1)*${"+module+"_addr_w}-1:(k)*${"+module+"_addr_w}] == cur_state) begin ",
                        # "divs[3:0] = mem_divs[(k+1)*4-1:(k)*4];",
                        "mem_div_out = mem_divs[(k+1)*4-1:(k)*4];",
                        "end else begin ",
                        "mem_div_out = 4'bz;",
                        "end",
                        "end",
                        "end",
                        "endgenerate"
                    ]
                else: 
                    lines += [
                        "genvar k;",
                        # "reg [3:0] mem_div_out;",
                        "generate for (k=0; k<${"+module+"_num_nstates}; k=k+1) begin : K",
                        "always @* begin ",
                        "if (mem_tags[(k+1)*${"+module+"_addr_w}-1:(k)*${"+module+"_addr_w}] == ((memory_controller_waitrequest == 1'b1) ? cur_state : next_state)) begin ",
                        # "divs[3:0] = mem_divs[(k+1)*4-1:(k)*4];",
                        "mem_div_out = mem_divs[(k+1)*4-1:(k)*4];",
                        "end else begin ",
                        "mem_div_out = 4'bz;",
                        "end",
                        "end",
                        "end",
                        "endgenerate"
                    ]
                i = len(lines) - 1
                while i >= 0: 
                    verilog.insert(idx,lines[i])
                    i -= 1
                insert_idx = idx
                idx += len(lines)+1
            insert_select = idx
            
            if module == "top":
                line = verilog[idx] 
                while 'input' in line or 'output' in line:
                    idx += 1
                    line = verilog[idx]
                verilog.insert(idx,"always @(posedge clk) div_top_reg <= div_top;")

            line = verilog[idx] 
            insert_lines = []
            while 'endmodule' not in line:
                # find a new module declaration 
                if len(line.split()) > 1 and line.split()[0] in modules and line.split()[0] in line.split()[1]:
                    m = line.split()[0]
                    i = line.strip('(').split()[1]
                    # if module not in instance_per_module.keys(): instance_per_module[module] = []
                    instance_per_module[module].append(i)
                    if m not in instance_names_per_module.keys():
                        instance_names_per_module[m] = []
                    instance_names_per_module[m].append(i)
                    select_idx = idx
                    while ".start" not in line:
                        idx += 1
                        line = verilog[idx]
                    start_sig = line.split('(')[-1].split(')')[0].strip()
                    if start_sig in instructions_per_start_sig.keys():
                        tail_calls = instructions_per_start_sig[start_sig]
                    else: tail_calls = []
                    states = []
                    for state in [s for s in instructions_per_state.keys() if module in s]:
                        instructions = instructions_per_state[state]
                        for tc in tail_calls:
                            if tc in instructions:
                                states.append(state)

                    if module in nstatesPerModule.keys(): instance_count_per_module[module] += 1
                    if len(states) > 0:
                        verilog.insert(select_idx, "end")
                        verilog.insert(select_idx, "endcase")
                        verilog.insert(select_idx, "default: divs[({}+1)*4-1:(".format(instance_count_per_module[module])+"{})*4] = 4'd3;".format(instance_count_per_module[module]))
                        
                        for state_name in states:
                            subroutine_calls[module][state] = i
                        for state_val in [value_per_state[state] for state in states]:
                            subroutine_states[module].append(state_val)
                            verilog.insert(select_idx, "{}: divs[(".format(state_val)+"{}+1)*4-1:(".format(instance_count_per_module[module])+"{})*4] = div_{};".format(instance_count_per_module[module], i))
                        if pipeline:
                            verilog.insert(select_idx, "case (cur_state)")
                        else:
                            verilog.insert(select_idx, "case (next_state)")
                        verilog.insert(select_idx, "always @* begin")
                    else:
                        verilog.insert(select_idx, "always @* divs[("+"{}+1)*4-1:(".format(instance_count_per_module[module])+"{})*4] = div_{};".format(instance_count_per_module[module], i))

                    if module not in nstatesPerModule.keys(): instance_count_per_module[module] += 1

                    verilog.insert(select_idx,"wire [3:0] div_{};".format(i))

                    idx += 3
                    verilog.insert(idx,".div_{}( div_{} ),".format(m,i))
                
                if 'reg' in line and 'next_state;' in line:
                    insert_lines.append(line)
                    verilog[idx] = "// "+line

                if 'reg' in line and 'cur_state;' in line:
                    insert_lines.append(line)
                    verilog[idx] = "// "+line

                ########
                idx += 1
                line = verilog[idx]
                
            add = 0
            lines = ["end"]
            i = len(lines) -1
            while i >= 0:
                verilog.insert(insert_select, lines[i])
                i -= 1
                add += 1

            i = instance_count_per_module[module] 
            if  module != 'top': i += 1
            while i > 0:
                i -= 1
                verilog.insert(insert_select,"if (divs[({}+1)*4-1:{}*4] > div_{}) div_{} = divs[({}+1)*4-1:{}*4]; // select greatest div".format(i,i,module,module,i,i))
                add += 1

            lines = [
                "reg [31:0] j;",
                "always @* begin ",
                "div_{} = 0;".format(module)]
            i = len(lines) -1
            while i >= 0:
                verilog.insert(insert_select, lines[i])
                i -= 1
                add += 1

            if module != 'top':
                if len(subroutine_states[module]) > 0:
                    verilog.insert(insert_select, "end")
                    verilog.insert(insert_select, "else divs[3:0] = mem_div_out;")
                    for x,state_val in enumerate(subroutine_states[module]):
                        verilog.insert(insert_select, "divs[3:0] = 4'd3;")
                        if x < len(subroutine_states[module])-1:
                            verilog.insert(insert_select, "else if ((cur_state == {}) && (next_state == {}))".format(state_val, state_val))
                        else:
                            verilog.insert(insert_select, "if ((cur_state == {}) && (next_state == {}))".format(state_val, state_val))
                    verilog.insert(insert_select, "always @* begin")
                else: verilog.insert(insert_select, "always @* divs[3:0] = mem_div_out;")

            for i_line in insert_lines:
                verilog.insert(insert_idx, i_line)
            
            idx += len(insert_lines)+1+add
        idx += 1

    idx = 0
    while idx < len(verilog):
        line = verilog[idx]
        if 'module top' in line:
            count = 1 
            while ('output wire [31:0] return_val' not in verilog[idx + count]): count += 1
            count += 1
            idx = idx + count
            def populate_paths(paths, done_paths):
                if len(paths) == 0: return paths,done_paths 
                new_paths = []
                while len(paths) > 0:
                    p = paths[0]
                    paths.remove(p)
                    inst = p.split('.')[0]
                    instantiators = []
                    for instantiator, instances in instance_per_module.items():
                        if inst in instances: instantiators.extend(instance_names_per_module[instantiator])
                    for instantiator in instantiators:
                        new_path = '{}.{}'.format(instantiator, p)
                        if 'top_inst' in new_path: done_paths.append(new_path)
                        else: new_paths.append(new_path)
                return populate_paths(new_paths, done_paths)

            strings = ["always @(posedge clk) begin"]
            instances = []
            for k,v in instance_names_per_module.items():
                instances.extend(v)
            all_paths = []
            for instance in instances:
                paths = ['{}.cur_state'.format(instance)]
                p,done = populate_paths(paths,[])
                all_paths.extend(done)
            l = '$display("STATE '
            m = '"'
            all_paths = list(dict.fromkeys(all_paths))
            for path in all_paths:
                path = path.split('.')[1::]
                path = '.'.join(path)
                basepath = path.split('.')[0:-1]
                basepath = '.'.join(basepath)
                l = l +'{}\t%d\t'.format(basepath)
                m = m +',{}'.format(path)
            m = m + ");"
            strings.append(l+m)
            strings.append('end')
            i = len(strings)-1
            while i >= 0:
                verilog.insert(idx, strings[i])
                i -= 1
        idx += 1

    # now we have formats and lengths, so we should save to a template
    v_string = ''
    for line in verilog:
        v_string = v_string + line + '\n'

    v_template = Template(v_string)
    # nstatesPerModule = get_num_nStates(out_dir)
    bitsPerModule = get_num_bits(verilog_file)
    template_dict = {}
    for module in instance_count_per_module.keys():
        template_dict["{}_count_instances".format(module)] = instance_count_per_module[module]
    for module in nstatesPerModule.keys():
        template_dict["{}_num_nstates".format(module)] = nstatesPerModule[module]
    for module in bitsPerModule.keys():
        template_dict["{}_addr_w".format(module)] = bitsPerModule[module]

    for m, instances in instance_per_module.items():
        for i in instances:
            if i == "main_inst":
                instance_per_module[m].remove(i)
                instance_per_module[m].append('main')
    save(os.path.join(out_dir,"instancesPerModule.json"), instance_per_module)
    save(os.path.join(out_dir,"subroutine_calls.json"), subroutine_calls)

    return v_template.safe_substitute(template_dict).split('\n')

def get_num_nStates(out_dir):
    """ Returns dict of max(next_states) per module """
    nextStates = read_file(os.path.join(out_dir, "hls_nstatesPerState.json"))
    statesPerModule = read_file(os.path.join(out_dir, "hls_statesPerModule.json"))
    nstatesPerModule = {}
    for module, states in statesPerModule.items():
        nstatesPerModule[module] = max([len(nextStates[state]) for state in states])
    return nstatesPerModule

def get_num_bits(verilog_file):
    """ Returns dict of state_bits per module """
    modules = get_modules(verilog_file)
    lines = get_states(verilog_file)
    bits = {}
    for module in modules:
        bits[module] = [line[1][0] for line in lines if module in line[0].split('_LEGUP')[0]]
        bits[module] = list(dict.fromkeys(bits[module]))
        assert(len(bits[module]) == 1)
        bits[module] = int(bits[module][0])
    return bits

def get_tags_per_address(out_dir, verilog_file, module):
    """ next state ``tags'' for each state """
    nextStateNames = read_file(os.path.join(out_dir, "hls_nstatesPerState.json"))
    data = get_states(verilog_file)

    stateValues = {} # dict to translate state name to numerical value
    for line in data:
        state = line[0]
        value = int(line[1][1])
        stateValues[state] = value 

    nStates = {}
    for state, nstates in nextStateNames.items():
        if module in state:
            nStates[stateValues[state]] = []
            for nstate in nstates:
                nStates[stateValues[state]].append(stateValues[nstate])

    return nStates