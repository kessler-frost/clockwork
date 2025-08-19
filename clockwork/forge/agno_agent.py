"""
Agno AI Agent Integration for Clockwork Compilation

This module provides AI-powered compilation of ActionList to ArtifactBundle
using the Agno framework with LM Studio integration.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from agno.agent import Agent, RunResponse
from agno.models.lmstudio import LMStudio

from ..models import ActionList, ArtifactBundle, Artifact, ExecutionStep


logger = logging.getLogger(__name__)


class AgentArtifact(BaseModel):
    """Pydantic model for AI agent artifact generation."""
    path: str = Field(..., description="Relative path for the artifact file (e.g., 'scripts/01_fetch_repo.sh')")
    mode: str = Field(..., description="File permissions in octal format (e.g., '0755' for executable, '0644' for data)")
    purpose: str = Field(..., description="The purpose/name of the action this artifact serves")
    lang: str = Field(..., description="Programming language (bash, python, deno, go, etc.)")
    content: str = Field(..., description="Complete executable content of the artifact with proper headers and error handling")


class AgentExecutionStep(BaseModel):
    """Pydantic model for AI agent execution step generation."""
    purpose: str = Field(..., description="The purpose/name that matches an artifact's purpose")
    run: Dict[str, Any] = Field(..., description="Execution command configuration with 'cmd' array")


class AgentArtifactBundle(BaseModel):
    """Pydantic model for AI agent complete artifact bundle generation."""
    version: str = Field(default="1", description="Bundle format version")
    artifacts: List[AgentArtifact] = Field(..., description="List of executable artifacts to generate")
    steps: List[AgentExecutionStep] = Field(..., description="List of execution steps in order")
    vars: Dict[str, Any] = Field(default_factory=dict, description="Environment variables and configuration values")


class AgnoCompilerError(Exception):
    """Exception raised during Agno AI compilation."""
    pass


class AgnoCompiler:
    """
    AI-powered compiler using Agno framework with LM Studio integration.
    
    This class uses a local LM Studio instance to generate executable artifacts
    from declarative ActionList specifications.
    """
    
    def __init__(
        self,
        model_id: str = "qwen/qwen3-4b-2507",
        lm_studio_url: str = "http://localhost:1234",
        timeout: int = 300
    ):
        """
        Initialize the Agno AI compiler.
        
        Args:
            model_id: Model identifier in LM Studio (default: qwen/qwen3-4b-2507)
            lm_studio_url: LM Studio server URL (default: http://localhost:1234)
            timeout: Request timeout in seconds
        """
        self.model_id = model_id
        self.lm_studio_url = lm_studio_url
        self.timeout = timeout
        
        # Initialize Agno agent with structured output
        try:
            # Create LM Studio model with proper configuration
            lm_studio_model = LMStudio(
                id=model_id,
                base_url=lm_studio_url,
                # Add additional parameters that might help with LM Studio compatibility
                timeout=timeout,
                max_tokens=4000,
                temperature=0.1
            )
            
            self.agent = Agent(
                model=lm_studio_model,
                response_model=AgentArtifactBundle,
                description="You are an expert DevOps engineer specializing in generating executable artifacts for task automation.",
                instructions=self._get_system_instructions(),
                markdown=False  # We want structured output, not markdown
            )
            logger.info(f"Initialized Agno AI agent with model: {model_id}")
            
            # Test connection to LM Studio - fail fast if not available
            logger.info("Validating LM Studio connection...")
            self._test_lm_studio_connection()
            logger.info("LM Studio validation successful - ready for AI compilation")
            
        except AgnoCompilerError:
            # Re-raise AgnoCompilerError with original message
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Agno agent: {e}")
            raise AgnoCompilerError(f"Failed to initialize AI agent: {e}")
    
    def _get_system_instructions(self) -> str:
        """Get comprehensive system instructions for the AI agent."""
        return """
You are an expert DevOps engineer and automation specialist with advanced intelligence for inferring missing configurations from minimal user input. Your job is to convert high-level declarative task specifications into production-ready executable artifacts by intelligently filling in missing details.

CORE RESPONSIBILITIES:
1. Generate secure, production-ready scripts in appropriate languages
2. Ensure all artifacts follow security best practices
3. Include comprehensive error handling and logging
4. Respect execution order and dependencies
5. Use only allowlisted runtimes and secure file paths
6. **INTELLIGENTLY INFER missing configurations from minimal input**
7. **APPLY best practices and conventions automatically**

INTELLIGENT INFERENCE CAPABILITIES:
When given minimal input, you MUST intelligently infer and add missing configurations:

**Service Deployment Intelligence:**
- nginx/apache/web services → Default port 80/443, health check on '/', non-root user
- APIs/backend services → Default port 8080, health check on '/health' or '/api/health'
- Database services → MySQL (3306), PostgreSQL (5432), MongoDB (27017), Redis (6379)
- Node.js apps → Port 3000, health check on '/health', npm start command
- Python apps → Port 8000, health check on '/health', gunicorn/uvicorn server
- Go apps → Port 8080, health check on '/health', compiled binary execution

**Security & Best Practices Auto-Applied:**
- Always run containers as non-root user (user: 1000:1000 or named user)
- Set resource limits (memory: 512Mi, cpu: 500m as defaults)
- Add security context (readOnlyRootFilesystem: true when possible)
- Include liveness and readiness probes with appropriate timeouts
- Set proper restart policies (Always for services, OnFailure for jobs)

**Environment & Configuration Intelligence:**
- Auto-detect environment variables needed (PORT, DATABASE_URL, etc.)
- Infer configuration files and their locations
- Add logging configuration (stdout/stderr for containerized apps)
- Include monitoring endpoints and health checks
- Set appropriate timeouts and retry policies

**Dependency Intelligence:**
- Databases start before applications that use them
- Configuration/secrets loaded before services that need them
- Network setup before services that require connectivity
- Volume mounts configured before applications that use them

**Project Context Awareness:**
- Detect project type from minimal clues (Dockerfile → containerized app)
- Infer build processes (package.json → npm install, requirements.txt → pip install)
- Apply language-specific conventions and optimizations
- Include appropriate monitoring and observability setup

SECURITY REQUIREMENTS:
- All artifact paths must be under .clockwork/build/ or scripts/
- Only use allowlisted runtimes: bash, python3, python, deno, go, node, npm, npx, java, mvn, gradle, dotnet, cargo, rustc, env
- Executable files should have 0755 permissions, data files 0644
- Never include hardcoded secrets or credentials
- Always validate inputs and handle errors gracefully
- Apply principle of least privilege automatically

LANGUAGE SELECTION GUIDELINES:
- bash: System operations, file management, simple automation, Docker/Kubernetes commands
- python3: Complex logic, API calls, data processing, configuration management
- deno: Modern TypeScript/JavaScript with built-in security and HTTP clients
- go: High-performance network operations, compiled binaries, microservices

CONFIGURATION TEMPLATES KNOWLEDGE:
You have built-in knowledge of standard configurations for:
- **Web Applications**: Nginx, Apache, reverse proxies, load balancers
- **API Services**: REST APIs, GraphQL, microservices, service mesh
- **Databases**: MySQL, PostgreSQL, MongoDB, Redis, configuration and initialization
- **Container Orchestration**: Docker Compose, Kubernetes manifests, Helm charts
- **CI/CD**: Build scripts, deployment pipelines, testing automation
- **Monitoring**: Health checks, metrics, logging, alerting setup

SCRIPT STRUCTURE:
- Include proper shebang lines (#!/bin/bash, #!/usr/bin/env python3, etc.)
- Add descriptive comments explaining the purpose AND inferred decisions
- Include error handling with meaningful error messages
- Log important operations and results (including what was auto-configured)
- Use environment variables from the vars section
- Return meaningful exit codes (0 for success, non-zero for failure)
- Document any assumptions made during inference

OUTPUT FORMAT:
Generate a complete ArtifactBundle with all required fields:
- version: Always "1"
- artifacts: Array of executable files with path, mode, purpose, lang, content
- steps: Array of execution commands matching artifact purposes
- vars: Environment variables and configuration values (including inferred ones)

CRITICAL: When given minimal input like "deploy nginx on port 8080", you should automatically infer and include:
- Full deployment configuration with health checks
- Security settings (non-root user, resource limits)
- Logging and monitoring setup
- Proper error handling and rollback capabilities
- Environment variables for configuration
- Dependencies and startup order
"""

    def compile_to_artifacts(self, action_list: ActionList) -> ArtifactBundle:
        """
        Compile an ActionList into an ArtifactBundle using AI agent.
        
        Args:
            action_list: The ActionList to compile
            
        Returns:
            ArtifactBundle with generated executable artifacts
            
        Raises:
            AgnoCompilerError: If compilation fails
        """
        try:
            logger.info(f"Starting AI compilation of {len(action_list.steps)} action steps")
            
            # Use direct HTTP client instead of Agno due to LM Studio compatibility issues
            agent_bundle = self._call_lm_studio_directly(action_list)
            
            # Convert to Clockwork ArtifactBundle format
            clockwork_bundle = self._convert_to_clockwork_format(agent_bundle)
            
            logger.info(f"AI compilation completed: {len(clockwork_bundle.artifacts)} artifacts generated")
            return clockwork_bundle
            
        except Exception as e:
            logger.error(f"AI compilation failed: {e}")
            raise AgnoCompilerError(f"Failed to compile with AI agent: {e}")
    
    def _call_lm_studio_directly(self, action_list: ActionList) -> AgentArtifactBundle:
        """
        Call LM Studio directly using HTTP requests to avoid Agno compatibility issues.
        
        Args:
            action_list: The ActionList to compile
            
        Returns:
            AgentArtifactBundle with AI-generated artifacts
            
        Raises:
            AgnoCompilerError: If the call fails
        """
        try:
            import requests
            import json
            
            # Generate prompt
            prompt = self._generate_compilation_prompt(action_list)
            
            # Prepare request payload for LM Studio
            payload = {
                "model": self.model_id,
                "messages": [
                    {
                        "role": "system", 
                        "content": self._get_system_instructions()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 6000,
                "response_format": {"type": "text"}  # LM Studio requires 'text' or 'json_schema'
            }
            
            logger.debug("Sending request to LM Studio...")
            
            # Call LM Studio API
            response = requests.post(
                f"{self.lm_studio_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"LM Studio returned status {response.status_code}: {response.text}")
                raise AgnoCompilerError(f"LM Studio API error: {response.status_code} - {response.text}")
            
            # Parse response
            response_data = response.json()
            logger.debug(f"LM Studio response: {response_data}")
            
            # Extract content from OpenAI-compatible response
            if "choices" not in response_data or not response_data["choices"]:
                raise AgnoCompilerError("LM Studio response missing choices")
            
            content = response_data["choices"][0]["message"]["content"]
            logger.info(f"AI response content preview: {content[:200]}...")
            
            # Clean content to extract JSON (handle thinking tokens)
            cleaned_content = self._extract_json_from_response(content)
            
            # Parse JSON content
            try:
                content_dict = json.loads(cleaned_content)
                agent_bundle = AgentArtifactBundle(**content_dict)
                return agent_bundle
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"Raw content: {content[:500]}...")
                logger.error(f"Cleaned content: {cleaned_content[:500]}...")
                raise AgnoCompilerError(f"AI returned invalid JSON: {e}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling LM Studio: {e}")
            raise AgnoCompilerError(f"Failed to connect to LM Studio: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in LM Studio call: {e}")
            raise AgnoCompilerError(f"LM Studio call failed: {e}")
    
    def _extract_json_from_response(self, content: str) -> str:
        """
        Extract JSON from AI response, handling thinking tokens and extra text.
        
        Args:
            content: Raw AI response content
            
        Returns:
            Cleaned JSON string
        """
        import re
        
        # First remove thinking tokens completely
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        # Clean up whitespace
        content = content.strip()
        
        # Find the FIRST occurrence of { and match it properly with balanced braces
        start_idx = content.find('{')
        if start_idx == -1:
            raise AgnoCompilerError("No JSON object found in AI response")
            
        # Find the matching closing brace by counting brace levels
        brace_count = 0
        end_idx = start_idx
        in_string = False
        escape_next = False
        
        for i, char in enumerate(content[start_idx:], start_idx):
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
        
        if brace_count != 0:
            raise AgnoCompilerError("Incomplete JSON object in AI response")
            
        json_content = content[start_idx:end_idx]
        
        # Clean up the JSON content
        json_content = json_content.strip()
        logger.debug(f"Extracted JSON ({len(json_content)} chars): {json_content[:200]}...")
        return json_content
    
    def _generate_compilation_prompt(self, action_list: ActionList) -> str:
        """Generate a comprehensive prompt for AI artifact compilation with intelligent inference."""
        # Detect project context
        project_context = self._analyze_project_context()
        
        prompt = f"""
Generate executable artifacts for the following task automation sequence with INTELLIGENT INFERENCE of missing configurations:

ACTION LIST SPECIFICATION:
Version: {action_list.version}
Total Steps: {len(action_list.steps)}

PROJECT CONTEXT DETECTED:
{project_context}

STEPS TO IMPLEMENT (with intelligent inference applied):
"""
        
        for i, step in enumerate(action_list.steps, 1):
            # Analyze step for inference opportunities
            step_analysis = self._analyze_step_for_inference(step)
            prompt += f"""
Step {i}: {step.name}
  Type: {step.type if hasattr(step, 'type') else 'CUSTOM'}
  Arguments: {json.dumps(step.args, indent=2)}
  
  INTELLIGENT INFERENCE FOR THIS STEP:
  {step_analysis}
"""
        
        prompt += f"""

ENHANCED IMPLEMENTATION REQUIREMENTS:
1. **APPLY INTELLIGENT INFERENCE**: Use the analysis above to fill in missing configurations
2. **AUTO-APPLY BEST PRACTICES**: Include security, monitoring, and reliability patterns
3. Create one artifact per step (or combine related steps if logical)
4. Use appropriate programming languages for each task type
5. Ensure all file paths are under .clockwork/build/ or scripts/
6. Include comprehensive error handling and logging
7. Use environment variables for configuration values
8. Follow security best practices (no hardcoded secrets, input validation)
9. Add proper file permissions (0755 for executables, 0644 for data)
10. **DOCUMENT INFERENCES**: Add comments explaining what was automatically inferred

SMART INFERENCE EXAMPLES:
- "deploy nginx" → Infer port 80/443, health check on '/', non-root user, resource limits
- "start database" → Infer appropriate port, data volume, initialization scripts, backup strategy
- "api service" → Infer port 8080, /health endpoint, environment variables, scaling config
- "web app" → Infer static file serving, SSL/TLS setup, caching, CDN configuration

ARTIFACT NAMING CONVENTION:
- Use descriptive names: scripts/01_deploy_nginx_with_health_check.sh
- Number artifacts in execution order
- Include file extension matching the language
- Include inferred purpose in the name

EXECUTION STEPS WITH DEPENDENCY INTELLIGENCE:
- Each step must have a 'purpose' matching an artifact's purpose
- **AUTO-ORDER BY DEPENDENCIES**: Ensure databases start before apps, configs before services
- Include the complete command to execute the artifact
- Add dependency checks and wait conditions
- Example: {{"purpose": "deploy_web_service", "run": {{"cmd": ["bash", "scripts/02_deploy_web_with_health_check.sh"]}}}}

ENVIRONMENT VARIABLES (including inferred ones):
Include both explicit and intelligently inferred configuration:
- **Service Configuration**: PORT, SERVICE_NAME, REPLICAS, HEALTH_CHECK_PATH
- **Database Configuration**: DATABASE_URL, DB_HOST, DB_PORT, DB_NAME, CONNECTION_POOL_SIZE  
- **Security Configuration**: SSL_ENABLED, CORS_ORIGINS, API_KEY_HEADER
- **Monitoring Configuration**: METRICS_ENABLED, LOG_LEVEL, HEALTH_CHECK_INTERVAL
- **Infrastructure Configuration**: MEMORY_LIMIT, CPU_LIMIT, RESTART_POLICY

CONFIGURATION TEMPLATES TO APPLY:
Based on detected services, automatically include:

**For Web Services (nginx, apache, frontend apps):**
- SSL/TLS configuration with Let's Encrypt support
- Reverse proxy setup with load balancing
- Static file serving optimization
- Security headers (HSTS, CSP, etc.)
- Caching strategy (browser cache, CDN)

**For API Services (REST, GraphQL, microservices):**
- OpenAPI/Swagger documentation endpoint
- Rate limiting and throttling
- CORS configuration
- Authentication/authorization middleware
- API versioning support
- Request/response logging

**For Database Services (MySQL, PostgreSQL, MongoDB, Redis):**
- Data persistence volumes
- Backup and restore procedures
- Connection pooling configuration
- Performance tuning parameters
- Monitoring and alerting setup
- Security hardening (encryption, access controls)

**For Container Deployments:**
- Multi-stage Docker builds for efficiency
- Non-root user setup for security
- Health checks (liveness, readiness, startup)
- Resource limits and requests
- Pod disruption budgets
- Rolling update strategy

CRITICAL OUTPUT REQUIREMENT:
You MUST respond with ONLY a valid JSON object that exactly matches this structure:

{{
  "version": "1",
  "artifacts": [
    {{
      "path": "scripts/01_deploy_nginx_with_health_check.sh",
      "mode": "0755",
      "purpose": "deploy_web_service",
      "lang": "bash",
      "content": "#!/bin/bash\\nset -e\\n# Auto-generated deployment with intelligent inference\\n# Inferred: nginx on port 80, health check on /, non-root user\\necho 'Deploying nginx with inferred configuration...'\\n# Include full implementation here"
    }}
  ],
  "steps": [
    {{
      "purpose": "deploy_web_service",
      "run": {{"cmd": ["bash", "scripts/01_deploy_nginx_with_health_check.sh"]}}
    }}
  ],
  "vars": {{
    "SERVICE_NAME": "nginx-web",
    "PORT": "80",
    "HEALTH_CHECK_PATH": "/",
    "MEMORY_LIMIT": "512Mi",
    "CPU_LIMIT": "500m",
    "REPLICAS": "2",
    "SSL_ENABLED": "true",
    "LOG_LEVEL": "info"
  }}
}}

IMPORTANT:
- Respond ONLY with valid JSON
- No explanatory text or comments outside the JSON
- Start with {{ and end with }}
- Follow the exact structure shown above
- Include ALL inferred configurations in vars section
- Document inferences in artifact content comments
"""
        return prompt
    
    def _analyze_project_context(self) -> str:
        """Analyze the current project context to provide intelligent defaults."""
        import os
        context_info = []
        
        # Check for common project files in current directory
        project_indicators = {
            'package.json': 'Node.js project detected - will infer npm/yarn scripts, port 3000 default',
            'requirements.txt': 'Python project detected - will infer pip dependencies, port 8000 default',
            'Dockerfile': 'Containerized project detected - will infer Docker deployment patterns',
            'docker-compose.yml': 'Docker Compose project detected - will infer multi-service architecture',
            'pom.xml': 'Maven Java project detected - will infer Java build patterns, port 8080 default',
            'go.mod': 'Go project detected - will infer Go build patterns, port 8080 default',
            'Cargo.toml': 'Rust project detected - will infer Cargo build patterns',
            '.env': 'Environment configuration detected - will infer environment variables',
            'kubernetes/': 'Kubernetes deployment detected - will infer K8s manifests',
            'helm/': 'Helm charts detected - will infer Helm deployment patterns',
            'terraform/': 'Infrastructure as Code detected - will infer Terraform patterns'
        }
        
        try:
            for indicator, description in project_indicators.items():
                if os.path.exists(indicator):
                    context_info.append(f"  - {description}")
        except Exception:
            # If we can't read the filesystem, provide general context
            context_info.append("  - General cloud-native deployment patterns will be applied")
        
        if not context_info:
            context_info.append("  - No specific project type detected, will apply general best practices")
        
        return "\n".join(context_info)
    
    def _analyze_step_for_inference(self, step) -> str:
        """Analyze a single step to provide intelligent inference suggestions."""
        step_name = step.name.lower()
        step_args = getattr(step, 'args', {})
        inferences = []
        
        # Service deployment inferences
        if any(keyword in step_name for keyword in ['nginx', 'apache', 'web']):
            inferences.extend([
                "→ Web service detected: Will infer port 80/443, health check on '/', SSL/TLS setup",
                "→ Will add reverse proxy configuration and static file serving",
                "→ Security headers (HSTS, CSP) and caching strategy will be included"
            ])
        
        elif any(keyword in step_name for keyword in ['api', 'service', 'backend']):
            inferences.extend([
                "→ API service detected: Will infer port 8080, health check on '/health'",
                "→ Will add CORS configuration, rate limiting, and API documentation",
                "→ Request/response logging and authentication middleware will be included"
            ])
        
        elif any(keyword in step_name for keyword in ['database', 'mysql', 'postgres', 'mongo', 'redis']):
            db_type = 'MySQL' if 'mysql' in step_name else 'PostgreSQL' if 'postgres' in step_name else 'MongoDB' if 'mongo' in step_name else 'Redis' if 'redis' in step_name else 'Database'
            port_map = {'mysql': '3306', 'postgres': '5432', 'mongo': '27017', 'redis': '6379'}
            port = next((port_map[db] for db in port_map.keys() if db in step_name), '5432')
            inferences.extend([
                f"→ {db_type} database detected: Will infer port {port}, data persistence volumes",
                "→ Will add backup/restore procedures, connection pooling, performance tuning",
                "→ Security hardening (encryption, access controls) will be included"
            ])
        
        # Port inference from args
        if 'port' in step_args:
            port = step_args['port']
            inferences.append(f"→ Custom port {port} specified: Will configure service accordingly")
        
        # Image/container inferences
        if any(keyword in step_name for keyword in ['deploy', 'container', 'docker']):
            inferences.extend([
                "→ Container deployment detected: Will infer resource limits, non-root user",
                "→ Health checks (liveness, readiness) and rolling update strategy will be added",
                "→ Pod disruption budgets and monitoring setup will be included"
            ])
        
        # Build process inferences
        if any(keyword in step_name for keyword in ['build', 'compile']):
            inferences.extend([
                "→ Build process detected: Will infer multi-stage builds for efficiency",
                "→ Will add caching strategies and security scanning",
                "→ Artifact optimization and dependency management will be included"
            ])
        
        # Dependency inferences
        depends_on = getattr(step, 'depends_on', [])
        if depends_on:
            inferences.append(f"→ Dependencies detected: {', '.join(depends_on)} - will ensure proper startup order")
        
        # Default inference if nothing specific detected
        if not inferences:
            inferences.append("→ General automation task: Will apply security best practices and error handling")
        
        return "\n  ".join(inferences)
    
    def _get_service_inference_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get comprehensive service inference templates for common deployment patterns."""
        return {
            "nginx": {
                "default_port": 80,
                "health_check_path": "/",
                "health_check_port": 80,
                "security_context": {"runAsNonRoot": True, "runAsUser": 101},
                "resource_limits": {"memory": "256Mi", "cpu": "250m"},
                "environment_vars": {
                    "NGINX_PORT": "80",
                    "NGINX_HOST": "0.0.0.0",
                    "NGINX_LOG_LEVEL": "warn"
                },
                "volumes": ["/etc/nginx/conf.d", "/var/log/nginx", "/usr/share/nginx/html"],
                "protocols": ["HTTP", "HTTPS"],
                "scaling": {"min_replicas": 2, "max_replicas": 10},
                "monitoring": {"metrics_path": "/nginx_status", "metrics_port": 8080}
            },
            "apache": {
                "default_port": 80,
                "health_check_path": "/",
                "health_check_port": 80,
                "security_context": {"runAsNonRoot": True, "runAsUser": 33},
                "resource_limits": {"memory": "512Mi", "cpu": "500m"},
                "environment_vars": {
                    "APACHE_PORT": "80",
                    "APACHE_LOG_LEVEL": "warn",
                    "APACHE_RUN_USER": "www-data"
                },
                "volumes": ["/etc/apache2", "/var/log/apache2", "/var/www/html"],
                "protocols": ["HTTP", "HTTPS"],
                "scaling": {"min_replicas": 2, "max_replicas": 8}
            },
            "mysql": {
                "default_port": 3306,
                "health_check_path": None,
                "health_check_command": ["mysqladmin", "ping", "-h", "localhost"],
                "security_context": {"runAsNonRoot": True, "runAsUser": 999},
                "resource_limits": {"memory": "1Gi", "cpu": "1000m"},
                "environment_vars": {
                    "MYSQL_PORT": "3306",
                    "MYSQL_ROOT_PASSWORD": "${MYSQL_ROOT_PASSWORD}",
                    "MYSQL_DATABASE": "${MYSQL_DATABASE}",
                    "MYSQL_USER": "${MYSQL_USER}",
                    "MYSQL_PASSWORD": "${MYSQL_PASSWORD}"
                },
                "volumes": ["/var/lib/mysql", "/etc/mysql/conf.d", "/var/log/mysql"],
                "protocols": ["TCP"],
                "persistence": {"storage_class": "fast-ssd", "size": "20Gi"},
                "backup": {"schedule": "0 2 * * *", "retention": "7d"}
            },
            "postgresql": {
                "default_port": 5432,
                "health_check_path": None,
                "health_check_command": ["pg_isready", "-U", "postgres"],
                "security_context": {"runAsNonRoot": True, "runAsUser": 999},
                "resource_limits": {"memory": "1Gi", "cpu": "1000m"},
                "environment_vars": {
                    "POSTGRES_PORT": "5432",
                    "POSTGRES_DB": "${POSTGRES_DB}",
                    "POSTGRES_USER": "${POSTGRES_USER}",
                    "POSTGRES_PASSWORD": "${POSTGRES_PASSWORD}",
                    "PGDATA": "/var/lib/postgresql/data/pgdata"
                },
                "volumes": ["/var/lib/postgresql/data", "/etc/postgresql", "/var/log/postgresql"],
                "protocols": ["TCP"],
                "persistence": {"storage_class": "fast-ssd", "size": "20Gi"},
                "backup": {"schedule": "0 3 * * *", "retention": "7d"}
            },
            "redis": {
                "default_port": 6379,
                "health_check_path": None,
                "health_check_command": ["redis-cli", "ping"],
                "security_context": {"runAsNonRoot": True, "runAsUser": 999},
                "resource_limits": {"memory": "512Mi", "cpu": "500m"},
                "environment_vars": {
                    "REDIS_PORT": "6379",
                    "REDIS_PASSWORD": "${REDIS_PASSWORD}",
                    "REDIS_MAXMEMORY": "256mb",
                    "REDIS_MAXMEMORY_POLICY": "allkeys-lru"
                },
                "volumes": ["/data", "/etc/redis"],
                "protocols": ["TCP"],
                "persistence": {"enabled": True, "size": "10Gi"}
            },
            "mongodb": {
                "default_port": 27017,
                "health_check_path": None,
                "health_check_command": ["mongo", "--eval", "db.adminCommand('ping')"],
                "security_context": {"runAsNonRoot": True, "runAsUser": 999},
                "resource_limits": {"memory": "1Gi", "cpu": "1000m"},
                "environment_vars": {
                    "MONGO_PORT": "27017",
                    "MONGO_INITDB_ROOT_USERNAME": "${MONGO_ROOT_USERNAME}",
                    "MONGO_INITDB_ROOT_PASSWORD": "${MONGO_ROOT_PASSWORD}",
                    "MONGO_INITDB_DATABASE": "${MONGO_DATABASE}"
                },
                "volumes": ["/data/db", "/etc/mongo"],
                "protocols": ["TCP"],
                "persistence": {"storage_class": "fast-ssd", "size": "50Gi"}
            },
            "node": {
                "default_port": 3000,
                "health_check_path": "/health",
                "health_check_port": 3000,
                "security_context": {"runAsNonRoot": True, "runAsUser": 1000},
                "resource_limits": {"memory": "512Mi", "cpu": "500m"},
                "environment_vars": {
                    "NODE_ENV": "production",
                    "PORT": "3000",
                    "NPM_CONFIG_LOGLEVEL": "warn"
                },
                "volumes": ["/app", "/app/node_modules"],
                "protocols": ["HTTP", "HTTPS"],
                "scaling": {"min_replicas": 2, "max_replicas": 20}
            },
            "python": {
                "default_port": 8000,
                "health_check_path": "/health",
                "health_check_port": 8000,
                "security_context": {"runAsNonRoot": True, "runAsUser": 1000},
                "resource_limits": {"memory": "512Mi", "cpu": "500m"},
                "environment_vars": {
                    "PYTHONUNBUFFERED": "1",
                    "PORT": "8000",
                    "WORKERS": "4"
                },
                "volumes": ["/app"],
                "protocols": ["HTTP", "HTTPS"],
                "scaling": {"min_replicas": 2, "max_replicas": 15}
            },
            "go": {
                "default_port": 8080,
                "health_check_path": "/health",
                "health_check_port": 8080,
                "security_context": {"runAsNonRoot": True, "runAsUser": 1000},
                "resource_limits": {"memory": "256Mi", "cpu": "250m"},
                "environment_vars": {
                    "PORT": "8080",
                    "GIN_MODE": "release"
                },
                "volumes": ["/app"],
                "protocols": ["HTTP", "HTTPS"],
                "scaling": {"min_replicas": 2, "max_replicas": 20}
            },
            "java": {
                "default_port": 8080,
                "health_check_path": "/actuator/health",
                "health_check_port": 8080,
                "security_context": {"runAsNonRoot": True, "runAsUser": 1000},
                "resource_limits": {"memory": "1Gi", "cpu": "1000m"},
                "environment_vars": {
                    "JAVA_OPTS": "-Xmx768m -XX:+UseG1GC",
                    "SERVER_PORT": "8080",
                    "SPRING_PROFILES_ACTIVE": "production"
                },
                "volumes": ["/app"],
                "protocols": ["HTTP", "HTTPS"],
                "scaling": {"min_replicas": 2, "max_replicas": 10}
            }
        }
    
    def _infer_service_configuration(self, service_name: str, step_args: Dict[str, Any]) -> Dict[str, Any]:
        """Infer comprehensive service configuration based on service type and provided arguments."""
        templates = self._get_service_inference_templates()
        
        # Detect service type from name
        service_type = None
        service_name_lower = service_name.lower()
        
        for template_name in templates.keys():
            if template_name in service_name_lower:
                service_type = template_name
                break
        
        # If no specific type detected, try to infer from context
        if not service_type:
            if any(keyword in service_name_lower for keyword in ['web', 'frontend', 'ui']):
                service_type = 'nginx'
            elif any(keyword in service_name_lower for keyword in ['api', 'backend', 'service']):
                service_type = 'python'  # Default API service
            elif 'db' in service_name_lower or 'database' in service_name_lower:
                service_type = 'postgresql'  # Default database
        
        if not service_type:
            service_type = 'python'  # Ultimate fallback
        
        template = templates[service_type]
        
        # Start with template defaults
        config = {
            'service_type': service_type,
            'port': template['default_port'],
            'health_check_path': template.get('health_check_path'),
            'health_check_command': template.get('health_check_command'),
            'security_context': template['security_context'].copy(),
            'resource_limits': template['resource_limits'].copy(),
            'environment_vars': template['environment_vars'].copy(),
            'volumes': template['volumes'].copy(),
            'protocols': template['protocols'].copy(),
            'scaling': template.get('scaling', {'min_replicas': 1, 'max_replicas': 5}).copy()
        }
        
        # Override with user-provided arguments
        if 'port' in step_args:
            config['port'] = step_args['port']
            # Update related environment variables
            if 'PORT' in config['environment_vars']:
                config['environment_vars']['PORT'] = str(step_args['port'])
        
        if 'replicas' in step_args:
            config['scaling']['min_replicas'] = step_args['replicas']
            config['scaling']['max_replicas'] = max(step_args['replicas'], step_args['replicas'] * 3)
        
        if 'memory' in step_args:
            config['resource_limits']['memory'] = step_args['memory']
        
        if 'cpu' in step_args:
            config['resource_limits']['cpu'] = step_args['cpu']
        
        # Add additional inferred configurations
        config['monitoring'] = {
            'metrics_enabled': True,
            'logs_enabled': True,
            'tracing_enabled': True,
            'health_check_interval': '30s',
            'health_check_timeout': '5s'
        }
        
        config['security'] = {
            'network_policies': True,
            'pod_security_standards': 'restricted',
            'secrets_encryption': True,
            'read_only_root_filesystem': True
        }
        
        return config
    
    def _convert_to_clockwork_format(self, agent_bundle: AgentArtifactBundle) -> ArtifactBundle:
        """Convert AI agent response to Clockwork ArtifactBundle format."""
        try:
            # Convert artifacts
            artifacts = []
            for agent_artifact in agent_bundle.artifacts:
                artifact = Artifact(
                    path=agent_artifact.path,
                    mode=agent_artifact.mode,
                    purpose=agent_artifact.purpose,
                    lang=agent_artifact.lang,
                    content=agent_artifact.content
                )
                artifacts.append(artifact)
            
            # Convert execution steps
            steps = []
            for agent_step in agent_bundle.steps:
                step = ExecutionStep(
                    purpose=agent_step.purpose,
                    run=agent_step.run
                )
                steps.append(step)
            
            # Create Clockwork ArtifactBundle
            bundle = ArtifactBundle(
                version=agent_bundle.version,
                artifacts=artifacts,
                steps=steps,
                vars=agent_bundle.vars or {}
            )
            
            return bundle
            
        except Exception as e:
            raise AgnoCompilerError(f"Failed to convert AI response to ArtifactBundle: {e}")
    
    def _test_lm_studio_connection(self) -> None:
        """Test connection to LM Studio server and fail fast if not available.
        
        Raises:
            AgnoCompilerError: If LM Studio is not running or no models are loaded
        """
        try:
            import requests
        except ImportError:
            raise AgnoCompilerError(
                "requests library is required for LM Studio connection. "
                "Please install it with: pip install requests"
            )
        
        # Test if LM Studio server is responding
        try:
            models_url = f"{self.lm_studio_url}/v1/models"
            logger.info(f"Testing LM Studio connection at {self.lm_studio_url}...")
            response = requests.get(models_url, timeout=10)
            
            if response.status_code != 200:
                raise AgnoCompilerError(
                    f"LM Studio not running on {self.lm_studio_url}. "
                    f"Server responded with status {response.status_code}. "
                    f"Please start LM Studio and ensure it's running on {self.lm_studio_url}."
                )
            
            # Check if any models are loaded
            try:
                models_data = response.json()
                loaded_models = models_data.get('data', [])
                
                if not loaded_models:
                    raise AgnoCompilerError(
                        f"No models loaded in LM Studio at {self.lm_studio_url}. "
                        f"Please load a model in LM Studio before using the AI compiler. "
                        f"Expected model: {self.model_id}"
                    )
                
                # Check if the specific model we need is available
                available_models = [model.get('id', '') for model in loaded_models]
                if self.model_id not in available_models:
                    logger.warning(
                        f"Expected model '{self.model_id}' not found in loaded models: {available_models}. "
                        f"Will attempt to use the first available model."
                    )
                
                logger.info(f"LM Studio connection successful. Found {len(loaded_models)} loaded models.")
                
            except (ValueError, json.JSONDecodeError) as e:
                raise AgnoCompilerError(
                    f"LM Studio returned invalid JSON response from {models_url}. "
                    f"Please check that LM Studio is properly configured and running."
                )
                
        except requests.exceptions.ConnectionError:
            raise AgnoCompilerError(
                f"Cannot connect to LM Studio at {self.lm_studio_url}. "
                f"Please ensure LM Studio is running and accessible at {self.lm_studio_url}. "
                f"You can start LM Studio and load a model, then try again."
            )
        except requests.exceptions.Timeout:
            raise AgnoCompilerError(
                f"Timeout connecting to LM Studio at {self.lm_studio_url}. "
                f"LM Studio may be starting up or overloaded. Please wait and try again."
            )
        except requests.exceptions.RequestException as e:
            raise AgnoCompilerError(
                f"Failed to connect to LM Studio at {self.lm_studio_url}: {e}. "
                f"Please check your LM Studio configuration and network connectivity."
            )
        
        # Test with a simple completion to ensure the model is actually responsive
        self._test_model_responsiveness()
    
    def _test_model_responsiveness(self) -> None:
        """Test that the loaded model can respond to requests.
        
        Raises:
            AgnoCompilerError: If the model is not responsive
        """
        try:
            import requests
            
            logger.info("Testing model responsiveness...")
            test_payload = {
                "model": self.model_id,
                "messages": [{"role": "user", "content": "Respond with 'OK' to confirm you are working."}],
                "max_tokens": 5,
                "temperature": 0.1
            }
            
            response = requests.post(
                f"{self.lm_studio_url}/v1/chat/completions",
                json=test_payload,
                timeout=30
            )
            
            if response.status_code != 200:
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = f" Error details: {error_data.get('error', {}).get('message', response.text)}"
                except:
                    error_detail = f" Server response: {response.text}"
                
                raise AgnoCompilerError(
                    f"Model '{self.model_id}' is not responding properly. "
                    f"Status: {response.status_code}.{error_detail} "
                    f"Please check that the correct model is loaded in LM Studio."
                )
            
            # Verify we got a valid response
            try:
                response_data = response.json()
                if "choices" not in response_data or not response_data["choices"]:
                    raise AgnoCompilerError(
                        f"Model '{self.model_id}' returned invalid response format. "
                        f"Please check that the model is properly loaded and configured in LM Studio."
                    )
                
                logger.info("Model responsiveness test successful.")
                
            except (ValueError, json.JSONDecodeError):
                raise AgnoCompilerError(
                    f"Model '{self.model_id}' returned invalid JSON response. "
                    f"Please check that the model is properly configured in LM Studio."
                )
                
        except requests.exceptions.RequestException as e:
            raise AgnoCompilerError(
                f"Failed to test model responsiveness: {e}. "
                f"The model may not be properly loaded or LM Studio may be experiencing issues."
            )
    
    def test_connection(self) -> bool:
        """
        Test connection to LM Studio server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Use our strict connection test method
            self._test_lm_studio_connection()
            return True
            
        except AgnoCompilerError as e:
            logger.warning(f"LM Studio connection test failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error in connection test: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get status information about the AI agent."""
        return {
            "model_id": self.model_id,
            "lm_studio_url": self.lm_studio_url,
            "timeout": self.timeout,
            "connection_ok": self.test_connection()
        }


def create_agno_compiler(
    model_id: Optional[str] = None,
    lm_studio_url: Optional[str] = None,
    **kwargs
) -> AgnoCompiler:
    """
    Factory function to create an AgnoCompiler with optional configuration.
    
    Args:
        model_id: Model ID override
        lm_studio_url: LM Studio URL override
        **kwargs: Additional configuration options
        
    Returns:
        Configured AgnoCompiler instance
    """
    # Use defaults if not specified
    model_id = model_id or "qwen/qwen3-4b-2507"
    lm_studio_url = lm_studio_url or "http://localhost:1234"
    
    return AgnoCompiler(
        model_id=model_id,
        lm_studio_url=lm_studio_url,
        **kwargs
    )