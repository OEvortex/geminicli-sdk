#!/usr/bin/env python3
"""
Sync version across all SDK packages from the root VERSION file.

Usage:
    python scripts/sync_version.py
    python scripts/sync_version.py --bump patch  # 0.1.0 -> 0.1.1
    python scripts/sync_version.py --bump minor  # 0.1.0 -> 0.2.0
    python scripts/sync_version.py --bump major  # 0.1.0 -> 1.0.0
    python scripts/sync_version.py --set 1.2.3   # Set specific version
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
VERSION_FILE = ROOT / "VERSION"


def read_version() -> str:
    """Read the current version from VERSION file."""
    return VERSION_FILE.read_text().strip()


def write_version(version: str) -> None:
    """Write version to VERSION file."""
    VERSION_FILE.write_text(version + "\n")


def bump_version(current: str, bump_type: str) -> str:
    """Bump version based on type."""
    parts = current.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {current}")
    
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")
    
    return f"{major}.{minor}.{patch}"


def update_python(version: str) -> None:
    """Update Python SDK version."""
    # Update pyproject.toml
    pyproject = ROOT / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        content = re.sub(
            r'^version\s*=\s*"[^"]+"',
            f'version = "{version}"',
            content,
            flags=re.MULTILINE
        )
        pyproject.write_text(content)
        print(f"  Updated pyproject.toml")
    
    # Update __init__.py
    init_file = ROOT / "src" / "python" / "geminisdk" / "__init__.py"
    if init_file.exists():
        content = init_file.read_text()
        content = re.sub(
            r'^__version__\s*=\s*"[^"]+"',
            f'__version__ = "{version}"',
            content,
            flags=re.MULTILINE
        )
        # Also handle VERSION = pattern
        content = re.sub(
            r'^VERSION\s*=\s*"[^"]+"',
            f'VERSION = "{version}"',
            content,
            flags=re.MULTILINE
        )
        init_file.write_text(content)
        print(f"  Updated Python __init__.py")


def update_typescript(version: str) -> None:
    """Update TypeScript SDK version."""
    package_json = ROOT / "src" / "typescript" / "package.json"
    if package_json.exists():
        data = json.loads(package_json.read_text())
        data["version"] = version
        package_json.write_text(json.dumps(data, indent=2) + "\n")
        print(f"  Updated TypeScript package.json")
    
    # Update index.ts VERSION constant
    index_ts = ROOT / "src" / "typescript" / "src" / "index.ts"
    if index_ts.exists():
        content = index_ts.read_text()
        content = re.sub(
            r"^export const VERSION\s*=\s*'[^']+';",
            f"export const VERSION = '{version}';",
            content,
            flags=re.MULTILINE
        )
        index_ts.write_text(content)
        print(f"  Updated TypeScript index.ts")


def update_rust(version: str) -> None:
    """Update Rust SDK version."""
    cargo_toml = ROOT / "src" / "rust" / "Cargo.toml"
    if cargo_toml.exists():
        content = cargo_toml.read_text()
        # Update package version (first occurrence)
        content = re.sub(
            r'^version\s*=\s*"[^"]+"',
            f'version = "{version}"',
            content,
            count=1,
            flags=re.MULTILINE
        )
        cargo_toml.write_text(content)
        print(f"  Updated Rust Cargo.toml")


def update_go(version: str) -> None:
    """Update Go SDK version."""
    geminisdk_go = ROOT / "src" / "go" / "geminisdk.go"
    if geminisdk_go.exists():
        content = geminisdk_go.read_text()
        content = re.sub(
            r'^const Version\s*=\s*"[^"]+"',
            f'const Version = "{version}"',
            content,
            flags=re.MULTILINE
        )
        geminisdk_go.write_text(content)
        print(f"  Updated Go geminisdk.go")


def update_cpp(version: str) -> None:
    """Update C++ SDK version."""
    # Update CMakeLists.txt
    cmake = ROOT / "src" / "cpp" / "CMakeLists.txt"
    if cmake.exists():
        content = cmake.read_text()
        content = re.sub(
            r'project\(geminisdk VERSION [^ ]+',
            f'project(geminisdk VERSION {version}',
            content
        )
        cmake.write_text(content)
        print(f"  Updated C++ CMakeLists.txt")
    
    # Update types.hpp version constant
    types_hpp = ROOT / "src" / "cpp" / "include" / "geminisdk" / "types.hpp"
    if types_hpp.exists():
        content = types_hpp.read_text()
        content = re.sub(
            r'constexpr const char\* VERSION\s*=\s*"[^"]+";',
            f'constexpr const char* VERSION = "{version}";',
            content
        )
        types_hpp.write_text(content)
        print(f"  Updated C++ types.hpp")


def sync_all(version: str) -> None:
    """Sync version across all SDKs."""
    print(f"Syncing version {version} across all SDKs...")
    update_python(version)
    update_typescript(version)
    update_rust(version)
    update_go(version)
    update_cpp(version)
    print(f"\n✅ Version {version} synced to all SDKs!")


def main():
    parser = argparse.ArgumentParser(description="Sync SDK versions")
    parser.add_argument(
        "--bump",
        choices=["major", "minor", "patch"],
        help="Bump version (major/minor/patch)"
    )
    parser.add_argument(
        "--set",
        type=str,
        help="Set specific version (e.g., 1.2.3)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check current version without changing"
    )
    
    args = parser.parse_args()
    
    current = read_version()
    
    if args.check:
        print(f"Current version: {current}")
        return 0
    
    if args.set:
        # Validate version format
        if not re.match(r'^\d+\.\d+\.\d+$', args.set):
            print(f"Invalid version format: {args.set}")
            return 1
        new_version = args.set
    elif args.bump:
        new_version = bump_version(current, args.bump)
    else:
        # Just sync current version
        new_version = current
    
    if new_version != current:
        print(f"Bumping version: {current} -> {new_version}")
        write_version(new_version)
    
    sync_all(new_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
