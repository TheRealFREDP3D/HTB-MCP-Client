"""
HackTheBox MCP Client - Core MCP session wrapper
"""

import json
from pathlib import Path
from typing import Optional, List, Any

from mcp import ClientSession
from mcp.types import Tool, Resource, Prompt


def extract_full_text(data: Any) -> str:
    """Extract full text from data.content blocks."""
    full_text = ""
    if hasattr(data, "content") and isinstance(data.content, list):
        for block in data.content:
            full_text += block.text if hasattr(block, "text") else str(block)
    return full_text


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

    async def get_tool_by_name(self, name: str) -> Optional[Tool]:
        tools = await self.list_tools()
        return next((t for t in tools if t.name == name), None)

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
