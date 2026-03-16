# Tenant-VLite

An AI-powered chatbot system for customer service and QA operations on user management platforms. Tenant-VLite acts as a virtual "service QA employee" that can look up user accounts, traverse organizational hierarchies, generate reports, and verify compliance through natural language conversations.

## Architecture Overview

Tenant-VLite uses a **multi-process, event-driven architecture** with **ZeroMQ (ZMQ)** for inter-process communication:

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER (Browser)                            │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────────────────┐
│  WebUI (React + Vite) - Port 3000                               │
│  - Chat interface with streaming responses                      │
└──────────────────────┬──────────────────────────────────────────┘
                       │ Proxy to /api
┌──────────────────────▼──────────────────────────────────────────┐
│  API Gateway (FastAPI + Uvicorn) - Port 5000                    │
│  - Handles chat history, SSE streaming                          │
└──────────────────────┬──────────────────────────────────────────┘
                       │ ZMQ ROUTER/DEALER (port 5557)
┌──────────────────────▼──────────────────────────────────────────┐
│  BRAIN (v-aws.py)                                               │
│  - AWS Bedrock integration (moonshotai.kimi-k2.5)               │
│  - ZMQ PUB socket (port 5555) - broadcasts to observers         │
│  - ZMQ PULL socket (port 5556) - receives tool results          │
└──────────────────────┬──────────────────────────────────────────┘
                       │ ZMQ PUB (port 5555)
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌─────────────┐ ┌──────────────┐
│   READER     │ │  EXECUTOR   │ │   CONTEXT    │
│  (reader.py) │ │ (executor.  │ │  (context.py)│
│  Reads .md   │ │     py)     │ │  Extracts    │
│  manuals     │ │ Executes DB │ │  <CONTEXT>   │
└──────────────┘ │  scripts    │ │   tags       │
               └─────────────┘ └──────────────┘
