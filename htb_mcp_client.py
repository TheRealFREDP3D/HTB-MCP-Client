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
        self.state_file = Path("htb_mcp_state.json")
        self.state = {
            "selected_event": None,
            "selected_team": None,
            "selected_challenge": None,
            "challenges_cache": [],
            "container_status": None
        }
        self.load_state()

    def load_state(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    loaded_state = json.load(f)
                    self.state.update(loaded_state)
            except Exception:
                # Silently continue with default state if loading fails
                pass

    def save_state(self):
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception:
            # Silently continue if state saving fails
            pass

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

    def __init__(self, tool: Tool, auto_exec_args: Optional[Dict] = None):
        super().__init__()
        self.tool = tool
        self.auto_exec_args = auto_exec_args or {}

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

        # Auto-execute if requested (e.g. list_ctf_events or passed auto_exec_args)
        if self.tool.name == "list_ctf_events" or self.auto_exec_args:
            # If auto_exec_args provided, ensure they are in the input box
            if self.auto_exec_args:
                 current_text = self.query_one("#args_input").text
                 try:
                     current_json = json.loads(current_text)
                     current_json.update(self.auto_exec_args)
                     self.query_one("#args_input").load_text(json.dumps(current_json, indent=2))
                 except:
                     pass
            
            # Only auto-execute if it's list_ctf_events OR we explicitly want to (maybe add a flag?)
            # For now, let's auto-execute if it's list_ctf_events. 
            # For start_container, user might want to review args.
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
        selected_challenge = getattr(self.app, "selected_challenge", None)
        
        for prop_name, prop_details in properties.items():
            value_placeholder = None
            prop_type = prop_details.get("type", "string")
            
            # Use auto_exec_args if available
            if prop_name in self.auto_exec_args:
                value_placeholder = self.auto_exec_args[prop_name]
            
            # Auto-fill logic for event IDs
            elif selected_event and prop_name in ["ctf_id", "id", "event_id"] and "id" in selected_event:
                 event_id = selected_event["id"]
                 if prop_type == "integer":
                     try:
                         value_placeholder = int(event_id)
                     except (ValueError, TypeError):
                         value_placeholder = 0
                 else:
                     value_placeholder = str(event_id)
            
            # Auto-fill logic for challenge IDs
            elif selected_challenge and prop_name in ["challenge_id", "id"] and "id" in selected_challenge:
                 challenge_id = selected_challenge["id"]
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
            
            # Handle specific tool results
            if self.tool.name == "list_ctf_events":
                self.app.push_screen(EventSelectionScreen(result, f"Tool Result: {self.tool.name}", self.tool.name))
            elif self.tool.name == "retrieve_ctf":
                self.app.push_screen(ChallengeSelectionScreen(result, f"Tool Result: {self.tool.name}", self.tool.name))
            elif self.tool.name == "retrieve_my_teams":
                self.app.push_screen(TeamSelectionScreen(result, f"Tool Result: {self.tool.name}", self.tool.name))
            elif self.tool.name == "start_container":
                # Parse result to get IP/Port if available
                # Assuming result content has text with IP/Port or success message
                # For now, just notify and maybe update status if we can parse it
                # If success, return to main menu
                self.app.notify("Container started!", severity="information")
                # TODO: Parse actual IP/Port from result
                # self.app.container_status = {"ip": "...", "port": "..."}
                # self.app.save_app_state()
                self.app.push_screen(ResultScreen(result, f"Tool Result: {self.tool.name}", self.tool.name))
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


class ChallengeSelectionScreen(Screen):
    """Screen to display Challenges with split-panel selection interface."""

    CSS = """
    #challenges_container {
        layout: horizontal;
        height: 1fr;
    }
    
    #challenges_table {
        width: 50%;
    }
    
    #challenge_details {
        width: 50%;
        border: heavy #9FEF00;
        padding: 1;
    }
    
    #buttons_container {
        width: 50%;
        align: center middle;
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
            Button("Back", id="btn_back"),
            id="buttons_container"
        )
        yield Footer()

    def on_mount(self):
        self.process_challenges()

    @work
    async def process_challenges(self):
        # Extract challenges from data
        try:
            full_text = ""
            if hasattr(self.data, "content") and isinstance(self.data.content, list):
                for block in self.data.content:
                    if hasattr(block, "type") and block.type == "text":
                        full_text += block.text
                    elif isinstance(block, str):
                        full_text += block
            
            try:
                parsed_json = json.loads(full_text)
                # Check if it's a dict with "challenges" key or just a list
                if isinstance(parsed_json, dict) and "challenges" in parsed_json:
                    self.challenges_data = parsed_json["challenges"]
                elif isinstance(parsed_json, list):
                    self.challenges_data = parsed_json
            except json.JSONDecodeError:
                pass
        except Exception:
            pass

        # Populate table
        table = self.query_one("#challenges_table")
        table.cursor_type = "row"
        table.add_columns("ID", "Name", "Category", "Diff", "Pts", "Solved")
        
        for idx, chall in enumerate(self.challenges_data):
            if isinstance(chall, dict):
                c_id = str(chall.get('id', ''))
                name = chall.get('name', 'Unknown')
                cat = str(chall.get('challenge_category_id', '')) # Map to name if possible, but ID is safer for now
                diff = chall.get('difficulty', '')
                pts = str(chall.get('points', ''))
                solved = "Yes" if chall.get('solved') else "No"
                
                table.add_row(c_id, name, cat, diff, pts, solved, key=str(idx))
        
        # Focus the table
        table.focus()
        
        # Show first challenge if available
        if self.challenges_data:
            self.display_challenge_details(self.challenges_data[0])

    def display_challenge_details(self, chall: dict):
        """Display details of selected challenge in right panel."""
        md = f"## 🚩 {chall.get('name', 'Unknown')}\\n\\n"
        md += f"**ID**: {chall.get('id', 'N/A')}\\n\\n"
        md += f"**Difficulty**: {chall.get('difficulty', 'N/A')}\\n\\n"
        md += f"**Points**: {chall.get('points', 'N/A')}\\n\\n"
        md += f"**Solved**: {chall.get('solved', False)}\\n\\n"
        
        desc = chall.get('description', '')
        if desc:
             md += f"### Description\\n{desc}\\n\\n"
        
        # Docker info
        if chall.get('hasDocker'):
            md += "### 🐳 Docker Info\\n"
            md += f"- **Image**: `{chall.get('docker_image', 'N/A')}`\\n"
            md += f"- **Port**: `{chall.get('docker_port', 'N/A')}`\\n\\n"

        # Files
        filename = chall.get('filename', '')
        if filename:
            md += f"### 📁 Files\\n- `{filename}`\\n\\n"

        md += "### Additional Details\\n\\n"
        for k, v in chall.items():
            if k not in ["name", "id", "difficulty", "points", "solved", "description", "hasDocker", "docker_image", "docker_port", "filename"]:
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
            # Store in app state and save
            self.app.selected_challenge = selected
            self.app.save_app_state()
            self.app.notify(f"Selected Challenge: {selected.get('name')}", severity="information")
            # Return to main menu by switching screen
            self.app.switch_screen("main_menu")
            # Update the IDs display on main menu
            main_menu = self.app.get_screen("main_menu")
            if hasattr(main_menu, 'update_display'):
                main_menu.update_display()

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
            path = self.app.client.save_to_file(self.markdown_content, filename)
            self.app.notify(f"Saved Markdown to {path}", severity="information")
        except Exception as e:
            self.app.notify(f"Save failed: {e}", severity="error")

    @on(Button.Pressed, "#btn_back")
    def go_back(self):
        self.app.pop_screen()


class PlayPage(Screen):
    """Screen for the main 'Play' flow."""

    CSS = """
    #play_container {
        layout: horizontal;
        height: 1fr;
    }
    
    #challenges_list {
        width: 30%;
        border-right: heavy #9FEF00;
    }
    
    #play_details {
        width: 70%;
        padding: 1;
    }
    
    #play_actions {
        height: auto;
        align: center middle;
        padding: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Play Mode", classes="screen_title")
        
        yield Horizontal(
            Vertical(
                Label("Challenges", classes="label"),
                DataTable(id="play_challenges_table"),
                id="challenges_list"
            ),
            Vertical(
                Markdown("", id="play_markdown"),
                Container(
                    Button("Start Container", id="btn_start_container", variant="success"),
                    Button("Stop Container", id="btn_stop_container", variant="error"),
                    Button("Download Files", id="btn_download", variant="primary"),
                    Button("Back to Menu", id="btn_back"),
                    id="play_actions"
                ),
                id="play_details"
            ),
            id="play_container"
        )
        yield Footer()

    def on_mount(self):
        self.load_challenges()
        self.display_current_challenge()

    def load_challenges(self):
        # Load challenges from cache or current selection context
        table = self.query_one("#play_challenges_table")
        table.cursor_type = "row"
        table.clear()
        table.add_columns("ID", "Name")
        
        # If we have a selected challenge, show it. 
        if self.app.selected_challenge:
            c_id = str(self.app.selected_challenge.get('id', ''))
            name = self.app.selected_challenge.get('name', 'Unknown')
            table.add_row(c_id, name, key="current")
            
        table.focus()

    def display_current_challenge(self):
        if self.app.selected_challenge:
            chall = self.app.selected_challenge
            md = f"# 🚩 {chall.get('name', 'Unknown')}\\n\\n"
            md += f"**ID**: {chall.get('id', 'N/A')} | **Diff**: {chall.get('difficulty', 'N/A')} | **Pts**: {chall.get('points', 'N/A')}\\n\\n"
            
            desc = chall.get('description', '')
            if desc:
                 md += f"### Description\\n{desc}\\n\\n"
            
            # Docker info
            if chall.get('hasDocker'):
                md += "### 🐳 Docker Info\\n"
                md += "Container required for this challenge.\\n"

            # Files
            filename = chall.get('filename', '')
            if filename:
                md += f"### 📁 Files\\n- `{filename}`\\n\\n"
            
            self.query_one("#play_markdown").update(md)

    @on(Button.Pressed, "#btn_start_container")
    def start_container(self):
        if self.app.selected_challenge:
            chall_id = self.app.selected_challenge.get("id")
            # Auto-execute start_container tool
            self.app.push_screen(ToolExecutionScreen(
                Tool(name="start_container", description="Start a container", inputSchema={}),
                auto_exec_args={"challenge_id": chall_id}
            ))

    @on(Button.Pressed, "#btn_stop_container")
    def stop_container(self):
        # Auto-execute stop_container tool
        self.app.push_screen(ToolExecutionScreen(
            Tool(name="stop_container", description="Stop a container", inputSchema={}),
            auto_exec_args={}
        ))

    @on(Button.Pressed, "#btn_download")
    def download_files(self):
        if self.app.selected_challenge:
            chall_id = self.app.selected_challenge.get("id")
            # Auto-execute download_challenge tool
            self.app.push_screen(ToolExecutionScreen(
                Tool(name="download_challenge", description="Download challenge files", inputSchema={}),
                auto_exec_args={"challenge_id": chall_id}
            ))

    @on(Button.Pressed, "#btn_back")
    def go_back(self):
        self.app.switch_screen("main_menu")


