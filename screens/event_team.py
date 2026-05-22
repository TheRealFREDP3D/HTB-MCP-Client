"""
HackTheBox MCP Client - Event and Team selection screens
"""

import json
from typing import Any

from textual.app import ComposeResult
from textual.widgets import Header, Footer, Button, Label, DataTable
from textual.screen import Screen
from textual import on, work

from client import extract_full_text


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
            full_text = extract_full_text(self.data)
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
            full_text = extract_full_text(self.data)
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
