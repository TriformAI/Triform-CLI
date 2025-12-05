"""Execute Triform components."""

import json
from pathlib import Path
from typing import Optional, Generator

from ..api import TriformAPI, APIError
from ..config import ProjectConfig, SyncState


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
        modifiers: Optional modifiers
    
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


def execute_component(
    component_id: str,
    payload: Optional[dict] = None,
    environment: Optional[list[dict]] = None,
    trace: bool = False,
    api: Optional[TriformAPI] = None
) -> dict | Generator[dict, None, None]:
    """
    Execute a component by ID.
    
    Args:
        component_id: The component ID to execute
        payload: Input values
        environment: Optional environment variables
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
    execution = build_execution_payload(component, payload, environment)
    
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
    
    # Find component by node key
    if node_key not in sync_state.components:
        # Try to find by directory name
        for key, state in sync_state.components.items():
            dir_name = Path(state.get("dir", "")).name
            if dir_name == node_key:
                node_key = key
                break
        else:
            raise ValueError(f"Component '{node_key}' not found in project")
    
    component_id = sync_state.components[node_key]["component_id"]
    
    # Load environment from project.json
    project_file = project_dir / "project.json"
    environment = []
    if project_file.exists():
        try:
            project_data = json.loads(project_file.read_text())
            environment = project_data.get("environment", {}).get("variables", [])
        except (json.JSONDecodeError, KeyError):
            pass
    
    return execute_component(
        component_id,
        payload=payload,
        environment=environment,
        trace=trace,
        api=api
    )


def print_execution_events(events: Generator[dict, None, None]) -> dict:
    """
    Print execution events as they arrive and return final result.
    
    Args:
        events: Generator of execution events
    
    Returns:
        Final result dict
    """
    last_result = {}
    
    for event in events:
        event_type = event.get("event", "unknown")
        path = event.get("path", [])
        path_str = " > ".join(path) if path else "root"
        
        if event_type == "running":
            print(f"🏃 Running: {path_str}")
            if event.get("payload"):
                print(f"   Payload: {json.dumps(event['payload'], indent=2)}")
        
        elif event_type == "completed":
            print(f"✅ Completed: {path_str}")
            output = event.get("output", {})
            if output:
                print(f"   Output: {json.dumps(output, indent=2)}")
            last_result = output
        
        elif event_type == "failed":
            print(f"❌ Failed: {path_str}")
            output = event.get("output", {})
            if output:
                print(f"   Error: {json.dumps(output, indent=2)}")
            stderr = event.get("stderr")
            if stderr:
                print(f"   Stderr: {stderr}")
            stacktrace = event.get("stacktrace")
            if stacktrace:
                print(f"   Stacktrace:\n{stacktrace}")
            last_result = {"error": output, "stderr": stderr, "stacktrace": stacktrace}
        
        else:
            print(f"📝 {event_type}: {path_str}")
    
    return last_result

