"""Execute Triform components."""

import json
import sys
from pathlib import Path
from typing import Optional, Generator

from ..api import TriformAPI, APIError
from ..config import ProjectConfig, SyncState


def _print(msg: str):
    """Print with immediate flush."""
    print(msg, flush=True)


def build_execution_payload(
    component: dict,
    payload: dict,
    environment: Optional[list[dict]] = None,
    modifiers: Optional[dict] = None
) -> dict:
    """
    Build an execution payload for the API.
    
    Args:
        component: Resolved component dict
        payload: Input values
        environment: Optional environment variables
        modifiers: Optional modifiers (node_path -> [{modifier_id, spec}])
    
    Returns:
        Execution payload dict
    """
    return {
        "resource": "execution/v1",
        "meta": {"name": ""},
        "spec": {
            "component": component,
            "payload": payload,
            "modifiers": modifiers or {},
            "environment": {
                "variables": environment or []
            }
        }
    }


def get_project_modifiers(project: dict, node_key: str) -> dict:
    """
    Extract modifiers relevant to a node from project spec.
    
    Modifiers are mapped by path like "node_key/child_node_key".
    We need to include any modifiers that start with our node_key.
    
    Args:
        project: Project dict with spec.modifiers
        node_key: The node key we're executing
    
    Returns:
        Filtered modifiers dict
    """
    all_modifiers = project.get("spec", {}).get("modifiers", {})
    relevant_modifiers = {}
    
    for path, mods in all_modifiers.items():
        # Include modifiers for this node or its children
        if path.startswith(node_key):
            relevant_modifiers[path] = mods
    
    return relevant_modifiers


def execute_component(
    component_id: str,
    payload: Optional[dict] = None,
    environment: Optional[list[dict]] = None,
    modifiers: Optional[dict] = None,
    trace: bool = False,
    api: Optional[TriformAPI] = None
) -> dict | Generator[dict, None, None]:
    """
    Execute a component by ID.
    
    Args:
        component_id: The component ID to execute
        payload: Input values
        environment: Optional environment variables
        modifiers: Optional modifiers mapping
        trace: If True, stream execution events
        api: Optional API client instance
    
    Returns:
        If trace=False: Final result dict
        If trace=True: Generator yielding execution events
    """
    api = api or TriformAPI()
    payload = payload or {}
    
    # Fetch the component with full resolution
    component = api.get_component(component_id, depth=999)
    if not component:
        raise ValueError(f"Component {component_id} not found")
    
    # Build execution payload
    execution = build_execution_payload(component, payload, environment, modifiers)
    
    if trace:
        return api.execute_trace(execution)
    else:
        result = api.execute_run(execution)
        return result


def execute_from_project(
    node_key: str,
    payload: Optional[dict] = None,
    project_dir: Optional[Path] = None,
    trace: bool = False,
    api: Optional[TriformAPI] = None
) -> dict | Generator[dict, None, None]:
    """
    Execute a component from a local project by node key.
    
    Args:
        node_key: The node key in the project (e.g., "my_action")
        payload: Input values
        project_dir: Project directory (defaults to current dir)
        trace: If True, stream execution events
        api: Optional API client instance
    
    Returns:
        If trace=False: Final result dict
        If trace=True: Generator yielding execution events
    """
    project_dir = Path(project_dir) if project_dir else Path.cwd()
    api = api or TriformAPI()
    
    # Load project config
    project_config = ProjectConfig.load(project_dir)
    if not project_config:
        raise ValueError("Not a Triform project directory")
    
    # Load sync state
    sync_state = SyncState.load(project_dir)
    
    original_node_key = node_key
    
    # Find component by node key
    if node_key not in sync_state.components:
        # Try to find by directory name
        for key, state in sync_state.components.items():
            dir_name = Path(state.get("dir", "")).name
            if dir_name == node_key:
                node_key = key
                break
        else:
            raise ValueError(f"Component '{original_node_key}' not found in project")
    
    component_id = sync_state.components[node_key]["component_id"]
    
    # Fetch the full project to get environment and modifiers
    project = api.get_project(project_config.project_id)
    environment = project.get("spec", {}).get("environment", {}).get("variables", [])
    
    # Get modifiers relevant to this node
    modifiers = get_project_modifiers(project, node_key)
    if modifiers:
        _print(f"📎 Found {len(modifiers)} modifier mapping(s) for this component")
    
    return execute_component(
        component_id,
        payload=payload,
        environment=environment,
        modifiers=modifiers,
        trace=trace,
        api=api
    )


