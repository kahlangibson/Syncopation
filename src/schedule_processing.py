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
import re, os
from .settings import *

def get_hls_data(verilog_file):
    """
    Extract States, Instructions, and Transitions from HLS Schedule
    As well as extracting sources and drains
    """
    project_folder = os.path.dirname(verilog_file)
    schedule_file = os.path.join(project_folder,"scheduling.legup.rpt")
    project_name = verilog_file.split(".")[0]
    out_dir = project_name+"_files"

    lines = read_file(schedule_file)

    instructions = []
    states = []
    modules = []
    registers = []

    states_per_module = {}
    instructions_per_module = {}
    alloca_per_module = {}
    regs_per_module = {}
    basic_blocks_per_module = {}

    nstates_per_state = {}
    instructions_per_state = {}
    sources_per_state = {}
    drains_per_state = {}

    starts_per_instruction = {}
    finishes_per_instruction = {}
    sources_per_instruction = {}
    drains_per_instruction = {}

    currentLine = ""
    currentState = ""
    currentModule = ""

    ## Logic for parsing each line ##
    def extract_module(currentLine):
        if "Start Function" in currentLine: 
            return currentLine.split(':')[1].strip()
        else: return None

    def extract_state(currentModule, currentLine):
        if "state:" in currentLine:
            return currentModule+'_'+currentLine.split(':')[1].strip()
        else: return None

    def extract_finish_state(currentModule, currentLine):
        if "(endState:" in currentLine:
            return currentModule+'_'+currentLine.split('(endState: ')[1].split(')')[0].strip()
        else: return None

    def extract_instruction(currentLine):
        if "printf" in currentLine: return None
        elif "Transition" in currentLine: return None
        elif "(endState:" in currentLine:
            if 'alloca' in currentLine:
                return None # these instructions are RAM instantiations!
            else: 
                return currentLine.split('(endState:')[0].strip()
        elif "br" in currentLine:
            return currentLine.strip()
        elif "ret" in currentLine:
            return currentLine.strip()
        elif "switch" in currentLine:
            return currentLine.strip()
        else: return None

    def extract_next_states(currentModule, currentLine):
        if "Transition" in currentLine:
            return [currentModule+'_'+s for s in currentLine.split(" ") if 'LEGUP_' in s]
        else: return None

    def extract_alloca(currentLine):
        if 'alloca' in currentLine:
            return currentLine.split('=')[0].strip().split('%')[-1]
        else: return None

    def extract_branch_registers(instruction):
        # finds all non-label registers in a branch instruction, 
        # returns in a list
        regs = []
        prev_word = ''
        for word in instruction.split():
            reg = [r.split('%')[1] for r in re.findall(r'%[a-zA-Z0-9_\.\-]+', word)]
            if len(reg) > 0 and prev_word != 'label':
                regs.extend(reg)
            prev_word = word
        return regs

    def extract_instruction_registers(instruction):
        """ 
        Given an instruction, extracts all registers.
        returns a list of register names in RTL format (removes "%" "." characters)
        """
        regex = r'%[a-zA-Z0-9_\.\-]+'
        if "=" in instruction: 
            strings = instruction.split('=')
        else:
            strings = ["", instruction]
        # find all occurences, remove %, remove periods (.)
        results = []
        for substring in strings:
            results.append([r.split('%')[1] for r in re.findall(regex, substring)])
        return results[0], results[1]

    def extract_basic_block(currentLine):
        regex = r'%[a-zA-Z0-9_\.\-]+'
        if "Basic Block:" in currentLine:
            regs = [r.split('%')[1] for r in re.findall(regex, currentLine)]
            return regs[0]
        else: return None

    for idx,currentLine in enumerate(lines):
        module = extract_module(currentLine)
        state = extract_state(currentModule, currentLine)
        finish_state = extract_finish_state(currentModule, currentLine)
        instruction = extract_instruction(currentLine)
        next_states = extract_next_states(currentModule, currentLine)
        alloca = extract_alloca(currentLine)
        basic_block = extract_basic_block(currentLine)

        if bool(basic_block):
            basic_blocks_per_module[currentModule].append(basic_block)

        if bool(module):
            currentModule = module
            if currentModule not in modules:
                basic_blocks_per_module[currentModule] = []
                modules.append(currentModule)
                states_per_module[currentModule] = []
                instructions_per_module[currentModule] = []
                alloca_per_module[currentModule] = []
                regs_per_module[currentModule] = []
            else:
                if DEBUG: print("DEBUG: HLS Module {} detected multiple times on line {}".format(currentModule, idx+1))
        
        if bool(alloca):
            alloca_per_module[currentModule].append(alloca)

        if bool(state):
            currentState = state
            if currentState not in states:
                states.append(currentState)
                nstates_per_state[currentState] = []
                if currentState not in instructions_per_state.keys():
                    instructions_per_state[currentState] = []
                if currentState not in sources_per_state.keys():
                    sources_per_state[currentState] = []
                if currentState not in drains_per_state.keys():
                    drains_per_state[currentState] = []
                states_per_module[currentModule].append(currentState)
            else:
                if DEBUG: print("DEBUG: HLS State {} from module {} detected multiple times on line {}".format(currentState, currentModule, idx+1))

        if bool(instruction):
            if instruction not in instructions_per_module[currentModule]:
                instructions.append(instruction)
                sources_per_instruction[instruction] = []
                drains_per_instruction[instruction] = []
            if 'ret ' in instruction: 
                nstates_per_state[currentState].extend([currentState])

            # elif 'br' or 'tail call' not in instruction:
            #     print("HLS Instruction {} in module {} and state {} detected multiple times on line {}".format(instruction, currentModule, currentState, idx+1))

            if bool(finish_state):
                finish = finish_state
            else: 
                # print("No finish state for instruction {}".format(instruction))
                finish = currentState

            if instruction not in starts_per_instruction.keys():
                starts_per_instruction[instruction] = []
            starts_per_instruction[instruction].append(currentState)
            if instruction not in finishes_per_instruction.keys():
                finishes_per_instruction[instruction] = []
            finishes_per_instruction[instruction].append(finish)

            instructions_per_state[currentState].append(instruction)
            if finish not in instructions_per_state.keys():
                instructions_per_state[finish] = []
            instructions_per_state[finish].append(instruction)
            instructions_per_module[currentModule].append(instruction)

            sources = []
            drains = []
            if 'br' in instruction:
                sources = extract_branch_registers(instruction)
            elif '=' in instruction:
                drains, sources = extract_instruction_registers(instruction)
            else:
                _,sources = extract_instruction_registers(instruction)

            if finish not in drains_per_state.keys(): 
                drains_per_state[finish] = []

            for source in sources:
                sources_per_instruction[instruction].append(source)
                sources_per_state[currentState].append(source)
                registers.append(source)
                regs_per_module[currentModule].append(source)
            for drain in drains:
                drains_per_instruction[instruction].append(drain)
                drains_per_state[finish].append(drain)
                registers.append(drain)
                regs_per_module[currentModule].append(drain)

            if ' = mul' in instruction:
                drains_per_state[currentState].extend(['{}_stage0'.format(drains[0])])
                drains_per_instruction[instruction].extend(['{}_stage0'.format(drains[0])])
                registers.extend(['{}_stage0'.format(drains[0])])
         
        if bool(next_states):
            nstates_per_state[currentState].extend([n for n in next_states])


    save(os.path.join(out_dir,"hls_instructions.csv"), instructions)
    save(os.path.join(out_dir,"hls_states.csv"), states)
    save(os.path.join(out_dir,"hls_modules.csv"), modules)
    save(os.path.join(out_dir,"hls_registers.csv"), registers)

    for k,v in nstates_per_state.items(): nstates_per_state[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"hls_nstatesPerState.json"), nstates_per_state)
    for k,v in sources_per_state.items(): sources_per_state[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"hls_sourcesPerState.json"), sources_per_state)
    for k,v in drains_per_state.items(): drains_per_state[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"hls_drainsPerState.json"), drains_per_state)
    for k,v in instructions_per_state.items(): instructions_per_state[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"hls_instructionsPerState.json"), instructions_per_state)
    
    for k,v in instructions_per_module.items(): instructions_per_module[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"hls_instructionsPerModule.json"), instructions_per_module)
    for k,v in regs_per_module.items(): regs_per_module[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"hls_regsPerModule.json"), regs_per_module)
    for k,v in states_per_module.items(): states_per_module[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"hls_statesPerModule.json"), states_per_module)
    for k,v in alloca_per_module.items(): alloca_per_module[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"hls_allocaPerModule.json"), alloca_per_module)
    for k,v in basic_blocks_per_module.items(): basic_blocks_per_module[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"hls_basicBlocksPerModule.json"), basic_blocks_per_module)

    save(os.path.join(out_dir,"hls_startStatesPerInstruction.json"), starts_per_instruction)
    save(os.path.join(out_dir,"hls_finishStatesPerInstruction.json"), finishes_per_instruction)
    for k,v in sources_per_instruction.items(): sources_per_instruction[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"hls_sourcesPerInstruction.json"), sources_per_instruction)
    for k,v in drains_per_instruction.items(): drains_per_instruction[k] = list(dict.fromkeys(v))
    save(os.path.join(out_dir,"hls_drainsPerInstruction.json"), drains_per_instruction)
