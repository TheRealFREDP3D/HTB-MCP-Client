#!/usr/bin/env python3
"""
HackTheBox MCP Client
A Textual-based TUI client for the HackTheBox Model Context Protocol server.

Provides an interactive terminal interface for browsing CTF events and challenges,
executing tools, and managing resources from the HackTheBox MCP API.
"""

__version__ = "1.0.0"
__author__ = "Fred P3D"
__license__ = "MIT"


import asyncio
import argparse
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    from mcp.types import Tool, Resource, Prompt
    from dotenv import dotenv_values
    import pyfiglet
    
    from textual.app import App, ComposeResult
    from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
    from textual.widgets import (
        Header, Footer, Button, Label, DataTable, Input, 
        TextArea, Static, SelectionList, Select, Markdown
    )
    from textual.screen import Screen, ModalScreen
    from textual.binding import Binding
    from textual import on, work
    from textual.message import Message
except ImportError:
    print("Error: Dependencies not installed. Install with: pip install -r requirements.txt")
    sys.exit(1)


class HTBMCPClient:
    """
    Helper class to manage MCP session and data.
    Decoupled from UI logic.
    """
    def __init__(self, session: ClientSession):
        self.session = session
        self.output_dir = Path("htb_mcp_output")
        self.output_dir.mkdir(exist_ok=True)

    async def list_tools(self) -> List[Tool]:
        result = await self.session.list_tools()
        return result.tools

    async def list_resources(self) -> List[Resource]:
        result = await self.session.list_resources()
        return result.resources

    async def list_prompts(self) -> List[Prompt]:
        result = await self.session.list_prompts()
        return result.prompts

    async def call_tool(self, name: str, arguments: dict) -> Any:
        result = await self.session.call_tool(name, arguments)
        return result

    async def read_resource(self, uri: str) -> Any:
        result = await self.session.read_resource(uri)
        return result

    def save_to_file(self, data: Any, filename: str) -> str:
        filepath = self.output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            if isinstance(data, (dict, list)):
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                f.write(str(data))
        return str(filepath.absolute())


class MainMenu(Screen):
    """The main menu screen."""
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        # ASCII art banner (centered above the box)
        # Using HackTheBox green (#9FEF00) from settings.json
        ascii_banner = """\033[38;2;159;239;0m
┓┏┏┳┓┳┓  ┳┳┓┏┓┏┓  ┏┓┓ ┳┏┓┳┓┏┳┓
┣┫ ┃ ┣┫━━┃┃┃┃ ┃┃  ┃ ┃ ┃┣ ┃┃ ┃ 
┛┗ ┻ ┻┛  ┛ ┗┗┛┣┛  ┗┛┗┛┻┗┛┛┗ ┻ 
\033[0m"""
        
        # Wrap everything in a Vertical container for centering
        yield Vertical(
            Static(ascii_banner, id="ascii_banner"),
            Container(
                Label("", id="ids_display", classes="description"),
                Button("List Tools", id="btn_tools", variant="primary"),
                Button("List Resources", id="btn_resources", variant="primary"),
                Button("Call Tool", id="btn_call_tool", variant="success"),
                Button("Read Resource", id="btn_read_resource", variant="warning"),
                Button("Exit", id="btn_exit", variant="error"),
                id="main_menu_container"
            ),
            id="main_menu_wrapper"
        )
        yield Footer()

    def on_mount(self):
        self.update_ids_display()

    def update_ids_display(self):
        # Get current IDs or use ***
        event_id = "***"
        team_id = "***"
        challenge_id = "***"
        
        if hasattr(self.app, 'selected_event') and self.app.selected_event:
            event_id = str(self.app.selected_event.get('id', '***'))
        
        if hasattr(self.app, 'selected_team') and self.app.selected_team:
            team_id = str(self.app.selected_team.get('id', '***'))
        
        if hasattr(self.app, 'selected_challenge') and self.app.selected_challenge:
            challenge_id = str(self.app.selected_challenge.get('id', '***'))
        
        self.query_one("#ids_display").update(
            f"Event ID: {event_id} | Team ID: {team_id} | Challenge ID: {challenge_id}"
        )

    @on(Button.Pressed, "#btn_tools")
    def show_tools(self):
        self.app.push_screen("tools_list")

    @on(Button.Pressed, "#btn_resources")
    def show_resources(self):
        self.app.push_screen("resources_list")

    @on(Button.Pressed, "#btn_call_tool")
    def call_tool(self):
        self.app.push_screen("tool_selection")

    @on(Button.Pressed, "#btn_read_resource")
    def read_resource(self):
        # Simple input for URI for now
        self.app.push_screen("resource_input")

    @on(Button.Pressed, "#btn_exit")
    def exit_app(self):
        self.app.exit()


