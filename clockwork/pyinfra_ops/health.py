"""
Clockwork Health Check Operations

PyInfra operations for performing various health checks including HTTP endpoints,
TCP connections, service status, and custom command-based health validations.
"""

import json
import logging
import time
from typing import Dict, List, Optional, Union

from pyinfra import host
from pyinfra.api import operation, OperationError
from pyinfra.api.command import StringCommand, FunctionCommand
from pyinfra.facts.server import Command

logger = logging.getLogger(__name__)


@operation()
def http_health_check(
    url: str,
    method: str = "GET",
    expected_status: Union[int, List[int]] = 200,
    expected_content: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    retries: int = 3,
    retry_delay: int = 5,
    follow_redirects: bool = True,
    verify_ssl: bool = True,
    user_agent: Optional[str] = None,
):
    """
    Perform HTTP health check using curl.

    Args:
        url: URL to check
        method: HTTP method to use
        expected_status: Expected HTTP status code(s)
        expected_content: Expected content in response body
        headers: HTTP headers to send
        timeout: Request timeout in seconds
        retries: Number of retry attempts
        retry_delay: Delay between retries in seconds
        follow_redirects: Follow HTTP redirects
        verify_ssl: Verify SSL certificates
        user_agent: Custom User-Agent header

    Example:
        http_health_check(
            url="https://api.example.com/health",
            expected_status=200,
            expected_content="OK",
            timeout=10
        )
    """
    if isinstance(expected_status, int):
        expected_status = [expected_status]

    # Build curl command
    cmd_parts = ["curl", "-s", "-w", "%{http_code}"]

    # Add method
    if method != "GET":
        cmd_parts.extend(["-X", method])

    # Add timeout
    cmd_parts.extend(["--max-time", str(timeout)])

    # Add SSL verification
    if not verify_ssl:
        cmd_parts.append("-k")

    # Add redirect following
    if follow_redirects:
        cmd_parts.append("-L")

    # Add headers
    if headers:
        for key, value in headers.items():
            cmd_parts.extend(["-H", f"{key}: {value}"])

    # Add user agent
    if user_agent:
        cmd_parts.extend(["-A", user_agent])

    # Add URL
    cmd_parts.append(url)

    # Execute health check with retries
    for attempt in range(retries + 1):
        if attempt > 0:
            yield StringCommand(f"sleep {retry_delay}")

        # Execute curl command and capture output
        result_cmd = " ".join(cmd_parts)
        yield StringCommand(f"""
RESPONSE=$({result_cmd})
STATUS_CODE=$(echo "$RESPONSE" | tail -c 4)
BODY=$(echo "$RESPONSE" | head -c -4)

echo "HTTP Status: $STATUS_CODE"
echo "Response Body: $BODY"

# Check status code
VALID_STATUS=false
for valid in {' '.join(map(str, expected_status))}; do
    if [ "$STATUS_CODE" = "$valid" ]; then
        VALID_STATUS=true
        break
    fi
done

if [ "$VALID_STATUS" = "false" ]; then
    echo "ERROR: Expected status {expected_status}, got $STATUS_CODE"
    exit 1
fi

# Check expected content if specified
{f'''
if [ -n "{expected_content}" ]; then
    if ! echo "$BODY" | grep -q "{expected_content}"; then
        echo "ERROR: Expected content '{expected_content}' not found in response"
        exit 1
    fi
fi
''' if expected_content else ''}

echo "Health check passed"
""")

        # If we reach here without error, break the retry loop
        break


@operation()
def tcp_health_check(
    host_address: str,
    port: int,
    timeout: int = 10,
    retries: int = 3,
    retry_delay: int = 5,
):
    """
    Perform TCP connection health check.

    Args:
        host_address: Hostname or IP address
        port: TCP port number
        timeout: Connection timeout in seconds
        retries: Number of retry attempts
        retry_delay: Delay between retries in seconds

    Example:
        tcp_health_check(
            host_address="database.example.com",
            port=5432,
            timeout=5
        )
    """
    # Execute TCP health check with retries
    for attempt in range(retries + 1):
        if attempt > 0:
            yield StringCommand(f"sleep {retry_delay}")

        # Use netcat or telnet for TCP check
        yield StringCommand(f"""
if command -v nc >/dev/null 2>&1; then
    if nc -z -w {timeout} {host_address} {port}; then
        echo "TCP connection to {host_address}:{port} successful"
        exit 0
    else
        echo "TCP connection to {host_address}:{port} failed (attempt {attempt + 1}/{retries + 1})"
        if [ {attempt} -eq {retries} ]; then
            exit 1
        fi
    fi
elif command -v timeout >/dev/null 2>&1; then
    if timeout {timeout} bash -c "</dev/tcp/{host_address}/{port}"; then
        echo "TCP connection to {host_address}:{port} successful"
        exit 0
    else
        echo "TCP connection to {host_address}:{port} failed (attempt {attempt + 1}/{retries + 1})"
        if [ {attempt} -eq {retries} ]; then
            exit 1
        fi
    fi
else
    echo "ERROR: Neither nc nor timeout command available for TCP check"
    exit 1
fi
""")


