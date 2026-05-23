"""
HackTheBox MCP Client - Help / Getting Started modal screen
"""

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Container
from textual.screen import ModalScreen


class GettingStartedScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Container(
            Static(
                "[#9FEF00]HTB MCP Client - Getting Started[/]\n\n"
                "1. [b]Select Event[/]: Choose the CTF event.\n"
                "2. [b]Select Team[/]: Select your active team.\n"
                "3. [b]Select Challenge[/]: Browse and select a challenge.\n"
                "4. [b]Play Page[/]: Go to the Play Page to start containers.\n\n"
                "Press any key to close."
            ),
            id="getting_started_container"
        )

    def on_key(self, event):
        self.app.pop_screen()

    def on_click(self, event):
        self.app.pop_screen()
