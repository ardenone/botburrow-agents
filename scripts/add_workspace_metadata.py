#!/usr/bin/env python3
"""
Add workspace metadata to all open beads in the JSONL file.

This script:
1. Reads .beads/issues.jsonl
2. Adds 'workspace' field to all open beads that don't have it
3. Preserves all other fields and formatting
4. Creates a backup before modifying
"""

import json
import shutil
from pathlib import Path

def add_workspace_metadata():
    """Add workspace metadata to all open beads."""

    workspace = "/home/coder/botburrow-agents"
    jsonl_file = Path(".beads/issues.jsonl")
    backup_file = Path(".beads/issues.jsonl.backup")

    if not jsonl_file.exists():
        print(f"❌ Error: {jsonl_file} not found")
        return False

    # Create backup
    shutil.copy2(jsonl_file, backup_file)
    print(f"✅ Backup created: {backup_file}")

    # Read all beads
    beads = []
    with open(jsonl_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                beads.append(json.loads(line))

    print(f"📊 Total beads: {len(beads)}")

    # Update open beads without workspace
    updated_count = 0
    open_count = 0

    for bead in beads:
        if bead.get('status') == 'open':
            open_count += 1
            if not bead.get('workspace'):
                bead['workspace'] = workspace
                updated_count += 1

    print(f"📊 Open beads: {open_count}")
    print(f"📝 Updated beads: {updated_count}")

    # Write back to file
    with open(jsonl_file, 'w') as f:
        for bead in beads:
            f.write(json.dumps(bead) + '\n')

    print(f"✅ Updated {jsonl_file}")

    # Verify
    print("\n🔍 Verification:")
    with open(jsonl_file, 'r') as f:
        for line in f:
            bead = json.loads(line.strip())
            if bead.get('status') == 'open':
                workspace_val = bead.get('workspace', 'NONE')
                print(f"  {bead['id']} | workspace: {workspace_val}")

    return True

if __name__ == "__main__":
    import os
    os.chdir('/home/coder/botburrow-agents')
    add_workspace_metadata()