@operation()
def command_health_check(
    command: str,
    expected_exit_code: int = 0,
    expected_output: Optional[str] = None,
    timeout: int = 30,
    retries: int = 3,
    retry_delay: int = 5,
    working_directory: Optional[str] = None,
    environment: Optional[Dict[str, str]] = None,
):
    """
    Perform health check by executing a custom command.

    Args:
        command: Command to execute
        expected_exit_code: Expected exit code
        expected_output: Expected output pattern (regex)
        timeout: Command timeout in seconds
        retries: Number of retry attempts
        retry_delay: Delay between retries in seconds
        working_directory: Working directory for command
        environment: Environment variables

    Example:
        command_health_check(
            command="python -c 'import requests; print(requests.get(\"http://localhost:8080/health\").status_code)'",
            expected_output="200",
            timeout=10
        )
    """
    # Prepare environment variables
    env_vars = ""
    if environment:
        env_parts = [f"{k}={v}" for k, v in environment.items()]
        env_vars = " ".join(env_parts) + " "

    # Prepare working directory change
    cd_prefix = f"cd {working_directory} && " if working_directory else ""

    # Execute command health check with retries
    for attempt in range(retries + 1):
        if attempt > 0:
            yield StringCommand(f"sleep {retry_delay}")

        # Build the check command
        full_command = f"{env_vars}{cd_prefix}{command}"

        yield StringCommand(f"""
echo "Executing health check command (attempt {attempt + 1}/{retries + 1}): {command}"

# Execute command with timeout
if command -v timeout >/dev/null 2>&1; then
    OUTPUT=$(timeout {timeout} bash -c '{full_command}' 2>&1)
    EXIT_CODE=$?
else
    OUTPUT=$({full_command} 2>&1)
    EXIT_CODE=$?
fi

echo "Command output: $OUTPUT"
echo "Exit code: $EXIT_CODE"

# Check exit code
if [ $EXIT_CODE -ne {expected_exit_code} ]; then
    echo "ERROR: Expected exit code {expected_exit_code}, got $EXIT_CODE"
    if [ {attempt} -eq {retries} ]; then
        exit 1
    fi
    continue
fi

# Check expected output if specified
{f'''
if [ -n "{expected_output}" ]; then
    if ! echo "$OUTPUT" | grep -E "{expected_output}"; then
        echo "ERROR: Expected output pattern '{expected_output}' not found"
        if [ {attempt} -eq {retries} ]; then
            exit 1
        fi
        continue
    fi
fi
''' if expected_output else ''}

echo "Command health check passed"
exit 0
""")


