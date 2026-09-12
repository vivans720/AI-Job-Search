# Hermes + OmniRoute Inspection Report

## System Environment
- **OS**: macOS (darwin-arm64)
- **Node**: v24.19.0
- **Python**: 3.14.7
- **Docker**: 29.7.2 with Docker Compose v5.4.0 (running)

## OmniRoute Configuration
- **Process**: `omniroute (v16.3.1)` active on port `20128`
- **Base URL**: `http://localhost:20128/v1`
- **Auth Key**: Read from `~/.omniroute/.env` / `~/.hermes/.env` (masked `sk-placeholder-omniroute-key`)
- **Protocol**: OpenAI-compatible REST API (`/v1/chat/completions`, `/v1/models`)
- **Models Available**: Catalog across providers (OpenAI, Anthropic, Gemini, Groq, SiliconFlow, Qwen, DeepSeek, etc.)

## Hermes Agent Configuration
- **Install Path**: `~/.hermes`
- **Binary**: `~/.hermes/hermes-agent/venv/bin/hermes`
- **Configuration**: `~/.hermes/config.yaml`
- **Model Configured**: Custom provider pointing to `http://localhost:20128/v1` with `auto/best-coding`
- **MCP Mechanism**: Built-in CLI command `hermes mcp add <name> --command <cmd> --args <args...>` or `hermes mcp add <name> --url <endpoint>`
- **Current MCP Servers**: 0 configured in `hermes mcp list`

## Integration Blueprint
- **LLM Provider in Backend**: Standard `openai` SDK pointing to `http://localhost:20128/v1` with key from `.env`.
- **MCP Server**: FastMCP exposed via stdio/SSE, registered to Hermes using `hermes mcp add`.