def print_execution_events(events: Generator[dict, None, None], verbose: bool = True) -> dict:
    """
    Print execution events as they arrive and return final result.
    
    Args:
        events: Generator of execution events
        verbose: If True, show full payloads/outputs
    
    Returns:
        Final result dict
    """
    last_result = {}
    event_count = 0
    
    def get_indent(path: list) -> str:
        """Get indentation based on path depth."""
        return "  " * len(path)
    
    def format_component_name(path: list) -> str:
        """Format component name from path."""
        if not path:
            return "root"
        # Extract meaningful name from path element
        name = path[-1]
        # Tool calls often have format "node_id:tool_xxx" - extract the tool part
        if ":tool_" in name:
            return name.split(":")[0][:12] + " (tool)"
        return name[:30] if len(name) > 30 else name
    
    def truncate(s: str, max_len: int = 200) -> str:
        """Truncate string for display."""
        if len(s) <= max_len:
            return s
        return s[:max_len] + "..."
    
    _print("📡 Streaming execution events...\n")
    
    for event in events:
        event_count += 1
        event_type = event.get("event", "unknown")
        path = event.get("path", [])
        indent = get_indent(path)
        component = format_component_name(path)
        depth = len(path)
        
        if event_type == "running":
            # Highlight tool/action calls
            if depth > 0:
                _print(f"{indent}🔧 Calling: {component}")
            else:
                _print(f"🚀 Starting execution: {component}")
            
            payload = event.get("payload", {})
            if verbose and payload:
                # Show key inputs without overwhelming output
                for key, value in list(payload.items())[:3]:
                    value_str = json.dumps(value) if not isinstance(value, str) else value
                    _print(f"{indent}   📥 {key}: {truncate(value_str, 80)}")
                if len(payload) > 3:
                    _print(f"{indent}   ... and {len(payload) - 3} more inputs")
        
        elif event_type == "completed":
            output = event.get("output", {})
            
            if depth > 0:
                _print(f"{indent}✅ {component} completed")
            else:
                _print(f"\n✅ Execution completed")
            
            if verbose and output:
                # Show key outputs
                if isinstance(output, dict):
                    for key, value in list(output.items())[:3]:
                        value_str = json.dumps(value) if not isinstance(value, str) else value
                        _print(f"{indent}   📤 {key}: {truncate(value_str, 120)}")
                    if len(output) > 3:
                        _print(f"{indent}   ... and {len(output) - 3} more outputs")
                else:
                    _print(f"{indent}   📤 {truncate(str(output), 200)}")
            
            last_result = output
        
        elif event_type == "failed":
            if depth > 0:
                _print(f"{indent}❌ {component} FAILED")
            else:
                _print(f"\n❌ Execution FAILED")
            
            output = event.get("output", {})
            if output:
                error_msg = output.get("message") or output.get("error") or str(output)
                _print(f"{indent}   Error: {truncate(str(error_msg), 300)}")
            
            stderr = event.get("stderr")
            if stderr:
                _print(f"{indent}   Stderr: {truncate(stderr, 200)}")
            
            stacktrace = event.get("stacktrace")
            if stacktrace and verbose:
                lines = stacktrace.strip().split('\n')
                _print(f"{indent}   Stacktrace (last 3 lines):")
                for line in lines[-3:]:
                    _print(f"{indent}     {line}")
            
            last_result = {"error": output, "stderr": stderr, "stacktrace": stacktrace}
        
        else:
            _print(f"{indent}📝 {event_type}: {component}")
    
    _print(f"\n📊 Total events: {event_count}")
    return last_result

