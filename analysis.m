% Thrust Stand analysis script

% define relevant parameters
F_thrust = 0.025; % N
k = 0.00167*(180/pi); % N-m/rad
g = 9.81; % m/s^2
m_thruster = 2.2+0.57; % Kg; both thruster and cathode assembly
l_thruster = 0.3048; % m
l_cw = 0.2286; % m
m_cw = 2.5; % kg
h_arm = 0.01; % kg
m_calarm = h_arm + 0.043; % kg; % mass of calibration arm and calibration bucket
m_hcw = h_arm + 0.024; % kg; mass of brass spacers and calibration arm  
d_calarm = 0.08255; % m
l_calarm = 0.15875; % m

% dynamic parameters
I = m_thruster*(l_thruster^2) + m_cw*(l_cw^2); % in kg-m^2


%% Initial Deflection (no thrust)

% this assumes thrust is zero; initial equilibrium position
theta = (180/pi)*(m_calarm*g*d_calarm - m_hcw*g*d_calarm)/(k - m_cw*g*l_cw - m_calarm*g*l_calarm + m_thruster*g*l_thruster + m_hcw*g*l_calarm) % deg

%% Static Analysis


% define design parameter sweeps and parameter setpoints
m_cw_sweep = 0:0.01:5; % 0-3 Kg

% Compute deflections for the mass sweep
def_sweep_cw = def_mass(m_cw_sweep, l_cw, l_thruster, m_thruster, g, k, F_thrust, m_calarm, d_calarm, l_calarm, m_hcw);

% plot results of mass sweep
figure;
hold on;
plot(m_cw_sweep, def_sweep_cw, 'r-');
xlabel('Counterweight Mass (Kg)');
ylabel('Deflection (degrees)');
title('Deflection vs. Counterweight Mass');
grid on;
hold off;

% define deflection function for sweeping mass
function [def] = def_mass(mass_sweep, l_cw, l_thruster, m_thruster, g, k, F_thrust, m_calarm, d_calarm, l_calarm, m_hcw)

    % define deflection equation
    def = (180/pi)*(F_thrust*l_thruster + m_calarm*g*d_calarm - m_hcw*g*d_calarm)./(k - mass_sweep.*g.*l_cw - m_calarm*g*l_calarm + m_thruster*g*l_thruster + m_hcw*g*l_calarm); % deg
end
%% Dynamic Analysis

% define initial conditions
theta0 = [theta*pi/180 0]; % initial angle and angular velocity
timeSpan = [0 30]; % time from 0 to 30 seconds

% solve ODE
[t, theta_sol] = ode45(@(t, theta) odefunc(t, theta, m_cw, l_cw, l_thruster, m_thruster, g, k, F_thrust, m_calarm, d_calarm, l_calarm, m_hcw, I), ...
    timeSpan, theta0);

% determine natural frequency by finding the peaks of undamped graph
[pks, locs] = findpeaks(theta_sol(:, 1).*(180/pi), t);
w_d = (2*pi)/(locs(2) - locs(1)); % rad/s

% plot angular displacement over time
figure;
plot(t, theta_sol(:, 1).*(180/pi), 'b-');
xlabel('Time (s)');
ylabel('Angular Displacement (degrees)');
title('Angular Displacement vs. Time');
grid on;
hold on;

plot(locs, pks, 'ro')

%-----------------------------------------------------------
% plot damper B as a function of gap distance
damper = readtable("Damper B-fields.csv");
damper_gap = damper{:, 1};
damper_B = damper{:, 2};

% interpolation
damper_eq = polyfit(damper_gap, damper_B, 7);
damper_fitted = polyval(damper_eq, damper_gap);

% plot damper B-field curve
figure;
plot(damper_gap, damper_B, 'b');
hold on;
plot(damper_gap, damper_fitted, 'ro');
xlabel("Gap Distance (mm)")
ylabel("B-field (G)")
title("B-field (G) vs. Gap Distance (mm)")
subtitle("Damper Curve")
legend("Theoretical Curve", "Fitted Curve")
hold off;

% define damping parameters
% d_copper = 0.0047625; % m, thickness of copper plate
% w_copper = 0.0381; % m, width of copper plate
% h_copper = 0.04572; % m, height of copper plate
d_aluminum = 0.00762; % m
gap = [5:15]; % mm
R = 2.65e-8; % ohm-m, resistivity
rho = 2720; % kg/m^3

% damper power dissipation as a function of B
B_gap = polyval(damper_eq, gap)*0.0001; % T
power_dissipation = ((pi^2).*(B_gap.^2).*(d_aluminum^2).*(w_d^2))./(6*R*rho); % W/kg

% plot results
figure;
yyaxis left
plot(gap, power_dissipation)
xlabel("Gap Distance (mm)")
ylabel("Power Dissipation per Unit Mass (W/kg)")
title("Power Dissipation per Unit Mass (W/kg) vs. Gap Distance (mm)")
subtitle("Damper Performance")

yyaxis right
plot(gap, B_gap)
ylabel("Peak B-field (T)")


function d_theta = odefunc(t, theta, m_cw, l_cw, l_thruster, m_thruster, g, k, F_thrust, m_calarm, d_calarm, l_calarm, m_hcw, I)

    % state definition of a 2nd order ode
    d_theta = zeros(2,1);
    d_theta(1) = theta(2);
    d_theta(2) = (-k.*theta(1) + m_cw*g*l_cw.*theta(1) + F_thrust*l_thruster + m_calarm.*g.*(l_calarm.*theta(1) + d_calarm) - m_hcw.*g.*(l_calarm.*theta(1) + d_calarm)- m_thruster*g.*(l_thruster.*theta(1)))./I;
end