```

## System Components

### Core Backend Services (`scripts/`)

| File | Purpose |
|------|---------|
| `tenant.py` | **Main orchestrator** - starts and manages all subprocesses |
| `v-aws.py` | **AI Brain** - AWS Bedrock integration, ZMQ routing, tool execution loops |
| `api.py` | **API Gateway** - FastAPI server with REST endpoints and SSE streaming |
| `reader.py` | **Manual Reader** - Reads markdown manuals for LLM tool guidance |
| `executor.py` | **Function Executor** - Executes database scripts with circuit breaker protection |
| `context.py` | **Memory Manager** - Extracts and persists `<CONTEXT>` tags to chat history |
| `onboard.py` | **Setup Wizard** - Interactive AWS credential configuration |

### Frontend (`webui/`)

| File | Purpose |
|------|---------|
| `App.jsx` | Main React component - chat UI, streaming, history sidebar |
| `index.css` | Complete styling (1655+ lines of custom CSS) |
| `main.jsx` | React application entry point |
| `vite.config.js` | Vite configuration with API proxy |

### Data & Function Archives

| Directory | Purpose |
|-----------|---------|
| `function-archive/` | **5 Markdown manuals** describing available AI tools |
| `executor-archive/` | **5 Python scripts** that execute database queries |
| `database/` | **tenant_dev.users.json** - Mock user database (~18MB) |
| `history/` | Chat conversation storage (JSON files per conversation) |

## Key Features

### AI-Powered Database Operations
The system uses **AWS Bedrock** (Kimi K2.5 model) to process natural language queries and execute database operations through a tool-calling architecture:

- **Account Lookup** - Query single user accounts and profiles
- **Hierarchy Management** - Traverse parent/child relationships, ancestors, descendants
- **Aggregation & Reporting** - Generate counts and summary reports
- **Compliance Verification** - Check compliance status
- **System Integrity** - Verify system health

### Smart Tool System

1. **Phase 1 - Knowledge Retrieval**: `read(category)` commands fetch relevant manual markdown files
2. **Phase 2 - Execution**: `<FUNCTION_CALL>` blocks trigger Python scripts on the database
3. **Circuit Breaker**: Prevents LLM context overflow by rejecting payloads >16,000 characters

### Long-term Memory
The LLM writes rolling diary summaries using `<CONTEXT>` tags that persist across conversations, enabling multi-session continuity.

### Real-time Streaming
Responses stream to the frontend via **Server-Sent Events (SSE)** for a responsive chat experience.

## Prerequisites

- Python 3.8+
- Node.js 16+
- AWS Account with Bedrock access
- AWS credentials (Access Key ID and Secret Access Key)

## Installation

### Quick Start (macOS/Linux)

```bash
chmod +x setup.sh
./setup.sh
```

### Quick Start (Windows)

```cmd
setup.bat
```

### Manual Setup

1. **Create and activate Python virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure AWS credentials (first run):**
   ```bash
   python scripts/onboard.py
   ```

4. **Install frontend dependencies:**
   ```bash
   cd webui
   npm install
   cd ..
   ```

5. **Start the application:**
   ```bash
   python scripts/tenant.py
   ```

## Usage

Once started, the system runs on:

- **WebUI**: http://localhost:3000
- **API**: http://localhost:5000

### Example Queries

- "Find user with email john@example.com"
- "Show me all children of organization ID 12345"
- "Get ancestors for user ID 67890"
- "How many active users are in the system?"
- "Check compliance status for org ABC"

## ZMQ Communication Ports

| Port | Socket Type | Purpose |
|------|-------------|---------|
| 5555 | PUB/SUB | Brain broadcasts messages to observers |
| 5556 | PUSH/PULL | Observers send tool results back to Brain |
| 5557 | ROUTER/DEALER | API Gateway ↔ Brain bidirectional communication |

## Project Structure

```
Tenant-VLite/
├── scripts/              # Python backend services
│   ├── tenant.py         # Main orchestrator
│   ├── v-aws.py          # AI brain (AWS Bedrock)
│   ├── api.py            # FastAPI gateway
│   ├── reader.py         # Manual file reader
│   ├── executor.py       # Database script executor
│   ├── context.py        # Memory/context manager
│   ├── onboard.py        # AWS setup wizard
│   └── aws_credentials.json  # AWS credentials (gitignored)
├── webui/                # React frontend
│   ├── src/
│   │   ├── App.jsx       # Main chat interface
│   │   ├── main.jsx      # Entry point
│   │   └── index.css     # Styling
│   ├── package.json      # Node dependencies
│   └── vite.config.js    # Vite configuration
├── function-archive/     # LLM tool manuals (.md)
│   ├── account_lookup.md
│   ├── hierarchy_management.md
│   ├── aggregation.md
│   ├── compliance.md
│   └── system_integrity.md
├── executor-archive/     # Database query scripts (.py)
│   ├── account_lookup.py
│   ├── hierarchy_management.py
│   ├── aggregation.py
│   ├── compliance.py
│   └── system_integrity.py
├── database/             # Data storage
│   └── tenant_dev.users.json
├── history/              # Chat conversation storage
├── requirements.txt      # Python dependencies
├── setup.sh             # macOS/Linux setup
├── setup.bat            # Windows setup
└── .gitignore
```

## Technology Stack

| Category | Technologies |
|----------|--------------|
| **Backend** | Python 3, FastAPI, Uvicorn, ZeroMQ (PyZMQ), Boto3 |
| **AI/LLM** | AWS Bedrock (moonshotai.kimi-k2.5) |
| **Frontend** | React 18, Vite, React Markdown, Lottie Web |
| **Database** | JSON file-based |
| **Communication** | ZMQ, Server-Sent Events |
| **Build Tools** | Vite, pip |

## Dependencies

### Python (`requirements.txt`)
- fastapi
- uvicorn
- python-multipart
- pyzmq
- tornado>=6.1
- boto3
- httpx
- groq
- pydantic==2.12.5

### Frontend (`webui/package.json`)
- react, react-dom
- react-markdown, remark-gfm
- lottie-web
- vite

## Security Notes

- `aws_credentials.json` is excluded from Git via `.gitignore`
- Never commit AWS credentials to version control
- The `onboard.py` script helps securely configure credentials locally

## Troubleshooting

### Port Conflicts
If ports 3000, 5000, 5555-5557 are in use, the system may fail to start. Check for other running processes.

### ZMQ Connection Issues
Ensure all components start in the correct order via `tenant.py` - it orchestrates the startup sequence.

### AWS Bedrock Errors
Verify your AWS credentials in `scripts/aws_credentials.json` and ensure your account has Bedrock access enabled.

## Development

### Adding New Tools

1. Create a manual in `function-archive/` describing the tool
2. Create an executor script in `executor-archive/`
3. The system will automatically detect and use them via the tool-calling architecture

### Modifying the Frontend

```bash
cd webui
npm run dev    # Development server
npm run build  # Production build
```

## License

[Your License Here]

## Author

PanosEZ
