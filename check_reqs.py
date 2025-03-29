#!/usr/bin/env python
import argparse
import sys
import os
from pkg_resources import (
    parse_requirements,
    get_distribution,
    DistributionNotFound,
    VersionConflict, # Keep this although less likely with new method
    Requirement, # To access specifier
)

# Check if setuptools (which provides pkg_resources) is available
try:
    import pkg_resources
except ImportError:
    print("Error: The 'setuptools' package is required but not found.", file=sys.stderr)
    print("Please install it: python -m pip install setuptools", file=sys.stderr)
    sys.exit(2) # Use exit code 2 for setup/dependency issues


def check_requirements(requirements_path):
    """
    Checks if packages specified in a requirements file are installed
    and meet version constraints based *only* on the listed requirement,
    not its full dependency tree at check time.

    Args:
        requirements_path (str): Path to the requirements file.

    Returns:
        int: Exit code (0 for success, 1 for unmet requirements).
             Raises FileNotFoundError/IOError if the file cannot be processed.
    """
    missing = []
    conflicts = []
    met_count = 0
    required_items = [] # Store Requirement objects

    print(f"--- Checking requirements from: {requirements_path} ---")

    try:
        with open(requirements_path, 'r') as f:
            try:
                # Parse requirements into Requirement objects
                required_items = list(parse_requirements(f))
            except Exception as parse_err:
                print(f"\nError parsing requirements file '{requirements_path}':", file=sys.stderr)
                print(f"  {parse_err}", file=sys.stderr)
                raise IOError(f"Failed to parse requirements file: {parse_err}")

        if not required_items:
            print("No requirements found in the file.")
            print("\n✅ Success! No requirements listed in the file.")
            return 0 # Success, nothing to check

        print(f"Found {len(required_items)} requirements to check.")

        for req in required_items:
            req_str = str(req) # Original string like 'numpy<2' or 'requests==1.2.3'
            try:
                # Get the currently installed distribution for this package name
                dist = get_distribution(req.project_name)

                # Check if the installed version meets the requirement's specifier
                # The 'in' operator for Requirement objects checks version compatibility
                if dist.version in req:
                    print(f"✅ Met:      {req_str} (found {dist.version})")
                    met_count += 1
                else:
                    # Version conflict: Package found, but version doesn't match specifier
                    print(f"❌ CONFLICT: {req_str} (found {dist.project_name} {dist.version})")
                    conflicts.append(f"{req_str} (found {dist.version})")

            except DistributionNotFound:
                # The package itself is not installed
                print(f"❌ MISSING:  {req.project_name} (needed for '{req_str}')")
                missing.append(req_str)
            except Exception as e:
                # Catch other potential errors during checking for this specific requirement
                print(f"❓ ERROR checking {req_str}: {type(e).__name__} - {e}")
                # Treat unexpected errors as conflicts for safety
                conflicts.append(f"{req_str} (Error: {e})")

    except FileNotFoundError:
        print(f"\nError: Requirements file not found at '{requirements_path}'", file=sys.stderr)
        raise # Re-raise to be caught by the main handler
    except Exception as e:
        # Catch errors during file opening/reading before parsing loop
        print(f"\nError reading requirements file '{requirements_path}': {e}", file=sys.stderr)
        raise # Re-raise to be caught by the main handler

    print("\n--- Check Summary ---")
    total_required = len(required_items)
    issues_found = len(missing) + len(conflicts)

    if not missing and not conflicts:
        print(f"\n🎉 Success! All {total_required} specified requirements are met.")
        return 0  # Success
    else:
        print(f"\n⚠️ Failure! {issues_found} out of {total_required} requirements were not met:")
        if missing:
            print(f"\n  Missing Packages ({len(missing)}):")
            for item in missing:
                print(f"    - {item}")
        if conflicts:
            print(f"\n  Version Conflicts ({len(conflicts)}):")
            for item in conflicts:
                print(f"    - {item}")
        return 1  # Failure due to unmet requirements

def main():
    parser = argparse.ArgumentParser(
        description="Check if requirements from a file are met in the current Python environment.",
        epilog="Exits with code 0 if all requirements met, 1 if any are missing/conflicting, 2 if the file is not found or cannot be read/parsed."
    )
    parser.add_argument(
        "requirements_file",
        help="Path to the requirements.txt file to check."
    )
    args = parser.parse_args()

    try:
        # Basic file existence check
        if not os.path.exists(args.requirements_file):
            raise FileNotFoundError(f"File not found: {args.requirements_file}")
        if not os.path.isfile(args.requirements_file):
            raise IsADirectoryError(f"Path is a directory, not a file: {args.requirements_file}")

        exit_code = check_requirements(args.requirements_file)
        sys.exit(exit_code)

    except (FileNotFoundError, IsADirectoryError, IOError) as e:
        # Catch errors related to file access or parsing explicitly
        print(f"\nError accessing, reading, or parsing file: {e}", file=sys.stderr)
        sys.exit(2) # Exit code for file not found or read/parse errors
    except Exception as e:
        # Catch any unexpected errors during the process
        print(f"\nAn unexpected error occurred: {type(e).__name__} - {e}", file=sys.stderr)
        # You might want to print traceback here for debugging
        # import traceback
        # traceback.print_exc()
        sys.exit(2) # Use the general file/setup error code

if __name__ == "__main__":
    main()