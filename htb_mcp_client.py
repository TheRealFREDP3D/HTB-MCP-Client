#!/usr/bin/env python3
"""
HackTheBox MCP Client
A Textual-based TUI client for the HackTheBox Model Context Protocol server.
"""

__version__ = "1.1.0"
__author__ = "Fred P3D"
__license__ = "MIT"

import asyncio
import os
import sys
import traceback

try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    from dotenv import dotenv_values
except ImportError:
    print("Error: Dependencies not installed. Install with: pip install -r requirements.txt")
    sys.exit(1)

from client import HTBMCPClient
from app import HTBMCPApp


async def main():
    config = dotenv_values()
    api_token = os.getenv("API_ACCESS_TOKEN") or config.get("API_ACCESS_TOKEN")
    url = os.getenv("HTB_MCP_URL") or config.get("HTB_MCP_URL", "https://mcp.hackthebox.ai/v1/ctf/mcp/")

    if not api_token:
        print("Error: API_ACCESS_TOKEN not set. Please set it in .env or as an environment variable.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {api_token}"}

    try:
        async with streamablehttp_client(url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                client_helper = HTBMCPClient(session)
                app = HTBMCPApp(client_helper)
                await app.run_async()
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
