# Contributing to GeminiSDK

Thank you for your interest in contributing to GeminiSDK! This document provides guidelines for contributing to any of the SDK implementations.

## Development Setup

### Prerequisites

- **Python SDK**: Python 3.10+
- **TypeScript SDK**: Node.js 18+, npm
- **Rust SDK**: Rust 1.70+ (via rustup)
- **Go SDK**: Go 1.21+
- **C++ SDK**: CMake 3.14+, C++17 compiler, libcurl

### Getting Started

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/geminicli-sdk.git
   cd geminicli-sdk
   ```

2. Install Gemini CLI and authenticate:
   ```bash
   npm install -g @google/gemini-cli
   gemini auth login
   ```

3. Choose an SDK to work on and follow its specific setup.

## SDK-Specific Development

### Python SDK

```bash
cd src/python
pip install -e ".[dev]"
pytest tests/
ruff check geminisdk/
mypy geminisdk/
```

### TypeScript SDK

```bash
cd src/typescript
npm install
npm run typecheck
npm run build
npm test
```

### Rust SDK

```bash
cd src/rust
cargo build
cargo test
cargo clippy
cargo fmt --check
```

### Go SDK

```bash
cd src/go
go build ./...
go test ./...
go vet ./...
```

### C++ SDK

```bash
cd src/cpp
mkdir build && cd build
cmake ..
cmake --build .
```

## Versioning

We maintain a single version across all SDKs. The version is stored in the root `VERSION` file.

### Version Sync

After changes, sync the version across all SDKs:

```bash
python scripts/sync_version.py
```

### Bumping Versions

```bash
# Bump patch (0.1.0 -> 0.1.1)
python scripts/sync_version.py --bump patch

# Bump minor (0.1.0 -> 0.2.0)
python scripts/sync_version.py --bump minor

# Bump major (0.1.0 -> 1.0.0)
python scripts/sync_version.py --bump major

# Set specific version
python scripts/sync_version.py --set 2.0.0
```

## Pull Request Process

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes
3. Ensure all tests pass for affected SDKs
4. Run linters and formatters
5. Commit with a descriptive message
6. Push and create a Pull Request

## Code Style

### Python
- Follow PEP 8
- Use type hints
- Run `ruff` for linting

### TypeScript
- Follow ESLint rules
- Use TypeScript strict mode
- Run `npm run lint`

### Rust
- Follow Rust conventions
- Run `cargo fmt` and `cargo clippy`

### Go
- Follow Go conventions
- Run `go fmt` and `go vet`

### C++
- Follow modern C++17 style
- Use header guards with `#pragma once`

## Adding New Features

When adding a feature that should exist across all SDKs:

1. Implement in one SDK first (preferably Python as reference)
2. Document the API design
3. Implement in remaining SDKs with consistent API
4. Add tests for all implementations
5. Update READMEs

## Releasing

Releases are automated via GitHub Actions:

1. Bump version: `python scripts/sync_version.py --bump <type>`
2. Commit and push
3. Create a tag: `git tag v<version>`
4. Push the tag: `git push origin v<version>`
5. GitHub Actions will:
   - Run CI tests
   - Publish Python to PyPI
   - Publish TypeScript to npm
   - Publish Rust to crates.io
   - Tag Go module
   - Create GitHub Release

## Questions?

Open an issue or discussion on GitHub!
