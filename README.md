A portable periodic multi-timer to assist with healthier PC usage.

# Motivation
Many "PC health" programs exist, however they are often overcomplicated and their interruptions can often be ignored by the user, only showing notifications or annoying popups. It's a lot harder to ignore the whole screen suddenly becoming blank.

# Features
* Get forced to blink or take a break regularly
* Define multiple timers
* Timers run in a loop
* Obstructs all screens with a solid color when a timer expires
* Configurable obstruction delay, period and colors
* Continue typing while the screen obstruction is shown (no focus stealing)
* Click the screen to dismiss obstruction
* Interaction via a tray icon
* Portable - the only real dependency is [pystray](https://pystray.readthedocs.io/en/latest/usage.html#selecting-a-backend)

# Running
```bash
PYSTRAY_BACKEND=gtk python3 blink_timer.pyw
```
Select backend accordingly.

# Configuration
```bash
mkdir -p ~/.config/blinktimer
cp config.json.example ~/.config/blinktimer/config.json
```
