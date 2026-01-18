#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Odoo Module Renamer
Renames ylhc_* modules to seisei_* modules

Developed by Seisei
"""

import os
import re
import shutil
from pathlib import Path

# Working directory
WORK_DIR = Path(__file__).parent

# Rename mappings
MODULE_RENAMES = {
    'ylhc_print_manager': 'seisei_print_manager',
    'ylhc_pos_printer': 'seisei_pos_printer',
    'ylhc_mutex_toggle': 'seisei_mutex_toggle',
}

# String replacements (order matters - more specific first)
STRING_REPLACEMENTS = [
    # Module technical names
    ('ylhc_print_manager', 'seisei_print_manager'),
    ('ylhc_pos_printer', 'seisei_pos_printer'),
    ('ylhc_mutex_toggle', 'seisei_mutex_toggle'),

    # Model names (ylhc.xxx -> seisei.xxx)
    ('ylhc.station', 'seisei.station'),
    ('ylhc.printer', 'seisei.printer'),
    ('ylhc.print.job', 'seisei.print.job'),
    ('ylhc.print.mapping', 'seisei.print.mapping'),

    # Channel names
    ('ylhc_service.', 'seisei_service.'),
    ('ylhc_service_message', 'seisei_service_message'),

    # XML IDs and references
    ('ylhc_', 'seisei_'),

    # Generic ylhc references (be careful with this)
    ('YLHC', 'Seisei'),
    ('Ylhc', 'Seisei'),
]

# Author info to add
NEW_AUTHOR = "Seisei"
NEW_WEBSITE = "https://github.com/seisei"


def replace_in_file(filepath: Path, replacements: list) -> bool:
    """Replace strings in a file"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        original = content
        for old, new in replacements:
            content = content.replace(old, new)

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"  Error processing {filepath}: {e}")
        return False


def update_manifest(filepath: Path):
    """Update __manifest__.py with new author info"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Update author
        content = re.sub(
            r"'author'\s*:\s*['\"][^'\"]*['\"]",
            f"'author': '{NEW_AUTHOR}'",
            content
        )

        # Update website if exists
        if "'website'" in content:
            content = re.sub(
                r"'website'\s*:\s*['\"][^'\"]*['\"]",
                f"'website': '{NEW_WEBSITE}'",
                content
            )

        # Update module name in description
        for old, new in MODULE_RENAMES.items():
            content = content.replace(old, new)

        # Apply string replacements
        for old, new in STRING_REPLACEMENTS:
            content = content.replace(old, new)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  Updated: {filepath.name}")
    except Exception as e:
        print(f"  Error updating manifest {filepath}: {e}")


def process_module(old_name: str, new_name: str):
    """Process a single module"""
    old_path = WORK_DIR / old_name
    new_path = WORK_DIR / new_name

    if not old_path.exists():
        print(f"Module not found: {old_name}")
        return False

    print(f"\n{'='*60}")
    print(f"Processing: {old_name} -> {new_name}")
    print('='*60)

    # Rename directory
    if new_path.exists():
        shutil.rmtree(new_path)
    shutil.move(str(old_path), str(new_path))
    print(f"  Renamed directory: {old_name} -> {new_name}")

    # Process all files
    file_count = 0
    for root, dirs, files in os.walk(new_path):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != '__pycache__']

        for filename in files:
            filepath = Path(root) / filename

            # Process based on file type
            if filename.endswith(('.py', '.xml', '.js', '.css', '.scss')):
                if replace_in_file(filepath, STRING_REPLACEMENTS):
                    file_count += 1
                    print(f"  Updated: {filepath.relative_to(new_path)}")

            # Special handling for manifest
            if filename == '__manifest__.py':
                update_manifest(filepath)

    print(f"  Total files updated: {file_count}")
    return True


def cleanup_pycache(path: Path):
    """Remove all __pycache__ directories"""
    for root, dirs, files in os.walk(path):
        for d in dirs:
            if d == '__pycache__':
                pycache_path = Path(root) / d
                shutil.rmtree(pycache_path)
                print(f"  Removed: {pycache_path.relative_to(path)}")


def main():
    print("="*60)
    print("  Odoo Module Renamer: ylhc -> seisei")
    print("  Developed by Seisei")
    print("="*60)

    # Process each module
    for old_name, new_name in MODULE_RENAMES.items():
        process_module(old_name, new_name)

    # Cleanup __pycache__
    print(f"\n{'='*60}")
    print("Cleaning up __pycache__ directories...")
    print('='*60)
    for new_name in MODULE_RENAMES.values():
        module_path = WORK_DIR / new_name
        if module_path.exists():
            cleanup_pycache(module_path)

    # Summary
    print(f"\n{'='*60}")
    print("  COMPLETED!")
    print('='*60)
    print("\nRenamed modules:")
    for old, new in MODULE_RENAMES.items():
        new_path = WORK_DIR / new
        if new_path.exists():
            print(f"  ✓ {new}")
        else:
            print(f"  ✗ {new} (failed)")

    print("\nNext steps:")
    print("  1. Copy modules to Odoo addons directory")
    print("  2. Update Odoo Apps list")
    print("  3. Uninstall old ylhc_* modules (if installed)")
    print("  4. Install new seisei_* modules")


if __name__ == "__main__":
    main()
