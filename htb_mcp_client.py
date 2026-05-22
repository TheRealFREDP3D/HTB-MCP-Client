#!/usr/bin/env python3
"""
HackTheBox MCP Client
A Textual-based TUI client for the HackTheBox Model Context Protocol server.
"""

__version__ = "1.0.0"
__author__ = "Fred P3D"
__license__ = "MIT"

CATEGORY_MAP = {
    "1": "Web",
    "2": "Pwn",
    "3": "Crypto",
    "4": "Reverse",
    "5": "Forensics",
    "6": "Misc",
    "7": "OSINT",
    "8": "Hardware",
    "9": "Mobile",
    "10": "Cloud"
}

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
    def __init__(self, session: ClientSession):
        self.session = session
        self.tools_cache = []
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
                pass

    def save_state(self):
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    async def list_tools(self) -> List[Tool]:
        if self.tools_cache:
            return self.tools_cache
        result = await self.session.list_tools()
        self.tools_cache = result.tools
        return self.tools_cache

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
    def __init__(self, title: str, data_type: str):
        super().__init__()
        self.screen_title = title
        self.data_type = data_type

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
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
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
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
    def __init__(self, tool: Tool, auto_exec_args: Optional[Dict] = None):
        super().__init__()
        self.tool = tool
        self.auto_exec_args = auto_exec_args or {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label(f"Execute Tool: {self.tool.name}", classes="screen_title")
        if self.tool.description:
            yield Label(self.tool.description, classes="description")
        
        schema = self.tool.inputSchema
        has_args = schema and "properties" in schema and schema["properties"]
        
        if has_args:
            yield Label("Argument Schema:", classes="label")
            yield DataTable(id="args_table")
        else:
            yield Label("No arguments required.", classes="description")

        yield Label("Arguments (JSON):", classes="label")
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
            pass

        if self.tool.name == "list_ctf_events" or self.auto_exec_args:
            if self.auto_exec_args:
                 current_text = self.query_one("#args_input").text
                 try:
                     current_json = json.loads(current_text)
                     current_json.update(self.auto_exec_args)
                     self.query_one("#args_input").load_text(json.dumps(current_json, indent=2))
                 except:
                     pass
            
            if self.tool.name == "list_ctf_events":
                self.execute_tool()

    def _generate_template_from_schema(self, schema: Dict[str, Any]) -> str:
        if not schema or "properties" not in schema:
            return "{}"
        
        template = {}
        properties = schema.get("properties", {})
        
        selected_event = getattr(self.app, "selected_event", None)
        selected_challenge = getattr(self.app, "selected_challenge", None)
        
        for prop_name, prop_details in properties.items():
            value_placeholder = None
            prop_type = prop_details.get("type", "string")
            
            if prop_name in self.auto_exec_args:
                value_placeholder = self.auto_exec_args[prop_name]
            elif selected_event and prop_name in ["ctf_id", "id", "event_id"] and "id" in selected_event:
                 event_id = selected_event["id"]
                 value_placeholder = int(event_id) if prop_type == "integer" else str(event_id)
            elif selected_challenge and prop_name in ["challenge_id", "id"] and "id" in selected_challenge:
                 challenge_id = selected_challenge["id"]
                 value_placeholder = int(challenge_id) if prop_type == "integer" else str(challenge_id)
            elif "default" in prop_details:
                value_placeholder = prop_details["default"]
            else:
                mapping = {"string": "<string>", "integer": 0, "number": 0.0, "boolean": False, "array": [], "object": {}}
                value_placeholder = mapping.get(prop_type, "<value>")
                
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
            if self.tool.name == "list_ctf_events":
                self.app.push_screen(EventSelectionScreen(result, f"Tool Result: {self.tool.name}", self.tool.name))
            elif self.tool.name == "retrieve_ctf":
                self.app.push_screen(ChallengeSelectionScreen(result, f"Tool Result: {self.tool.name}", self.tool.name))
            elif self.tool.name == "retrieve_my_teams":
                self.app.push_screen(TeamSelectionScreen(result, f"Tool Result: {self.tool.name}", self.tool.name))
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
    CSS = """
    #challenges_container { layout: horizontal; height: 1fr; }
    #challenges_table { width: 50%; }
    #challenge_details { width: 50%; border: heavy #9FEF00; padding: 1; }
    #buttons_container { width: 50%; align: center middle; }
    """

    def __init__(self, data: Any, title: str, tool_name: str = "tool"):
        super().__init__()
        self.data = data
        self.page_title = title
        self.tool_name = tool_name
        self.challenges_data = []
        self.markdown_content = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label(self.page_title, classes="screen_title")
        yield Horizontal(DataTable(id="challenges_table"), Markdown("", id="challenge_details"), id="challenges_container")
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
        try:
            full_text = ""
            if hasattr(self.data, "content") and isinstance(self.data.content, list):
                for block in self.data.content:
                    full_text += block.text if hasattr(block, "text") else str(block)
            parsed_json = json.loads(full_text)
            self.challenges_data = parsed_json.get("challenges", parsed_json) if isinstance(parsed_json, dict) else parsed_json
        except Exception:
            pass

        table = self.query_one("#challenges_table")
        table.cursor_type = "row"
        table.add_columns("ID", "Name", "Category", "Diff", "Pts", "Solved")
        
        for idx, chall in enumerate(self.challenges_data):
            if isinstance(chall, dict):
                c_id = str(chall.get('id', ''))
                name = chall.get('name', 'Unknown')
                cat_id = str(chall.get('challenge_category_id', ''))
                cat = CATEGORY_MAP.get(cat_id, cat_id)
                diff = chall.get('difficulty', '')
                pts = str(chall.get('points', ''))
                solved = "Yes" if chall.get('solved') else "No"
                table.add_row(c_id, name, cat, diff, pts, solved, key=str(idx))
        
        table.focus()
        if self.challenges_data:
            self.display_challenge_details(self.challenges_data[0])

    def display_challenge_details(self, chall: dict):
        md = f"## 🚩 {chall.get('name', 'Unknown')}\n\n"
        md += f"**ID**: {chall.get('id', 'N/A')}\n\n"
        md += f"**Difficulty**: {chall.get('difficulty', 'N/A')}\n\n"
        md += f"**Points**: {chall.get('points', 'N/A')}\n\n"
        md += f"**Solved**: {chall.get('solved', False)}\n\n"
        if desc := chall.get('description', ''):
             md += f"### Description\n{desc}\n\n"
        self.markdown_content = md
        self.query_one("#challenge_details").update(md)

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted):
        if event.row_key:
            idx = int(event.row_key.value)
            if 0 <= idx < len(self.challenges_data):
                self.display_challenge_details(self.challenges_data[idx])

    @on(Button.Pressed, "#btn_select")
    def select_challenge(self):
        table = self.query_one("#challenges_table")
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self.challenges_data):
            selected = self.challenges_data[table.cursor_row]
            self.app.selected_challenge = selected
            self.app.save_app_state()
            self.app.notify(f"Selected Challenge: {selected.get('name')}")
            self.app.switch_screen("main_menu")

    @on(Button.Pressed, "#btn_save_md")
    def save_md(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.tool_name}-{timestamp}.md"
        full_md = "# CTF Challenges\n\n"
        for chall in self.challenges_data:
            if isinstance(chall, dict):
                full_md += f"## 🚩 {chall.get('name')}\n**ID**: {chall.get('id')}\n\n---\n\n"
        path = self.app.client.save_to_file(full_md, filename)
        self.app.notify(f"Saved to {path}")

    @on(Button.Pressed, "#btn_back")
    def go_back(self):
        self.app.pop_screen()


