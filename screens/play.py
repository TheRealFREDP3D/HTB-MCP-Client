"""
HackTheBox MCP Client - Play mode screen
"""

from textual.app import ComposeResult
from textual.widgets import Header, Footer, Button, Label, DataTable, Markdown
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual import on


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
        table = self.query_one("#play_challenges_table")
        table.cursor_type = "row"
        table.add_columns("ID", "Name")
        if self.app.selected_challenge:
            table.add_row(
                str(self.app.selected_challenge.get('id')),
                self.app.selected_challenge.get('name')
            )
        self.display_current_challenge()

    def display_current_challenge(self):
        if self.app.selected_challenge:
            chall = self.app.selected_challenge
            md = f"# 🚩 {chall.get('name')}\n\n**ID**: {chall.get('id')}\n\n{chall.get('description', '')}"
            self.query_one("#play_markdown").update(md)

    @on(Button.Pressed, "#btn_start_container")
    async def start_container(self):
        from screens.tool_screens import ToolExecutionScreen
        if self.app.selected_challenge:
            tools = await self.app.client.list_tools()
            tool = next((t for t in tools if t.name == "start_container"), None)
            if tool:
                self.app.push_screen(ToolExecutionScreen(
                    tool,
                    auto_exec_args={"challenge_id": self.app.selected_challenge.get("id")}
                ))

    @on(Button.Pressed, "#btn_stop_container")
    async def stop_container(self):
        from screens.tool_screens import ToolExecutionScreen
        tools = await self.app.client.list_tools()
        tool = next((t for t in tools if t.name == "stop_container"), None)
        if tool:
            self.app.push_screen(ToolExecutionScreen(tool))

    @on(Button.Pressed, "#btn_download")
    async def download_files(self):
        from screens.tool_screens import ToolExecutionScreen
        if self.app.selected_challenge:
            tools = await self.app.client.list_tools()
            tool = next((t for t in tools if t.name == "download_challenge"), None)
            if tool:
                self.app.push_screen(ToolExecutionScreen(
                    tool,
                    auto_exec_args={"challenge_id": self.app.selected_challenge.get("id")}
                ))

    @on(Button.Pressed, "#btn_back")
    def go_back(self):
        self.app.switch_screen("main_menu")