@operation()
def service_health_check(
    service_name: str,
    service_manager: str = "systemd",
    expected_status: str = "active",
    check_ports: Optional[List[int]] = None,
    timeout: int = 30,
    retries: int = 3,
    retry_delay: int = 5,
):
    """
    Perform service health check using system service manager.

    Args:
        service_name: Name of the service
        service_manager: Service manager (systemd, sysv, docker)
        expected_status: Expected service status
        check_ports: List of ports the service should be listening on
        timeout: Check timeout in seconds
        retries: Number of retry attempts
        retry_delay: Delay between retries in seconds

    Example:
        service_health_check(
            service_name="nginx",
            service_manager="systemd",
            check_ports=[80, 443]
        )
    """
    valid_managers = ["systemd", "sysv", "docker"]
    if service_manager not in valid_managers:
        raise OperationError(f"Invalid service manager: {service_manager}. Must be one of: {valid_managers}")

    # Execute service health check with retries
    for attempt in range(retries + 1):
        if attempt > 0:
            yield StringCommand(f"sleep {retry_delay}")

        if service_manager == "systemd":
            yield StringCommand(f"""
echo "Checking systemd service {service_name} (attempt {attempt + 1}/{retries + 1})"

# Check service status
STATUS=$(systemctl is-active {service_name} 2>/dev/null || echo "inactive")
echo "Service status: $STATUS"

if [ "$STATUS" != "{expected_status}" ]; then
    echo "ERROR: Expected status '{expected_status}', got '$STATUS'"
    if [ {attempt} -eq {retries} ]; then
        # Show detailed status for debugging
        systemctl status {service_name} --no-pager -l
        exit 1
    fi
    continue
fi

{f'''
# Check ports if specified
PORTS="{' '.join(map(str, check_ports or []))}"
if [ -n "$PORTS" ]; then
    PORT_CHECK_FAILED=false
    for port in $PORTS; do
        if ! netstat -ln | grep -q ":$port "; then
            echo "ERROR: Service not listening on port $port"
            PORT_CHECK_FAILED=true
        else
            echo "Port $port is listening"
        fi
    done

    if [ "$PORT_CHECK_FAILED" = "true" ]; then
        if [ {attempt} -eq {retries} ]; then
            echo "Port check failed"
            netstat -ln | grep -E ":({'|'.join(map(str, check_ports or []))}) "
            exit 1
        fi
        continue
    fi
fi
''' if check_ports else ''}

echo "Service health check passed"
exit 0
""")

        elif service_manager == "sysv":
            yield StringCommand(f"""
echo "Checking SysV service {service_name} (attempt {attempt + 1}/{retries + 1})"

# Check service status
if service {service_name} status >/dev/null 2>&1; then
    STATUS="active"
else
    STATUS="inactive"
fi

echo "Service status: $STATUS"

if [ "$STATUS" != "{expected_status}" ]; then
    echo "ERROR: Expected status '{expected_status}', got '$STATUS'"
    if [ {attempt} -eq {retries} ]; then
        service {service_name} status
        exit 1
    fi
    continue
fi

echo "Service health check passed"
exit 0
""")

        elif service_manager == "docker":
            yield StringCommand(f"""
echo "Checking Docker container {service_name} (attempt {attempt + 1}/{retries + 1})"

# Check container status
STATUS=$(docker inspect -f '{{{{.State.Status}}}}' {service_name} 2>/dev/null || echo "not_found")
echo "Container status: $STATUS"

EXPECTED_DOCKER_STATUS="running"
if [ "{expected_status}" = "inactive" ]; then
    EXPECTED_DOCKER_STATUS="exited"
fi

if [ "$STATUS" != "$EXPECTED_DOCKER_STATUS" ]; then
    echo "ERROR: Expected status '$EXPECTED_DOCKER_STATUS', got '$STATUS'"
    if [ {attempt} -eq {retries} ]; then
        docker logs {service_name} --tail 50
        exit 1
    fi
    continue
fi

echo "Service health check passed"
exit 0
""")


