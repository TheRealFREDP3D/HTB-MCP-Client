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

```text
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
├── doc/                    # Documentation and screenshots
├── htb_mcp_output/         # Saved tool output files (auto-created at runtime)
├── htb_mcp_state.json      # Persisted session state (auto-created at runtime)
├── .env                    # API credentials (never commit this)
├── .env.example            # Environment variables template
├── pyproject.toml          # Project configuration and dependencies
├── requirements.txt        # Python dependencies
├── CHANGELOG.md            # Version history
├── CONTRIBUTING.md         # Contribution guidelines
├── PROJECT_OVERVIEW.md     # Detailed project documentation
├── ROADMAP.md              # Future plans
└── HTB-MCP-Client-Banner.png # Project banner
```

## Requirements

- Python 3.10+
- HackTheBox account with API access token
- uv (recommended) or pip for package management

## Installation

### Using uv (recommended)

```bash
uv sync
```

### Using pip

```bash
pip install -r requirements.txt
```

Or install from pyproject.toml:

```bash
pip install -e .
```

## Configuration

Copy the example environment file and add your credentials:

```bash
copy .env.example .env
```

Then edit `.env` with your API credentials:

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

### v1.0.0
- Initial release with Textual TUI interface
- Event, team, and challenge selection screens
- Tool execution with argument schema display
- Result display with Markdown formatting
- Export functionality (JSON/Markdown)
- State persistence across sessions

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

## Security

- Proper exception handling with logging (no silent failures)
- Environment variables for sensitive credentials
- `.env` file excluded from version control
- API tokens never logged or exposed in output

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## Documentation

- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) - Detailed technical documentation
- [ROADMAP.md](ROADMAP.md) - Future development plans
- [CHANGELOG.md](CHANGELOG.md) - Version history

## License

MIT — Fred P3D
