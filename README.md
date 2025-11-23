# HackTheBox MCP Client

A Python client for interacting with the HackTheBox Model Context Protocol (MCP) server.

## Features

- 🔌 Connect to HackTheBox MCP server using Streamable HTTP
- 📋 List available tools, resources, and prompts
- 🔧 Call tools with custom arguments
- 📖 Read resources from the server
- 💬 Interactive menu-driven interface
- 🧙 **NEW**: Tool Argument Wizard - Guided argument collection with JSON Schema support
- 🔄 **NEW**: Live Server Data Reload - Caching with 5-minute TTL
- 💾 **NEW**: Auto-save results to file with sanitized filenames

## Prerequisites

- Python 3.10 or later
- HackTheBox API access token (JWT)

## Installation

1. **Install dependencies:**

   ```powershell
   # We now use python-dotenv and InquirerPy for enhanced UX
   pip install -r requirements.txt

````

Or using `uv`:

```powershell
uv pip install -r requirements.txt
```

2.  **Set your API token:**

    The client requires your HackTheBox API access token. The recommended way is to create a **`.env`** file in the same directory as `htb_mcp_client.py`.

    **Create a `.env` file:**

    ```env
    API_ACCESS_TOKEN=your-very-long-jwt-token-here
    # Optional: uncomment and change if you're connecting to a different endpoint
    # HTB_MCP_URL=https://mcp.hackthebox.ai/v1/ctf/mcp/
    ```

    Alternatively, you can still use environment variables (they will take precedence over the `.env` file):

    **Windows PowerShell:**

    ```powershell
    $env:API_ACCESS_TOKEN="your-hackthebox-jwt-token-here"
    ```

    **Linux/Mac:**

    ```bash
    export API_ACCESS_TOKEN="your-hackthebox-jwt-token-here"
    ```

    You can find your token in the `.mcp.json` file or generate a new one from your HackTheBox profile settings.

## Usage

### Run the Interactive Client

```powershell
python htb_mcp_client.py
```

### Interactive Menu

Once connected, you'll see an interactive menu:

```
🎯 HackTheBox MCP Client - Interactive Menu
================================================================================
1. List available tools
2. List available resources
3. List available prompts
4. Call a tool
5. Read a resource
6. Refresh server data
7. Exit
================================================================================
⚡ Cache last refreshed: Never
```

### Menu Options

1.  **List available tools** - Shows all tools provided by the HackTheBox MCP server
2.  **List available resources** - Shows all resources (challenges, machines, etc.)
3.  **List available prompts** - Shows available prompt templates
4.  **Call a tool** - Execute a tool with wizard-guided or manual JSON arguments
5.  **Read a resource** - Fetch a resource by its URI
6.  **Refresh server data** - Update cached tools/resources/prompts from server
7.  **Exit** - Close the client

### Feature Highlights

#### Tool Argument Wizard

When calling a tool (option 4), you can use the interactive wizard:

```
Enter tool name: search_writeups
Use argument wizard? (Y/n): y

🧙 Tool Argument Wizard for: search_writeups
machine_name (required): Target machine name
  → Lame
difficulty (optional): Easy/Medium/Hard
  → Easy

✅ Arguments collected
```

The wizard automatically:
- Parses the tool's JSON Schema
- Creates appropriate prompts for each argument type (string, number, boolean, array)
- Validates required fields
- Provides helpful descriptions

#### Auto-Save Results

After every tool call or resource read, you'll be prompted to save:

```
💾 Save to file? (Y/n): y
File name [tool_search_writeups_20251121_200530.json]: 
✅ Saved to: D:\...\htb_mcp_output\tool_search_writeups_20251121_200530.json
```

Files are saved to `htb_mcp_output/` with:
- Sanitized filenames (invalid characters removed)
- Automatic timestamp suffixes
- UTF-8 encoding for international characters

#### Live Server Data Reload

Refresh server metadata without restarting:

```
Enter your choice (1-7): 6

🔄 Refreshing server data...
✅ Refreshed server data:
   - Tools: 12
   - Resources: 8
   - Prompts: 5
   - Cache timestamp: 2025-11-21 20:05:30
```

Cache age is displayed in the menu and refreshes are intelligent (5-minute TTL).

### Example: Calling a Tool

When you select option 4, you'll be prompted:
