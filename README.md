# ApolloBot - UAD Console Alt Monitor Automation

## Project Overview
ApolloBot was created to automate my monitor switching workflow for my Universal Audio Apollo 8 interface.

I have an alternative monitoring setups that isn't possible to set up using the standard analog outputs (3/4) set when you add an alt speaker in console settings, but is actually connected to a secondary amp via digital coax (S/PDIF).  Since there is no configuration for a setup like this within the console settings, we have to intercept the alt monitor signal and set the cue 1 output to send the mix accordingly.

Note this does mean that outputs 3/4 and cue 1 (and headphone 1) are not usable in this setup.  This is an acceptable trade-off in my case.  If I need to use either, I can stop the watcher and disable the alt count in the settings.

Also note that the commands don't always line up perfectly...there may be a split second where both monitors are playing at the same time, or a split-second of silence when you click the alt button.  Again, for me, this is within acceptable bounds for my use case.

## Hardware Setup
- **Interface**: Universal Audio Apollo 8
- **Main Monitors**: Connected via analog monitor outputs (standard setup)
- **Alt Monitors**: Connected via S/PDIF (coax) output → digital streamer → tube amp stereo hi-fi system

## Software Setup
- **macOS**: 15.6.1 (Sequoia)
- **UAD Console**: 1.2.6

I have no way of testing on windows.  If you'd like to help me out here and test that and help me modify things to work, I'd appreciate the help!

## Original Manual Workflow
To switch to alt monitors:
1. Mute the main output in UAD Console
2. Open cue output window
3. Set cue 1 to "mirror to s/pdif"
4. Click the mix button to send mix to S/PDIF

To switch back to main monitors:
1. Unselect the mix button in cue window
2. Unmute the main monitor

## Implementation Method
**TCP Protocol Automation**: This uses a reverse-engineered version of UAD Console's internal TCP communication protocol on Console's standard port (port 4710) to directly send commands.  These commands are reflected within the Console UI and on the Apollo's hardware.

**Credit**: This implementation was made possible by the groundbreaking work of [Radu Varga's UA-Midi-Control](https://github.com/raduvarga/UA-Midi-Control) project, which first reverse-engineered UAD's TCP messaging protocol using Wireshark. Thank you to Radu for open-sourcing this research and making UAD automation accessible to the community!

It was also entirely vibe coded using claude code.

## Technology Stack
- **Language**: Python 3 (standard library only...I specifically tested with 3.12.8)
- **Protocol**: Raw TCP sockets to UAD Console
- **Deployment**: Single executable file with global CLI access

### TCP Messages Used
ApolloBot communicates with UAD Console via TCP on port 4710 using these key messages:

**Monitor Control:**
- `get /devices/0/AltMonSelection` - Read hardware Alt button state
- `set /devices/0/AltMonSelection/value {0|1}` - Set Alt button state (0=main, 1=alt)

**S/PDIF Routing:**
- `get /devices/0/outputs/18/MixInSource` - Read S/PDIF output source
- `set /devices/0/outputs/18/MixInSource/value "mon"` - Route main mix to S/PDIF
- `set /devices/0/outputs/18/MixInSource/value "cue"` - Route cue 1 to S/PDIF (muted)

All messages are NULL-terminated and responses are JSON-formatted.

### How It Works
1. **Alt Monitor ON**: Sets S/PDIF output to route main monitor mix → tube amp gets main mix
2. **Alt Monitor OFF**: Sets S/PDIF output to route cue 1 mix (muted) → analog monitors active
3. **Auto-sync**: Background daemon watches for manual Alt button presses and syncs routing

### Installation

**Option 1: Run directly (no installation required)**
```bash
python3 apollobot.py status
python3 apollobot.py toggle
python3 apollobot.py start
```
etc.

**Option 2: Make globally accessible**
```bash
# Create ~/bin and add to PATH
mkdir -p ~/bin
ln -sf "$(pwd)/apollobot.py" ~/bin/apollobot
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc

# Reload shell or open new terminal, then use:
apollobot status
apollobot toggle  
apollobot start
```
etc.

### Usage

Here are all the commands that are implemented:

```bash
apollobot alt      # Switch to alt monitors
apollobot main     # Switch to main monitors  
apollobot toggle   # Toggle between setups
apollobot status   # Show current state
apollobot start    # Start background watcher daemon
apollobot stop     # Stop background watcher
apollobot log      # Show daemon activity
```

You can also use `apollobot --help` to see these commands within the terminal
