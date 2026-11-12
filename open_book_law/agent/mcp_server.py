"""Serve the tools over MCP on this machine, by HTTP because loading is slow. Args: library retriever."""

import sys

from mcp.server.mcpserver import MCPServer

from open_book_law.agent.tools import open_tools

server = MCPServer("open-book")
for function in open_tools(*sys.argv[1:3]).values():
    server.tool()(function)
server.run("streamable-http", host="127.0.0.1", port=8765)
