%
% Parameter of the Energy Management & Motion Control Strategy
%
% Strategy: active front steering (no yaw moment control), static
% torque distribution biased to the front motors (lower copper loss),
% loss-minimising d-axis current, and a per-wheel slip limiter inside the
% "Energy Management & Motion Control Strategy" block ("Slip control").
% The limiter scales each wheel torque by max(0, 1 - Slip.k*(|lambda|-Slip.th)^+),
% where lambda is the slip ratio computed from the wheel encoders, the
% optical sensor speed and the IMU yaw rate. It works for traction and regeneration.
%
flag.DYC = 0; flag.current = 1;

% 1. Active front steering
Steer.Kp_pos =  0.6842;                    % P gain of the lateral position control via front steering
Steer.Kp_yaw =  2.9632;                    % P gain of the yaw angle control control via front steering
Steer.Kd     =  0.1873;                    % yaw-rate damping gain of the steering command

% 2. Yaw moment control (not used, flag.DYC = 0)
DYC.Kp_pos   =  4000;
DYC.Ki_pos   =  20;
DYC.Kd_pos   =  1000;
DYC.Taud_pos =  0.005;
DYC.Kp_yaw   =  5000;

% 3. Torque distribution
tdis_FR      =  0.3455;                    % torque distribution gain (front right)
tdis_FL      =  0.3455;                    % torque distribution gain (front left)
tdis_RR      =  0.1545;                    % torque distribution gain (rear right)
tdis_RL      =  1 - (tdis_FR + tdis_FL + tdis_RR);  % torque distribution gain (rear left)

% 4. Slip limiter
Slip.th      =  0.0411;                    % slip ratio threshold
Slip.k       =  57.5;                      % gate gain
Slip.vmin    =  1.84;                      % minimum speed in the slip ratio denominator [m/s]
