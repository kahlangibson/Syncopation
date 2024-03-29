# Syncopation

Syncopation is an open-source tool-flow that automatically instruments arbitrary circuits synthesized with LegUp HLS to enable adaptive clock management.

Our flow is integrated within the standard LegUp flow to automatically generate compatible Verilog RTL and clock management resources.

Publications available soon.

## Installing dependencies

### LegUp

LeFlow was built to be compatible with LegUp 4.0. We recommend downloading the virtual machine available at [legup.eecg.utoronto.ca](http://legup.eecg.utoronto.ca/).

### Syncopation Setup

Once this project has been cloned, you can install the Syncopation tool and dependencies using the following command:

```pip3 install -e .```

To test, type `syncopation` into the terminal to obtain the help message:

```
Syncopation

Usage:
    syncopation make [--no_synth_directives] [--add_synth_directives] [--no_sync_hardware] [--pipeline]
    syncopation modelsim [--log=<LOG_FILE>]
    syncopation synth [--log=<LOG_FILE>] [--enhanced_synthesis] [--no_synthesis] [--no_sta]
    syncopation timing
    syncopation -h|--help

Options:
    -h --help               Show this screen
    --no_synth_directives   No annotations in generated RTL for Syncopation circuits
    --add_synth_directives  Add synthesis directives to baseline circuit
    --no_sync_hardware      No syncopation DMs, clock generator
    --pipeline              Pipeline the divisor selection logic; use conservative predict
    --enhanced_synthesis    If no enhanced synthesis constraints are found, generate them. If found, resynthesize
    --no_synthesis          Perform performance eval without resynthesizing design
    --no_sta                Perform synthesis without performance eval/fine-grained sta
    --log=<LOG_FILE>        Modelsim log file generated by simulation and used to assess Syncopation performance
```

## Getting Started

### Running a single example

To get started with syncopation, try the following:

- Enter the design directory (i.e. Legup-4.0/examples/chstone/adpcm) of any design you would like to synthesize.

- To generate Syncopation hardware from C code, run

  ```syncopation make```
  
- To test generated hardware using Modelsim, run

  ```syncopation modelsim```
  
- To synthesize the above example, run 

  ```syncopation synth```
  
- To run synthesis with enhanced synthesis, run

  ```syncopation synth --enhanced_synthesis```
  
  Once to generate the constraints file, and again run 
  
  ```syncopation synth --enhanced_synthesis``` 

### Syncopation Settings

If you are interested in changing some of the default syncopation parameters, take a look at `settings.py`.

## Contents:

- src -- includes source code for syncopation

## Default Parameters:

Default Syncopation parameters are set in `src/settings.py`. 

This file includes settings for the system Python Path, the pll frequency (which corresponds to a directory in `src/pll`), the number of bits in the bit clock generator counter, and verbosity messages.

## Contributors

* **Kahlan Gibson** - *kahlangibson-at-ece.ubc.ca* 
* **Esther Roorda**
* **Daniel Holanda Noronha**
* **Steve Wilton**

## License

This project is licensed under the MIT License - see the [LICENSE.txt](LICENSE.txt) file for details