@operation()
def database_health_check(
    database_type: str,
    connection_string: Optional[str] = None,
    host_address: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    query: Optional[str] = None,
    timeout: int = 30,
    retries: int = 3,
    retry_delay: int = 5,
):
    """
    Perform database connectivity and query health check.

    Args:
        database_type: Type of database (postgresql, mysql, mongodb, redis)
        connection_string: Full connection string (alternative to individual params)
        host_address: Database host
        port: Database port
        database: Database name
        username: Database username
        password: Database password
        query: Custom query to execute
        timeout: Query timeout in seconds
        retries: Number of retry attempts
        retry_delay: Delay between retries in seconds

    Example:
        database_health_check(
            database_type="postgresql",
            host_address="localhost",
            port=5432,
            database="myapp",
            username="app_user",
            query="SELECT 1"
        )
    """
    valid_types = ["postgresql", "mysql", "mongodb", "redis"]
    if database_type not in valid_types:
        raise OperationError(f"Invalid database type: {database_type}. Must be one of: {valid_types}")

    # Execute database health check with retries
    for attempt in range(retries + 1):
        if attempt > 0:
            yield StringCommand(f"sleep {retry_delay}")

        if database_type == "postgresql":
            # Build PostgreSQL connection
            if connection_string:
                conn_str = connection_string
            else:
                parts = []
                if host_address:
                    parts.append(f"host={host_address}")
                if port:
                    parts.append(f"port={port}")
                if database:
                    parts.append(f"dbname={database}")
                if username:
                    parts.append(f"user={username}")
                if password:
                    parts.append(f"password={password}")
                conn_str = " ".join(parts)

            test_query = query or "SELECT 1"

            yield StringCommand(f"""
echo "Testing PostgreSQL connection (attempt {attempt + 1}/{retries + 1})"

if command -v psql >/dev/null 2>&1; then
    if timeout {timeout} psql "{conn_str}" -c "{test_query}" >/dev/null 2>&1; then
        echo "PostgreSQL health check passed"
        exit 0
    else
        echo "PostgreSQL connection failed"
        if [ {attempt} -eq {retries} ]; then
            exit 1
        fi
    fi
else
    echo "ERROR: psql command not available"
    exit 1
fi
""")

        elif database_type == "mysql":
            # Build MySQL connection
            mysql_args = []
            if host_address:
                mysql_args.extend(["-h", host_address])
            if port:
                mysql_args.extend(["-P", str(port)])
            if username:
                mysql_args.extend(["-u", username])
            if password:
                mysql_args.append(f"-p{password}")
            if database:
                mysql_args.append(database)

            test_query = query or "SELECT 1"

            yield StringCommand(f"""
echo "Testing MySQL connection (attempt {attempt + 1}/{retries + 1})"

if command -v mysql >/dev/null 2>&1; then
    if timeout {timeout} mysql {" ".join(mysql_args)} -e "{test_query}" >/dev/null 2>&1; then
        echo "MySQL health check passed"
        exit 0
    else
        echo "MySQL connection failed"
        if [ {attempt} -eq {retries} ]; then
            exit 1
        fi
    fi
else
    echo "ERROR: mysql command not available"
    exit 1
fi
""")

        elif database_type == "mongodb":
            # Build MongoDB connection
            if connection_string:
                mongo_uri = connection_string
            else:
                mongo_uri = f"mongodb://{host_address or 'localhost'}:{port or 27017}"
                if database:
                    mongo_uri += f"/{database}"

            test_query = query or "db.runCommand({ping: 1})"

            yield StringCommand(f"""
echo "Testing MongoDB connection (attempt {attempt + 1}/{retries + 1})"

if command -v mongo >/dev/null 2>&1; then
    if timeout {timeout} mongo "{mongo_uri}" --eval "{test_query}" >/dev/null 2>&1; then
        echo "MongoDB health check passed"
        exit 0
    else
        echo "MongoDB connection failed"
        if [ {attempt} -eq {retries} ]; then
            exit 1
        fi
    fi
elif command -v mongosh >/dev/null 2>&1; then
    if timeout {timeout} mongosh "{mongo_uri}" --eval "{test_query}" >/dev/null 2>&1; then
        echo "MongoDB health check passed"
        exit 0
    else
        echo "MongoDB connection failed"
        if [ {attempt} -eq {retries} ]; then
            exit 1
        fi
    fi
else
    echo "ERROR: mongo or mongosh command not available"
    exit 1
fi
""")

        elif database_type == "redis":
            # Build Redis connection
            redis_args = []
            if host_address:
                redis_args.extend(["-h", host_address])
            if port:
                redis_args.extend(["-p", str(port)])
            if password:
                redis_args.extend(["-a", password])

            test_command = query or "PING"

            yield StringCommand(f"""
echo "Testing Redis connection (attempt {attempt + 1}/{retries + 1})"

if command -v redis-cli >/dev/null 2>&1; then
    if timeout {timeout} redis-cli {" ".join(redis_args)} {test_command} >/dev/null 2>&1; then
        echo "Redis health check passed"
        exit 0
    else
        echo "Redis connection failed"
        if [ {attempt} -eq {retries} ]; then
            exit 1
        fi
    fi
else
    echo "ERROR: redis-cli command not available"
    exit 1
fi
""")


