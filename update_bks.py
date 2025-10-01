#!/usr/bin/env python3
"""
Script to update .out files with new BKS values and recalculate metrics.
"""

import re
import os
from pathlib import Path

# Parse BKS values from bks_instances.txt
def parse_bks_file(bks_file_path):
    bks_dict = {}
    with open(bks_file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Format: MDG-a_21_n2000_m200.txt 114271
            match = re.search(r'(MDG-[abc]_\d+_n\d+_m\d+)\.txt\s+(\d+)', line)
            if match:
                instance_name = match.group(1)
                bks_value = float(match.group(2))
                bks_dict[instance_name] = bks_value
    return bks_dict

# Update CPLEX format file
def update_cplex_file(file_path, bks_dict, content, instance_name, new_bks):
    # Extract heuristic solution
    heuristic_match = re.search(r'HEURISTIC_SOLUTION\s*:\s*(\d+)', content)
    if not heuristic_match:
        print(f"  Warning: Could not find HEURISTIC_SOLUTION in {file_path}")
        return False

    heuristic_solution = float(heuristic_match.group(1))

    # Calculate new heuristic gap
    new_heuristic_gap = ((heuristic_solution - new_bks) / new_bks) * 100 if new_bks > 0 else 0

    # Update HEURISTIC GAP line
    content = re.sub(r'HEURISTIC GAP \(%\)\s*:\s*-?[\d.]+%',
                     f'HEURISTIC GAP (%)  : {new_heuristic_gap:.2f}%', content)

    # Write updated content back to file
    with open(file_path, 'w') as f:
        f.write(content)

    return True

# Update a single .out file
def update_out_file(file_path, bks_dict):
    with open(file_path, 'r') as f:
        content = f.read()

    # Find instance name in the file
    instance_match = re.search(r'instances/MDG-[abc]/(MDG-[abc]_\d+_n\d+_m\d+)\.txt', content)
    if not instance_match:
        # Try alternate format for instance name
        instance_match = re.search(r'INSTANCE_NAME\s*:\s*(MDG-[abc]_\d+_n\d+_m\d+)', content)
        if not instance_match:
            print(f"  Warning: Could not find instance name in {file_path}")
            return False

    instance_name = instance_match.group(1)

    if instance_name not in bks_dict:
        print(f"  Warning: No BKS value found for {instance_name}")
        return False

    new_bks = bks_dict[instance_name]

    # Check if this is a CPLEX format file
    if 'HEURISTIC_SOLUTION' in content:
        return update_cplex_file(file_path, bks_dict, content, instance_name, new_bks)

    # Extract best solution value (try both formats)
    best_solution_match = re.search(r'Best Solution (?:Benefit|Value):\s+([\d.]+)', content)
    if not best_solution_match:
        print(f"  Warning: Could not find Best Solution in {file_path}")
        return False

    best_solution = float(best_solution_match.group(1))

    # Extract average solution value
    avg_solution_match = re.search(r'Average Solution:\s+([\d.]+)', content)
    if not avg_solution_match:
        print(f"  Warning: Could not find Average Solution in {file_path}")
        return False

    avg_solution = float(avg_solution_match.group(1))

    # Calculate new metrics
    new_distance = new_bks - best_solution
    new_percentage_distance = (new_distance / new_bks) * 100
    new_avg_percentage_distance = ((new_bks - avg_solution) / new_bks) * 100

    # Extract all solution values for updating per-execution distances
    exec_pattern = r'Exec (\d+): Solution=([\d.]+), Time=([\d.]+) sec, Minerações=(\d+), Dist BKS=([\d.]+)%'
    exec_matches = list(re.finditer(exec_pattern, content))

    # Update BKS value
    old_bks_match = re.search(r'BKS:\s+([\d.]+)', content)
    if old_bks_match:
        old_bks = float(old_bks_match.group(1))
        content = re.sub(r'BKS:\s+[\d.]+', f'BKS: {new_bks:.6f}', content)

    # Update Distance to BKS
    content = re.sub(r'Distance to BKS:\s+[\d.]+', f'Distance to BKS: {new_distance:.6f}', content)

    # Update Percentage Distance to BKS
    content = re.sub(r'Percentage Distance to BKS:\s+[\d.]+%', f'Percentage Distance to BKS: {new_percentage_distance:.2f}%', content)

    # Update Average Percentage Distance to BKS
    content = re.sub(r'Average Percentage Distance to BKS:\s+[\d.]+%', f'Average Percentage Distance to BKS: {new_avg_percentage_distance:.2f}%', content)

    # Update per-execution distances
    for match in exec_matches:
        exec_num = match.group(1)
        exec_solution = float(match.group(2))
        exec_time = match.group(3)
        exec_mineracoes = match.group(4)

        # Calculate new distance for this execution
        exec_new_distance = ((new_bks - exec_solution) / new_bks) * 100

        # Find and replace this specific execution line
        old_line = match.group(0)
        new_line = f'Exec {exec_num}: Solution={exec_solution:.6f}, Time={exec_time} sec, Minerações={exec_mineracoes}, Dist BKS={exec_new_distance:.2f}%'
        content = content.replace(old_line, new_line)

    # Write updated content back to file
    with open(file_path, 'w') as f:
        f.write(content)

    return True

# Main function
def main():
    script_dir = Path(__file__).parent
    bks_file = script_dir / 'bks_instances.txt'

    print("Parsing BKS values...")
    bks_dict = parse_bks_file(bks_file)
    print(f"Found {len(bks_dict)} BKS values")

    print("\nFinding all .out files...")
    out_files = list(script_dir.rglob('*.out'))
    print(f"Found {len(out_files)} .out files")

    print("\nUpdating files...")
    updated_count = 0
    for out_file in out_files:
        try:
            if update_out_file(out_file, bks_dict):
                updated_count += 1
                print(f"  ✓ Updated: {out_file.relative_to(script_dir)}")
            else:
                print(f"  ✗ Skipped: {out_file.relative_to(script_dir)}")
        except Exception as e:
            print(f"  ✗ Error processing {out_file.relative_to(script_dir)}: {e}")

    print(f"\n✓ Successfully updated {updated_count}/{len(out_files)} files")

if __name__ == '__main__':
    main()
