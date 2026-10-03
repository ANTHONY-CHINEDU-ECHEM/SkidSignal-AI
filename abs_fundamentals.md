# Antilock brake system fundamentals

Original reference notes written for this project. They give the retrieval layer
plain language engineering context to ground explanations of complaint patterns.

## What an antilock brake system does
An antilock brake system (ABS) prevents the wheels from locking during hard braking or braking on a low friction surface. A locked wheel slides, and a sliding tyre produces less braking force and almost no steering force. By keeping each wheel rotating close to the slip ratio where tyre grip peaks, ABS preserves steering control and, on most surfaces, shortens stopping distance. ABS does not add braking force. It only reduces, holds or restores hydraulic pressure that the driver has already requested.

## Main components
A typical hydraulic ABS has four groups of parts. Wheel speed sensors read a toothed tone ring or magnetic encoder at each wheel. An electronic control unit compares the wheel speeds and estimates slip. A hydraulic control unit, also called the modulator or hydraulic electronic control unit, contains inlet and outlet solenoid valves, a return pump and an electric motor. Finally a warning lamp on the instrument panel tells the driver when the system has detected a fault and switched itself off. On most modern vehicles the control unit and the hydraulic unit are bolted together as one module mounted in the engine compartment.

## Control cycle
During an ABS event the controller cycles each wheel through three phases many times per second: pressure hold, pressure release and pressure reapply. The driver feels this as a rapid pulsation in the brake pedal and hears the pump motor. Pulsation during a genuine low grip stop is normal operation. Pulsation at low speed on dry pavement, with no wheel close to locking, usually means a wheel speed signal is wrong, for example because of a cracked tone ring, corrosion under a sensor or a damaged harness.

## Fail safe behaviour
When the controller detects a fault it disables antilock control, lights the ABS warning lamp and leaves the base hydraulic brakes working. The vehicle then brakes like a vehicle without ABS, so wheels can lock in a panic stop. Because traction control, electronic stability control and often automatic emergency braking share the same sensors, pump and valves, a single ABS fault commonly disables those functions at the same time and several warning lamps light together.

## Shared hardware with stability and driver assistance functions
Electronic stability control uses the ABS hydraulic unit to brake individual wheels and adds steering angle, yaw rate and lateral acceleration sensors. Traction control, hill start assist, brake assist and automatic emergency braking also command pressure through the same unit. For surveillance this matters in two ways. A complaint filed under stability control, forward collision avoidance or the electrical system may in fact describe an ABS hardware failure, and a defect in the ABS module can remove several safety functions at once.
