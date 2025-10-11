# Development Environment Example

A comprehensive example demonstrating intelligent orchestration of all Clockwork resource types to create a complete, reproducible Mac development environment.

## What This Example Creates

This example sets up a **complete development environment** with:

### 1. Development Tools (Homebrew)
- `jq` - JSON processor
- `git` - Version control
- `tree` - Directory visualizer

### 2. Directory Structure
```
scratch/devenv/
├── src/           # Source code (755)
│   ├── fastapi/   # FastAPI repository
│   └── vue/       # Vue.js repository
├── data/          # Data storage (700 - restricted)
├── .env           # Environment variables
├── docker-compose.yml  # Docker services config
├── requirements.txt    # Python dependencies
├── Makefile       # Development tasks
└── README.md      # Setup instructions
```

### 3. Git Repositories
- **FastAPI** - Python web framework (`scratch/devenv/src/fastapi`)
- **Vue.js** - Frontend framework (`scratch/devenv/src/vue`)

### 4. Configuration Files (AI-Generated)
- `.env` - Environment variables (AI-generated)
- `docker-compose.yml` - Docker services (AI-generated)
- `requirements.txt` - Python dependencies (AI-generated)
- `Makefile` - Development tasks (AI-generated)
- `README.md` - Setup guide (AI-generated)

### 5. Apple Container Services
- **PostgreSQL 15** - Database on port 5432
- **Redis 7** - Cache on port 6379
- **Nginx** - Reverse proxy on port 8080

## Prerequisites

- **macOS** (this example is Mac-specific)
- **Homebrew** installed
- **Docker Desktop for Mac** installed and running
- **API key** configured in `.env` file (for cloud AI models)

## Usage

### 1. Set Up API Key

Create a `.env` file in the project root:
```bash
cd /Users/sankalp/dev/clockwork
echo "CW_API_KEY=your-api-key-here" > .env
```

### 2. Deploy the Environment

```bash
cd examples/dev-environment
uv run clockwork apply
```

This will:
- ✅ Install Homebrew packages
- ✅ Create directory structure
- ✅ Clone Git repositories (FastAPI, Vue.js)
- ✅ Generate configuration files
- ✅ Start Apple Container services

**Note**: The initial run may take 5-10 minutes as it:
- Clones large repositories (~100MB for FastAPI + Vue.js)
- Pulls Docker images (~200MB total)
- Generates multiple configuration files via AI

### 3. Validate the Environment

```bash
uv run clockwork assert
```

This verifies:
- ✅ All directories exist with correct permissions
- ✅ All files exist with expected content
- ✅ Apple Containers are running
- ✅ Ports are accessible (5432, 6379, 8080)
- ✅ Nginx responds to HTTP requests

### 4. Check What Was Created

```bash
# View directory structure
tree scratch/devenv -L 2

# Check Apple Container services
container ls

# Verify services
curl http://localhost:8080  # Nginx
nc -zv localhost 5432       # PostgreSQL
nc -zv localhost 6379       # Redis
```

### 5. Explore Generated Files

```bash
# View environment variables
cat scratch/devenv/.env

# Check Docker Compose config
cat scratch/devenv/docker-compose.yml

# Read the AI-generated README
cat scratch/devenv/README.md

# View Python requirements
cat scratch/devenv/requirements.txt

# Check available Make targets
cat scratch/devenv/Makefile
```

## Cleanup / Destroy

### Complete Cleanup (Recommended)

To remove **everything** created by this example:

```bash
cd examples/dev-environment
uv run clockwork destroy
```

This will:
- ✅ Stop and remove Apple Containers
- ✅ Remove container volumes (postgres_data, redis_data)
- ✅ Remove cloned Git repositories
- ✅ Delete all generated files
- ✅ Remove directory structure

**Note**: Homebrew packages are **NOT** uninstalled during destroy (by design). If you want to remove them:
```bash
brew uninstall jq git tree
```

### Manual Cleanup (If Needed)

If `clockwork destroy` fails or you need to clean up manually:

```bash
# Stop and remove Apple Containers
container stop dev-postgres dev-redis dev-nginx
container rm dev-postgres dev-redis dev-nginx

# Remove container volumes
container volume rm postgres_data redis_data

# Remove directory
rm -rf scratch/devenv
```

## Troubleshooting

### Container Services Won't Start

**Issue**: `container: Error response from daemon: Conflict. The container name "/dev-postgres" is already in use.`

**Solution**:
```bash
container ls -a | grep -E "dev-postgres|dev-redis|dev-nginx"
container rm -f dev-postgres dev-redis dev-nginx
uv run clockwork apply
```

### Git Clone Fails

**Issue**: `fatal: unable to access 'https://github.com/...': Could not resolve host`

**Solution**: Check internet connection and retry:
```bash
# Test connectivity
curl -I https://github.com

# Retry deployment
uv run clockwork destroy
uv run clockwork apply
```

### Port Conflicts

**Issue**: `Bind for 0.0.0.0:5432 failed: port is already allocated`

**Solution**: Stop conflicting services:
```bash
# Check what's using the port
lsof -i :5432
lsof -i :6379
lsof -i :8080

# Stop conflicting services
brew services stop postgresql  # If PostgreSQL is running via Homebrew
```

## What This Demonstrates

This example showcases Clockwork's intelligent orchestration capabilities:

1. **Compose Multiple Resource Types** - Seamlessly orchestrates 6 different resource types
2. **AI Intelligence** - Generates configuration files based on descriptions
3. **Declarative Infrastructure** - Define desired state, Clockwork orchestrates the rest
4. **Idempotency** - Running `apply` multiple times is safe
5. **Complete Lifecycle Management** - Deploy, validate, and destroy with simple commands
6. **Type-Safe Assertions** - Validate everything is working correctly
7. **Mac-Native Tools** - Uses Homebrew, Docker Desktop, cron, and standard Unix utilities

## Resources Created

| Count | Resource Type | Examples |
|-------|--------------|----------|
| 1 | BrewPackageResource | dev-tools |
| 3 | DirectoryResource | project-root, src-dir, data-dir |
| 2 | GitRepoResource | fastapi-repo, vue-repo |
| 5 | FileResource | .env, docker-compose.yml, requirements.txt, Makefile, README.md |
| 3 | AppleContainerResource | postgres-db, redis-cache, nginx-proxy |
| **14** | **Total Resources** | **Complete development environment** |

## Next Steps

After deploying this environment:

1. **Explore the generated files** - See what AI created for you
2. **Customize the configuration** - Edit `scratch/devenv/.env` or other files
3. **Add your own resources** - Extend `main.py` with additional services
4. **Run tests** - Use the generated Makefile targets
5. **Build something** - Start developing with FastAPI or Vue.js

## Learn More

- [Clockwork Documentation](../../CLAUDE.md)
- [PyInfra Documentation](https://docs.pyinfra.com)
- [Other Examples](../)
