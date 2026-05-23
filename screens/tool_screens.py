"""
HackTheBox MCP Client - Tool selection and execution screens
"""

import json
from typing import Optional, Dict, Any

from textual.app import ComposeResult
from textual.widgets import Header, Footer, Button, Label, DataTable, TextArea, Select, Markdown
from textual.containers import Container
from textual.screen import Screen
from textual import on, work
from mcp.types import Tool


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
        self._setup_args_table()
        self._apply_auto_exec_args()
        self._maybe_auto_execute()

    def _setup_args_table(self):
        try:
            table = self.query_one("#args_table")
            table.add_columns("Name", "Type", "Required", "Description")
            schema = self.tool.inputSchema
            if not schema or "properties" not in schema:
                return
            properties = schema.get("properties", {})
            required_list = schema.get("required", [])
            for prop_name, prop_details in properties.items():
                prop_type = prop_details.get("type", "unknown")
                is_required = "Yes" if prop_name in required_list else "No"
                desc = prop_details.get("description", "")
                table.add_row(prop_name, prop_type, is_required, desc)
        except Exception:
            pass

    def _apply_auto_exec_args(self):
        if not self.auto_exec_args:
            return
        try:
            current_text = self.query_one("#args_input").text
            current_json = json.loads(current_text)
            current_json.update(self.auto_exec_args)
            self.query_one("#args_input").load_text(json.dumps(current_json, indent=2))
        except Exception:
            pass

    def _maybe_auto_execute(self):
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
                mapping = {
                    "string": "<string>", "integer": 0, "number": 0.0,
                    "boolean": False, "array": [], "object": {}
                }
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
        from .challenge import ChallengeSelectionScreen
        from .event_team import EventSelectionScreen, TeamSelectionScreen
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