@operation()
def file_health_check(
    file_path: str,
    should_exist: bool = True,
    min_size: Optional[int] = None,
    max_age: Optional[int] = None,
    expected_content: Optional[str] = None,
    permissions: Optional[str] = None,
    owner: Optional[str] = None,
    group: Optional[str] = None,
):
    """
    Perform file-based health check.

    Args:
        file_path: Path to file to check
        should_exist: Whether file should exist
        min_size: Minimum file size in bytes
        max_age: Maximum file age in seconds
        expected_content: Expected content pattern
        permissions: Expected file permissions (octal)
        owner: Expected file owner
        group: Expected file group

    Example:
        file_health_check(
            file_path="/var/log/app.log",
            should_exist=True,
            min_size=100,
            max_age=3600
        )
    """
    yield StringCommand(f"""
echo "Checking file health: {file_path}"

# Check existence
if [ -f "{file_path}" ]; then
    FILE_EXISTS=true
    echo "File exists: {file_path}"
else
    FILE_EXISTS=false
    echo "File does not exist: {file_path}"
fi

# Validate existence expectation
if [ "{str(should_exist).lower()}" = "true" ] && [ "$FILE_EXISTS" = "false" ]; then
    echo "ERROR: File should exist but does not: {file_path}"
    exit 1
elif [ "{str(should_exist).lower()}" = "false" ] && [ "$FILE_EXISTS" = "true" ]; then
    echo "ERROR: File should not exist but does: {file_path}"
    exit 1
fi

# Only run remaining checks if file should exist and does
if [ "{str(should_exist).lower()}" = "true" ] && [ "$FILE_EXISTS" = "true" ]; then

{f'''
    # Check minimum size
    if [ -n "{min_size}" ]; then
        ACTUAL_SIZE=$(stat -c%s "{file_path}" 2>/dev/null || stat -f%z "{file_path}" 2>/dev/null)
        if [ "$ACTUAL_SIZE" -lt {min_size} ]; then
            echo "ERROR: File size $ACTUAL_SIZE is less than minimum {min_size}"
            exit 1
        else
            echo "File size check passed: $ACTUAL_SIZE >= {min_size}"
        fi
    fi
''' if min_size else ''}

{f'''
    # Check maximum age
    if [ -n "{max_age}" ]; then
        CURRENT_TIME=$(date +%s)
        FILE_TIME=$(stat -c%Y "{file_path}" 2>/dev/null || stat -f%m "{file_path}" 2>/dev/null)
        FILE_AGE=$((CURRENT_TIME - FILE_TIME))
        if [ "$FILE_AGE" -gt {max_age} ]; then
            echo "ERROR: File age $FILE_AGE seconds exceeds maximum {max_age}"
            exit 1
        else
            echo "File age check passed: $FILE_AGE <= {max_age}"
        fi
    fi
''' if max_age else ''}

{f'''
    # Check expected content
    if [ -n "{expected_content}" ]; then
        if grep -q "{expected_content}" "{file_path}"; then
            echo "Content check passed: found '{expected_content}'"
        else
            echo "ERROR: Expected content '{expected_content}' not found"
            exit 1
        fi
    fi
''' if expected_content else ''}

{f'''
    # Check permissions
    if [ -n "{permissions}" ]; then
        ACTUAL_PERMS=$(stat -c%a "{file_path}" 2>/dev/null || stat -f%A "{file_path}" 2>/dev/null)
        if [ "$ACTUAL_PERMS" != "{permissions}" ]; then
            echo "ERROR: File permissions $ACTUAL_PERMS do not match expected {permissions}"
            exit 1
        else
            echo "Permissions check passed: {permissions}"
        fi
    fi
''' if permissions else ''}

{f'''
    # Check owner
    if [ -n "{owner}" ]; then
        ACTUAL_OWNER=$(stat -c%U "{file_path}" 2>/dev/null || stat -f%Su "{file_path}" 2>/dev/null)
        if [ "$ACTUAL_OWNER" != "{owner}" ]; then
            echo "ERROR: File owner $ACTUAL_OWNER does not match expected {owner}"
            exit 1
        else
            echo "Owner check passed: {owner}"
        fi
    fi
''' if owner else ''}

{f'''
    # Check group
    if [ -n "{group}" ]; then
        ACTUAL_GROUP=$(stat -c%G "{file_path}" 2>/dev/null || stat -f%Sg "{file_path}" 2>/dev/null)
        if [ "$ACTUAL_GROUP" != "{group}" ]; then
            echo "ERROR: File group $ACTUAL_GROUP does not match expected {group}"
            exit 1
        else
            echo "Group check passed: {group}"
        fi
    fi
''' if group else ''}

fi

echo "File health check passed"
""")