* Automatic Gain Control (AGC) System

.INCLUDE models/opamp_gain_stage.lib
.INCLUDE models/peak_detector.lib
* The Verilog-A model is included via the opamp_gain_stage

* --- Main Circuit ---

* Input Signal: Starts at 0.1V amplitude, steps up to 0.5V at 10ms
* PULSE(V1 V2 TD TR TF PW PER)
Vin in 0 PULSE(0 0.1V 0 1us 1us 10ms 20ms) SIN(0 1V 10kHz)

* 1. Variable Gain Amplifier (VGA) Stage
* Inputs: in, v_gain_control | Output: vga_out
X_VGA in vga_out v_gain_control vga_stage

* 2. Peak Detector Stage
* Measures the peak of the VGA output to create a DC control signal
* Input: vga_out | Output: v_peak
X_PEAK_DET vga_out v_peak peak_detector_circuit

* 3. Feedback Loop (Integrator)
* Compares the detected peak with a reference voltage (Vref) and integrates
* the error to generate the final gain control signal.
Vref v_ref 0 1.0V  ; Target output peak is 1.0V
R_int v_peak 10 10k
C_int 10 v_gain_control 1uF
* Ideal op-amp as an integrator
X_INT 0 10 v_gain_control opamp_ideal_for_int

* --- Analysis ---
.INCLUDE analysis/dc_analysis.inc
.INCLUDE analysis/transient_analysis.inc

.END

* Subcircuit for the integrator's opamp
.SUBCKT opamp_ideal_for_int v_plus v_minus v_out
E_INT_GAIN v_out 0 v_plus v_minus 1e6
.ENDS opamp_ideal_for_int