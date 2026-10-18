#!/usr/bin/env python3
"""
Systematic discovery script for cue 1 mirror settings in UAD TCP protocol

This script tests various command patterns to find the TCP commands
that control cue 1 "mirror to S/PDIF" settings.

Usage:
1. Make sure UAD Console is running
2. Manually set cue 1 to "mirror to S/PDIF" in Console (for reference)
3. Run this script to discover the commands
4. Check the results to identify the working commands

"""

import socket
import json
import time
import sys

class CueMirrorDiscovery:
    def __init__(self, host='127.0.0.1', port=4710):
        self.host = host
        self.port = port
        self.device_id = "0"  # Apollo 8 device ID

        # Store successful commands and their responses
        self.successful_commands = {}
        self.mirror_candidates = {}

    def send_tcp_command(self, command):
        """Send TCP command and get response"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((self.host, self.port))

            # Send command
            message = f"{command}\x00"
            sock.send(message.encode('utf-8'))

            # Read response
            response = ""
            start_time = time.time()

            while time.time() - start_time < 2:
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
                try:
                    data = json.loads(response)
                    return data
                except json.JSONDecodeError:
                    return {"raw": response}
            else:
                return None

        except Exception as e:
            return {"error": str(e)}

    def test_command_pattern(self, pattern_name, commands):
        """Test a group of related commands"""
        print(f"\n🔍 Testing {pattern_name}...")
        print("-" * 50)

        results = {}
        for cmd in commands:
            print(f"Testing: {cmd}")
            result = self.send_tcp_command(cmd)

            if result and "error" not in result:
                self.successful_commands[cmd] = result
                results[cmd] = result

                # Check if this looks like mirror-related data
                if self.looks_like_mirror_data(result):
                    self.mirror_candidates[cmd] = result
                    print(f"  ✅ SUCCESS - Potential mirror data found!")
                else:
                    print(f"  ✅ SUCCESS - Got response")
            else:
                print(f"  ❌ No response or error")

            time.sleep(0.1)  # Small delay between commands

        return results

    def looks_like_mirror_data(self, data):
        """Check if response data looks like it could be mirror settings"""
        if not isinstance(data, dict):
            return False

        # Convert to string for searching
        data_str = json.dumps(data).lower()

        # Look for mirror-related keywords
        mirror_keywords = [
            'mirror', 'spdif', 's/pdif', 'coax', 'digital',
            'route', 'destination', 'target', 'source'
        ]

        for keyword in mirror_keywords:
            if keyword in data_str:
                return True

        # Look for output routing patterns
        if 'value' in data and isinstance(data['value'], str):
            value = data['value'].lower()
            if any(word in value for word in ['spdif', 'coax', 'digital', 'cue']):
                return True

        return False

    def discover_cue_outputs(self):
        """Discover potential cue output IDs"""
        print("🎯 Step 1: Discovering cue output IDs...")

        # Test various output IDs that might be cue outputs
        # Apollo 8 typically has outputs 1-8 for analog, then digital outputs
        potential_cue_ids = [
            "16", "17", "19", "20", "21", "22",  # Common cue output IDs
            "0", "1", "2", "3", "4", "5",        # Sometimes cues are low numbers
        ]

        commands = []
        for output_id in potential_cue_ids:
            commands.extend([
                f"get /devices/{self.device_id}/outputs/{output_id}",
                f"get /devices/{self.device_id}/outputs/{output_id}/properties",
                f"get /devices/{self.device_id}/outputs/{output_id}/MixInSource",
            ])

        return self.test_command_pattern("Cue Output Discovery", commands)

    def test_mirror_patterns(self):
        """Test various mirror-related command patterns"""
        print("🪞 Step 2: Testing mirror-related patterns...")

        # Based on successful output IDs, test mirror patterns
        output_ids = ["16", "17", "18", "19", "20"]  # Include known S/PDIF (18) and likely cue IDs

        commands = []
        for output_id in output_ids:
            commands.extend([
                f"get /devices/{self.device_id}/outputs/{output_id}/Mirror",
                f"get /devices/{self.device_id}/outputs/{output_id}/MirrorTo",
                f"get /devices/{self.device_id}/outputs/{output_id}/MirrorTarget",
                f"get /devices/{self.device_id}/outputs/{output_id}/MirrorSource",
                f"get /devices/{self.device_id}/outputs/{output_id}/MirrorDest",
                f"get /devices/{self.device_id}/outputs/{output_id}/MirrorDestination",
                f"get /devices/{self.device_id}/outputs/{output_id}/Route",
                f"get /devices/{self.device_id}/outputs/{output_id}/RouteTarget",
                f"get /devices/{self.device_id}/outputs/{output_id}/Destination",
            ])

        return self.test_command_pattern("Mirror Patterns", commands)

    def test_cue_specific_patterns(self):
        """Test cue-specific command patterns"""
        print("🎵 Step 3: Testing cue-specific patterns...")

        commands = [
            # Direct cue paths
            f"get /devices/{self.device_id}/cues",
            f"get /devices/{self.device_id}/cues/0",
            f"get /devices/{self.device_id}/cues/1",
            f"get /devices/{self.device_id}/cue/0",
            f"get /devices/{self.device_id}/cue/1",

            # Cue mirror settings
            f"get /devices/{self.device_id}/cues/0/Mirror",
            f"get /devices/{self.device_id}/cues/0/MirrorTo",
            f"get /devices/{self.device_id}/cues/0/MirrorTarget",
            f"get /devices/{self.device_id}/cues/1/Mirror",
            f"get /devices/{self.device_id}/cues/1/MirrorTo",
            f"get /devices/{self.device_id}/cues/1/MirrorTarget",

            # Cue properties
            f"get /devices/{self.device_id}/cues/0/properties",
            f"get /devices/{self.device_id}/cues/1/properties",
        ]

        return self.test_command_pattern("Cue-Specific Patterns", commands)

    def test_device_level_patterns(self):
        """Test device-level patterns that might contain cue info"""
        print("🔧 Step 4: Testing device-level patterns...")

        commands = [
            f"get /devices/{self.device_id}",
            f"get /devices/{self.device_id}/properties",
            f"get /devices/{self.device_id}/routing",
            f"get /devices/{self.device_id}/mixer",
            f"get /devices/{self.device_id}/monitor",
            f"get /devices/{self.device_id}/outputs",
        ]

        return self.test_command_pattern("Device-Level Patterns", commands)

    def analyze_results(self):
        """Analyze all results and provide recommendations"""
        print("\n" + "="*60)
        print("📊 DETAILED ANALYSIS RESULTS")
        print("="*60)

        print(f"\n✅ Total successful commands: {len(self.successful_commands)}")
        print(f"🪞 Commands with potential mirror data: {len(self.mirror_candidates)}")

        # Show ALL successful command responses in detail
        print(f"\n📋 ALL SUCCESSFUL COMMANDS WITH FULL RESPONSES:")
        print("="*80)
        for cmd in sorted(self.successful_commands.keys()):
            print(f"\n🔍 COMMAND: {cmd}")
            print("-" * 60)
            data = self.successful_commands[cmd]
            print(json.dumps(data, indent=2))
            print("-" * 60)

        if self.mirror_candidates:
            print("\n🎯 TOP MIRROR CANDIDATES:")
            print("="*40)
            for cmd, data in self.mirror_candidates.items():
                print(f"\n⭐ MIRROR CANDIDATE: {cmd}")
                print("=" * 50)
                print(json.dumps(data, indent=2))
                print("=" * 50)

        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        print("="*40)
        if self.mirror_candidates:
            print("1. Focus on the mirror candidates above")
            print("2. Try 'set' commands with these paths")
            print("3. Test changing values and observe UAD Console")
        else:
            print("1. No obvious mirror candidates found")
            print("2. Try manually toggling cue 1 mirror in Console")
            print("3. Re-run this script to compare before/after")

        print("4. Check ApolloBot's current S/PDIF output ID (18) for comparison")
        print("5. Look for properties that contain routing or destination info")
        print("6. Run analyze_outputs.py for detailed property analysis")

    def run_discovery(self):
        """Run the complete discovery process"""
        print("🤖 ApolloBot Cue Mirror Discovery")
        print("="*60)
        print("Discovering TCP commands for cue 1 'mirror to S/PDIF' settings...")
        print()

        # Check connection first
        print("🔌 Testing UAD Console connection...")
        test_result = self.send_tcp_command(f"get /devices/{self.device_id}/AltMonSelection")
        if not test_result or "error" in test_result:
            print("❌ Cannot connect to UAD Console!")
            print("   Make sure UAD Console is running and try again.")
            return False
        else:
            print("✅ Connected to UAD Console")

        # Run discovery steps
        self.discover_cue_outputs()
        self.test_mirror_patterns()
        self.test_cue_specific_patterns()
        self.test_device_level_patterns()

        # Analyze and report
        self.analyze_results()

        return True

def main():
    print("Before running this script:")
    print("1. Make sure UAD Console is running")
    print("2. Manually set cue 1 to 'mirror to S/PDIF' in Console")
    print("3. This gives us a reference state to discover")
    print()

    input("Press Enter when ready to start discovery...")

    discovery = CueMirrorDiscovery()
    success = discovery.run_discovery()

    if success:
        print(f"\n🎯 Next steps:")
        print("1. Review the mirror candidates above")
        print("2. Test 'set' commands with promising paths")
        print("3. Integrate working commands into apollobot.py")

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
