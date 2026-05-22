"""
HackTheBox MCP Client - Main application and menu
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Label, Static
from textual.containers import Vertical, Container
from textual.screen import Screen
from textual import on

from client import HTBMCPClient
from screens import (
    DataListScreen, ToolSelectionScreen, ToolExecutionScreen,
    PlayPage, GettingStartedScreen
)


APP_CSS = """
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


class MainMenu(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Vertical(
            Static(
                "[#9FEF00]\n ┓┏┏┳┓┳┓  ┳┳┓┏┓┏┓  ┏┓┓ ┳┏┓┳┓┏┳┓\n"
                " ┣┫ ┃ ┣┫━━┃┃┃┃ ┃┃  ┃ ┃ ┃┣ ┃┃ ┃ \n"
                " ┛┗ ┻ ┻┛  ┛ ┗┗┛┣┛  ┗┛┗┛┻┗┛┛┗ ┻ \n[/]",
                id="ascii_banner"
            ),
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
        self.query_one("#ids_display").update(
            f"Event: {event_name} | Team: {team_name} | Challenge: {chall_name}"
        )
        self.query_one("#btn_play").disabled = not all([
            self.app.selected_event,
            self.app.selected_team,
            self.app.selected_challenge
        ])

    @on(Button.Pressed, "#btn_list_events")
    async def list_events(self):
        tools = await self.app.client.list_tools()
        tool = next((t for t in tools if t.name == "list_ctf_events"), None)
        if tool:
            self.app.push_screen(ToolExecutionScreen(tool))

    @on(Button.Pressed, "#btn_list_teams")
    async def list_teams(self):
        tools = await self.app.client.list_tools()
        tool = next((t for t in tools if t.name == "retrieve_my_teams"), None)
        if tool:
            self.app.push_screen(ToolExecutionScreen(tool))

    @on(Button.Pressed, "#btn_list_challenges")
    async def list_challenges(self):
        tools = await self.app.client.list_tools()
        tool = next((t for t in tools if t.name == "retrieve_ctf"), None)
        if tool:
            self.app.push_screen(ToolExecutionScreen(tool))

    @on(Button.Pressed, "#btn_play")
    def on_play(self):
        self.app.push_screen("play_page")

    @on(Button.Pressed, "#btn_tools")
    def show_tools(self):
        self.app.push_screen("tools_list")

    @on(Button.Pressed, "#btn_call_tool")
    def call_tool(self):
        self.app.push_screen("tool_selection")

    @on(Button.Pressed, "#btn_help")
    def show_help(self):
        self.app.push_screen(GettingStartedScreen())

    @on(Button.Pressed, "#btn_exit")
    def exit_app(self):
        self.app.exit()


class HTBMCPApp(App):
    TITLE = "HackTheBox MCP Client"
    CSS = APP_CSS

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
