"""
Network-based MCP Server using FastAPI and SSE transport

This module provides an HTTP/SSE-based MCP server implementation that allows
the Gemini MCP Server to be accessed over the network instead of stdio.
This enables usage without Claude Desktop and supports any MCP client that
can communicate over HTTP/SSE.

The server provides:
- SSE endpoint for server-to-client streaming at /sse
- POST endpoint for client-to-server messages at /messages
- No authentication (local use only)
- Full access to all existing tools
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import JSONRPCMessage, JSONRPCRequest, JSONRPCResponse
from sse_starlette.sse import EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware

from config import (
    GEMINI_MODEL,
    MAX_CONTEXT_TOKENS,
    __author__,
    __updated__,
    __version__,
)
from server import TOOLS, configure_gemini, handle_call_tool, handle_list_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server instance
mcp_server = Server("gemini-server")

# Register the existing handlers
mcp_server.list_tools()(handle_list_tools)
mcp_server.call_tool()(handle_call_tool)

# Store active SSE connections
connections: Dict[str, asyncio.Queue] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown.
    """
    # Startup
    logger.info(f"Starting Gemini MCP Server (Network Mode) v{__version__}")
    configure_gemini()
    yield
    # Shutdown
    logger.info("Shutting down Gemini MCP Server")


# Create FastAPI app
app = FastAPI(
    title="Gemini MCP Server",
    description="Network-accessible MCP server powered by Google's Gemini models",
    version=__version__,
    lifespan=lifespan,
)

# Add CORS middleware to allow Claude Code to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with server information."""
    return {
        "name": "Gemini MCP Server",
        "version": __version__,
        "transport": "sse",
        "endpoints": {
            "sse": "/sse",
            "messages": "/messages/{connection_id}",
        },
        "tools": list(TOOLS.keys()) + ["get_version"],
    }


@app.get("/sse")
async def handle_sse(request: Request):
    """
    SSE endpoint for server-to-client streaming.
    
    This endpoint establishes a Server-Sent Events connection that allows
    the server to push messages to the client. Each client gets a unique
    connection ID that is used to route messages.
    """
    # Generate unique connection ID
    connection_id = f"conn_{datetime.now().timestamp()}"
    
    # Create message queue for this connection
    message_queue = asyncio.Queue()
    connections[connection_id] = message_queue
    
    async def event_generator():
        """Generate SSE events from the message queue."""
        try:
            # Send endpoint information to client (MCP SSE format)
            # Get the base URL from the request
            base_url = f"{request.url.scheme}://{request.url.netloc}"
            yield {
                "event": "endpoint",
                "data": f"{base_url}/messages/{connection_id}",
            }
            
            # Send messages from queue
            while True:
                try:
                    message = await asyncio.wait_for(message_queue.get(), timeout=30.0)
                    if message is None:  # Shutdown signal
                        break
                    yield {
                        "event": "message",
                        "data": json.dumps(message),
                    }
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {
                        "event": "ping",
                        "data": "keepalive",
                    }
        finally:
            # Clean up connection
            connections.pop(connection_id, None)
            logger.info(f"SSE connection closed: {connection_id}")
    
    logger.info(f"SSE connection established: {connection_id}")
    return EventSourceResponse(event_generator())


@app.post("/messages/{connection_id}")
async def handle_messages(connection_id: str, request: Request):
    """
    POST endpoint for client-to-server messages.
    
    Clients send JSON-RPC messages to this endpoint, which are processed
    by the MCP server and responses are sent back via the SSE connection.
    """
    try:
        # Parse request body (should be the JSON-RPC message directly)
        message = await request.json()
        
        if not message:
            return Response(
                content=json.dumps({"error": "Missing message"}),
                status_code=400,
                media_type="application/json",
            )
        
        # Get connection queue
        message_queue = connections.get(connection_id)
        if not message_queue:
            return Response(
                content=json.dumps({"error": "Invalid connectionId"}),
                status_code=404,
                media_type="application/json",
            )
        
        # Process the message based on its type
        if message.get("method") == "initialize":
            # Handle initialization
            response = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                    },
                    "serverInfo": {
                        "name": "gemini-server",
                        "version": __version__,
                    },
                },
            }
            await message_queue.put(response)
        
        elif message.get("method") == "tools/list":
            # Handle tool listing
            tools = await handle_list_tools()
            response = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema,
                        }
                        for tool in tools
                    ]
                },
            }
            await message_queue.put(response)
        
        elif message.get("method") == "tools/call":
            # Handle tool execution
            params = message.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            try:
                result = await handle_call_tool(tool_name, arguments)
                response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": content.text,
                            }
                            for content in result
                        ]
                    },
                }
            except Exception as e:
                response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {
                        "code": -32603,
                        "message": str(e),
                    },
                }
            
            await message_queue.put(response)
        
        else:
            # Unknown method
            response = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {message.get('method')}",
                },
            }
            await message_queue.put(response)
        
        return Response(
            content=json.dumps({"status": "ok"}),
            media_type="application/json",
        )
        
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        return Response(
            content=json.dumps({"error": str(e)}),
            status_code=500,
            media_type="application/json",
        )


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )