# HTB-MCP-Client

A Textual-based TUI (Terminal User Interface) client for the HackTheBox Model Context Protocol (MCP) server. Built as a hobbyist Python project for learning CTF tooling, MCP integration, and terminal UI design.

## Features

- Browse and select CTF events, teams, and challenges via interactive TUI
- Execute MCP tools directly from the interface
- Start/stop Docker containers for challenges
- Download challenge files
- Persistent state across sessions (auto-saved to `htb_mcp_state.json`)
- Save challenge data to `.json` or `.md` files

## Project Structure

```
HTB-MCP-Client/
├── htb_mcp_client.py       # Entry point
├── app.py                  # HTBMCPApp (Textual App) + MainMenu screen
├── client.py               # HTBMCPClient — MCP session wrapper + state management
├── config.py               # Constants (CATEGORY_MAP, etc.)
├── screens/
│   ├── __init__.py         # Package exports
│   ├── data_list.py        # DataListScreen — browse tools/resources
│   ├── tool_screens.py     # ToolSelectionScreen, ToolExecutionScreen, ResultScreen
│   ├── challenge.py        # ChallengeSelectionScreen
│   ├── event_team.py       # EventSelectionScreen, TeamSelectionScreen
│   ├── play.py             # PlayPage — container management
│   └── help.py             # GettingStartedScreen (modal)
├── htb_mcp_output/         # Saved tool output files (auto-created at runtime)
├── htb_mcp_state.json      # Persisted session state (auto-created at runtime)
├── .env                    # API credentials (never commit this)
└── requirements.txt        # Python dependencies
```

## Requirements

- Python 3.10+
- HackTheBox account with API access token

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:

```env
API_ACCESS_TOKEN=your_htb_api_token_here
HTB_MCP_URL=https://mcp.hackthebox.ai/v1/ctf/mcp/
```

> ⚠️ Never commit your `.env` file. It is listed in `.gitignore`.

## Usage

```bash
python htb_mcp_client.py
```

### Workflow

1. **Select Event** — Choose the active CTF event
2. **Select Team** — Choose your participating team
3. **Select Challenge** — Browse and pick a challenge
4. **Play Page** — Start/stop containers, download files

## Changelog

### v1.1.0
- Refactored monolithic `htb_mcp_client.py` into modular package structure
- Split screens into dedicated modules under `screens/`
- Extracted `HTBMCPClient` to `client.py`
- Extracted constants to `config.py`
- Entry point reduced to ~35 lines

### v1.0.0
- Initial release

## License

MIT — Fred P3D
