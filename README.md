# Tenant-VLite

Tenant-VLite is an Agentic LLM based system that utilizes RAG based mechanics for dynamic information retrieval from a massive database of users. It is designed for customer service and QA operations on user management platforms. It acts as a virtual agent that can look up accounts, traverse organizational hierarchies, generate reports, and verify compliance using natural language.

## Architecture

The system uses a multi-process architecture communicating via ZeroMQ:
- **WebUI**: React frontend for chatting
- **API Gateway (`api.py`)**: FastAPI server handling HTTP/SSE
- **Brain (`v-aws.py`)**: AWS Bedrock integration that processes queries and orchestrates tools
- **Workers**:
  - `reader.py`: Reads markdown manuals to understand available tools
  - `executor.py`: Executes Python scripts to query the JSON database
  - `context.py`: Manages long-term memory across conversations

## Setup & Run

### Prerequisites
- Python 3.8+
- Node.js 16+
- AWS Account with Bedrock access (Kimi K2.5 model)

### Quick Start

**macOS/Linux:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows:**
```cmd
setup.bat
```

The setup scripts will create a virtual environment, install dependencies, prompt for AWS credentials, and start the system.

### Manual Start
If you've already run the setup script once, you can start the system directly using two terminals:

**Terminal 1 (Backend):**
```bash
source venv/bin/activate  # Or venv\Scripts\activate on Windows
python scripts/tenant.py
```

**Terminal 2 (Frontend):**
```bash
cd webui
npm run dev
```

The application will be available at:
- Frontend: http://localhost:3000
- API: http://localhost:5000

## How It Works

1. User asks a question in the WebUI.
2. The AI Brain (AWS Bedrock) decides if it needs data.
3. If yes, it asks the Reader to fetch a tool manual from `function-archive/`.
4. The AI then formats a query and sends it to the Executor.
5. The Executor runs the corresponding script in `executor-archive/` against the database.
6. The AI reads the result and streams the final answer back to the user.

## Adding New Capabilities

1. Add a markdown manual in `function-archive/` describing the new tool.
2. Add the corresponding Python execution script in `executor-archive/`.
3. The AI will automatically discover and use the new tool when relevant.