class DataListScreen(Screen):
    """Generic screen to display a list of items in a table."""
    
    def __init__(self, title: str, data_type: str):
        super().__init__()
        self.screen_title = title
        self.data_type = data_type

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(self.screen_title, classes="screen_title")
        yield DataTable(id="data_table")
        yield Button("Back", id="btn_back")
        yield Footer()

    def on_mount(self):
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        if self.data_type == "tools":
            table.add_columns("Name", "Description", "Schema")
            self.load_tools()
        elif self.data_type == "resources":
            table.add_columns("Name", "URI", "MIME Type")
            self.load_resources()

    @work
    async def load_tools(self):
        try:
            tools = await self.app.client.list_tools()
            table = self.query_one(DataTable)
            table.clear()
            self.tools_map = {t.name: t for t in tools}
            for tool in tools:
                schema_summ = "Yes" if tool.inputSchema else "No"
                # Use tool name as row key for easy retrieval
                table.add_row(tool.name, tool.description or "", schema_summ, key=tool.name)
        except Exception as e:
            self.app.notify(f"Error loading tools: {e}", severity="error")

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected):
        if self.data_type == "tools":
            tool_name = event.row_key.value
            if tool_name in self.tools_map:
                tool = self.tools_map[tool_name]
                self.app.push_screen(ToolExecutionScreen(tool))

    @work
    async def load_resources(self):
        try:
            resources = await self.app.client.list_resources()
            table = self.query_one(DataTable)
            table.clear()
            for res in resources:
                table.add_row(res.name, res.uri, res.mimeType or "")
        except Exception as e:
            self.app.notify(f"Error loading resources: {e}", severity="error")

    @on(Button.Pressed, "#btn_back")
    def go_back(self):
        self.app.pop_screen()


