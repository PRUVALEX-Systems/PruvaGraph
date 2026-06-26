import pytest

from pruvagraph import mcp_server


def test_tools_have_handlers():
    """Every tool declared in `TOOLS` must have a handler in `TOOL_HANDLERS`."""
    tools = getattr(mcp_server, "TOOLS", None)
    handlers = getattr(mcp_server, "TOOL_HANDLERS", None)

    assert isinstance(tools, list), "mcp_server.TOOLS must be a list"
    assert isinstance(handlers, dict), "mcp_server.TOOL_HANDLERS must be a dict"

    names = [t.get("name") for t in tools]
    for n in names:
        assert n in handlers, f"Tool '{n}' has no handler registered"


def test_no_duplicate_tool_names():
    """Tool names should be unique."""
    tools = getattr(mcp_server, "TOOLS", [])
    names = [t.get("name") for t in tools]
    assert len(names) == len(set(names)), "Duplicate tool names found in TOOLS"
