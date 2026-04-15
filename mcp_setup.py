"""
MCP Server Setup — loads tools from HubSpot, BigQuery, and Gmail MCP servers.
Tools are automatically discovered and made available to LangGraph agents.
"""
import os
from langchain_mcp_adapters.client import MultiServerMCPClient

# MCP server configuration
# Each server runs as a subprocess (stdio transport) or connects to a remote endpoint
MCP_SERVERS = {
    "hubspot": {
        "command": "npx",
        "args": ["@hubspot/mcp-server"],
        "env": {
            "HUBSPOT_ACCESS_TOKEN": os.environ.get("HUBSPOT_ACCESS_TOKEN", ""),
        },
        "transport": "stdio",
    },
    "gmail": {
        "command": "node",
        "args": ["./gmail-mcp/dist/index.js"],  # Path to cloned gmail-mcp
        "env": {
            "GMAIL_CLIENT_ID": os.environ.get("GMAIL_CLIENT_ID", ""),
            "GMAIL_CLIENT_SECRET": os.environ.get("GMAIL_CLIENT_SECRET", ""),
        },
        "transport": "stdio",
    },
    # BigQuery: configure as stdio with local server
    "bigquery": {
        "command": "npx",
        "args": ["mcp-server-bigquery"],
        "env": {
            "GOOGLE_APPLICATION_CREDENTIALS": os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
            "BIGQUERY_PROJECT_ID": os.environ.get("BIGQUERY_PROJECT_ID", ""),
            "BIGQUERY_DATASET": os.environ.get("BIGQUERY_DATASET", ""),
        },
        "transport": "stdio",
    },
}


async def get_mcp_tools():
    """
    Start all MCP servers and return their tools as LangChain-compatible tools.
    These tools can be bound directly to a LangGraph agent via .bind_tools().
    """
    async with MultiServerMCPClient(MCP_SERVERS) as client:
        tools = client.get_tools()
        return tools


# For POC: allow selective loading if some MCP servers aren't configured
async def get_mcp_tools_safe():
    """
    Load MCP tools, skipping servers that fail to start.
    Returns whatever tools are available.
    """
    available_tools = []

    for server_name, config in MCP_SERVERS.items():
        try:
            async with MultiServerMCPClient({server_name: config}) as client:
                tools = client.get_tools()
                available_tools.extend(tools)
                print(f"Loaded {len(tools)} tools from {server_name}: {[t.name for t in tools]}")
        except Exception as e:
            print(f"Warning: Could not load {server_name} MCP server: {e}")
            print(f"Skipping {server_name} — continuing without it.")

    return available_tools
