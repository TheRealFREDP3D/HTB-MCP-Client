#!/usr/bin/env python3
"""
HackTheBox MCP Client (TUI Version)
A Textual-based TUI client for the HackTheBox Model Context Protocol server.
"""

import asyncio
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
        yield Container(
            Label("HackTheBox MCP Client", id="title"),
            Label("", id="selected_event_label", classes="description"),
            Button("List Tools", id="btn_tools", variant="primary"),
            Button("List Resources", id="btn_resources", variant="primary"),
            Button("Challenges", id="btn_challenges", variant="primary"),
            Button("Call Tool", id="btn_call_tool", variant="success"),
            Button("Read Resource", id="btn_read_resource", variant="warning"),
            Button("Exit", id="btn_exit", variant="error"),
            id="main_menu_container"
        )
        yield Footer()

    def on_mount(self):
        self.update_selected_event_display()

    def update_selected_event_display(self):
        if hasattr(self.app, 'selected_event') and self.app.selected_event:
            event = self.app.selected_event
            self.query_one("#selected_event_label").update(
                f"🎯 Selected: {event.get('name', 'Unknown')} (ID: {event.get('id', 'N/A')})"
            )
        else:
            self.query_one("#selected_event_label").update("")

    @on(Button.Pressed, "#btn_tools")
    def show_tools(self):
        self.app.push_screen("tools_list")

    @on(Button.Pressed, "#btn_resources")
    def show_resources(self):
        self.app.push_screen("resources_list")

    @on(Button.Pressed, "#btn_challenges")
    def show_challenges(self):
        if hasattr(self.app, "stored_challenges") and self.app.stored_challenges:
             self.app.push_screen(ChallengeSelectionScreen(self.app.stored_challenges, "Stored Challenges", "stored"))
        else:
             self.app.notify("No challenges stored yet. Call 'retrieve_ctf' or similar tool first.", severity="warning")

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
            # Auto-fill logic for challenge IDs
            elif hasattr(self.app, "selected_challenge") and self.app.selected_challenge and prop_name in ["challenge_id", "id"] and "id" in self.app.selected_challenge:
                 challenge_id = self.app.selected_challenge["id"]
                 if prop_type == "integer":
                     try:
                         value_placeholder = int(challenge_id)
                     except (ValueError, TypeError):
                         value_placeholder = 0
                 else:
                     value_placeholder = str(challenge_id)
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
            elif self.tool.name in ["get_challenges", "list_challenges", "retrieve_ctf"]:
                # Save challenges automatically
                try:
                    # Attempt to parse and save
                    content_to_save = result
                    if hasattr(result, "content") and isinstance(result.content, list):
                        full_text = ""
                        for block in result.content:
                            if hasattr(block, "type") and block.type == "text":
                                full_text += block.text
                            elif isinstance(block, str):
                                full_text += block
                        try:
                             # Verify it's JSON before saving as challenges
                             json.loads(full_text)
                             self.app.client.save_to_file(result, "challenges.json")
                             self.app.stored_challenges = result
                        except json.JSONDecodeError:
                             pass
                except Exception:
                    pass
                
                self.app.push_screen(ChallengeSelectionScreen(result, f"Tool Result: {self.tool.name}", self.tool.name))
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
        width: 40%;
        border: solid $accent;
        background: #0c0c0c;
    }
    
    #event_details {
        width: 60%;
        border: solid $accent;
        background: #0c0c0c;
        color: #20C20E;
        padding: 1;
    }
    
    Markdown {
        background: #0c0c0c;
        color: #20C20E;
    }
    Markdown H1, Markdown H2, Markdown H3 {
        color: #00ff00;
        text-style: bold;
        background: #0c0c0c;
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
            classes="buttons_row"
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
            # Return to main menu and update display
            self.app.pop_screen()  # Close this screen
            if hasattr(self.app.screen, 'update_selected_event_display'):
                self.app.screen.update_selected_event_display()

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


class ChallengeSelectionScreen(Screen):
    """Screen to display Challenges with split-panel selection interface."""

    CSS = """
    #challenges_container {
        layout: horizontal;
        height: 1fr;
    }
    
    #challenges_table {
        width: 40%;
        border: solid $accent;
        background: #0c0c0c;
    }
    
    #challenge_details {
        width: 60%;
        border: solid $accent;
        background: #0c0c0c;
        color: #20C20E;
        padding: 1;
    }
    
    Markdown {
        background: #0c0c0c;
        color: #20C20E;
    }
    Markdown H1, Markdown H2, Markdown H3 {
        color: #00ff00;
        text-style: bold;
        background: #0c0c0c;
    }
    """

    def __init__(self, data: Any, title: str, tool_name: str = "tool"):
        super().__init__()
        self.data = data
        self.page_title = title
        self.tool_name = tool_name
        self.challenges_data = []
        self.markdown_content = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(self.page_title, classes="screen_title")
        
        yield Horizontal(
            DataTable(id="challenges_table"),
            Markdown("", id="challenge_details"),
            id="challenges_container"
        )
        
        yield Container(
            Button("Select Challenge", id="btn_select", variant="success"),
            Button("Save to .json", id="btn_save_json", variant="primary"),
            Button("Save to .md", id="btn_save_md", variant="primary"),
            Button("Close", id="btn_close"),
            classes="buttons_row"
        )
        yield Footer()

    def on_mount(self):
        self.process_challenges()

    @work
    async def process_challenges(self):
        # Extract challenges from data
        try:
            print(f"DEBUG: Data type: {type(self.data)}")
            print(f"DEBUG: Has content attr: {hasattr(self.data, 'content')}")
            
            if hasattr(self.data, "content") and isinstance(self.data.content, list):
                full_text = ""
                for block in self.data.content:
                    if hasattr(block, "type") and block.type == "text":
                        full_text += block.text
                    elif isinstance(block, str):
                        full_text += block
                
                print(f"DEBUG: Extracted text length: {len(full_text)}")
                print(f"DEBUG: First 200 chars: {full_text[:200]}")
                
                try:
                    parsed_json = json.loads(full_text)
                    print(f"DEBUG: Parsed JSON type: {type(parsed_json)}")
                    
                    # Handle both list and dict formats
                    if isinstance(parsed_json, list):
                        self.challenges_data = parsed_json
                    elif isinstance(parsed_json, dict):
                        # Try common keys that might contain the challenges list
                        for key in ['challenges', 'data', 'results', 'items']:
                            if key in parsed_json and isinstance(parsed_json[key], list):
                                self.challenges_data = parsed_json[key]
                                print(f"DEBUG: Found challenges in '{key}' key")
                                break
                        else:
                            # If no list found, maybe it's a single challenge wrapped in dict
                            if 'id' in parsed_json and 'name' in parsed_json:
                                self.challenges_data = [parsed_json]
                                print("DEBUG: Treating single dict as one-item list")
                    
                    print(f"DEBUG: challenges_data length: {len(self.challenges_data)}")
                except json.JSONDecodeError as e:
                    print(f"DEBUG: JSON decode error: {e}")
            else:
                print("DEBUG: Data does not have expected content structure")
        except Exception as e:
            print(f"DEBUG: Exception in process_challenges: {e}")
            import traceback
            traceback.print_exc()

        # Populate table
        table = self.query_one("#challenges_table")
        table.cursor_type = "row"
        table.add_columns("ID", "Name", "Difficulty", "Points")
        
        print(f"DEBUG: About to populate table with {len(self.challenges_data)} challenges")
        for idx, challenge in enumerate(self.challenges_data):
            if isinstance(challenge, dict) and "id" in challenge and "name" in challenge:
                print(f"DEBUG: Adding row {idx}: {challenge.get('name')}")
                table.add_row(
                    str(challenge.get('id')), 
                    challenge.get('name'), 
                    challenge.get('difficulty', 'N/A'),
                    str(challenge.get('points', 'N/A')),
                    key=str(idx)
                )
            else:
                print(f"DEBUG: Skipping invalid challenge at {idx}: {type(challenge)}")
        
        # Focus the table
        table.focus()
        
        # Show first challenge if available
        if self.challenges_data:
            self.display_challenge_details(self.challenges_data[0])

    def display_challenge_details(self, challenge: dict):
        """Display details of selected challenge in right panel."""
        md = f"## 🚩 {challenge.get('name', 'Unknown')}\\n\\n"
        md += f"**ID**: {challenge.get('id', 'N/A')}\\n\\n"
        md += f"**Difficulty**: {challenge.get('difficulty', 'N/A')}\\n\\n"
        md += f"**Points**: {challenge.get('points', 'N/A')}\\n\\n"
        md += f"**Category**: {challenge.get('category_name', 'N/A')}\\n\\n"
        
        if "description" in challenge:
             md += f"### Description\\n\\n{challenge.get('description')}\\n\\n"

        md += "### Additional Details\\n\\n"
        for k, v in challenge.items():
            if k not in ["name", "id", "difficulty", "points", "category_name", "description"]:
                md += f"- **{k}**: `{v}`\\n"
        
        self.markdown_content = md
        self.query_one("#challenge_details").update(md)

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted):
        """Update details when user navigates the list."""
        if event.row_key:
            idx = int(event.row_key.value)
            if 0 <= idx < len(self.challenges_data):
                self.display_challenge_details(self.challenges_data[idx])

    @on(Button.Pressed, "#btn_select")
    def select_challenge(self):
        """Select the highlighted challenge and return to main menu."""
        table = self.query_one("#challenges_table")
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self.challenges_data):
            selected = self.challenges_data[table.cursor_row]
            # Store in app state
            self.app.selected_challenge = selected
            self.app.notify(f"Selected: {selected.get('name')}", severity="information")
            # Return to main menu and update display
            self.app.pop_screen()  # Close this screen
            if hasattr(self.app.screen, 'update_selected_event_display'):
                self.app.screen.update_selected_event_display()

    @on(Button.Pressed, "#btn_save_json")
    def save_json(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.tool_name}-{timestamp}.json"
        try:
            to_save = self.data.model_dump() if hasattr(self.data, "model_dump") else self.data
            path = self.app.client.save_to_file(to_save, filename)
            self.app.notify(f"Saved JSON to {path}", severity="information")
            self.app.pop_screen()
        except Exception as e:
            self.app.notify(f"Save failed: {e}", severity="error")

    @on(Button.Pressed, "#btn_save_md")
    def save_md(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.tool_name}-{timestamp}.md"
        try:
            path = self.app.client.save_to_file(self.markdown_content, filename)
            self.app.notify(f"Saved Markdown to {path}", severity="information")
            self.app.pop_screen()
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
        self.process_and_animate()
        # Focus the markdown widget so user can scroll immediately
        self.query_one("#result_markdown").focus()

    @work
    async def process_and_animate(self):
        # 1. Extract content
        content_str = ""
        try:
            # Handle MCP CallToolResult
            if hasattr(self.data, "content") and isinstance(self.data.content, list):
                # Concatenate text from all text content blocks
                full_text = ""
                for block in self.data.content:
                    if hasattr(block, "type") and block.type == "text":
                        full_text += block.text
                    elif isinstance(block, str): # Fallback if it's just strings
                        full_text += block
                
                # Try to parse this text as JSON (as seen in the screenshot)
                try:
                    parsed_json = json.loads(full_text)
                    # Convert to Markdown
                    content_str = self._json_to_markdown(parsed_json)
                except json.JSONDecodeError:
                    # Not JSON, just use the text
                    content_str = full_text
            else:
                # Fallback for other data types
                content_str = str(self.data)
        except Exception as e:
            content_str = f"Error processing result: {e}\n\nRaw Data:\n{self.data}"

        self.markdown_content = content_str

        # 2. Animate
        markdown_widget = self.query_one("#result_markdown")
        lines = content_str.splitlines()
        current_text = ""
        
        for line in lines:
            current_text += line + "\n"
            # Update the markdown widget
            markdown_widget.update(current_text)
            await asyncio.sleep(0.05) # Typewriter speed

    def _json_to_markdown(self, data: Any) -> str:
        # Helper to make it pretty
        if isinstance(data, list):
            md = ""
            for item in data:
                if isinstance(item, dict):
                    # CTF Event specific formatting if detected
                    if "name" in item and "id" in item:
                        md += f"## 🚩 {item.get('name')} (ID: {item.get('id')})\n"
                        md += f"**Status**: {item.get('status')} | **Format**: {item.get('format')}\n"
                        md += f"**Date**: {item.get('starts_at')} to {item.get('ends_at')}\n"
                        # Add other fields in a collapsed way or just list them
                        md += "### Details\n"
                        for k, v in item.items():
                            if k not in ["name", "id", "status", "format", "starts_at", "ends_at"]:
                                md += f"- **{k}**: `{v}`\n"
                        md += "\n---\n"
                    else:
                        # Generic list item
                        md += "### Item\n"
                        for k, v in item.items():
                            md += f"- **{k}**: `{v}`\n"
                        md += "\n---\n"
            return md
        elif isinstance(data, dict):
            md = ""
            for k, v in data.items():
                md += f"- **{k}**: `{v}`\n"
            return md
        else:
            return f"```json\n{json.dumps(data, indent=2)}\n```"

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
    
    CSS = """
    Screen {
        align: center middle;
    }
    
    #main_menu_container {
        width: 40;
        height: auto;
        border: heavy $accent;
        padding: 1 2;
    }
    
    Button {
        width: 100%;
        margin-bottom: 1;
    }
    
    .screen_title {
        text-align: center;
        text-style: bold;
        margin: 1 0;
        width: 100%;
    }
    
    DataTable {
        height: 1fr;
        border: solid $secondary;
    }
    
    TextArea {
        height: 1fr;
        border: solid $secondary;
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
        color: $text-muted;
    }
    
    .label {
        margin-top: 1;
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
        self.selected_challenge = None # Store selected Challenge
        self.stored_challenges = None # Store loaded challenges data

    def on_mount(self):
        # Try to load stored challenges
        try:
            challenges_path = self.client.output_dir / "challenges.json"
            if challenges_path.exists():
                with open(challenges_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Create a mock result object to match what ChallengeSelectionScreen expects
                    class MockResult:
                        def __init__(self, data):
                            self.content = [type("MockBlock", (), {"type": "text", "text": json.dumps(data)})]
                            
                    self.stored_challenges = MockResult(data)
        except Exception as e:
            print(f"Failed to load stored challenges: {e}")

        self.install_screen(MainMenu(), name="main_menu")
        self.install_screen(DataListScreen("Available Tools", "tools"), name="tools_list")
        self.install_screen(DataListScreen("Available Resources", "resources"), name="resources_list")
        self.install_screen(ToolSelectionScreen(), name="tool_selection")
        self.install_screen(ResourceInputScreen(), name="resource_input")
        self.push_screen("main_menu")


async def main():
    """Main entry point."""
    
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
