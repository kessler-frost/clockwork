# Clockwork Showcase

**One comprehensive example demonstrating all major Clockwork features.**

Learn everything Clockwork can do in 5 minutes.

## What This Demonstrates

### 1. File Resources
- **Manual creation**: You provide content directly
- **AI generation**: AI creates content from description

### 2. Git Repositories
- **AI discovery**: AI finds repo URL from description

### 3. Docker Containers
- **Container deployment** with health checks
- **Comprehensive assertions** (running, port accessible, HTTP health)

### 4. Tool Integration (Optional)
- **Web search**: DuckDuckGo integration
- **Custom tools**: Your Python functions as AI tools

## Quick Start

```bash
cd examples/showcase

# Deploy all resources
clockwork apply

# Validate with assertions
clockwork assert

# Clean up
clockwork destroy
```

## What Gets Created

After `clockwork apply`:

```
scratch/
├── README.md              # Manual file
├── config.yaml            # AI-generated file
└── repos/
    └── fastapi/           # Cloned git repo

Docker:
└── nginx-showcase         # Running container on port 8080
```

## Prerequisites

**Required:**
- Docker installed and running

**Optional (for tool examples):**
- API key in `.env` file (for web search)

## Example Breakdown

### Files: Manual vs AI

```python
# You provide everything
readme_manual = FileResource(
    name="README.md",
    content="# My Content",  # You write this
    directory="scratch"
)

# AI generates content
config_ai = FileResource(
    name="config.yaml",
    description="Database config: host localhost, port 5432",
    directory="scratch"
    # AI writes the content!
)
```

### Git Repositories

```python
# Just describe it - AI finds the repo
fastapi_repo = GitRepoResource(
    description="FastAPI Python web framework repository",
    branch="master"  # Specify branch (FastAPI uses master, not main)
    # AI fills in: repo_url, name
)
```

### Docker with Assertions

```python
nginx_container = DockerResource(
    name="nginx-showcase",
    image="nginx:alpine",
    ports=["8080:80"],
    assertions=[
        ContainerRunningAssert(),              # Is it running?
        PortAccessibleAssert(port=8080),       # Can we connect?
        HealthcheckAssert(url="http://..."),   # HTTP 200 OK?
    ]
)
```

## Testing Assertions

```bash
# Run all assertions
clockwork assert

# Expected output:
# ✓ FileExistsAssert: scratch/README.md
# ✓ FileContentMatchesAssert: scratch/README.md (pattern: Clockwork)
# ✓ ContainerRunningAssert: nginx-showcase
# ✓ PortAccessibleAssert: localhost:8080
# ✓ HealthcheckAssert: http://localhost:8080
# ... (10 total assertions)
```

## Enabling Tool Examples

Uncomment the tool examples in `main.py` to try:

1. **Web Search Tool**:
```python
web_search_report = FileResource(
    description="Summary of latest AI infrastructure trends",
    tools=[duckduckgo_search_tool()]
)
```

2. **Custom Python Tool**:
```python
def get_current_time(format_type: str) -> str:
    """AI can call this function!"""
    return datetime.now().strftime('%Y-%m-%d')

report = FileResource(
    description="Report with current date",
    tools=[get_current_time]
)
```

## Configuration

Create `.env` file for API settings:

```bash
# Local (LM Studio)
CW_API_KEY=lm-studio
CW_MODEL=local-model
CW_BASE_URL=http://localhost:1234/v1

# Cloud (OpenRouter)
CW_API_KEY=your-key
CW_MODEL=meta-llama/llama-4-scout:free
CW_BASE_URL=https://openrouter.ai/api/v1
```

## Next Steps

After mastering this example:

1. **Real-world example**: See `examples/connected-services/` for:
   - Multi-service deployments
   - Resource dependencies
   - Deployment ordering
   - Connection context sharing

2. **Build your own**: Start with this example and modify for your needs

## Cleanup

```bash
# Remove everything
clockwork destroy
```

## Expected Duration

- **Apply**: ~30-60 seconds (depending on AI model)
- **Assert**: ~5-10 seconds
- **Destroy**: ~5 seconds

## Troubleshooting

**Docker container won't start:**
```bash
docker ps -a  # Check container status
docker logs nginx-showcase  # View logs
```

**AI generation fails:**
- Check `.env` has valid API key
- Verify model supports tool calls
- Try a different model

**Assertions fail:**
```bash
# Wait a bit for container to fully start
sleep 5 && clockwork assert

# Check specific ports
lsof -i :8080
```

---

**Duration**: ~1 min | **Resources**: 7 | **Assertions**: 10 | **Difficulty**: 🟢 Beginner
