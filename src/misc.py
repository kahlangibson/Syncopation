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

import os, sys, json, csv
import subprocess

from .settings import *

def execute(command, cd='.', err=False, t=1200, wait=False, quiet=False, filename=None, print_output=False):
    """ 
    Given a command described as a list of strings, run using subprocess.
    Execute command executed in directory indicated by dir.
    Returns stdout as string. 
    """
    if isinstance(command, str):
        command = command.split(' ')
    outs = ''
    errs = ''
    if VERBOSE:
        command_str = ' '.join(command)
        print("VERBOSE: Executing `"+command_str+"` in dir "+cd)

    if wait:
        subprocess.Popen(command, cwd=cd, stdout=subprocess.PIPE,stderr=subprocess.PIPE).wait()
        return None
    elif filename:
        log = open(filename, 'w+')
        subprocess.Popen(command, cwd=cd, stdout=log, stderr=log, shell=True).wait()
    elif print_output:
        p = subprocess.Popen(command, cwd=cd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        while p.poll() is None:
            l = str(p.stdout.readline(), 'utf-8').strip('\n')
            if len(l) > 0 and '#' != l[0]:
                print(l)
            outs = outs + l + '\n'
        while l:
            l = str(p.stdout.readline(), 'utf-8').strip('\n')
            if len(l) > 0 and '#' != l[0]:
                print(l)
            outs = outs + l + '\n'
    else:
        try:
            with subprocess.Popen(command, cwd=cd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid) as process:
                try:
                    outs, errs = process.communicate(timeout=t)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGINT)
                    output = process.communicate()[0]
        except subprocess.CalledProcessError as e:
            print(e)

        if type(outs) is bytes: outs = outs.decode('UTF-8')
        if type(errs) is bytes: errs = errs.decode('UTF-8')
        if outs and not quiet:
            print(outs)
        if errs and not quiet and not print_output:
            print(errs)
            sys.exit(2)

    if err: return (outs,errs)
    else: return outs

def clean_file(filename):
    if not os.path.exists(os.path.dirname(os.path.abspath(filename))):
        os.makedirs(os.path.dirname(os.path.abspath(filename)))
    with open(filename, 'w+') as f:
        f.write(' ')

def read_file(filename):
    """
    Return contents of a file as list.
    """
    lines = []
    try: 
        f = open(filename, 'r')
    except (SystemExit, KeyboardInterrupt):
        raise 
    if filename.split('.')[-1] == 'json':
        with open(filename, 'r') as f:
            lines = json.load(f)
    else:
        with open(filename, 'r') as f:
            while True:
                line = f.readline()
                if not line:
                    break 
                lines.append(line.strip())
    return lines

def save(filename, data):
    if DEBUG: print("DEBUG: Saving "+filename)
    if isinstance(data, list):
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        with open(filename, 'w+') as f:
            w = csv.writer(f)
            for each in data:
                w.writerow([each])

    if isinstance(data, dict):
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        with open(filename, 'w+') as f:
            json.dump(data, f)

    if isinstance(data, str):
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        with open(filename, 'w+') as f:
            f.write(data)