class TeamSelectionScreen(Screen):
    """Screen to display Teams with split-panel selection interface."""

    CSS = """
    #teams_container {
        layout: horizontal;
        height: 1fr;
    }
    
    #teams_table {
        width: 50%;
    }
    
    #team_details {
        width: 50%;
        border: heavy #9FEF00;
        padding: 1;
    }
    
    #buttons_container {
        width: 50%;
        align: center middle;
    }
    """

    def __init__(self, data: Any, title: str, tool_name: str = "tool"):
        super().__init__()
        self.data = data
        self.page_title = title
        self.tool_name = tool_name
        self.teams_data = []
        self.markdown_content = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(self.page_title, classes="screen_title")
        
        yield Horizontal(
            DataTable(id="teams_table"),
            Markdown("", id="team_details"),
            id="teams_container"
        )
        
        yield Container(
            Button("Select Team", id="btn_select", variant="success"),
            Button("Save to .json", id="btn_save_json", variant="primary"),
            Button("Save to .md", id="btn_save_md", variant="primary"),
            Button("Close", id="btn_close"),
            id="buttons_container"
        )
        yield Footer()

    def on_mount(self):
        self.process_teams()

    @work
    async def process_teams(self):
        # Extract teams from data
        try:
            full_text = ""
            if hasattr(self.data, "content") and isinstance(self.data.content, list):
                for block in self.data.content:
                    if hasattr(block, "type") and block.type == "text":
                        full_text += block.text
                    elif isinstance(block, str):
                        full_text += block
            
            try:
                self.teams_data = json.loads(full_text)
                if not isinstance(self.teams_data, list):
                    self.teams_data = [self.teams_data]
            except json.JSONDecodeError:
                pass
        except Exception:
            pass

        # Populate table
        table = self.query_one("#teams_table")
        table.cursor_type = "row"
        table.add_columns("ID", "Name", "Captain")
        
        for idx, team in enumerate(self.teams_data):
            if isinstance(team, dict):
                t_id = str(team.get('id', ''))
                name = team.get('name', 'Unknown')
                captain = str(team.get('captain_id', 'Unknown'))
                table.add_row(t_id, name, captain, key=str(idx))
        
        # Focus the table
        table.focus()
        
        # Show first team if available
        if self.teams_data:
            self.display_team_details(self.teams_data[0])

    def display_team_details(self, team: dict):
        """Display details of selected team in right panel."""
        md = f"## 🛡️ {team.get('name', 'Unknown')}\\n\\n"
        md += f"**ID**: {team.get('id', 'N/A')}\\n"
        md += f"**Captain ID**: {team.get('captain_id', 'N/A')}\\n\\n"
        
        md += "### Members\\n"
        members = team.get('members', [])
        if members:
            for m in members:
                md += f"- {m.get('name', 'Unknown')} (ID: {m.get('id', 'N/A')})\\n"
        else:
            md += "No members listed.\\n"
        
        self.markdown_content = md
        self.query_one("#team_details").update(md)

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted):
        """Update details when user navigates the list."""
        if event.row_key:
            idx = int(event.row_key.value)
            if 0 <= idx < len(self.teams_data):
                self.display_team_details(self.teams_data[idx])

    @on(Button.Pressed, "#btn_select")
    def select_team(self):
        """Select the highlighted team and return to main menu."""
        table = self.query_one("#teams_table")
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self.teams_data):
            selected = self.teams_data[table.cursor_row]
            # Store in app state and save
            self.app.selected_team = selected
            self.app.save_app_state()
            self.app.notify(f"Selected Team: {selected.get('name')}", severity="information")
            # Return to main menu by switching screen
            self.app.switch_screen("main_menu")
            # Update the IDs display on main menu
            main_menu = self.app.get_screen("main_menu")
            if hasattr(main_menu, 'update_display'):
                main_menu.update_display()

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
            path = self.app.client.save_to_file(self.markdown_content, filename)
            self.app.notify(f"Saved Markdown to {path}", severity="information")
        except Exception as e:
            self.app.notify(f"Save failed: {e}", severity="error")

    @on(Button.Pressed, "#btn_close")
    def close(self):
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
    }
    
    #event_details {
        width: 50%;
        border: heavy #9FEF00;
        padding: 1;
    }
    
    #buttons_container {
        width: 50%;
        align: center middle;
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
            full_text = ""
            if hasattr(self.data, "content") and isinstance(self.data.content, list):
                for block in self.data.content:
                    if hasattr(block, "type") and block.type == "text":
                        full_text += block.text
                    elif isinstance(block, str):
                        full_text += block
            
            try:
                self.events_data = json.loads(full_text)
                if not isinstance(self.events_data, list):
                    self.events_data = [self.events_data]
            except json.JSONDecodeError:
                pass
        except Exception:
            pass

        # Populate table
        table = self.query_one("#events_table")
        table.cursor_type = "row"
        table.add_columns("ID", "Name", "Status")
        
        for idx, event in enumerate(self.events_data):
            if isinstance(event, dict):
                e_id = str(event.get('id', ''))
                name = event.get('name', 'Unknown')
                status = event.get('status', 'Unknown')
                table.add_row(e_id, name, status, key=str(idx))
        
        # Focus the table
        table.focus()
        
        # Show first event if available
        if self.events_data:
            self.display_event_details(self.events_data[0])

    def display_event_details(self, event: dict):
        """Display details of selected event in right panel."""
        md = f"## {event.get('name', 'Unknown')}\\n\\n"
        md += f"**ID**: {event.get('id', 'N/A')}\\n"
        md += f"**Status**: {event.get('status', 'N/A')}\\n"
        md += f"**Type**: {event.get('type', 'N/A')}\\n\\n"

        if desc := event.get('description', ''):
            md += f"### Description\\n{desc}\\n"
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
            # Store in app state and save
            self.app.selected_event = selected
            self.app.save_app_state()
            self.app.notify(f"Selected Event: {selected.get('name')}", severity="information")
            # Return to main menu by switching screen
            self.app.switch_screen("main_menu")
            # Update the IDs display on main menu
            main_menu = self.app.get_screen("main_menu")
            if hasattr(main_menu, 'update_display'):
                main_menu.update_display()

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
    """Screen to display results."""

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
        yield Markdown("", id="result_markdown")
        
        yield Container(
            Button("Save to .json", id="btn_save_json", variant="primary"),
            Button("Save to .md", id="btn_save_md", variant="primary"),
            Button("Close", id="btn_close"),
            classes="buttons_row"
        )
        yield Footer()

    def on_mount(self):
        self.markdown_content = self._json_to_markdown(self.data)
        self.query_one("#result_markdown").update(self.markdown_content)

    def _json_to_markdown(self, data: Any, indent_level: int = 0) -> str:
        """Recursively convert JSON/Dict data to Markdown."""
        indent = "  " * indent_level
        
        if isinstance(data, dict):
            if not data:
                return f"{indent}_empty object_\\n"
            
            md = ""
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    md += f"{indent}- **{k}**:\\n{self._json_to_markdown(v, indent_level + 1)}"
                elif v is None:
                    md += f"{indent}- **{k}**: `null`\\n"
                else:
                    md += f"{indent}- **{k}**: `{v}`\\n"
            return md
            
        elif isinstance(data, list):
            if not data:
                return f"{indent}_empty list_\\n"
            
            md = ""
            for item in data:
                if isinstance(item, (dict, list)):
                    md += f"{indent}- \\n{self._json_to_markdown(item, indent_level + 1)}"
                else:
                    md += f"{indent}- `{item}`\\n"
            return md
            
        else:
            return f"{indent}`{data}`\\n"

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
    /* HackTheBox Color Theme */
    Screen {
        align: center middle;
        background: #1A2332;
    }
    
    * {
        color: #A4B1CD;
        scrollbar-background: #1A2332;
        scrollbar-color: #9FEF00;
    }
    
    /* Main Menu Container */
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
        text-style: bold;
        margin-bottom: 1;
    }
    
    /* Buttons */
    Button {
        width: 100%;
        margin-bottom: 1;
        border: solid #313F55;
        background: #1A2332;
        color: #A4B1CD;
    }
    
    Button:hover {
        background: #313F55;
        border: solid #9FEF00;
        color: #9FEF00;
    }
    
    Button.-primary {
        border: solid #5CB2FF;
        color: #5CB2FF;
    }
    
    Button.-primary:hover {
        background: #5CB2FF;
        color: #1A2332;
    }
    
    Button.-success {
        border: solid #9FEF00;
        color: #9FEF00;
    }
    
    Button.-success:hover {
        background: #9FEF00;
        color: #1A2332;
    }
    
    Button.-warning {
        border: solid #FFAF00;
        color: #FFAF00;
    }
    
    Button.-warning:hover {
        background: #FFAF00;
        color: #1A2332;
    }
    
    Button.-error {
        border: solid #FF3E3E;
        color: #FF3E3E;
    }
    
    Button.-error:hover {
        background: #FF3E3E;
        color: #FFFFFF;
    }
    
    /* Titles */
    .screen_title {
        text-align: center;
        text-style: bold;
        margin: 1 0;
        width: 100%;
        color: #9FEF00;
        background: #1A2332;
        border-bottom: solid #9FEF00;
        padding-bottom: 1;
    }
    
    /* Data Tables */
    DataTable {
        height: 1fr;
        border: heavy #9FEF00;
        background: #1A2332;
        margin: 1;
    }
    
    DataTable > .datatable--header {
        background: #313F55;
        color: #9FEF00;
        text-style: bold;
        border-bottom: wide #9FEF00;
    }
    
    DataTable > .datatable--header-cell {
        text-align: center;
        text-style: bold;
        color: #9FEF00;
    }
    
    DataTable > .datatable--cell {
        text-align: center;
        color: #A4B1CD;
    }
    
    DataTable > .datatable--cursor {
        background: #9FEF00;
        color: #1A2332;
        text-style: bold;
    }
    
    DataTable > .datatable--odd-row {
        background: #1A2332;
    }
    
    DataTable > .datatable--even-row {
        background: #1E293B;
    }
    
    /* Inputs and TextAreas */
    TextArea {
        height: 1fr;
        border: heavy #9FEF00;
        background: #1A2332;
        color: #A4B1CD;
        margin: 1;
    }
    
    Input {
        border: heavy #9FEF00;
        background: #1A2332;
        color: #A4B1CD;
        margin: 1;
    }
    
    Input:focus {
        border: heavy #5CB2FF;
    }
    
    Select {
        border: heavy #9FEF00;
        background: #1A2332;
        margin: 1;
    }
    
    Select:focus {
        border: heavy #5CB2FF;
    }
    
    /* Markdown */
    Markdown {
        background: #1A2332;
        color: #A4B1CD;
        padding: 1;
    }
    
    Markdown H1, Markdown H2, Markdown H3 {
        color: #9FEF00;
        text-style: bold;
        background: #1A2332;
        border-bottom: solid #313F55;
    }
    
    Markdown Code {
        background: #313F55;
        color: #5CB2FF;
    }
    
    Markdown CodeBlock {
        background: #0F141E;
        color: #A4B1CD;
        border: solid #313F55;
    }
    
    /* Layout Utilities */
    .buttons_row {
        height: auto;
        align: center middle;
        layout: horizontal;
        margin-top: 1;
        background: #1A2332;
    }
    
    .buttons_row Button {
        width: auto;
        margin: 0 1;
        min-width: 15;
    }
    
    .description {
        margin-bottom: 1;
        color: #5CB2FF;
        text-align: center;
    }
    
    .label {
        margin-top: 1;
        color: #9FEF00;
        text-style: bold;
        margin-left: 1;
    }
    
    /* Header and Footer */
    Header {
        background: #313F55;
        color: #9FEF00;
        height: 3;
        dock: top;
    }
    
    Footer {
        background: #313F55;
        color: #A4B1CD;
        dock: bottom;
        height: 1;
    }
    
    Footer > .footer--key {
        color: #9FEF00;
        background: #313F55;
    }
    
    Footer > .footer--highlight {
        background: #5CB2FF;
        color: #1A2332;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
    ]

    def __init__(self, client: HTBMCPClient):
        super().__init__()
        self.client = client
        # Load state from client
        self.selected_event = self.client.state.get("selected_event")
        self.selected_team = self.client.state.get("selected_team")
        self.selected_challenge = self.client.state.get("selected_challenge")
        self.container_status = self.client.state.get("container_status")

    def on_mount(self):
        self.install_screen(MainMenu(), name="main_menu")
        self.install_screen(DataListScreen("Available Tools", "tools"), name="tools_list")
        self.install_screen(DataListScreen("Available Resources", "resources"), name="resources_list")
        self.install_screen(ToolSelectionScreen(), name="tool_selection")
        self.install_screen(ResourceInputScreen(), name="resource_input")
        self.install_screen(PlayPage(), name="play_page")
        self.push_screen("main_menu")

    def save_app_state(self):
        """Sync app state back to client and save to disk."""
        self.client.state["selected_event"] = self.selected_event
        self.client.state["selected_team"] = self.selected_team
        self.client.state["selected_challenge"] = self.selected_challenge
        self.client.state["container_status"] = self.container_status
        self.client.save_state()


