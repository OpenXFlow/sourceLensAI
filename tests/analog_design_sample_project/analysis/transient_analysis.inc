* Transient Analysis
* Run the simulation for 20ms to observe the AGC reaction.
* .TRAN TSTEP TSTOP
.TRAN 1us 20ms

.PROBE V(in) V(vga_out) V(v_peak) V(v_gain_control)