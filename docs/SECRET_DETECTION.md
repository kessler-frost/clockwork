# Secret Detection

This repository uses automated secret detection to prevent accidental commit of sensitive information like API keys, passwords, and tokens.

## 🛡️ Pre-Commit Hook

The pre-commit hook automatically scans staged files for potential secrets before each commit. If secrets are detected, the commit will be blocked with detailed information about what was found.

### What happens during commit:
1. Hook scans all staged `.py`, `.json`, `.yaml`, `.yml`, `.env`, `.md`, `.sh`, `.js`, `.ts` files
2. Excludes build/cache directories (`.venv/`, `.clockwork/`, `.pytest_cache/`, `.git/`)
3. Blocks commit if new secrets are detected
4. Provides clear instructions for resolution

## 🔍 Manual Scanning

Use the provided script to manually scan for secrets:

```bash
# Scan for new secrets
./scripts/check-secrets.sh

# Update baseline with new false positives
./scripts/check-secrets.sh --update

# Check current status
./scripts/check-secrets.sh
```

## 📋 Managing False Positives

Some detections are false positives (like the word "SECRET" in enum values). These are managed in `.secrets.baseline`:

1. **Review detections:** `uv run detect-secrets audit .secrets.baseline`
2. **Mark as false positive:** Use the audit tool to mark secrets as verified/false positives
3. **Update baseline:** `./scripts/check-secrets.sh --update`

## 🚨 Current Baseline

The repository currently has these approved false positives:
- `clockwork/models.py:50` - Enum value `SECRET = "secret"` (not a real secret)

## ⚠️ If You Need to Commit Anyway

**Only use this if you're absolutely sure the detection is a false positive:**

```bash
git commit --no-verify -m "your message"
```

**Better approach:** Add the false positive to the baseline instead.

## 🔧 Tool Configuration

- **Tool:** [detect-secrets](https://github.com/Yelp/detect-secrets) v1.5.0
- **Installation:** Managed via `uv` as dev dependency
- **Baseline file:** `.secrets.baseline`
- **Excluded paths:** `.venv/`, `.clockwork/`, `.pytest_cache/`, `.git/`

## 🎯 Detected Secret Types

The tool detects:
- API keys (AWS, OpenAI, GitHub, etc.)
- Private keys and certificates  
- Database passwords and connection strings
- High entropy strings (Base64, Hex)
- Basic auth credentials
- JWT tokens
- And many more patterns

## 📚 Best Practices

1. **Never commit real secrets** - Use environment variables or secure vaults
2. **Review all detections** - Don't blindly add things to baseline
3. **Use `.env.example`** - Provide template files with dummy values
4. **Regular audits** - Periodically review the baseline with `detect-secrets audit`