class ToolSelectionScreen(Screen):
    """Screen to select a tool to execute."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Select a Tool to Call", classes="screen_title")
        yield Select([], id="tool_select", prompt="Choose a tool...")
        yield Label("", id="tool_description", classes="description")
        yield Container(
            Button("Next", id="btn_next", variant="primary", disabled=True),
            Button("Back", id="btn_back"),
            classes="buttons_row"
        )
        yield Footer()

    def on_mount(self):
        self.load_tools()

    @work
    async def load_tools(self):
        try:
            tools = await self.app.client.list_tools()
            self.tools_map = {t.name: t for t in tools}
            select = self.query_one(Select)
            # Use tool name as value (string) instead of Tool object
            options = [(t.name, t.name) for t in tools]
            select.set_options(options)
        except Exception as e:
            self.app.notify(f"Error loading tools: {e}", severity="error")

    @on(Select.Changed)
    def on_select_change(self, event: Select.Changed):
        self.query_one("#btn_next").disabled = event.value is None
        if event.value and hasattr(self, "tools_map") and event.value in self.tools_map:
             description = self.tools_map[event.value].description or "No description available."
             self.query_one("#tool_description").update(description)
        else:
             self.query_one("#tool_description").update("")

    @on(Button.Pressed, "#btn_next")
    def on_next(self):
        select = self.query_one(Select)
        if select.value and hasattr(self, "tools_map") and select.value in self.tools_map:
            tool = self.tools_map[select.value]
            self.app.push_screen(ToolExecutionScreen(tool))

    @on(Button.Pressed, "#btn_back")
    def go_back(self):
        self.app.pop_screen()


class ToolExecutionScreen(Screen):
    """Screen to input arguments and execute a tool."""

    def __init__(self, tool: Tool):
        super().__init__()
        self.tool = tool

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(f"Execute Tool: {self.tool.name}", classes="screen_title")
        if self.tool.description:
            yield Label(self.tool.description, classes="description")
        
        # Check for arguments
        schema = self.tool.inputSchema
        has_args = schema and "properties" in schema and schema["properties"]
        
        if has_args:
            yield Label("Argument Schema:", classes="label")
            yield DataTable(id="args_table")
        else:
            yield Label("No arguments required.", classes="description")

        yield Label("Arguments (JSON):", classes="label")
        # Generate template from schema
        initial_json = self._generate_template_from_schema(self.tool.inputSchema)
        yield TextArea(initial_json, language="json", id="args_input")
        
        yield Container(
            Button("Execute", id="btn_execute", variant="success"),
            Button("Back", id="btn_back"),
            classes="buttons_row"
        )
        yield Label("", id="status_label")
        yield Footer()

    def on_mount(self):
        # Populate args table if it exists
        try:
            table = self.query_one("#args_table")
            table.add_columns("Name", "Type", "Required", "Description")
            
            schema = self.tool.inputSchema
            if schema and "properties" in schema:
                properties = schema.get("properties", {})
                required_list = schema.get("required", [])
                
                for prop_name, prop_details in properties.items():
                    prop_type = prop_details.get("type", "unknown")
                    is_required = "Yes" if prop_name in required_list else "No"
                    desc = prop_details.get("description", "")
                    table.add_row(prop_name, prop_type, is_required, desc)
        except Exception:
            # Table might not exist if no args
            pass

        # Auto-execute if requested (e.g. list_ctf_events)
        if self.tool.name == "list_ctf_events":
            self.execute_tool()

    def _generate_template_from_schema(self, schema: Dict[str, Any]) -> str:
        """Generates a JSON template string from the tool's input schema."""
        if not schema or "properties" not in schema:
            return "{}"
        
        template = {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        # Check if we have a selected event to auto-fill from
        selected_event = getattr(self.app, "selected_event", None)
        
        for prop_name, prop_details in properties.items():
            value_placeholder = None
            prop_type = prop_details.get("type", "string")
            
            # Auto-fill logic for event IDs
            if selected_event and prop_name in ["ctf_id", "id", "event_id"] and "id" in selected_event:
                 event_id = selected_event["id"]
                 if prop_type == "integer":
                     try:
                         value_placeholder = int(event_id)
                     except (ValueError, TypeError):
                         value_placeholder = 0
                 else:
                     value_placeholder = str(event_id)
            elif "default" in prop_details:
                value_placeholder = prop_details["default"]
            elif prop_type == "string":
                value_placeholder = "<string>"
            elif prop_type == "integer":
                value_placeholder = 0
            elif prop_type == "number":
                value_placeholder = 0.0
            elif prop_type == "boolean":
                value_placeholder = False
            elif prop_type == "array":
                value_placeholder = []
            elif prop_type == "object":
                value_placeholder = {}
            else:
                value_placeholder = "<value>"
                
            template[prop_name] = value_placeholder
            
        return json.dumps(template, indent=2)

    @on(Button.Pressed, "#btn_execute")
    async def execute_tool(self):
        args_text = self.query_one("#args_input").text
        try:
            args = json.loads(args_text)
        except json.JSONDecodeError:
            self.app.notify("Invalid JSON arguments", severity="error")
            return

        self.query_one("#status_label").update("Executing...")
        self.query_one("#btn_execute").disabled = True
        
        self.run_tool(args)

    @work
    async def run_tool(self, args):
        try:
            result = await self.app.client.call_tool(self.tool.name, args)
            # Show result - use EventSelectionScreen for CTF events
            if self.tool.name == "list_ctf_events":
                self.app.push_screen(EventSelectionScreen(result, f"Tool Result: {self.tool.name}", self.tool.name))
            else:
                self.app.push_screen(ResultScreen(result, f"Tool Result: {self.tool.name}", self.tool.name))
        except Exception as e:
            self.app.notify(f"Execution failed: {e}", severity="error")
        finally:
            self.query_one("#status_label").update("")
            self.query_one("#btn_execute").disabled = False

    @on(Button.Pressed, "#btn_back")
    def go_back(self):
        self.app.pop_screen()


class EventSelectionScreen(Screen):
    """Screen to display CTF events with split-panel selection interface."""

    CSS = """
    #events_container {
        layout: horizontal;
        height: 1fr;
    }
    
    #events_table {
        width: 50%;
        border: heavy #9FEF00;
        background: #1A2332;
    }
    
    #event_details {
        width: 50%;
        border: heavy #9FEF00;
        background: #1A2332;
        color: #A4B1CD;
        padding: 1;
    }
    
    #buttons_container {
        width: 50%;
        align: center middle;
    }
    
    Markdown {
        background: #1A2332;
        color: #A4B1CD;
    }
    Markdown H1, Markdown H2, Markdown H3 {
        color: #9FEF00;
        text-style: bold;
        background: #1A2332;
    }
    """

    def __init__(self, data: Any, title: str, tool_name: str = "tool"):
        super().__init__()
        self.data = data
        self.page_title = title
        self.tool_name = tool_name
        self.events_data = []
        self.markdown_content = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(self.page_title, classes="screen_title")
        
        yield Horizontal(
            DataTable(id="events_table"),
            Markdown("", id="event_details"),
            id="events_container"
        )
        
        yield Container(
            Button("Select Event", id="btn_select", variant="success"),
            Button("Save to .json", id="btn_save_json", variant="primary"),
            Button("Save to .md", id="btn_save_md", variant="primary"),
            Button("Close", id="btn_close"),
            id="buttons_container"
        )
        yield Footer()

    def on_mount(self):
        self.process_events()

    @work
    async def process_events(self):
        # Extract events from data
        try:
            if hasattr(self.data, "content") and isinstance(self.data.content, list):
                full_text = ""
                for block in self.data.content:
                    if hasattr(block, "type") and block.type == "text":
                        full_text += block.text
                    elif isinstance(block, str):
                        full_text += block
                
                try:
                    parsed_json = json.loads(full_text)
                    if isinstance(parsed_json, list):
                        self.events_data = parsed_json
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

        # Populate table
        table = self.query_one("#events_table")
        table.cursor_type = "row"
        table.add_columns("Event ID", "Event Name")
        
        for idx, event in enumerate(self.events_data):
            if isinstance(event, dict) and "id" in event and "name" in event:
                table.add_row(str(event.get('id')), event.get('name'), key=str(idx))
        
        # Focus the table
        table.focus()
        
        # Show first event if available
        if self.events_data:
            self.display_event_details(self.events_data[0])

    def display_event_details(self, event: dict):
        """Display details of selected event in right panel."""
        md = f"## 🚩 {event.get('name', 'Unknown')}\\n\\n"
        md += f"**Event ID**: {event.get('id', 'N/A')}\\n\\n"
        md += f"**Status**: {event.get('status', 'N/A')}\\n\\n"
        md += f"**Format**: {event.get('format', 'N/A')}\\n\\n"
        md += f"**Starts**: {event.get('starts_at', 'N/A')}\\n\\n"
        md += f"**Ends**: {event.get('ends_at', 'N/A')}\\n\\n"
        
        md += "### Additional Details\\n\\n"
        for k, v in event.items():
            if k not in ["name", "id", "status", "format", "starts_at", "ends_at"]:
                md += f"- **{k}**: `{v}`\\n"
        
        self.markdown_content = md
        self.query_one("#event_details").update(md)

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted):
        """Update details when user navigates the list."""
        if event.row_key:
            idx = int(event.row_key.value)
            if 0 <= idx < len(self.events_data):
                self.display_event_details(self.events_data[idx])

    @on(Button.Pressed, "#btn_select")
    def select_event(self):
        """Select the highlighted event and return to main menu."""
        table = self.query_one("#events_table")
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self.events_data):
            selected = self.events_data[table.cursor_row]
            # Store in app state
            self.app.selected_event = selected
            self.app.notify(f"Selected: {selected.get('name')}", severity="information")
            # Return to main menu by switching screen
            self.app.switch_screen("main_menu")
            # Update the IDs display on main menu
            main_menu = self.app.get_screen("main_menu")
            if hasattr(main_menu, 'update_ids_display'):
                main_menu.update_ids_display()

    @on(Button.Pressed, "#btn_save_json")
    def save_json(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.tool_name}-{timestamp}.json"
        try:
            to_save = self.data.model_dump() if hasattr(self.data, "model_dump") else self.data
            path = self.app.client.save_to_file(to_save, filename)
            self.app.notify(f"Saved JSON to {path}", severity="information")
        except Exception as e:
            self.app.notify(f"Save failed: {e}", severity="error")

    @on(Button.Pressed, "#btn_save_md")
    def save_md(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.tool_name}-{timestamp}.md"
        try:
            # Generate full markdown for all events
            full_md = "# CTF Events\\n\\n"
            for event in self.events_data:
                if isinstance(event, dict):
                    full_md += f"## 🚩 {event.get('name', 'Unknown')}\\n"
                    full_md += f"**ID**: {event.get('id')}\\n"
                    full_md += f"**Status**: {event.get('status')}\\n"
                    full_md += f"**Format**: {event.get('format')}\\n"
                    full_md += f"**Dates**: {event.get('starts_at')} to {event.get('ends_at')}\\n\\n"
                    for k, v in event.items():
                        if k not in ["name", "id", "status", "format", "starts_at", "ends_at"]:
                            full_md += f"- **{k}**: `{v}`\\n"
                    full_md += "\\n---\\n\\n"
            
            path = self.app.client.save_to_file(full_md, filename)
            self.app.notify(f"Saved Markdown to {path}", severity="information")
        except Exception as e:
            self.app.notify(f"Save failed: {e}", severity="error")

    @on(Button.Pressed, "#btn_close")
    def close(self):
        self.app.pop_screen()


