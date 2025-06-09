# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gemini MCP Server is a Model Context Protocol (MCP) server that integrates Google's Gemini 2.5 Pro AI model with Claude. It provides specialized development tools that leverage Gemini's 1M token context window for enhanced code analysis, debugging, and architectural discussions.

## Common Development Commands

### Setup and Installation
```bash
# Initial setup (creates venv and installs dependencies)
./setup.sh  # macOS/Linux
setup.bat   # Windows

# Manual virtual environment activation if needed
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```

### Running Tests
```bash
# Run unit tests (no API key required)
python -m pytest tests/ --ignore=tests/test_live_integration.py -v

# Run with coverage report
python -m pytest tests/ --ignore=tests/test_live_integration.py --cov=. --cov-report=html

# Run specific test file
python -m pytest tests/test_server.py -v

# Run live integration tests (requires GEMINI_API_KEY)
export GEMINI_API_KEY=your-key-here
python tests/test_live_integration.py
```

### Code Quality
```bash
# Format code
black .

# Lint code
ruff check .

# Type checking (if mypy is added)
mypy . --ignore-missing-imports
```

## Architecture and Key Design Patterns

### Core Architecture
The server follows a plugin-based architecture with these key components:

1. **MCP Server (`server.py`)**: Main entry point handling MCP protocol communication via stdio
2. **Tool System**: Each tool inherits from `BaseTool` (abstract base class pattern)
3. **Request/Response Models**: Pydantic models in `tools/models.py` ensure type safety
4. **Prompt Management**: Centralized system prompts in `prompts/tool_prompts.py`

### Tool Implementation Pattern
All tools follow this workflow:
1. Inherit from `BaseTool` in `tools/base.py`
2. Implement `execute()` method for tool logic
3. Override `get_system_prompt()` to customize behavior
4. Use Pydantic models for request validation
5. Return standardized JSON responses

### Security Considerations
- All file paths must be absolute (enforced in `BaseTool.validate_and_read_files()`)
- Optional sandboxing via `MCP_PROJECT_ROOT` environment variable
- Automatic filtering of sensitive files (e.g., `.env`, `.git`)

### Adding New Tools
1. Create new file in `tools/` directory
2. Define request/response models in `tools/models.py`
3. Add system prompt to `prompts/tool_prompts.py`
4. Register tool in `TOOLS` dict in `server.py`

Example:
```python
# tools/my_tool.py
from tools.base import BaseTool
from tools.models import MyToolRequest

class MyTool(BaseTool):
    def execute(self, request: MyToolRequest) -> dict:
        # Tool implementation
        pass
```

### Testing Strategy
- **Unit tests**: Mock Gemini API responses for CI/CD compatibility
- **Live tests**: Separate file for actual API integration testing
- **Fixtures**: Shared test fixtures in `tests/conftest.py`
- **Coverage**: Aim for high coverage, especially for tool logic

## Development Guidelines

### When modifying tools:
1. Always validate file paths are absolute
2. Use appropriate thinking modes (minimal to max) based on task complexity
3. Handle dynamic context requests for better analysis
4. Return standardized JSON responses with proper status codes

### When working with prompts:
1. Edit `prompts/tool_prompts.py` for global prompt changes
2. Use temperature settings from `config.py` appropriately
3. Test prompt changes with both unit and live tests

### Error handling:
1. Tools should gracefully handle missing files
2. Provide informative error messages in response content
3. Use proper status codes: "success", "error", "requires_clarification"