class PlayPage(Screen):
    CSS = """
    #play_container { layout: horizontal; height: 1fr; }
    #challenges_list { width: 30%; border-right: heavy #9FEF00; }
    #play_details { width: 70%; padding: 1; }
    #play_actions { height: auto; align: center middle; padding: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label("Play Mode", classes="screen_title")
        yield Horizontal(
            Vertical(Label("Challenges", classes="label"), DataTable(id="play_challenges_table"), id="challenges_list"),
            Vertical(Markdown("", id="play_markdown"), Container(
                Button("Start Container", id="btn_start_container", variant="success"),
                Button("Stop Container", id="btn_stop_container", variant="error"),
                Button("Download Files", id="btn_download", variant="primary"),
                Button("Back to Menu", id="btn_back"),
                id="play_actions"
            ), id="play_details"),
            id="play_container"
        )
        yield Footer()

    def on_mount(self):
        table = self.query_one("#play_challenges_table")
        table.cursor_type = "row"
        table.add_columns("ID", "Name")
        if self.app.selected_challenge:
            table.add_row(str(self.app.selected_challenge.get('id')), self.app.selected_challenge.get('name'))
        self.display_current_challenge()

    def display_current_challenge(self):
        if self.app.selected_challenge:
            chall = self.app.selected_challenge
            md = f"# 🚩 {chall.get('name')}\n\n**ID**: {chall.get('id')}\n\n{chall.get('description', '')}"
            self.query_one("#play_markdown").update(md)

    @on(Button.Pressed, "#btn_start_container")
    async def start_container(self):
        if self.app.selected_challenge:
            tools = await self.app.client.list_tools()
            tool = next((t for t in tools if t.name == "start_container"), None)
            if tool:
                self.app.push_screen(ToolExecutionScreen(tool, auto_exec_args={"challenge_id": self.app.selected_challenge.get("id")}))

    @on(Button.Pressed, "#btn_stop_container")
    async def stop_container(self):
        tools = await self.app.client.list_tools()
        tool = next((t for t in tools if t.name == "stop_container"), None)
        if tool:
            self.app.push_screen(ToolExecutionScreen(tool))

    @on(Button.Pressed, "#btn_download")
    async def download_files(self):
        if self.app.selected_challenge:
            tools = await self.app.client.list_tools()
            tool = next((t for t in tools if t.name == "download_challenge"), None)
            if tool:
                self.app.push_screen(ToolExecutionScreen(tool, auto_exec_args={"challenge_id": self.app.selected_challenge.get("id")}))

    @on(Button.Pressed, "#btn_back")
    def go_back(self):
        self.app.switch_screen("main_menu")


class TeamSelectionScreen(Screen):
    def __init__(self, data: Any, title: str, tool_name: str = "tool"):
        super().__init__()
        self.data = data
        self.page_title = title
        self.tool_name = tool_name
        self.teams_data = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label(self.page_title, classes="screen_title")
        yield DataTable(id="teams_table")
        yield Button("Close", id="btn_close")
        yield Footer()

    def on_mount(self):
        self.process_teams()

    @work
    async def process_teams(self):
        try:
            full_text = ""
            if hasattr(self.data, "content") and isinstance(self.data.content, list):
                for block in self.data.content:
                    full_text += block.text if hasattr(block, "text") else str(block)
            self.teams_data = json.loads(full_text)
        except Exception:
            pass
        table = self.query_one("#teams_table")
        table.cursor_type = "row"
        table.add_columns("ID", "Name")
        for idx, team in enumerate(self.teams_data):
            table.add_row(str(team.get('id')), team.get('name'), key=str(idx))

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected):
        idx = int(event.row_key.value)
        self.app.selected_team = self.teams_data[idx]
        self.app.save_app_state()
        self.app.notify(f"Selected Team: {self.app.selected_team.get('name')}")
        self.app.switch_screen("main_menu")

    @on(Button.Pressed, "#btn_close")
    def close(self):
        self.app.pop_screen()


class EventSelectionScreen(Screen):
    def __init__(self, data: Any, title: str, tool_name: str = "tool"):
        super().__init__()
        self.data = data
        self.page_title = title
        self.tool_name = tool_name
        self.events_data = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label(self.page_title, classes="screen_title")
        yield DataTable(id="events_table")
        yield Button("Close", id="btn_close")
        yield Footer()

    def on_mount(self):
        self.process_events()

    @work
    async def process_events(self):
        try:
            full_text = ""
            if hasattr(self.data, "content") and isinstance(self.data.content, list):
                for block in self.data.content:
                    full_text += block.text if hasattr(block, "text") else str(block)
            self.events_data = json.loads(full_text)
        except Exception:
            pass
        table = self.query_one("#events_table")
        table.cursor_type = "row"
        table.add_columns("ID", "Name")
        for idx, event in enumerate(self.events_data):
            table.add_row(str(event.get('id')), event.get('name'), key=str(idx))

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected):
        idx = int(event.row_key.value)
        self.app.selected_event = self.events_data[idx]
        self.app.save_app_state()
        self.app.notify(f"Selected Event: {self.app.selected_event.get('name')}")
        self.app.switch_screen("main_menu")

    @on(Button.Pressed, "#btn_close")
    def close(self):
        self.app.pop_screen()


class ResultScreen(Screen):
    def __init__(self, data: Any, title: str, tool_name: str = "tool"):
        super().__init__()
        self.data = data
        self.page_title = title
        self.tool_name = tool_name

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label(self.page_title, classes="screen_title")
        yield Markdown(str(self.data), id="result_markdown")
        yield Button("Close", id="btn_close")
        yield Footer()

    @on(Button.Pressed, "#btn_close")
    def close(self):
        self.app.pop_screen()


class GettingStartedScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Container(
            Static("[#9FEF00]HTB MCP Client - Getting Started[/]\n\n"
                   "1. [b]Select Event[/]: Choose the CTF event.\n"
                   "2. [b]Select Team[/]: Select your active team.\n"
                   "3. [b]Select Challenge[/]: Browse and select a challenge.\n"
                   "4. [b]Play Page[/]: Go to the Play Page to start containers.\n\n"
                   "Press any key to close."),
            id="getting_started_container"
        )

    def on_key(self):
        self.app.pop_screen()

    def on_click(self):
        self.app.pop_screen()


class HTBMCPApp(App):
    TITLE = "HackTheBox MCP Client"
    CSS = """
    Screen { align: center middle; background: #1A2332; }
    * { color: #A4B1CD; scrollbar-background: #1A2332; scrollbar-color: #9FEF00; }
    #main_menu_container { width: 75; height: auto; border: heavy #9FEF00; background: #1A2332; padding: 1 2; }
    #ascii_banner { text-align: center; width: 100%; color: #9FEF00; }
    #workflow_label { text-align: center; width: 100%; margin-top: 1; }
    #ids_display { text-align: center; width: 100%; color: #5CB2FF; text-style: bold; margin-bottom: 1; }
    Button { width: 100%; margin-bottom: 1; border: solid #313F55; background: #1A2332; }
    Button:hover { background: #313F55; border: solid #9FEF00; color: #9FEF00; }
    Button.-primary { border: solid #5CB2FF; color: #5CB2FF; }
    Button.-success { border: solid #9FEF00; color: #9FEF00; }
    Button.-warning { border: solid #FFAF00; color: #FFAF00; }
    Button.-error { border: solid #FF3E3E; color: #FF3E3E; }
    .screen_title { text-align: center; text-style: bold; margin: 1; color: #9FEF00; border-bottom: solid #9FEF00; }
    DataTable { height: 1fr; border: heavy #9FEF00; }
    #getting_started_container { width: 60; height: auto; border: thick #9FEF00; background: #1A2332; padding: 2; align: center middle; }
    """

    def __init__(self, client: HTBMCPClient):
        super().__init__()
        self.client = client
        self.selected_event = self.client.state.get("selected_event")
        self.selected_team = self.client.state.get("selected_team")
        self.selected_challenge = self.client.state.get("selected_challenge")

    def on_mount(self):
        self.update_title()
        self.install_screen(MainMenu(), name="main_menu")
        self.install_screen(DataListScreen("Available Tools", "tools"), name="tools_list")
        self.install_screen(ToolSelectionScreen(), name="tool_selection")
        self.install_screen(PlayPage(), name="play_page")
        self.push_screen("main_menu")

    def save_app_state(self):
        self.client.state["selected_event"] = self.selected_event
        self.client.state["selected_team"] = self.selected_team
        self.client.state["selected_challenge"] = self.selected_challenge
        self.client.save_state()
        self.update_title()

    def update_title(self):
        event = self.selected_event.get("name") if self.selected_event else "No Event"
        chall = self.selected_challenge.get("name") if self.selected_challenge else "No Challenge"
        self.title = f"HTB MCP - {event} / {chall}"


class MainMenu(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Vertical(
            Static("[#9FEF00]\n ┓┏┏┳┓┳┓  ┳┳┓┏┓┏┓  ┏┓┓ ┳┏┓┳┓┏┳┓\n ┣┫ ┃ ┣┫━━┃┃┃┃ ┃┃  ┃ ┃ ┃┣ ┃┃ ┃ \n ┛┗ ┻ ┻┛  ┛ ┗┗┛┣┛  ┗┛┗┛┻┗┛┛┗ ┻ \n[/]", id="ascii_banner"),
            Container(
                Label("", id="ids_display"),
                Label("--- WORKFLOW ---", classes="label", id="workflow_label"),
                Button("1. Select Event", id="btn_list_events", variant="primary"),
                Button("2. Select Team", id="btn_list_teams", variant="primary"),
                Button("3. Select Challenge", id="btn_list_challenges", variant="primary"),
                Button("GO TO PLAY PAGE", id="btn_play", variant="success", disabled=True),
                Label("--- OTHER TOOLS ---", classes="label"),
                Button("List Tools", id="btn_tools"),
                Button("Call Tool", id="btn_call_tool"),
                Button("Help", id="btn_help", variant="warning"),
                Button("Exit", id="btn_exit", variant="error"),
                id="main_menu_container"
            ),
            id="main_menu_wrapper"
        )
        yield Footer()

    def on_mount(self):
        self.update_display()

    def update_display(self):
        event_name = self.app.selected_event.get('name', 'None') if self.app.selected_event else "None"
        team_name = self.app.selected_team.get('name', 'None') if self.app.selected_team else "None"
        chall_name = self.app.selected_challenge.get('name', 'None') if self.app.selected_challenge else "None"
        self.query_one("#ids_display").update(f"Event: {event_name} | Team: {team_name} | Challenge: {chall_name}")
        self.query_one("#btn_play").disabled = not all([self.app.selected_event, self.app.selected_team, self.app.selected_challenge])

    @on(Button.Pressed, "#btn_list_events")
    async def list_events(self):
        tools = await self.app.client.list_tools()
        tool = next((t for t in tools if t.name == "list_ctf_events"), None)
        if tool: self.app.push_screen(ToolExecutionScreen(tool))

    @on(Button.Pressed, "#btn_list_teams")
    async def list_teams(self):
        tools = await self.app.client.list_tools()
        tool = next((t for t in tools if t.name == "retrieve_my_teams"), None)
        if tool: self.app.push_screen(ToolExecutionScreen(tool))

    @on(Button.Pressed, "#btn_list_challenges")
    async def list_challenges(self):
        tools = await self.app.client.list_tools()
        tool = next((t for t in tools if t.name == "retrieve_ctf"), None)
        if tool: self.app.push_screen(ToolExecutionScreen(tool))

    @on(Button.Pressed, "#btn_play")
    def on_play(self): self.app.push_screen("play_page")

    @on(Button.Pressed, "#btn_tools")
    def show_tools(self): self.app.push_screen("tools_list")

    @on(Button.Pressed, "#btn_call_tool")
    def call_tool(self): self.app.push_screen("tool_selection")

    @on(Button.Pressed, "#btn_help")
    def show_help(self): self.app.push_screen(GettingStartedScreen())

    @on(Button.Pressed, "#btn_exit")
    def exit_app(self): self.app.exit()


async def main():
    config = dotenv_values()
    api_token = os.getenv("API_ACCESS_TOKEN") or config.get("API_ACCESS_TOKEN")
    url = os.getenv("HTB_MCP_URL") or config.get("HTB_MCP_URL", "https://mcp.hackthebox.ai/v1/ctf/mcp/")
    if not api_token: sys.exit(1)
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        async with streamablehttp_client(url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                client_helper = HTBMCPClient(session)
                app = HTBMCPApp(client_helper)
                await app.run_async()
    except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
