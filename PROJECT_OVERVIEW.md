# Project Overview: HTB MCP Client

## Purpose
The HackTheBox MCP Client provides a direct, TUI-based way to interact with the HackTheBox MCP server. It bypasses the need for an LLM agent for routine tasks like listing challenges or starting containers, providing a faster and more reliable interface for CTF players.

## Core Components
- **HTBMCPClient**: Manages the MCP session, tool calls, and state persistence.
- **HTBMCPApp**: The main Textual application container.
- **Screens**:
    - `MainMenu`: Central hub with guided workflow.
    - `EventSelectionScreen`, `TeamSelectionScreen`, `ChallengeSelectionScreen`: Split-panel selectors for CTF data.
    - `PlayPage`: Dedicated screen for interacting with a specific challenge.
    - `ToolExecutionScreen`: Dynamic form generator for any MCP tool.

## Technical Details
- **Framework**: [Textual](https://textual.textualize.io/)
- **Protocol**: [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- **Language**: Python 3.10+
