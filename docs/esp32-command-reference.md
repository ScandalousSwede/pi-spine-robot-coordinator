# ESP32 MiKoBots Firmware — Command Reference
**Firmware Version:** 1.22 | **Baud:** 57600 | **Line ending:** \n

---

## Connection Protocol

Send `CONNECT\n` → receive `ROBOT_CONNECTED\n` (motion) or `IO_CONNECTED\n` (IO box)

## Flow Control

The ESP32 uses a 10-slot command ring buffer with flow control:
- ESP sends `go` when buffer has space for more commands
- ESP sends `wait` when buffer is nearly full (8+ slots used)
- After executing a command, ESP sends position report then `END`
- Send `stop` to clear buffer and halt all motion
- Send `pauze` to pause execution (resume with `play`)

## Parameter Encoding

Commands use alphabet-indexed parameters. For a 6-DOF robot:
- `A` through `F` = joint/axis values (J1-J6 or X-Y-Z-yaw-pitch-roll)
- `G` = speed
- `H` = acceleration

Example: `jogJ A10 B0 C0 D0 E0 F0 G50 H30`
= Jog Joint 1 by 10 degrees at speed 50, acceleration 30

## Motion Commands

### Home
```
Home
```
Homes all joints in configured homing order. Each joint moves until limit switch triggers.

### jogJ (Joint Space Jog)
```
jogJ A{J1_delta} B{J2_delta} C{J3_delta} D{J4_delta} E{J5_delta} F{J6_delta} G{speed} H{accel}
```
Relative joint-space move. Values are delta degrees from current position.

### jogL (Cartesian Jog)
```
jogL A{X_delta} B{Y_delta} C{Z_delta} D{yaw_delta} E{pitch_delta} F{roll_delta} G{speed} H{accel}
```
Relative Cartesian move. Uses inverse kinematics. Interpolates in 1mm increments.

### MoveJ (Joint Space Move — Cartesian Target)
```
MoveJ A{X} B{Y} C{Z} D{yaw} E{pitch} F{roll} G{speed} H{accel}
```
Move to Cartesian target using joint-space interpolation (fastest path, not straight line).

### MoveJoint (Direct Joint Target)
```
MoveJoint A{J1} B{J2} C{J3} D{J4} E{J5} F{J6} G{speed} H{accel}
```
Move to absolute joint positions.

### MoveL (Linear Cartesian Move)
```
MoveL A{X} B{Y} C{Z} D{yaw} E{pitch} F{roll} G{speed} H{accel}
```
Linear interpolation in Cartesian space. Breaks path into 2mm increments, solving IK at each point.

### OffsetJ / OffsetL
```
OffsetJ A{J1} B{J2} ... G{speed} H{accel}
OffsetL A{X} B{Y} ... G{speed} H{accel}
```
Offset moves (relative to current position in joint or Cartesian space).

## Tool Commands

### Tool_move_to
```
Tool_move_to A{position}
```
Move tool servo to position.

### Tool_state
```
Tool_state A{0|1}
```
Set tool digital output (0=off, 1=on). Used for gripper, vacuum, etc.

## IO Commands

### IO_digitalWrite
```
IO_digitalWrite A{channel} B{0|1}
```
Set IO box digital output.

## Configuration Commands

These configure the firmware at runtime (sent by MiKoBots Studio on connection):

| Command | Purpose | Format |
|---------|---------|--------|
| `Set_number_of_joints` | Set DOF | `A{n}` |
| `Set_motor_type` | Stepper(0)/Servo(1) per joint | `A{j1} B{j2} ...` |
| `Set_motor_pin` | Step+Dir GPIO per joint | `A{step1} B{dir1} C{step2} D{dir2} ...` |
| `Set_servo_pin` | Servo GPIO per joint | `A{pin1} B{pin2} ...` |
| `Set_servo_pulse` | Servo min/max/range | `A{max1} B{min1} C{deg1} ...` |
| `Set_servo_position` | Servo zero position | `A{pos1} B{pos2} ...` |
| `Set_switch_pin` | Limit switch GPIO per joint | `A{pin1} B{pin2} ...` |
| `Set_lim_pos` | Position at limit switch | `A{pos1} B{pos2} ...` |
| `Set_max_pos` | Joint travel limits | `A{min1} B{max1} C{min2} D{max2} ...` |
| `Set_step_deg` | Steps per degree per joint | `A{spd1} B{spd2} ...` |
| `Set_dir_joints` | Direction inversion per joint | `A{0|1} B{0|1} ...` |
| `Set_dh_par` | Denavit-Hartenberg parameters | (complex, per-joint 4 params) |
| `Set_speed` | Max speed/accel per joint | `A{speed1} B{accel1} ...` |
| `Set_home_settings` | Homing order + direction | `A{order1} B{dir1} ...` |
| `Set_tools` | Tool type + pin config | (varies by tool type) |
| `Set_tool_frame` | Tool frame offset | (4x4 transform) |
| `Set_io_pin` | IO box pin config | `A{pin1} B{type1} ...` |

## Response Format

After motion commands, ESP sends:
```
POS: X {x} Y {y} Z {z} y {yaw} p {pitch} r {roll} J1 {j1} J2 {j2} J3 {j3} J4 {j4} J5 {j5} J6 {j6}
PSJstart: (same format)
END
```

## Error Handling

- `Error: Buffer overflow` — sent too many commands without waiting for `go`
- `Error: do not regonize this command` — typo in command (note: firmware has this typo)
- Kinematic errors silently skip movement (error flag set internally)

## Important Notes

- Firmware runs on ESP32 dual-core: Core 0 handles serial/BLE input, Core 1 executes motion
- Mutex protects the command buffer between cores
- BLE device name: `Robot_MiKoBots`
- Supports both ESP32 and Arduino Mega (auto-detected at compile time)
- The firmware creator notes: "disclaimer I'm not a software engineer"
