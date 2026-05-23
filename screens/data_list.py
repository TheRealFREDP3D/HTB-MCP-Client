"""
HackTheBox MCP Client - Data list and tool browsing screens
"""

from textual.app import ComposeResult
from textual.widgets import Header, Footer, Button, Label, DataTable
from textual.screen import Screen
from textual import on, work

from .tool_screens import ToolExecutionScreen


class DataListScreen(Screen):
    def __init__(self, title: str, data_type: str):
        super().__init__()
        self.screen_title = title
        self.data_type = data_type
        self.tools_map = {}

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