class ResultScreen(Screen):
    """Screen to display results with a typewriter animation."""

    CSS = """
    #result_markdown {
        height: 1fr;
        border: solid $accent;
        background: #0c0c0c;
        color: #20C20E; /* Hacker Green */
        padding: 1;
    }
    
    /* Force markdown styles to match hacker theme */
    Markdown {
        background: #0c0c0c;
        color: #20C20E;
    }
    Markdown H1, Markdown H2, Markdown H3 {
        color: #00ff00;
        text-style: bold;
        background: #0c0c0c;
    }
    Markdown CodeBlock {
        background: #1a1a1a;
        color: #00ff00;
    }
    """

    def __init__(self, data: Any, title: str, tool_name: str = "tool"):
        super().__init__()
        self.data = data
        self.page_title = title
        self.tool_name = tool_name
        self.markdown_content = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(self.page_title, classes="screen_title")
        
        # Container for the result - using Markdown for rich text
        # Markdown widgets are focusable by default (arrows/pgup/pgdn)
        yield Markdown("", id="result_markdown")
        
        yield Container(
            Button("Save to .json", id="btn_save_json", variant="primary"),
            Button("Save to .md", id="btn_save_md", variant="primary"),
            Button("Close", id="btn_close"),
            classes="buttons_row"
        )
        yield Footer()

    def on_mount(self):
                md += "\n---\n"
                return md
            
            # Generic dict formatting
            if not data:
                return f"{indent}_empty object_\n"
            
            md = ""
            for k, v in data.items():
                if isinstance(v, dict):
                    md += f"{indent}- **{k}**:\n{self._json_to_markdown(v, indent_level + 1)}"
                elif isinstance(v, list):
                    md += f"{indent}- **{k}**:\n{self._json_to_markdown(v, indent_level + 1)}"
                elif v is None:
                    md += f"{indent}- **{k}**: `null`\n"
                elif isinstance(v, bool):
                    md += f"{indent}- **{k}**: `{str(v).lower()}`\n"
                elif isinstance(v, (int, float)):
                    md += f"{indent}- **{k}**: `{v}`\n"
                else:
                    # String or other
                    md += f"{indent}- **{k}**: {v}\n"
            return md
            
        elif isinstance(data, list):
            if not data:
                return f"{indent}_empty list_\n"
            
            md = ""
            for idx, item in enumerate(data):
                if isinstance(item, dict):
                    # For dict items in a list, show index if not at top level
                    if indent_level > 0:
                        md += f"{indent}- **Item {idx + 1}**:\n{self._json_to_markdown(item, indent_level + 1)}"
                    else:
                        # Top-level list items get special treatment
                        md += self._json_to_markdown(item, indent_level)
                elif isinstance(item, list):
                    md += f"{indent}- **[{idx}]**:\n{self._json_to_markdown(item, indent_level + 1)}"
                elif item is None:
                    md += f"{indent}- `null`\n"
                elif isinstance(item, bool):
                    md += f"{indent}- `{str(item).lower()}`\n"
                elif isinstance(item, (int, float)):
                    md += f"{indent}- `{item}`\n"
                else:
                    md += f"{indent}- {item}\n"
            return md
            
        else:
            # Primitive values
            if data is None:
                return f"{indent}`null`\n"
            elif isinstance(data, bool):
                return f"{indent}`{str(data).lower()}`\n"
            elif isinstance(data, (int, float)):
                return f"{indent}`{data}`\n"
            else:
                return f"{indent}{data}\n"

    @on(Button.Pressed, "#btn_save_json")
    def save_json(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.tool_name}-{timestamp}.json"
        try:
            # Save the raw data
            to_save = self.data.model_dump() if hasattr(self.data, "model_dump") else self.data
            path = self.app.client.save_to_file(to_save, filename)
            self.app.notify(f"Saved JSON to {path}", severity="information")
        except Exception as e:
            self.app.notify(f"Save failed: {e}", severity="error")

    @on(Button.Pressed, "#btn_save_md")
    def save_md(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.tool_name}-{timestamp}.md"
        try:
            # Save the markdown content
            path = self.app.client.save_to_file(self.markdown_content, filename)
            self.app.notify(f"Saved Markdown to {path}", severity="information")
        except Exception as e:
            self.app.notify(f"Save failed: {e}", severity="error")

    @on(Button.Pressed, "#btn_close")
    def close(self):
        self.app.pop_screen()


