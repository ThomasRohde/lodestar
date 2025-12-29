# LSSPY - Lodestar Visualizer PRD

## Summary

**LSSPY** (Lodestar Spy) is a real-time visualization dashboard for monitoring Lodestar-managed repositories. It watches the `.lodestar/runtime.sqlite` database and `spec.yaml` for changes and dynamically updates beautiful, interactive dashboards showing agent activity, task status, dependency graphs, lease states, and communication flows.

**Package name**: `lsspy`
**CLI command**: `lsspy`
**Separate installation**: Yes (independent from lodestar-cli)
**Python**: 3.12+

---

## Problem

Teams using Lodestar for multi-agent coordination lack visibility into:
- What agents are currently active and what they're working on
- Task status distribution and bottlenecks in the dependency graph
- Lease health (expiring soon, stale claims)
- Communication patterns between agents
- Historical trends in agent productivity and task completion

Without a visual interface, understanding the state of a Lodestar-managed project requires running multiple CLI commands and mentally assembling the picture.

---

## Goals

1. **Real-time visibility** - Dashboard updates automatically when the database or spec changes
2. **Zero configuration** - Point at a `.lodestar` directory and it works
3. **Beautiful by default** - Modern, dark-mode-first UI with smooth animations
4. **Actionable insights** - Highlight issues (expiring leases, blocked tasks, idle agents)
5. **Lightweight** - Minimal resource footprint, no external database required
6. **Separate concern** - Independent package that doesn't add weight to lodestar-cli

---

## Non-Goals (v1)

- Modifying lodestar state (read-only visualization)
- Multi-repo aggregation (single repo per instance)
- User authentication (local tool, trusted environment)
- Historical data persistence beyond what's in SQLite
- Mobile-optimized interface

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Backend** | FastAPI | Async Python, native WebSocket support, automatic OpenAPI docs |
| **Real-time** | WebSockets | Push updates to browser on file changes |
| **File watching** | watchdog | Cross-platform file system events |
| **Frontend** | React 18 + TypeScript | Industry standard, rich ecosystem, excellent DX |
| **Styling** | Tailwind CSS | Utility-first, dark mode support, rapid prototyping |
| **Charts** | Recharts | React-native, composable, beautiful defaults |
| **Graph viz** | React Flow | Interactive node-based graphs for dependency DAG |
| **State** | Zustand | Lightweight React state management |
| **Build** | Vite | Fast builds, HMR, TypeScript support |
| **Bundling** | Single HTML | Embed built frontend in Python package for easy distribution |

### Why This Stack?

- **FastAPI + watchdog**: Efficient file monitoring with async WebSocket broadcasting
- **React + TypeScript**: Type safety catches bugs early, excellent tooling
- **Tailwind CSS**: Consistent styling without custom CSS overhead
- **Recharts + React Flow**: Purpose-built for the exact visualizations needed
- **Embedded frontend**: `pip install lsspy` includes everything, no npm required to run

---

## Architecture

```
lsspy/
├── backend/
│   ├── main.py           # FastAPI app, WebSocket handler
│   ├── watcher.py        # File system watcher (watchdog)
│   ├── readers/
│   │   ├── runtime.py    # SQLite reader (agents, leases, messages, events)
│   │   └── spec.py       # YAML spec reader (tasks, dependencies)
│   ├── models.py         # Pydantic models for API responses
│   └── static/           # Embedded frontend build
├── frontend/             # React app (built separately, embedded at release)
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── AgentPanel.tsx
│   │   │   ├── TaskBoard.tsx
│   │   │   ├── DependencyGraph.tsx
│   │   │   ├── LeaseMonitor.tsx
│   │   │   ├── MessageFeed.tsx
│   │   │   ├── EventTimeline.tsx
│   │   │   └── StatusBar.tsx
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts
│   │   ├── stores/
│   │   │   └── dataStore.ts
│   │   └── App.tsx
│   └── vite.config.ts
└── cli.py                # CLI entry point
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    .lodestar/ directory                      │
│  ┌──────────────┐              ┌──────────────────────────┐  │
│  │  spec.yaml   │              │    runtime.sqlite        │  │
│  │  (tasks)     │              │  (agents, leases, msgs)  │  │
│  └──────┬───────┘              └────────────┬─────────────┘  │
└─────────┼──────────────────────────────────┼────────────────┘
          │                                   │
          │         watchdog events           │
          ▼                                   ▼
    ┌─────────────────────────────────────────────┐
    │           LSSPY Backend (FastAPI)           │
    │  ┌─────────────┐    ┌──────────────────┐    │
    │  │ Spec Reader │    │  Runtime Reader  │    │
    │  └─────────────┘    └──────────────────┘    │
    │                  │                          │
    │           WebSocket broadcast               │
    └──────────────────┼──────────────────────────┘
                       │
                       ▼
    ┌─────────────────────────────────────────────┐
    │          Browser (React Dashboard)          │
    │  ┌─────────┐ ┌─────────┐ ┌──────────────┐   │
    │  │ Agents  │ │  Tasks  │ │  Dep Graph   │   │
    │  └─────────┘ └─────────┘ └──────────────┘   │
    │  ┌─────────┐ ┌─────────┐ ┌──────────────┐   │
    │  │ Leases  │ │Messages │ │   Timeline   │   │
    │  └─────────┘ └─────────┘ └──────────────┘   │
    └─────────────────────────────────────────────┘
```

---

## Dashboard Panels

### 1. Status Bar (Top)
- Project name and path
- Connection status (live/disconnected)
- Last update timestamp
- Quick stats: active agents, open tasks, expiring leases

### 2. Agent Panel
**Purpose**: Show all registered agents and their current status

| Column | Description |
|--------|-------------|
| Agent ID | Unique identifier (e.g., A12345678) |
| Name | Display name |
| Role | Agent role (coder, reviewer, etc.) |
| Status | Active (green), Idle (yellow), Offline (gray) |
| Current Task | Task ID if holding a lease |
| Last Seen | Relative timestamp |

**Visual elements**:
- Avatar icons with status indicators
- Sparkline showing activity over last hour
- Expandable row showing capabilities and session metadata

### 3. Task Board (Kanban-style)
**Purpose**: Visual task status at a glance

**Columns**:
- `TODO` - Tasks not yet ready
- `READY` - Claimable tasks (dependencies satisfied)
- `IN PROGRESS` - Tasks with active leases
- `DONE` - Completed, awaiting verification
- `VERIFIED` - Fully complete

**Card contents**:
- Task ID and title
- Priority badge (color-coded)
- Labels as tags
- Claiming agent avatar (if in progress)
- Lease countdown timer (if claimed)
- Dependency count indicator

**Interactions**:
- Click card to see full details in sidebar
- Filter by label, priority, or agent
- Search by task ID or title

### 4. Dependency Graph
**Purpose**: Interactive visualization of task dependencies

**Features**:
- Directed acyclic graph (DAG) layout
- Nodes colored by status
- Edges show dependency direction
- Zoom, pan, fit-to-screen controls
- Highlight critical path
- Click node to focus and show details

**Node styling**:
- `TODO`: Gray, dashed border
- `READY`: Blue, solid border
- `IN PROGRESS`: Yellow, pulsing animation
- `DONE`: Green, solid
- `VERIFIED`: Green, double border
- `BLOCKED`: Red, with warning icon

### 5. Lease Monitor
**Purpose**: Health check for active claims

**Table columns**:
- Task ID
- Agent ID
- Created at
- Expires at
- Time remaining (countdown)
- Status (healthy, warning <5min, critical <1min, expired)

**Visual elements**:
- Progress bar showing lease time consumed
- Color transitions: green → yellow → orange → red
- Toast notifications for expiring leases

### 6. Message Feed
**Purpose**: Real-time communication activity

**Features**:
- Filterable by agent or task thread
- Timestamp and sender
- Message preview with expand
- Unread indicator
- Thread grouping option

### 7. Event Timeline
**Purpose**: Audit log visualization

**Event types displayed**:
- `agent.join` - New agent registered
- `agent.heartbeat` - Agent activity
- `task.claim` - Task claimed
- `task.release` - Lease released
- `task.done` - Task completed
- `task.verify` - Task verified
- `message.send` - Message sent

**Visual**:
- Vertical timeline with icons
- Filterable by event type, agent, or task
- Relative timestamps
- Expandable event details

### 8. Statistics Panel (Collapsible)
**Purpose**: Aggregate metrics and trends

**Charts**:
- Task status distribution (donut chart)
- Tasks completed over time (line chart)
- Agent activity heatmap (hour × day)
- Lease duration histogram
- Dependency depth distribution

---

## CLI Interface

```bash
# Start the dashboard
lsspy                          # Auto-detect .lodestar in current dir
lsspy /path/to/repo            # Specify repo path
lsspy --port 8080              # Custom port (default: 5173)
lsspy --host 0.0.0.0           # Bind to all interfaces

# Options
--no-open                      # Don't auto-open browser
--poll-interval 1000           # Polling interval in ms (fallback)
--debug                        # Enable debug logging
--version                      # Show version

# Examples
lsspy .                        # Current directory
lsspy ~/projects/myapp         # Specific project
lsspy --port 3000 --no-open    # CI-friendly mode
```

