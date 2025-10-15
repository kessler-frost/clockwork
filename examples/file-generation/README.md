# File Generation Example

Basic file creation example demonstrating Clockwork's simplest use case.

## What It Does

Creates a README file in a `scratch/` directory with user-provided content and validates it exists with the correct content.

## Quick Start

```bash
cd examples/file-generation
clockwork apply     # Deploy
clockwork assert    # Validate (2 assertions)
clockwork destroy   # Clean up
```

## What You'll Learn

- Creating files with specified content
- Setting file permissions (mode: 644)
- Using assertions to validate file existence and content

## Resources Created

- **FileResource**: `scratch/README.md` with Clockwork documentation

## Expected Output

After `clockwork apply`:
```bash
ls scratch/
# README.md

cat scratch/README.md
# Shows Clockwork documentation
```

## Assertions

1. `FileExistsAssert` - Verifies file was created
2. `FileContentMatchesAssert` - Checks file contains "Clockwork"

---

**Duration**: ~10s | **AI Used**: No | **Difficulty**: 🟢 Beginner
