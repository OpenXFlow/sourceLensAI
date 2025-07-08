# Analog Sample Project: Automatic Gain Control (AGC) Amplifier

This project demonstrates a simple Automatic Gain Control (AGC) circuit. The goal of an AGC is to automatically adjust its gain to maintain a constant output amplitude, even if the input signal's amplitude varies.

## Key Components:
- **`agc_system.sp`**: The main SPICE netlist for the entire AGC system.
- **`models/`**: Library files for core components.
    - `opamp_gain_stage.lib`: A variable gain amplifier subcircuit.
    - `voltage_controlled_resistor.va`: A Verilog-A model for a resistor whose value is controlled by an external voltage. This is key for the variable gain.
    - `peak_detector.lib`: A subcircuit that detects the peak voltage of a signal.
- **`analysis/`**: Simulation control files.
    - `transient_analysis.inc`: Configures the time-domain simulation to observe the AGC's behavior over time.
    - `dc_analysis.inc`: Configures the DC operating point analysis.