---

## API Endpoints

### REST Endpoints

```
GET  /api/status              # Overall status + stats
GET  /api/agents              # List all agents
GET  /api/agents/{id}         # Agent details
GET  /api/tasks               # List all tasks
GET  /api/tasks/{id}          # Task details
GET  /api/leases              # List active leases
GET  /api/messages            # List messages (paginated)
GET  /api/events              # List events (paginated)
GET  /api/graph               # Dependency graph data
```

### WebSocket

```
WS   /ws                      # Real-time updates

# Message format (server → client)
{
  "type": "update",
  "scope": "agents" | "tasks" | "leases" | "messages" | "events" | "full",
  "data": { ... },
  "timestamp": "2025-01-01T12:00:00Z"
}

# Message format (client → server)
{
  "type": "subscribe",
  "scopes": ["agents", "tasks", "leases"]
}
```

---

## Real-time Update Strategy

### File Watching

1. **Primary**: `watchdog` library for file system events
   - Watch `runtime.sqlite` for modifications
   - Watch `spec.yaml` for modifications
   - Debounce rapid changes (100ms window)

2. **Fallback**: Polling when watchdog unavailable
   - Check file modification times every N seconds
   - Configurable interval (default: 1 second)

### Update Broadcasting

1. File change detected
2. Read affected data (SQLite query or YAML parse)
3. Compute diff from previous state (optional optimization)
4. Broadcast to all connected WebSocket clients
5. Frontend updates affected components

### SQLite Considerations

- Use `PRAGMA journal_mode=WAL` queries (read-only, non-blocking)
- Open database in read-only mode
- Handle locked database gracefully (retry with backoff)
- Parse timestamps consistently (ISO 8601)

---

## Visual Design

### Theme

