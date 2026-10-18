#!/usr/bin/env python3
"""
Analyze UAD output data to identify cue outputs and mirror settings

This script examines the successful output commands to understand:
1. Which outputs are cue outputs
2. What their current mirror settings look like
3. How to identify the cue 1 mirror to S/PDIF setting
"""

import socket
import json
import time
import sys

class OutputAnalyzer:
    def __init__(self, host='127.0.0.1', port=4710):
        self.host = host
        self.port = port
        self.device_id = "0"

        # Known successful output IDs from discovery
        self.output_ids = [
            "0", "1", "2", "3", "4", "5",
            "16", "17", "18", "19", "20", "21", "22"
        ]

    def send_tcp_command(self, command):
        """Send TCP command and get response"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((self.host, self.port))

            message = f"{command}\x00"
            sock.send(message.encode('utf-8'))

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
                    return json.loads(response)
                except json.JSONDecodeError:
                    return {"raw": response}
            return None

        except Exception as e:
            return {"error": str(e)}

    def get_output_details(self, output_id):
        """Get detailed information about an output"""
        commands = [
            f"get /devices/{self.device_id}/outputs/{output_id}",
            f"get /devices/{self.device_id}/outputs/{output_id}/MixInSource",
            f"get /devices/{self.device_id}/outputs/{output_id}/properties"
        ]

        details = {}
        for cmd in commands:
            result = self.send_tcp_command(cmd)
            if result and "error" not in result:
                cmd_key = cmd.split('/')[-1] if '/' in cmd else 'base'
                details[cmd_key] = result

        return details

    def print_detailed_properties(self, output_id, details):
        """Print all detailed properties of an output"""
        print(f"\n{'='*20} OUTPUT {output_id} DETAILS {'='*20}")

        for cmd_key, data in details.items():
            print(f"\n📋 {cmd_key.upper()}:")
            print("-" * 40)
            if isinstance(data, dict):
                print(json.dumps(data, indent=2))
            else:
                print(str(data))

        print(f"{'='*60}")

    def extract_all_properties(self, output_id, details):
        """Extract all available properties from output details"""
        all_props = []

        # From base output data
        if output_id in details:
            base_data = details[output_id].get('data', {})
            if 'properties' in base_data and isinstance(base_data['properties'], dict):
                all_props.extend(base_data['properties'].keys())

        # From properties endpoint if available
        if 'properties' in details:
            props_data = details['properties'].get('data', {})
            if isinstance(props_data, dict):
                all_props.extend(props_data.keys())

        return list(set(all_props))  # Remove duplicates

    def analyze_output_type(self, output_id, details):
        """Analyze output details to determine type (analog, cue, spdif, etc.)"""
        analysis = {
            'output_id': output_id,
            'type': 'unknown',
            'name': 'Unknown',
            'mix_source': 'unknown',
            'is_cue': False,
            'is_spdif': False,
            'properties': []
        }

        # Check MixInSource
        if 'MixInSource' in details:
            mix_data = details['MixInSource'].get('data', {})
            if 'value' in mix_data:
                analysis['mix_source'] = mix_data['value']

        # Check base output info
        if output_id in details:
            base_data = details[output_id].get('data', {})

            # Look for name or label
            if 'name' in base_data:
                analysis['name'] = base_data['name']
            elif 'label' in base_data:
                analysis['name'] = base_data['label']

            # Look for properties that indicate output type
            if 'properties' in base_data:
                props = base_data['properties']
                analysis['properties'] = list(props.keys()) if isinstance(props, dict) else []

                # Check for cue indicators
                prop_str = str(props).lower()
                if any(word in prop_str for word in ['cue', 'headphone', 'hp']):
                    analysis['is_cue'] = True
                    analysis['type'] = 'cue'

                # Check for S/PDIF indicators
                if any(word in prop_str for word in ['spdif', 's/pdif', 'coax', 'digital']):
                    analysis['is_spdif'] = True
                    analysis['type'] = 'spdif'

        # Infer type from output ID patterns (common Apollo conventions)
        output_num = int(output_id)
        if output_num <= 8:
            analysis['type'] = 'analog' if analysis['type'] == 'unknown' else analysis['type']
        elif output_num >= 16:
            analysis['type'] = 'digital_or_cue' if analysis['type'] == 'unknown' else analysis['type']

        return analysis

    def find_cue_outputs(self):
        """Find and analyze all cue outputs"""
        print("🎵 Analyzing outputs to identify cue outputs...")
        print("="*60)

        cue_outputs = []
        all_outputs = []

        for output_id in self.output_ids:
            print(f"\n📊 Analyzing output {output_id}...")

            details = self.get_output_details(output_id)
            analysis = self.analyze_output_type(output_id, details)
            all_outputs.append(analysis)

            # Print detailed properties for this output
            self.print_detailed_properties(output_id, details)

            # Extract all available properties
            all_props = self.extract_all_properties(output_id, details)
            analysis['all_properties'] = all_props

            print(f"\n📊 SUMMARY FOR OUTPUT {output_id}:")
            print(f"  Type: {analysis['type']}")
            print(f"  Name: {analysis['name']}")
            print(f"  Mix Source: {analysis['mix_source']}")
            print(f"  All Properties ({len(all_props)}): {', '.join(all_props)}")

            if analysis['is_cue']:
                cue_outputs.append(analysis)
                print(f"  ✅ IDENTIFIED AS CUE OUTPUT")

        return cue_outputs, all_outputs

    def test_mirror_properties(self, output_ids):
        """Test various mirror-related properties on given outputs"""
        print(f"\n🪞 Testing mirror properties on outputs: {output_ids}")
        print("="*60)

        mirror_properties = [
            'Mirror', 'MirrorTo', 'MirrorTarget', 'MirrorSource', 'MirrorDest',
            'Route', 'RouteTarget', 'Destination', 'Target', 'Send', 'SendTo'
        ]

        found_properties = {}

        for output_id in output_ids:
            print(f"\n🔍 Testing output {output_id}:")
            output_results = {}

            for prop in mirror_properties:
                cmd = f"get /devices/{self.device_id}/outputs/{output_id}/{prop}"
                result = self.send_tcp_command(cmd)

                if result and "error" not in result and result.get('data'):
                    print(f"  ✅ {prop}: Found data")
                    output_results[prop] = result
                else:
                    print(f"  ❌ {prop}: No data")

                time.sleep(0.05)  # Small delay

            if output_results:
                found_properties[output_id] = output_results

        return found_properties

    def compare_with_spdif(self):
        """Compare patterns with known S/PDIF output (18)"""
        print(f"\n📡 Comparing with known S/PDIF output (18)...")
        print("="*40)

        spdif_details = self.get_output_details("18")
        spdif_analysis = self.analyze_output_type("18", spdif_details)

        print(f"S/PDIF Output 18:")
        print(f"  Type: {spdif_analysis['type']}")
        print(f"  Mix Source: {spdif_analysis['mix_source']}")
        print(f"  Properties: {spdif_analysis['properties'][:5]}...")

        return spdif_analysis

    def run_analysis(self):
        """Run complete output analysis"""
        print("🤖 ApolloBot Output Analysis")
        print("="*60)
        print("Analyzing outputs to find cue mirror settings...")

        # Test connection
        print("🔌 Testing connection...")
        test_result = self.send_tcp_command(f"get /devices/{self.device_id}/AltMonSelection")
        if not test_result or "error" in test_result:
            print("❌ Cannot connect to UAD Console!")
            return False
        print("✅ Connected")

        # Find cue outputs
        cue_outputs, all_outputs = self.find_cue_outputs()

        # Compare with S/PDIF
        spdif_info = self.compare_with_spdif()

        # Test mirror properties on likely cue outputs
        cue_ids = [c['output_id'] for c in cue_outputs]
        if not cue_ids:
            # If no obvious cues found, test outputs 16, 17 (common cue positions)
            cue_ids = ["16", "17"]
            print(f"\n⚠️  No obvious cue outputs found, testing common positions: {cue_ids}")

        mirror_results = self.test_mirror_properties(cue_ids)

        # Final analysis
        print(f"\n" + "="*60)
        print("📊 FINAL ANALYSIS")
        print("="*60)

        print(f"\n🎵 Cue Outputs Found: {len(cue_outputs)}")
        for cue in cue_outputs:
            print(f"  - Output {cue['output_id']}: {cue['name']} (mix: {cue['mix_source']})")

        print(f"\n🪞 Mirror Properties Found: {len(mirror_results)}")
        for output_id, props in mirror_results.items():
            print(f"  - Output {output_id}: {list(props.keys())}")

        print(f"\n💡 RECOMMENDATIONS:")
        print("-" * 40)

        if mirror_results:
            print("1. Found mirror properties! Check detailed output above")
            print("2. Try setting these properties to control mirror destination")
            for output_id, props in mirror_results.items():
                for prop in props.keys():
                    cmd = f"set /devices/{self.device_id}/outputs/{output_id}/{prop}/value"
                    print(f"   Try: {cmd} [value]")
        else:
            print("1. No mirror properties found with standard names")
            print("2. The cue mirror might be controlled differently")
            print("3. Try examining output properties in detail:")
            for cue in cue_outputs:
                print(f"   Output {cue['output_id']} properties: {cue['properties']}")

        print("4. Compare cue output patterns with S/PDIF output 18")
        print("5. Look for properties that change when toggling mirror in Console")

        return True

def main():
    analyzer = OutputAnalyzer()
    success = analyzer.run_analysis()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
