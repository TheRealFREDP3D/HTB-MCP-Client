"""
HackTheBox MCP Client - Challenge selection screen
"""

import json
from datetime import datetime
from typing import Any

from textual.app import ComposeResult
from textual.widgets import Header, Footer, Button, Label, DataTable, Markdown
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual import on, work

from client import extract_full_text
from config import CATEGORY_MAP


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
        try:
            full_text = extract_full_text(self.data)
            parsed_json = json.loads(full_text)
            self.challenges_data = (
                parsed_json.get("challenges", parsed_json)
                if isinstance(parsed_json, dict)
                else parsed_json
            )
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