- **Primary**: Dark mode (reduce eye strain for monitoring)
- **Accent color**: Lodestar blue (#3B82F6)
- **Status colors**:
  - Active/Verified: Green (#22C55E)
  - Ready/In Progress: Blue (#3B82F6)
  - Warning/Idle: Yellow (#EAB308)
  - Error/Offline: Red (#EF4444)
  - Neutral/Todo: Gray (#6B7280)

### Typography

- **Headings**: Inter (or system font stack)
- **Monospace**: JetBrains Mono (task IDs, timestamps)

### Layout

- Responsive grid layout
- Collapsible sidebar for panel selection
- Full-screen mode for dependency graph
- Keyboard shortcuts for common actions

### Animations

- Smooth transitions for status changes
- Pulse animation for active leases
- Fade in/out for new items
- Graph layout transitions

---

## Package Structure

```
lsspy/
├── pyproject.toml
├── README.md
├── src/
│   └── lsspy/
│       ├── __init__.py
│       ├── __main__.py        # CLI entry
│       ├── cli.py             # Click/Typer CLI
│       ├── server.py          # FastAPI app
│       ├── watcher.py         # File watcher
│       ├── readers/
│       │   ├── __init__.py
│       │   ├── runtime.py     # SQLite queries
│       │   └── spec.py        # YAML parser
│       ├── models.py          # Pydantic models
│       └── static/            # Embedded frontend
│           └── index.html     # Built React app
├── frontend/                  # Source (not in wheel)
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── components/
│       ├── hooks/
│       ├── stores/
│       ├── types/
│       └── styles/
└── tests/
    ├── test_readers.py
    ├── test_watcher.py
    └── test_api.py
```

---

## Dependencies

### Python (Backend)

```toml
[project]
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "watchdog>=4.0.0",
    "pyyaml>=6.0",
    "pydantic>=2.0",
    "typer>=0.9.0",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.26.0",
    "ruff>=0.1.0",
]
```

### JavaScript (Frontend)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "recharts": "^2.12.0",
    "reactflow": "^11.10.0",
    "zustand": "^4.5.0",
    "date-fns": "^3.3.0",
    "clsx": "^2.1.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.3.0",
    "vite": "^5.1.0"
  }
}
```

---

## Build & Release

### Development

```bash
# Backend
cd lsspy
uv sync
uv run lsspy --debug /path/to/repo

# Frontend (separate terminal)
cd lsspy/frontend
npm install
npm run dev
```

### Production Build

```bash
# Build frontend
cd frontend
npm run build
# Output: dist/index.html (single file with inlined assets)

# Copy to package
cp dist/* ../src/lsspy/static/

# Build Python package
uv build
```

### Distribution

- PyPI: `pip install lsspy`
- Single package includes embedded frontend
- No Node.js required for end users

---

## Milestones

### M0 - Foundation (Days 1-2)
- Project scaffolding (pyproject.toml, frontend setup)
- FastAPI skeleton with static file serving
- Basic CLI with `--port` and `--path` options
- SQLite reader for agents and tasks

### M1 - Core Dashboard (Days 3-5)
- React app with routing
- Agent panel with status
- Task board (basic Kanban)
- WebSocket connection
- File watcher integration

### M2 - Visualizations (Days 6-8)
- Dependency graph (React Flow)
- Lease monitor with countdowns
- Message feed
- Real-time updates working

### M3 - Polish (Days 9-10)
- Event timeline
- Statistics panel with charts
- Dark mode styling
- Keyboard shortcuts
- Error handling and edge cases

### M4 - Release (Days 11-12)
- Frontend production build
- Embedded static files
- PyPI packaging
- Documentation
- GitHub release

---

## Success Criteria

1. `pip install lsspy && lsspy` works out of the box
2. Dashboard loads in <2 seconds
3. Updates appear within 500ms of file change
4. Works with repos containing 100+ tasks
5. Memory usage <100MB for typical repos
6. Zero configuration required for basic use

---

## Future Considerations (v2+)

- **Multi-repo view**: Aggregate multiple projects
- **Notifications**: Desktop notifications for events
- **Themes**: Light mode, custom themes
- **Export**: PNG/SVG export of graphs
- **Filters**: Save and share filter configurations
- **History**: Time-travel through past states
- **Annotations**: Add notes to tasks from dashboard
- **Integration**: Slack/Discord webhooks for events

---

## Open Questions

1. **Embedded vs. separate frontend?**
   - Embedded (single pip install) vs. separate npm package
   - Recommendation: Embedded for v1 simplicity

2. **Update granularity?**
   - Full refresh vs. incremental diffs
   - Recommendation: Full refresh for v1, optimize later if needed

3. **SQLite locking?**
   - How to handle if lodestar is actively writing
   - Recommendation: Read-only mode with retry, WAL compatible

4. **Browser support?**
   - Modern browsers only (Chrome, Firefox, Safari, Edge)
   - No IE11 support

---

## Appendix: Data Models

### API Response: Status

```json
{
  "project": {
    "name": "lodestar-demo",
    "path": "/home/user/projects/demo",
    "default_branch": "main"
  },
  "stats": {
    "agents": {
      "total": 3,
      "active": 2,
      "idle": 1,
      "offline": 0
    },
    "tasks": {
      "total": 25,
      "todo": 5,
      "ready": 8,
      "in_progress": 4,
      "done": 5,
      "verified": 3
    },
    "leases": {
      "active": 4,
      "expiring_soon": 1
    }
  },
  "last_event": "2025-01-01T12:30:00Z"
}
```

### API Response: Agent

```json
{
  "agent_id": "A12345678",
  "display_name": "Claude-1",
  "role": "coder",
  "status": "active",
  "created_at": "2025-01-01T10:00:00Z",
  "last_seen_at": "2025-01-01T12:30:00Z",
  "capabilities": ["python", "typescript", "testing"],
  "session_meta": {
    "tool": "claude-code",
    "model": "claude-3-opus"
  },
  "current_lease": {
    "task_id": "T001",
    "expires_at": "2025-01-01T12:45:00Z"
  }
}
```

### API Response: Task

```json
{
  "id": "T001",
  "title": "Implement user authentication",
  "description": "Add JWT-based auth to the API",
  "status": "in_progress",
  "priority": 10,
  "labels": ["backend", "security"],
  "depends_on": [],
  "dependents": ["T002", "T003"],
  "acceptance_criteria": [
    "Users can register with email/password",
    "JWT tokens issued on login",
    "Protected routes require valid token"
  ],
  "created_at": "2025-01-01T09:00:00Z",
  "updated_at": "2025-01-01T12:00:00Z",
  "lease": {
    "agent_id": "A12345678",
    "expires_at": "2025-01-01T12:45:00Z",
    "time_remaining_seconds": 900
  }
}
```

### WebSocket Message: Update

```json
{
  "type": "update",
  "scope": "leases",
  "timestamp": "2025-01-01T12:30:05Z",
  "data": {
    "leases": [
      {
        "lease_id": "L87654321",
        "task_id": "T001",
        "agent_id": "A12345678",
        "expires_at": "2025-01-01T12:45:00Z"
      }
    ]
  }
}
```
