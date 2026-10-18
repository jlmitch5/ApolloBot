#!/usr/bin/env python3
"""
ApolloBot - UAD Console Alt Monitor Automation
Automates monitor switching workflow for Apollo 8 interface

Based on reverse engineering of UAD Console TCP protocol
"""

import socket
import json
import time
import sys
import argparse
import os
import signal
import subprocess
from typing import Optional


LAUNCHD_TARGET = 'system/com.apollobot.watcher'
LAUNCHD_PLIST = '/Library/LaunchDaemons/com.apollobot.watcher.plist'

class ApolloBot:
    def __init__(self, host='127.0.0.1', port=4710):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.device_id = "0"  # Apollo 8 device ID
        self.spdif_output_id = "18"  # S/PDIF output (discovered via traffic capture)
        self.watching = False  # Watch mode flag
        self.pid_file = os.path.expanduser("~/.apollobot.pid")
        self.log_file = os.path.expanduser("~/.apollobot.log")
        
    def connect(self, quiet: bool = False) -> bool:
        """Connect to UAD Console"""
        if self.socket:
            self.socket.close()
        self.socket = None
        self.connected = False

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        try:
            sock.connect((self.host, self.port))
            self.socket = sock
            self.connected = True
            print(f"✓ Connected to UAD Console at {self.host}:{self.port}")
            return True
        except Exception as e:
            sock.close()
            if not quiet:
                print(f"✗ Connection failed: {e}")
                print("  Make sure UAD Console is running")
            return False
    
    def send_command(self, command: str) -> bool:
        """Send command to UAD Console"""
        if not self.connected:
            return False
            
        try:
            message = f"{command}\x00"
            data = message.encode('utf-8')
            self.socket.send(data)
            print(f"→ {command}")
            return True
        except Exception as e:
            print(f"✗ Send failed: {e}")
            self.connected = False
            return False
    
    def _get_alt_state_fresh_connection(self) -> Optional[int]:
        """Get Alt Monitor state with fresh connection for watch mode"""
        try:
            # Create fresh socket for this request
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((self.host, self.port))
            
            # Send command
            msg = f"get /devices/{self.device_id}/AltMonSelection\x00"
            sock.send(msg.encode('utf-8'))
            
            # Read response
            response = ""
            start_time = time.time()
            
            while time.time() - start_time < 1:
                try:
                    char = sock.recv(1)
                    if not char:
                        break
                        
                    char_str = char.decode('utf-8')
                    if char_str == '\x00':
                        break
                    response += char_str
                except:
                    break
            
            sock.close()
            
            if response:
                data = json.loads(response)
                response_data = data.get('data')
                if isinstance(response_data, dict) and 'value' in response_data:
                    return response_data['value']
                    
        except Exception as e:
            pass  # Silently fail in watch mode to avoid spam
            
        return None
    
    def get_alt_monitor_state(self) -> Optional[int]:
        """Get current alt monitor state"""
        # Create fresh connection for watch mode to avoid socket issues
        if self.watching:
            return self._get_alt_state_fresh_connection()
            
        if not self.send_command(f"get /devices/{self.device_id}/AltMonSelection"):
            return None
            
        try:
            # Read response
            response = ""
            start_time = time.time()
            
            while time.time() - start_time < 2:
                char = self.socket.recv(1)
                if not char:
                    break
                    
                char_str = char.decode('utf-8')
                if char_str == '\x00':
                    break
                response += char_str
            
            if response:
                data = json.loads(response)
                # Extract value from response structure
                response_data = data.get('data')
                if isinstance(response_data, dict):
                    # Check if value is directly in data
                    if 'value' in response_data:
                        alt_state = response_data['value']
                    else:
                        # Check in properties structure
                        properties = response_data.get('properties', {})
                        if 'value' in properties:
                            alt_state = properties['value'].get('value')
                        else:
                            alt_state = response_data
                else:
                    alt_state = response_data
                return alt_state
                
        except Exception as e:
            print(f"⚠️  Error reading alt state: {e}")
            
        return None
    
    def set_alt_monitor(self, state: int) -> bool:
        """Set alt monitor state (0=main, 1=alt)"""
        command = f"set /devices/{self.device_id}/AltMonSelection/value {state}"
        return self.send_command(command)
    
    def get_cue_mix_state(self) -> Optional[str]:
        """Get current cue mix state (mon/cue)"""
        if not self.send_command(f"get /devices/{self.device_id}/outputs/{self.spdif_output_id}/MixInSource"):
            return None
            
        try:
            # Read response
            response = ""
            start_time = time.time()
            
            while time.time() - start_time < 2:
                char = self.socket.recv(1)
                if not char:
                    break
                    
                char_str = char.decode('utf-8')
                if char_str == '\x00':
                    break
                response += char_str
            
            if response:
                data = json.loads(response)
                # Extract value from response structure
                cue_data = data.get('data')
                if isinstance(cue_data, dict):
                    # Check if value is directly in data
                    if 'value' in cue_data:
                        cue_state = cue_data['value']
                    else:
                        # Check in properties structure
                        properties = cue_data.get('properties', {})
                        if 'value' in properties:
                            cue_state = properties['value'].get('value')
                        else:
                            cue_state = cue_data
                else:
                    cue_state = cue_data
                return cue_state
                
        except Exception as e:
            print(f"⚠️  Error reading cue mix state: {e}")
            
        return None
    
    def set_cue_mix(self, source: str) -> bool:
        """Set cue mix source ('mon' for main mix, 'cue' for cue 1)"""
        command = f"set /devices/{self.device_id}/outputs/{self.spdif_output_id}/MixInSource/value \"{source}\""
        return self.send_command(command)
    
    def switch_to_alt_monitors(self) -> bool:
        """Switch to alt monitors (S/PDIF setup)"""
        print("🎵 Switching to ALT monitors (S/PDIF)...")
        
        # Step 1: Activate Alt Monitor selection (hardware button equivalent)
        alt_success = self.set_alt_monitor(1)
        
        # Step 2: Set S/PDIF to route main monitor mix (so you hear main mix on alt monitors)
        cue_success = self.set_cue_mix("mon")
        
        if alt_success and cue_success:
            print("✓ ALT monitors activated!")
            print("  → Alt Monitor selection: ON")
            print("  → S/PDIF source: Main monitor mix") 
            return True
        else:
            print("✗ Failed to switch to ALT monitors")
            if not alt_success:
                print("  ✗ Alt Monitor selection failed")
            if not cue_success:
                print("  ✗ Cue mix routing failed")
            return False
    
    def switch_to_main_monitors(self) -> bool:
        """Switch to main monitors (analog outputs)"""
        print("🔊 Switching to MAIN monitors (analog)...")
        
        # Step 1: Deactivate Alt Monitor selection
        alt_success = self.set_alt_monitor(0)
        
        # Step 2: Set S/PDIF to cue mix (mutes S/PDIF when using main monitors)  
        cue_success = self.set_cue_mix("cue")
        
        if alt_success and cue_success:
            print("✓ MAIN monitors activated!")
            print("  → Alt Monitor selection: OFF") 
            print("  → S/PDIF source: Cue 1 mix (muted)")
            return True
        else:
            print("✗ Failed to switch to MAIN monitors")
            if not alt_success:
                print("  ✗ Alt Monitor selection failed")
            if not cue_success:
                print("  ✗ Cue mix routing failed")
            return False
    
    def toggle_monitors(self) -> bool:
        """Toggle between main and alt monitors"""
        current_state = self.get_alt_monitor_state()
        
        if current_state is None:
            print("✗ Cannot determine current monitor state")
            return False
            
        if current_state == 0:
            # Currently on main, switch to alt
            return self.switch_to_alt_monitors()
        else:
            # Currently on alt, switch to main  
            return self.switch_to_main_monitors()
    
    def status(self) -> None:
        """Show current monitor status"""
        connected = self.connected or self.connect(quiet=True)
        if connected:
            alt_state = self.get_alt_monitor_state()
            cue_state = self.get_cue_mix_state()
        else:
            alt_state = None
            cue_state = None
        
        print("📊 Current Monitor Status:")

        if not connected:
            print(f"   ⚠️  UAD Console unavailable at {self.host}:{self.port}")
        
        if alt_state is None:
            print("   ❓ Cannot determine Alt Monitor state")
        elif alt_state == 0:
            print("   🔊 Alt Monitor: OFF (using analog outputs)")
        else:
            print("   🎵 Alt Monitor: ON (using S/PDIF output)")
            
        if cue_state is None:
            print("   ❓ Cannot determine S/PDIF source")
        elif cue_state == "mon":
            print("   📻 S/PDIF Source: Main monitor mix")
        elif cue_state == "cue":
            print("   🎛️  S/PDIF Source: Cue 1 mix")
        else:
            print(f"   ❓ S/PDIF Source: Unknown ({cue_state})")
            
        # Overall status
        if alt_state == 1 and cue_state == "mon":
            print("   ✅ ALT SETUP: Alt monitors + Main mix → S/PDIF → Tube amp")
        elif alt_state == 0 and cue_state == "cue":
            print("   ✅ MAIN SETUP: Analog monitors + S/PDIF muted (Cue 1)")
            
        # Daemon status
        print("")
        print("🤖 Daemon Status:")
        running, pid = self.is_daemon_running()
        if running:
            print(f"   ✅ Watcher running in background (PID: {pid})")
        else:
            launchd_pid = self.launchd_daemon_pid()
            if launchd_pid is not None:
                print(f"   ✅ Watcher running under launchd (PID: {launchd_pid})")
            else:
                print("   ⏹️  Watcher not running")
    
    def watch_for_alt_changes(self) -> None:
        """Watch for manual Alt Monitor button presses and sync cue mix"""
        print("👁️  ApolloBot Watch Mode")
        print("=" * 40)
        print("Monitoring for manual Alt Monitor button presses...")
        print("Will automatically sync S/PDIF cue mix routing")
        print("Press Ctrl+C to stop watching")
        print()
        
        # Get initial state
        last_alt_state = self.get_alt_monitor_state()
        if last_alt_state is None:
            print("❌ Cannot read initial Alt Monitor state")
            return
            
        print(f"📍 Initial Alt Monitor state: {last_alt_state}")
        self.watching = True
        
        try:
            while self.watching:
                # Check current Alt Monitor state
                current_alt_state = self.get_alt_monitor_state()
                
                if current_alt_state is None:
                    print("⚠️  Lost connection to UAD Console")
                    time.sleep(2)
                    # Try to reconnect
                    if not self.connect():
                        print("❌ Failed to reconnect")
                        break
                    continue
                
                # Check if Alt Monitor state changed
                if current_alt_state != last_alt_state:
                    timestamp = time.strftime("%H:%M:%S")
                    
                    if current_alt_state == 1:
                        # Alt Monitor turned ON - sync to main mix on S/PDIF
                        print(f"🎵 [{timestamp}] Alt Monitor activated manually!")
                        print("   → Syncing S/PDIF to main monitor mix...")
                        
                        cue_success = self.set_cue_mix("mon")
                        if cue_success:
                            print("   ✅ S/PDIF synced: Main mix → Tube amp")
                        else:
                            print("   ❌ Failed to sync S/PDIF")
                            
                    else:
                        # Alt Monitor turned OFF - mute S/PDIF
                        print(f"🔊 [{timestamp}] Alt Monitor deactivated manually!")
                        print("   → Muting S/PDIF (switching to Cue 1)...")
                        
                        cue_success = self.set_cue_mix("cue")
                        if cue_success:
                            print("   ✅ S/PDIF muted: Using analog monitors")
                        else:
                            print("   ❌ Failed to mute S/PDIF")
                    
                    last_alt_state = current_alt_state
                    print()
                
                # Poll every 500ms to reduce connection overhead
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            print("\n👋 Watch mode stopped")
            self.watching = False
        except Exception as e:
            print(f"\n❌ Watch error: {e}")
            self.watching = False

    def run_foreground(self, retry_interval: int = 15) -> None:
        """Run the watcher in the foreground, retrying until Console is available."""
        print("🤖 ApolloBot launchd watcher started")
        self.watching = True
        waiting_for_console = False

        try:
            while self.watching:
                if not self.connect(quiet=True):
                    if not waiting_for_console:
                        print(
                            f"UAD Console is not available at {self.host}:{self.port}; "
                            f"retrying every {retry_interval} seconds"
                        )
                        waiting_for_console = True
                    time.sleep(retry_interval)
                    continue

                if waiting_for_console:
                    print("UAD Console is available; starting watcher")
                    waiting_for_console = False

                self.watch_for_alt_changes()
                self.close()

                if self.watching:
                    print(
                        f"UAD Console disconnected; retrying in {retry_interval} seconds"
                    )
                    waiting_for_console = True
                    time.sleep(retry_interval)
        except KeyboardInterrupt:
            print("\n👋 ApolloBot watcher stopped")
        finally:
            self.watching = False
            self.close()
    
    def is_daemon_running(self) -> tuple[bool, Optional[int]]:
        """Check if watcher daemon is running"""
        if not os.path.exists(self.pid_file):
            return False, None
            
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is actually running
            os.kill(pid, 0)  # Signal 0 just checks if process exists
            return True, pid
        except (ValueError, OSError, ProcessLookupError):
            # PID file exists but process is dead, clean up
            try:
                os.remove(self.pid_file)
            except OSError:
                pass
            return False, None

    def launchd_service_info(self) -> tuple[Optional[bool], Optional[int]]:
        """Return whether the macOS LaunchDaemon is loaded and its running PID."""
        if sys.platform != 'darwin':
            return None, None

        try:
            result = subprocess.run(
                ['launchctl', 'print', LAUNCHD_TARGET],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None, None

        if result.returncode != 0:
            return False, None

        is_running = False
        pid = None
        for line in result.stdout.splitlines():
            field = line.strip()
            if field == 'state = running':
                is_running = True
            elif pid is None and field.startswith('pid = '):
                try:
                    pid = int(field.removeprefix('pid = '))
                except ValueError:
                    pass

        return True, pid if is_running else None

    def launchd_daemon_pid(self) -> Optional[int]:
        """Return the PID when the macOS launchd watcher is running."""
        loaded, pid = self.launchd_service_info()
        return pid if loaded is True else None

    def start_launchd(self) -> bool:
        """Start the installed macOS LaunchDaemon without restarting a live watcher."""
        if sys.platform != 'darwin':
            print("✗ The --launchd option is available only on macOS")
            return False

        loaded, pid = self.launchd_service_info()
        if loaded is None:
            print("✗ Could not query launchd for ApolloBot's service state")
            return False
        needs_bootstrap = loaded is False
        if needs_bootstrap and not os.path.isfile(LAUNCHD_PLIST):
            print("✗ ApolloBot's LaunchDaemon plist is not installed")
            print("  Install it with: python3 launchd/install.py")
            return False
        if pid is not None:
            print(f"✓ ApolloBot watcher already running under launchd (PID: {pid})")
            return True

        try:
            # Make the authorization prompt explicit before starting launchctl.
            authorization = subprocess.run(['sudo', '-v'], check=False)
            if authorization.returncode != 0:
                print("✗ Administrator authorization failed")
                return False

            if needs_bootstrap:
                print("Loading ApolloBot through launchd...")
                try:
                    bootstrap = subprocess.run(
                        ['sudo', 'launchctl', 'bootstrap', 'system', LAUNCHD_PLIST],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,
                    )
                except subprocess.TimeoutExpired:
                    loaded, pid = self.launchd_service_info()
                    if loaded is not True:
                        print("✗ launchctl did not load the service within 10 seconds")
                        print("  Check its state with: apollobot status")
                        return False
                else:
                    if bootstrap.returncode != 0:
                        loaded, pid = self.launchd_service_info()
                        if loaded is not True:
                            print("✗ launchctl could not load ApolloBot")
                            detail = bootstrap.stderr.strip()
                            if detail:
                                print(f"  {detail}")
                            print("  Check its state with: apollobot status")
                            return False
                    else:
                        loaded, pid = self.launchd_service_info()
                        if loaded is not True:
                            print("✗ launchctl returned, but ApolloBot is not loaded")
                            print("  Check its state with: apollobot status")
                            return False

                if pid is not None:
                    print(f"✓ ApolloBot watcher running under launchd (PID: {pid})")
                    return True

            print("Starting ApolloBot through launchd...")
            result = subprocess.run(
                ['sudo', 'launchctl', 'kickstart', LAUNCHD_TARGET],
                timeout=10,
                check=False,
            )
        except subprocess.TimeoutExpired:
            loaded, pid = self.launchd_service_info()
            if loaded is True and pid is not None:
                print(f"✓ ApolloBot watcher running under launchd (PID: {pid})")
                return True
            print("✗ launchctl did not respond within 10 seconds")
            print("  Check its state with: apollobot status")
            return False
        except OSError as error:
            print(f"✗ Could not start the LaunchDaemon: {error}")
            return False

        if result.returncode != 0:
            print("✗ launchctl could not start ApolloBot")
            return False

        loaded, pid = self.launchd_service_info()
        if loaded is True and pid is not None:
            print(f"✓ ApolloBot watcher running under launchd (PID: {pid})")
        else:
            print("✓ LaunchDaemon start requested; check status with: apollobot status")
        return True

    def stop_launchd(self) -> bool:
        """Stop and unload the installed macOS LaunchDaemon for this boot."""
        if sys.platform != 'darwin':
            print("✗ The --launchd option is available only on macOS")
            return False

        loaded, _ = self.launchd_service_info()
        if loaded is None:
            print("✗ Could not query launchd for ApolloBot's service state")
            return False
        if loaded is False:
            print("✓ ApolloBot LaunchDaemon is already stopped")
            return True

        try:
            # Request authorization separately so sudo can prompt in this terminal.
            authorization = subprocess.run(['sudo', '-v'], check=False)
            if authorization.returncode != 0:
                print("✗ Administrator authorization failed")
                return False

            print("Stopping ApolloBot through launchd...")
            result = subprocess.run(
                ['sudo', 'launchctl', 'bootout', LAUNCHD_TARGET],
                timeout=10,
                check=False,
            )
        except subprocess.TimeoutExpired:
            loaded, _ = self.launchd_service_info()
            if loaded is False:
                print("✓ ApolloBot LaunchDaemon stopped")
                return True
            print("✗ launchctl did not stop the service within 10 seconds")
            print("  Check its state with: apollobot status")
            return False
        except OSError as error:
            print(f"✗ Could not stop the LaunchDaemon: {error}")
            return False

        loaded, _ = self.launchd_service_info()
        if loaded is False:
            print("✓ ApolloBot LaunchDaemon stopped")
            return True
        if result.returncode != 0:
            print("✗ launchctl could not stop ApolloBot")
        else:
            print("✗ launchctl returned, but ApolloBot is still loaded")
        print("  Check its state with: apollobot status")
        return False
    
    def start_daemon(self) -> bool:
        """Start watcher in background daemon mode"""
        running, pid = self.is_daemon_running()
        if running:
            print(f"✓ ApolloBot watcher already running (PID: {pid})")
            return True

        launchd_pid = self.launchd_daemon_pid()
        if launchd_pid is not None:
            print(f"✓ ApolloBot watcher already running under launchd (PID: {launchd_pid})")
            return True
            
        # Fork to background
        try:
            pid = os.fork()
            if pid > 0:
                # Parent process
                print(f"✓ ApolloBot watcher started in background (PID: {pid})")
                return True
        except OSError as e:
            print(f"✗ Failed to fork daemon: {e}")
            return False
            
        # Child process - become daemon
        try:
            # Detach from parent
            os.setsid()
            
            # Write PID file
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
            
            # Redirect stdout/stderr to log file
            with open(self.log_file, 'w') as f:
                f.write(f"ApolloBot watcher started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.flush()
                
            # Close original stdin/stdout/stderr
            sys.stdin.close()
            sys.stdout = open(self.log_file, 'a')
            sys.stderr = sys.stdout
            
            # Setup signal handler for clean shutdown
            def signal_handler(signum, frame):
                del signum, frame  # Unused parameters
                self.watching = False
                try:
                    os.remove(self.pid_file)
                except OSError:
                    pass
                sys.exit(0)
                
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
            
            # Start watching
            if self.connect():
                self.watch_for_alt_changes()
                
        except Exception as e:
            print(f"Daemon error: {e}")
        finally:
            # Clean up PID file
            try:
                os.remove(self.pid_file)
            except OSError:
                pass
            sys.exit(0)
    
    def stop_daemon(self) -> bool:
        """Stop watcher daemon"""
        running, pid = self.is_daemon_running()
        if not running:
            launchd_pid = self.launchd_daemon_pid()
            if launchd_pid is not None:
                print("✓ ApolloBot watcher is managed by launchd")
                print("  Stop it with: apollobot stop --launchd")
                return False
            print("✓ ApolloBot watcher is not running")
            return True
            
        try:
            os.kill(pid, signal.SIGTERM)
            # Wait a bit for graceful shutdown
            time.sleep(1)
            
            # Check if it's still running
            still_running, _ = self.is_daemon_running()
            if still_running:
                # Force kill if needed
                os.kill(pid, signal.SIGKILL)
                time.sleep(0.5)
                
            print(f"✓ ApolloBot watcher stopped (PID: {pid})")
            return True
            
        except ProcessLookupError:
            # Process already dead
            print("✓ ApolloBot watcher stopped")
            return True
        except OSError as e:
            print(f"✗ Failed to stop watcher: {e}")
            return False
    
    def show_daemon_log(self, lines: int = 20) -> None:
        """Show recent daemon log entries"""
        if not os.path.exists(self.log_file):
            print("📝 No daemon log file found")
            return
            
        try:
            with open(self.log_file, 'r') as f:
                log_lines = f.readlines()
                
            if not log_lines:
                print("📝 Daemon log is empty")
                return
                
            print(f"📝 Last {min(lines, len(log_lines))} lines from daemon log:")
            print("-" * 50)
            for line in log_lines[-lines:]:
                print(line.rstrip())
                
        except Exception as e:
            print(f"✗ Error reading log: {e}")
    
    def close(self) -> None:
        """Close connection"""
        if self.socket:
            self.socket.close()
        self.connected = False

def main():
    parser = argparse.ArgumentParser(
        description='ApolloBot - UAD Console Alt Monitor Automation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Commands:
  alt      Switch to alt monitors (S/PDIF output)
  main     Switch to main monitors (analog outputs)  
  toggle   Toggle between main and alt monitors
  status   Show current monitor and daemon status
  start    Start background watcher daemon
  start --launchd  Start the watcher through the installed macOS LaunchDaemon
  run      Run watcher in foreground and retry until UAD Console is available
  stop     Stop background watcher daemon
  stop --launchd  Stop the watcher through the installed macOS LaunchDaemon
  log      Show recent daemon log entries
        ''')
    parser.add_argument('action', choices=['alt', 'main', 'toggle', 'status', 'start', 'run', 'stop', 'log'],
                       help='Monitor action to perform')
    parser.add_argument('--host', default='127.0.0.1', help='UAD Console host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=4710, help='UAD Console port (default: 4710)')
    parser.add_argument(
        '--launchd',
        action='store_true',
        help='start or stop the installed macOS LaunchDaemon (use with start or stop)',
    )
    
    args = parser.parse_args()
    if args.launchd and args.action not in ('start', 'stop'):
        parser.error('--launchd can only be used with the start or stop action')

    bot = ApolloBot(args.host, args.port)

    # launchd owns this long-running process, so bypass the one-shot availability
    # check and the fork-based manual daemon path.
    if args.action == 'run':
        try:
            bot.run_foreground()
        finally:
            bot.close()
        return
    
    print("🤖 ApolloBot - UAD Console Monitor Automation")
    print("=" * 50)

    if args.action in ('start', 'stop') and args.launchd:
        try:
            success = bot.start_launchd() if args.action == 'start' else bot.stop_launchd()
        finally:
            bot.close()
        if not success:
            sys.exit(1)
        return

    # Status must still report launchd while the watcher is waiting for UAD Console.
    if args.action == 'status':
        try:
            bot.status()
        finally:
            bot.close()
        return
    
    # Check if UAD Console is running
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(1)
        result = test_socket.connect_ex((args.host, args.port))
        test_socket.close()
        
        if result != 0:
            print(f"✗ UAD Console not detected on {args.host}:{args.port}")
            print("  Please make sure UAD Console application is running")
            sys.exit(1)
    except:
        print("✗ Cannot check UAD Console status")
        sys.exit(1)
    
    try:
        if not bot.connect():
            sys.exit(1)
            
        # Perform requested action
        if args.action == 'alt':
            success = bot.switch_to_alt_monitors()
        elif args.action == 'main':
            success = bot.switch_to_main_monitors()
        elif args.action == 'toggle':
            success = bot.toggle_monitors()
        elif args.action == 'status':
            bot.status()
            success = True
        elif args.action == 'start':
            success = bot.start_daemon()
        elif args.action == 'stop':
            success = bot.stop_daemon()
        elif args.action == 'log':
            bot.show_daemon_log()
            success = True
        
        if not success and args.action not in ['status', 'log']:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n👋 ApolloBot interrupted")
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    finally:
        bot.close()

if __name__ == "__main__":
    main()
