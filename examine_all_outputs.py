#!/usr/bin/env python3
"""
Examine all UAD outputs to find mirror properties

Focus on finding outputs with mirror-related properties like:
- MirrorsToDigital
- DigitalMirrorAvailable
- OutputDestination
"""

import socket
import json
import time
import sys

class AllOutputsExaminer:
    def __init__(self, host='127.0.0.1', port=4710):
        self.host = host
        self.port = port
        self.device_id = "0"

        # Test wider range of output IDs
        self.output_ids = list(range(0, 50))  # Test outputs 0-49

    def send_tcp_command(self, command):
        """Send TCP command and get response"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((self.host, self.port))

            message = f"{command}\x00"
            sock.send(message.encode('utf-8'))

            response = ""
            start_time = time.time()

            while time.time() - start_time < 1.5:
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
                    return json.loads(response)
                except json.JSONDecodeError:
                    return {"raw": response}
            return None

        except Exception as e:
            return None

    def get_output_properties(self, output_id):
        """Get properties for a single output"""
        result = self.send_tcp_command(f"get /devices/{self.device_id}/outputs/{output_id}")

        if result and "error" not in result:
            data = result.get('data', {})
            if 'properties' in data and isinstance(data['properties'], dict):
                return {
                    'exists': True,
                    'properties': list(data['properties'].keys()),
                    'name': data.get('name', f'Output {output_id}'),
                    'full_data': data
                }

        return {'exists': False, 'properties': [], 'name': 'Not found', 'full_data': None}

    def examine_all_outputs(self):
        """Examine all outputs and report properties"""
        print("🔍 Examining all UAD outputs for mirror properties...")
        print("="*80)

        # Test connection
        test_result = self.send_tcp_command(f"get /devices/{self.device_id}/AltMonSelection")
        if not test_result:
            print("❌ Cannot connect to UAD Console!")
            return False
        print("✅ Connected to UAD Console\n")

        working_outputs = []
        mirror_outputs = []

        print("📊 SCANNING ALL OUTPUTS...")
        print("-" * 60)

        for output_id in self.output_ids:
            if output_id % 10 == 0:
                print(f"Scanning outputs {output_id}-{output_id+9}...")

            info = self.get_output_properties(output_id)

            if info['exists']:
                working_outputs.append((output_id, info))

                # Check for mirror-related properties
                mirror_props = [p for p in info['properties'] if any(keyword in p.lower()
                               for keyword in ['mirror', 'digital', 'destination', 'route'])]

                if mirror_props:
                    mirror_outputs.append((output_id, info, mirror_props))

        # Report results
        print(f"\n📋 RESULTS SUMMARY:")
        print("="*60)
        print(f"✅ Working outputs found: {len(working_outputs)}")
        print(f"🪞 Outputs with mirror properties: {len(mirror_outputs)}")

        # Show all working outputs with properties
        print(f"\n📊 ALL WORKING OUTPUTS:")
        print("="*80)

        for output_id, info in working_outputs:
            print(f"\nOutput {output_id}: {info['name']}")
            print(f"  Properties ({len(info['properties'])}): {info['properties']}")

            # Highlight mirror-related properties
            mirror_props = [p for p in info['properties'] if any(keyword in p.lower()
                           for keyword in ['mirror', 'digital', 'destination', 'route', 'cue'])]
            if mirror_props:
                print(f"  🪞 MIRROR PROPS: {mirror_props}")

        # Detailed analysis of mirror outputs
        if mirror_outputs:
            print(f"\n🎯 DETAILED MIRROR OUTPUT ANALYSIS:")
            print("="*80)

            for output_id, info, mirror_props in mirror_outputs:
                print(f"\n🪞 OUTPUT {output_id}: {info['name']}")
                print("-" * 50)
                print(f"Mirror Properties: {mirror_props}")
                print(f"All Properties: {info['properties']}")
                print(f"\nFull Data:")
                print(json.dumps(info['full_data'], indent=2))
                print("-" * 50)

        # Focus on specific properties we found
        print(f"\n🔍 LOOKING FOR KEY MIRROR PROPERTIES:")
        print("="*60)

        key_properties = ['MirrorsToDigital', 'DigitalMirrorAvailable', 'OutputDestination']

        for prop in key_properties:
            print(f"\n🔑 Outputs with '{prop}':")
            found_any = False
            for output_id, info in working_outputs:
                if prop in info['properties']:
                    print(f"  Output {output_id}: {info['name']}")
                    found_any = True
            if not found_any:
                print(f"  None found")

        # Generate test commands for mirror properties
        print(f"\n🧪 SUGGESTED TEST COMMANDS:")
        print("="*60)

        for output_id, info, mirror_props in mirror_outputs:
            print(f"\nFor Output {output_id} ({info['name']}):")
            for prop in mirror_props:
                print(f"  get /devices/{self.device_id}/outputs/{output_id}/{prop}")
                print(f"  set /devices/{self.device_id}/outputs/{output_id}/{prop}/value [value]")

        return True

def main():
    examiner = AllOutputsExaminer()
    success = examiner.examine_all_outputs()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
