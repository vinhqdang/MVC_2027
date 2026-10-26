# Proposed strategy

- Active front steering (P gains plus a yaw-rate damping term, `Steer.Kd`), no yaw moment control.
- Static torque split biased to the front motors (FR=FL=0.3455, RR=RL=0.1545), loss-minimising d-axis current.
- New "Slip control" subsystem in the strategy block: per-wheel slip ratio from wheel encoders, optical speed and yaw rate; wheel torque scaled by `max(0, 1 - Slip.k*max(|lambda|-Slip.th, 0))`. Parameters (`Slip.th`, `Slip.k`, `Slip.vmin`) are in `meso_para.m`.

Evaluated with a C re-implementation generated from the .slx XML (see `tools/`), which reproduces the reference energies (334.7 Wh baseline, 317.3 Wh improved). Example cycle: Phi = 537.3 (Phi1 225.2 Wh, Phi2 0.107, Phi3 100.4, Phi4 0.447) versus 968.5 for the improved strategy. Not yet run in MATLAB/Simulink R2022b.