class MainMenu(Screen):
    """The main menu screen."""
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        # ASCII art banner (centered above the box)
        ascii_banner = """\033[38;2;159;239;0m
 ┓┏┏┳┓┳┓  ┳┳┓┏┓┏┓  ┏┓┓ ┳┏┓┳┓┏┳┓
 ┣┫ ┃ ┣┫━━┃┃┃┃ ┃┃  ┃ ┃ ┃┣ ┃┃ ┃ 
 ┛┗ ┻ ┻┛  ┛ ┗┗┛┣┛  ┗┛┗┛┻┗┛┛┗ ┻ 
\033[0m"""
        
        yield Vertical(
            Static(ascii_banner, id="ascii_banner"),
            Container(
                Label("", id="ids_display", classes="description"),
                Label("", id="container_display", classes="description"),
                Button("PLAY", id="btn_play", variant="success", disabled=True),
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
        self.update_display()

    def update_display(self):
        # Update IDs display
        event_name = self.app.selected_event.get('name', 'None') if self.app.selected_event else "None"
        team_name = self.app.selected_team.get('name', 'None') if self.app.selected_team else "None"
        chall_name = self.app.selected_challenge.get('name', 'None') if self.app.selected_challenge else "None"
        
        self.query_one("#ids_display").update(
            f"Event: {event_name} | Team: {team_name} | Challenge: {chall_name}"
        )

        # Update Container Status
        if self.app.container_status:
            ip = self.app.container_status.get("ip", "Unknown")
            port = self.app.container_status.get("port", "Unknown")
            self.query_one("#container_display").update(f"ACTIVE CONTAINER: {ip}:{port}")
            self.query_one("#container_display").styles.color = "#9FEF00"
        else:
            self.query_one("#container_display").update("No Active Container")
            self.query_one("#container_display").styles.color = "#A4B1CD"

        # Enable Play button if everything is selected
        can_play = all([self.app.selected_event, self.app.selected_team, self.app.selected_challenge])
        self.query_one("#btn_play").disabled = not can_play

    @on(Button.Pressed, "#btn_play")
    def on_play(self):
        self.app.push_screen("play_page")

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
        self.app.push_screen("resource_input")

    @on(Button.Pressed, "#btn_exit")
    def exit_app(self):
        self.app.exit()


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
