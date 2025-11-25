# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-11-23

### Added
- **Textual TUI Interface** - Complete rewrite from CLI to Terminal User Interface
- **Event Selection Screen** - Split-panel interface for browsing and selecting CTF events
  - Left panel: Event list with ID and Name
  - Right panel: Detailed event information in Markdown
  - Arrow key navigation and Enter to select
  - Selected event displayed in main menu
- **Challenge Selection Screen** - Browse and select CTF challenges
  - Table view with ID, Name, Difficulty, and Points
  - Detailed challenge information panel
  - Challenge selection stored in app state
  - Auto-population of challenge IDs in tool arguments
- **Tool Execution Interface** - Visual argument schema display
  - DataTable showing argument names, types, requirements, and descriptions
  - JSON template generation from schema
  - Auto-fill functionality for event and challenge IDs
  - TextArea with JSON syntax highlighting for argument input
- **Result Display System** - Markdown-formatted results with typewriter animation
  - JSON to Markdown conversion
  - Smooth line-by-line reveal animation
  - Scrollable result viewing
  - Hacker-themed green-on-black aesthetic
- **Export Functionality** - Save results to files
  - Save as JSON with full data structure
  - Save as Markdown with formatted output
  - Timestamped filenames
  - Auto-save challenges data
- **MCP Integration** - Full HackTheBox Model Context Protocol support
  - Streamable HTTP client connection
  - Tool listing and execution
  - Resource reading
  - Authentication via Bearer token
- **State Management** - Persistent selection across screens
  - Selected event stored and displayed
  - Selected challenge stored and auto-filled
  - Automatic challenge data loading from saved files

### Changed
- Migrated from CLI to Textual TUI framework
- Replaced InquirerPy prompts with native Textual widgets
- Improved visual design with custom CSS styling

### Technical Details
- Python 3.10+ required
- Dependencies: mcp, httpx, python-dotenv, textual
- Configuration via `.env` file
- Output directory: `htb_mcp_output/`

[1.0.0]: https://github.com/therealfredp3d/HTB-MCP-Client/releases/tag/v1.0.0
