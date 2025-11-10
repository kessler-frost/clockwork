# Architecture Diagram

## System Overview

```
                           CONNECTIONS SHOWCASE
                           ===================

┌──────────────────────────────────────────────────────────────────┐
│                         FRONTEND LAYER                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Frontend (nginx:alpine)                 │   │
│  │                          :80                              │   │
│  └───────────────────┬──────────────────┬────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
                       │                  │
                       │                  │
         ServiceMeshConnection    DependencyConnection
         (API_URL injection)       (deploy order)
                       │                  │
                       ▼                  ▼
┌──────────────────────────────────────────────────────────────────┐
│                       APPLICATION LAYER                          │
│  ┌─────────────────────────────────────┐   ┌─────────────────┐  │
│  │      API Server (nginx:alpine)      │   │ Redis (cache)   │  │
│  │            :8000                     │   │     :6379       │  │
│  │                                      │   └─────────────────┘  │
│  │  Connections:                        │           │            │
│  │  • DatabaseConnection (postgres)     │           │            │
│  │  • NetworkConnection (redis)         │◄──────────┘            │
│  │  • FileConnection (config.json)      │   NetworkConnection    │
│  │  • FileConnection (shared volume)    │   (backend-network)    │
│  └───────────┬──────────┬───────────────┘                        │
└──────────────────────────────────────────────────────────────────┘
               │          │
               │          │
    DatabaseConnection  FileConnection
     (DATABASE_URL)    (config mount)
               │          │
               ▼          ▼
┌──────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                               │
│  ┌───────────────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │   PostgreSQL      │   │ config.json  │   │ Shared Volume  │  │
│  │   (postgres:15)   │   │ FileResource │   │ (app-shared-   │  │
│  │      :5432        │   │              │   │     data)      │  │
│  │                   │   └──────────────┘   │                │  │
│  │  • schema.sql     │                      │  Mounted:      │  │
│  │    executed       │                      │  • api:/data/  │  │
│  │                   │                      │    shared      │  │
│  └───────────────────┘                      │  • storage:/   │  │
│                                             │    data/shared │  │
│                                             └────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Connection Flow Details

### 1. Frontend → API (ServiceMeshConnection)
```
Connection: ServiceMeshConnection
Direction:  frontend → api
Result:
  - Discovers api port: 8000
  - Injects: API_URL=http://api:8000
  - Adds health check: http://api:8000/health
  - Service discovery enabled
```

### 2. Frontend → Redis (DependencyConnection)
```
Connection: DependencyConnection (auto-created)
Direction:  frontend → redis
Result:
  - Ensures redis deploys before frontend
  - No environment variables injected
  - No setup resources created
```

### 3. API → PostgreSQL (DatabaseConnection)
```
Connection: DatabaseConnection
Direction:  api → postgres
Result:
  - Generates connection string
  - Injects: DATABASE_URL=postgresql://postgres:secret123@postgres:5432/appdb  # pragma: allowlist secret
  - Waits for postgres to be ready
  - Executes schema.sql
  - Creates tables: users, posts, comments
```

### 4. API → Redis (NetworkConnection)
```
Connection: NetworkConnection
Direction:  api → redis
Result:
  - Creates Docker network: backend-network
  - Connects api to backend-network
  - Connects redis to backend-network
  - Injects: REDIS_HOST=redis
  - Enables DNS: api can reach redis at "redis:6379"
```

### 5. API → config.json (FileConnection - Read-Only)
```
Connection: FileConnection
Direction:  api → config_file
Result:
  - Mounts config.json at /etc/app/config.json
  - Read-only mount (container can't modify)
  - Bind mount type
  - Source: ./config.json
```

### 6. API → Shared Volume (FileConnection - Volume)
```
Connection: FileConnection
Direction:  api → storage
Result:
  - Creates Docker volume: app-shared-data
  - Mounts to api at: /data/shared
  - Mounts to storage at: /data/shared
  - Read-write access
  - Both containers can share files
```

## Deployment Timeline

```
Time    Resource         Action                    Dependencies
─────   ─────────────    ──────────────────────    ────────────
t=0     postgres         Start container           None
t=0     redis            Start container           None
t=0     config_file      Create file               None
t=0     storage          Start container           None

t=1     schema.sql       Execute SQL               postgres ready
t=1     backend-network  Create Docker network     None
t=1     app-shared-data  Create Docker volume      None

t=2     api              Start container           postgres, redis,
                                                   config_file,
                                                   storage,
                                                   backend-network,
                                                   app-shared-data

t=3     frontend         Start container           api, redis
```

## Network Topology

```
┌─────────────────────────────────────────────────────────┐
│              backend-network (Docker Bridge)            │
│                                                         │
│   ┌─────────────────┐          ┌──────────────────┐    │
│   │  api            │          │  redis           │    │
│   │  172.18.0.2     │◄────────►│  172.18.0.3      │    │
│   │                 │  DNS:    │                  │    │
│   │                 │  redis   │                  │    │
│   └─────────────────┘          └──────────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              Host Network (External Access)             │
│                                                         │
│   ┌─────────────────┐          ┌──────────────────┐    │
│   │  postgres       │          │  frontend        │    │
│   │  localhost:5432 │          │  localhost:80    │    │
│   └─────────────────┘          │                  │    │
│                                └──────────────────┘    │
│   ┌─────────────────┐                                  │
│   │  api            │                                  │
│   │  localhost:8000 │                                  │
│   └─────────────────┘                                  │
└─────────────────────────────────────────────────────────┘
```

## File System Mounts

```
Host Machine                Container: api
────────────────            ──────────────────────────────

./config.json       ──►     /etc/app/config.json (ro)


Docker Volume: app-shared-data
────────────────────────────────

                    ──►     /data/shared (rw)
                    ──►     Container: storage
                            /data/shared (rw)
```

## Environment Variables Injected

### API Container
```bash
# From DatabaseConnection
DATABASE_URL=postgresql://postgres:secret123@postgres:5432/appdb # pragma: allowlist secret

# From NetworkConnection
REDIS_HOST=redis

# Original env vars
POSTGRES_DB=appdb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secret123
```

### Frontend Container
```bash
# From ServiceMeshConnection
API_URL=http://api:8000
```

## Data Flow Example

```
1. User Request Flow
   ────────────────
   Browser ──HTTP──► Frontend:80
                     │
                     │ API_URL=http://api:8000
                     ▼
                     API:8000
                     │
                     ├──► PostgreSQL:5432 (DATABASE_URL)
                     │    (Fetch user data)
                     │
                     └──► Redis:6379 (REDIS_HOST)
                          (Cache session)

2. Shared File Flow
   ────────────────
   API Container
   │
   ├── Write to /data/shared/upload.jpg
   │
   Storage Container
   │
   └── Read from /data/shared/upload.jpg
       (Same Docker volume)

3. Configuration Flow
   ──────────────────
   ./config.json (Host)
   │
   └── Mounted read-only to:
       /etc/app/config.json (API Container)
```

## Assertions and Health Checks

```
Resource    Assertion Type           Check
────────    ──────────────           ─────
postgres    ContainerRunningAssert   Container is running
redis       ContainerRunningAssert   Container is running
api         ContainerRunningAssert   Container is running
api         HealthcheckAssert        HTTP GET http://localhost:8000
storage     ContainerRunningAssert   Container is running
frontend    ContainerRunningAssert   Container is running
frontend    HealthcheckAssert        HTTP GET http://localhost:80

# ServiceMeshConnection adds automatically:
frontend    HealthcheckAssert        HTTP GET http://api:8000/health
```