class ResourceInputScreen(Screen):
    """Screen to input a resource URI."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Read Resource", classes="screen_title")
        yield Input(placeholder="Enter Resource URI", id="uri_input")
        yield Container(
            Button("Read", id="btn_read", variant="primary"),
            Button("Back", id="btn_back"),
            classes="buttons_row"
        )
        yield Footer()

    @on(Button.Pressed, "#btn_read")
    async def read_resource(self):
        uri = self.query_one("#uri_input").value
        if not uri:
            self.app.notify("Please enter a URI", severity="warning")
            return
            
        await self.do_read(uri)

    @work
    async def do_read(self, uri):
        try:
            result = await self.app.client.read_resource(uri)
            self.app.push_screen(ResultScreen(result, f"Resource: {uri}", "resource"))
        except Exception as e:
            self.app.notify(f"Read failed: {e}", severity="error")

    @on(Button.Pressed, "#btn_back")
    def go_back(self):
        self.app.pop_screen()


class HTBMCPApp(App):
    """The Textual Application."""
    
    TITLE = "HackTheBox MCP Client"
    
    CSS = """
    /* HackTheBox Color Theme from settings.json */
    Screen {
        align: center middle;
        background: #1A2332;
    }
    
    * {
        color: #A4B1CD;
    }
    
    #main_menu_container {
        width: 75;
        height: auto;
        border: heavy #9FEF00;
        background: #1A2332;
        padding: 1 2;
    }
    
    #main_menu_wrapper {
        width: auto;
        height: auto;
    }
    
    #ascii_banner {
        text-align: center;
        width: 100%;
        margin-bottom: 1;
        color: #9FEF00;
    }
    
    #ids_display {
        text-align: center;
        width: 100%;
        color: #5CB2FF;
    }
    
    Button {
        width: 100%;
        margin-bottom: 1;
        border: solid #313F55;
    }
    
    Button.-primary {
        background: #5CB2FF;
        color: #000000;
        border: solid #7FC4FF;
    }
    
    Button.-primary:hover {
        background: #7FC4FF;
        color: #000000;
    }
    
    Button.-success {
        background: #2EE7B6;
        color: #000000;
        border: solid #5CECC6;
    }
    
    Button.-success:hover {
        background: #5CECC6;
        color: #000000;
    }
    
    Button.-warning {
        background: #FFAF00;
        color: #000000;
        border: solid #FFCC5C;
    }
    
    Button.-warning:hover {
        background: #FFCC5C;
        color: #000000;
    }
    
    Button.-error {
        background: #FF3E3E;
        color: #FFFFFF;
        border: solid #FF8484;
    }
    
    Button.-error:hover {
        background: #FF8484;
        color: #FFFFFF;
    }
    
    .screen_title {
        text-align: center;
        text-style: bold;
        margin: 1 0;
        width: 100%;
        color: #9FEF00;
    }
    
    DataTable {
        height: 1fr;
        border: heavy #9FEF00;
        background: #1A2332;
    }
    
    /* Column Headers - the titles row */
    DataTable > .datatable--header {
        background: #313F55;
        color: #9FEF00;
        text-style: bold;
        border-bottom: wide #9FEF00;
        height: 3;
    }
    
    DataTable > .datatable--header-cell {
        text-align: center;
        text-style: bold;
    }
    
    /* Data cells - should be normal size and centered */
    DataTable > .datatable--cell {
        text-align: center;
    }
    
    /* Cursor (selected row) */
    DataTable > .datatable--cursor {
        background: #9FEF00 30%;
        color: #FFFFFF;
        text-style: bold;
    }
    
    /* Alternating row colors - gray tones */
    DataTable > .datatable--odd-row {
        background: #313F55;
    }
    
    DataTable > .datatable--even-row {
        background: #1C2332;
    }
    
    /* Alternative: use :odd and :even pseudo-classes */
    DataTable > .datatable--row:odd {
        background: #313F55;
    }
    
    DataTable > .datatable--row:even {
        background: #1C2332;
    }
    
    DataTable > .datatable--fixed {
        border-right: solid #313F55;
    }
    
    /* Focused cursor */
    DataTable:focus > .datatable--cursor {
        background: #9FEF00;
        color: #000000;
    }
    
    TextArea {
        height: 1fr;
        border: heavy #9FEF00;
        background: #1A2332;
    }
    
    Input {
        border: heavy #9FEF00;
        background: #1A2332;
    }
    
    Input:focus {
        border: heavy #9FEF00;
    }
    
    Select {
        border: heavy #9FEF00;
        background: #1A2332;
    }
    
    Select:focus {
        border: heavy #9FEF00;
    }
    
    Markdown {
        background: #1A2332;
        color: #A4B1CD;
    }
    
    Markdown H1, Markdown H2, Markdown H3 {
        color: #9FEF00;
        text-style: bold;
    }
    
    Markdown Code {
        background: #313F55;
        color: #5CB2FF;
    }
    
    Markdown CodeBlock {
        background: #313F55;
        color: #A4B1CD;
    }
    
    .buttons_row {
        height: auto;
        align: center middle;
        layout: horizontal;
        margin-top: 1;
    }
    
    .buttons_row Button {
        width: auto;
        margin: 0 1;
    }
    
    .description {
        margin-bottom: 1;
        color: #5CB2FF;
    }
    
    .label {
        margin-top: 1;
        color: #A4B1CD;
    }
    
    Header {
        background: #313F55;
        color: #9FEF00;
    }
    
    Footer {
        background: #313F55;
        color: #A4B1CD;
    }
    
    Footer > .footer--key {
        color: #9FEF00;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
    ]

    def __init__(self, client: HTBMCPClient):
        super().__init__()
        self.client = client
        self.selected_event = None  # Store selected CTF event

    def on_mount(self):
        self.install_screen(MainMenu(), name="main_menu")
        self.install_screen(DataListScreen("Available Tools", "tools"), name="tools_list")
        self.install_screen(DataListScreen("Available Resources", "resources"), name="resources_list")
        self.install_screen(ToolSelectionScreen(), name="tool_selection")
        self.install_screen(ResourceInputScreen(), name="resource_input")
        self.push_screen("main_menu")


async def main():
    """Main entry point."""
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="HackTheBox MCP Client - Interactive TUI for HackTheBox Model Context Protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--version', '-v',
        action='version',
        version=f'HTB-MCP-Client v{__version__}'
    )
    args = parser.parse_args()
    
    # Load configuration
    config = dotenv_values()
    url = os.getenv("HTB_MCP_URL") or config.get("HTB_MCP_URL", "https://mcp.hackthebox.ai/v1/ctf/mcp/")
    api_token = os.getenv("API_ACCESS_TOKEN") or config.get("API_ACCESS_TOKEN")

    if not api_token:
        print("Error: API_ACCESS_TOKEN not set.")
        sys.exit(1)

    print(f"Connecting to {url}...")

    headers = {"Authorization": f"Bearer {api_token}"}

    try:
        async with streamablehttp_client(url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                client_helper = HTBMCPClient(session)
                app = HTBMCPApp(client_helper)
                await app.run_async()
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
