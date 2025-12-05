"""Push local changes to Triform."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..api import APIError, TriformAPI
from ..config import ProjectConfig, SyncState
from .pull import compute_checksum


def find_source_file(component_dir: Path) -> Optional[Path]:
    """Find the Python source file in a component directory."""
    for py_file in component_dir.glob("*.py"):
        if py_file.name != "__init__.py":
            return py_file
    return None


def read_action_folder(action_dir: Path) -> tuple[dict, dict, str]:
    """Read an action from the granular folder structure."""
    # Read source from {name}.py
    source = ""
    source_file = find_source_file(action_dir)
    if source_file and source_file.exists():
        source = source_file.read_text()
    
    # Read pip requirements
    pip_requirements = ""
    pip_file = action_dir / "pip_requirements.txt"
    if pip_file.exists():
        pip_requirements = pip_file.read_text()
    # Also check old name
    if not pip_requirements:
        pip_file = action_dir / "requirements.txt"
        if pip_file.exists():
            pip_requirements = pip_file.read_text()

    # Read readme
    readme = ""
    readme_file = action_dir / "readme.md"
    if readme_file.exists():
        readme = readme_file.read_text()
    
    # Read io.json
    inputs = {}
    outputs = {}
    io_file = action_dir / "io.json"
    if io_file.exists():
        io_data = json.loads(io_file.read_text())
        inputs = io_data.get("inputs", {})
        outputs = io_data.get("outputs", {})
    
    # Read requirements.json to get intention/description
    intention = ""
    req_file = action_dir / "requirements.json"
    if req_file.exists():
        req_data = json.loads(req_file.read_text())
        intention = req_data.get("description", "")

    meta = {
        "name": action_dir.name,
        "intention": intention,
        "starred": False
    }

    spec = {
        "source": source,
        "requirements": pip_requirements,
        "readme": readme,
        "runtime": "python-3.13",
        "inputs": inputs,
        "outputs": outputs
    }

    return meta, spec, compute_checksum(source)


def read_flow_folder(flow_dir: Path) -> tuple[dict, dict, str]:
    """Read a flow from the granular folder structure."""
    # Read readme
    readme = ""
    readme_file = flow_dir / "readme.md"
    if readme_file.exists():
        readme = readme_file.read_text()
    
    # Read io.json
    inputs = {}
    outputs = {}
    io_file = flow_dir / "io.json"
    if io_file.exists():
        io_data = json.loads(io_file.read_text())
        inputs = io_data.get("inputs", {})
        outputs = io_data.get("outputs", {})
    
    # Read nodes.json
    nodes = {}
    nodes_file = flow_dir / "nodes.json"
    if nodes_file.exists():
        nodes = json.loads(nodes_file.read_text())
    
    # Read io_nodes.json
    io_nodes = {"input": {"x": 0, "y": 0}, "output": {"x": 0, "y": 0}}
    io_nodes_file = flow_dir / "io_nodes.json"
    if io_nodes_file.exists():
        io_nodes = json.loads(io_nodes_file.read_text())
    
    # Read requirements.json to get intention
    intention = ""
    req_file = flow_dir / "requirements.json"
    if req_file.exists():
        req_data = json.loads(req_file.read_text())
        intention = req_data.get("description", "")

    meta = {
        "name": flow_dir.name,
        "intention": intention,
        "starred": False
    }
    
    spec = {
        "readme": readme,
        "nodes": nodes,
        "outputs": outputs,
        "inputs": inputs,
        "io_nodes": io_nodes
    }

    return meta, spec, compute_checksum(json.dumps(spec))


def read_agent_folder(agent_dir: Path) -> tuple[dict, dict, str]:
    """Read an agent from the granular folder structure."""
    # Read readme
    readme = ""
    readme_file = agent_dir / "readme.md"
    if readme_file.exists():
        readme = readme_file.read_text()
    
    # Read io.json
    inputs = {}
    outputs = {}
    io_file = agent_dir / "io.json"
    if io_file.exists():
        io_data = json.loads(io_file.read_text())
        inputs = io_data.get("inputs", {})
        outputs = io_data.get("outputs", {})
    
    # Read nodes.json
    nodes = {}
    nodes_file = agent_dir / "nodes.json"
    if nodes_file.exists():
        nodes = json.loads(nodes_file.read_text())
    
    # Read prompts.json
    prompts = {"system": [], "user": []}
    prompts_file = agent_dir / "prompts.json"
    if prompts_file.exists():
        prompts = json.loads(prompts_file.read_text())
    
    # Read settings.json
    model = "gemma-3-27b-it"
    settings = {}
    settings_file = agent_dir / "settings.json"
    if settings_file.exists():
        settings_data = json.loads(settings_file.read_text())
        model = settings_data.get("model", model)
        settings = settings_data.get("settings", {})
    
    # Read requirements.json to get intention
    intention = ""
    req_file = agent_dir / "requirements.json"
    if req_file.exists():
        req_data = json.loads(req_file.read_text())
        intention = req_data.get("description", "")

    meta = {
        "name": agent_dir.name,
        "intention": intention,
        "starred": False
    }
    
    spec = {
        "readme": readme,
        "model": model,
        "prompts": prompts,
        "settings": settings,
        "nodes": nodes,
        "inputs": inputs,
        "outputs": outputs
    }

    return meta, spec, compute_checksum(json.dumps(spec))


def detect_component_type(component_dir: Path) -> Optional[str]:
    """Detect the component type from folder contents."""
    # Check for source file (action)
    if find_source_file(component_dir):
        return "action"
    
    # Check for settings.json or prompts.json (agent)
    if (component_dir / "settings.json").exists() or (component_dir / "prompts.json").exists():
        return "agent"
    
    # Check for io_nodes.json (flow)
    if (component_dir / "io_nodes.json").exists():
        return "flow"
    
    # Check for nodes.json - could be flow or agent, default to flow
    if (component_dir / "nodes.json").exists():
        return "flow"
    
    return None


def read_component_folder(component_dir: Path) -> tuple[dict, dict, str, str]:
    """
    Read a component from the granular folder structure.
    Returns (meta, spec, checksum, component_type).
    """
    comp_type = detect_component_type(component_dir)
    
    if comp_type == "action":
        meta, spec, checksum = read_action_folder(component_dir)
    elif comp_type == "agent":
        meta, spec, checksum = read_agent_folder(component_dir)
    elif comp_type == "flow":
        meta, spec, checksum = read_flow_folder(component_dir)
    else:
        return {}, {}, "", ""
    
    return meta, spec, checksum, comp_type


def find_all_components(project_dir: Path) -> list[tuple[Path, str, str]]:
    """
    Find all component folders in the project directory.
    Returns list of (path, component_id, component_type) tuples.
    """
    components = []
    
    # Load sync state to get component IDs
    state_file = project_dir / ".triform" / "state.json"
    if not state_file.exists():
        return components
    
    try:
        state_data = json.loads(state_file.read_text())
        components_state = state_data.get("components", {})
    except (json.JSONDecodeError, IOError):
        return components
    
    # Build reverse map: dir -> (component_id, type)
    dir_to_id = {}
    for node_key, state in components_state.items():
        dir_name = state.get("dir", "")
        component_id = state.get("component_id", "")
        comp_type = state.get("type", "")
        if dir_name and component_id:
            dir_to_id[dir_name] = (component_id, comp_type)
    
    # Find all component folders (directories with nodes.json, io.json, or .py files)
    for item in project_dir.iterdir():
        if not item.is_dir():
            continue
        if item.name.startswith("."):
            continue
        if item.name == "triggers":
            continue
        
        # Check if this is a component folder
        comp_type = detect_component_type(item)
        if comp_type:
            # Look up component ID from state
            if item.name in dir_to_id:
                component_id, _ = dir_to_id[item.name]
                components.append((item, component_id, comp_type))
            
            # Also find nested components recursively
            components.extend(find_nested_components(item, project_dir, dir_to_id))
    
    return components


def find_nested_components(
    parent_dir: Path,
    project_dir: Path,
    dir_to_id: dict
) -> list[tuple[Path, str, str]]:
    """Find nested components within a parent component folder."""
    components = []
    
    for item in parent_dir.iterdir():
        if not item.is_dir():
            continue
        if item.name.startswith("."):
            continue
        
        comp_type = detect_component_type(item)
        if comp_type:
            # For nested components, the dir in state might be just the folder name
            # or a relative path - try to match
            if item.name in dir_to_id:
                component_id, _ = dir_to_id[item.name]
                components.append((item, component_id, comp_type))
            
            # Recursively find deeper nested components
            components.extend(find_nested_components(item, project_dir, dir_to_id))
    
    return components


def push_component(
    component_dir: Path,
    component_id: str,
    comp_type: str,
    api: TriformAPI,
    force: bool = False,
    stored_checksum: Optional[str] = None
) -> tuple[bool, str, Optional[str]]:
    """
    Push a single component to Triform.
    Returns (updated, message, new_checksum).
    """
    meta, spec, new_checksum, _ = read_component_folder(component_dir)
    
    if not force and stored_checksum and new_checksum == stored_checksum:
        return False, "unchanged", new_checksum
    
    try:
        if comp_type == "action":
            # Don't send inputs/outputs for actions - computed server-side
            spec_to_send = {
                "source": spec.get("source", ""),
                "requirements": spec.get("requirements", ""),
                "readme": spec.get("readme", ""),
                "runtime": spec.get("runtime", "python-3.13")
            }
            api.update_component(component_id, meta=meta, spec=spec_to_send)
        else:
            api.update_component(component_id, meta=meta, spec=spec)
        
        return True, "updated", new_checksum
    except APIError as e:
        return False, f"error: {e}", None


def push_project(
    project_dir: Optional[Path] = None,
    api: Optional[TriformAPI] = None,
    force: bool = False
) -> dict:
    """
    Push local changes to Triform.

    Handles the granular folder structure with separate files for
    io.json, nodes.json, prompts.json, settings.json, requirements.json, etc.

    Args:
        project_dir: Project directory (defaults to current dir)
        api: Optional API client instance
        force: Force push even if no changes detected

    Returns:
        Dict with push results
    """
    project_dir = Path(project_dir) if project_dir else Path.cwd()
    api = api or TriformAPI()

    # Load project config
    project_config = ProjectConfig.load(project_dir)
    if not project_config:
        raise ValueError(
            "Not a Triform project directory. "
            "Run 'triform pull <project_id>' first or ensure .triform/config.json exists."
        )

    project_id = project_config.project_id

    # Load sync state
    sync_state = SyncState.load(project_dir)

    print(f"Pushing changes for project '{project_config.project_name}'...")

    results = {
        "updated": [],
        "errors": [],
        "skipped": []
    }

    # Update project metadata from requirements.json
    req_file = project_dir / "requirements.json"
    
    try:
        meta_update = {"name": project_config.project_name}
        
        # Get intention/description from requirements.json
        if req_file.exists():
            req_data = json.loads(req_file.read_text())
            intention = req_data.get("description", "")
            if intention:
                meta_update["intention"] = intention
        
        api.update_project(project_id, meta=meta_update, spec=None)
        results["updated"].append("project metadata")
        print("  Updated project metadata")
    except APIError as e:
        results["errors"].append(f"project metadata: {e}")
        print(f"  Error updating project metadata: {e}")

    # Update project requirements
    if req_file.exists():
        try:
            req_data = json.loads(req_file.read_text())
            # Remove description field for requirements API
            requirements = {k: v for k, v in req_data.items() if k != "description"}
            if requirements:
                api.update_project_requirements(project_id, requirements)
                results["updated"].append("requirements.json")
                print("  Updated project requirements")
        except APIError as e:
            results["errors"].append(f"requirements.json: {e}")
            print(f"  Error updating requirements: {e}")

    # Find and push all components
    components = find_all_components(project_dir)
    
    if components:
        print(f"  Found {len(components)} components")
        
        # Build checksum map from sync state
        checksum_map = {}
        for node_key, state in sync_state.components.items():
            checksum_map[state.get("component_id")] = state.get("checksum")
        
        for component_path, component_id, comp_type in components:
            rel_path = str(component_path.relative_to(project_dir))
            stored_checksum = checksum_map.get(component_id)
            
            updated, message, new_checksum = push_component(
                component_path,
                component_id,
                comp_type,
                api,
                force,
                stored_checksum
            )
            
            if updated:
                results["updated"].append(rel_path)
                print(f"  Updated: {rel_path}")
                # Update sync state
                for node_key, state in sync_state.components.items():
                    if state.get("component_id") == component_id:
                        sync_state.components[node_key]["checksum"] = new_checksum
                        break
            elif "error" in message:
                results["errors"].append(f"{rel_path}: {message}")
                print(f"  Error: {rel_path} - {message}")
            else:
                results["skipped"].append(rel_path)
            
            # Also update component requirements
            comp_req_file = component_path / "requirements.json"
            if comp_req_file.exists():
                try:
                    comp_req_data = json.loads(comp_req_file.read_text())
                    comp_requirements = {k: v for k, v in comp_req_data.items() if k != "description"}
                    if comp_requirements:
                        api.update_component_requirements(component_id, comp_requirements)
                except APIError:
                    pass

    # Save updated sync state
    sync_state.last_sync = datetime.utcnow().isoformat()
    sync_state.save(project_dir)

    print("\nPush complete:")
    print(f"  - {len(results['updated'])} updated")
    print(f"  - {len(results['skipped'])} unchanged")
    if results["errors"]:
        print(f"  - {len(results['errors'])} errors")

    return results
