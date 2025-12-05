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


def read_triform_json(component_dir: Path) -> Optional[dict]:
    """Read .triform.json from component folder."""
    triform_file = component_dir / ".triform.json"
    if triform_file.exists():
        try:
            return json.loads(triform_file.read_text())
        except json.JSONDecodeError:
            pass
    return None


def write_triform_json(component_dir: Path, component_id: str, comp_type: str) -> None:
    """Write .triform.json to component folder."""
    triform_file = component_dir / ".triform.json"
    triform_file.write_text(json.dumps({
        "id": component_id,
        "type": comp_type
    }, indent=2))


def detect_component_type(component_dir: Path) -> Optional[str]:
    """Detect component type from folder contents."""
    if find_source_file(component_dir):
        return "action"
    if (component_dir / "settings.json").exists() or (component_dir / "prompts.json").exists():
        return "agent"
    if (component_dir / "io_nodes.json").exists():
        return "flow"
    if (component_dir / "nodes.json").exists():
        return "flow"
    return None


def read_action_folder(action_dir: Path) -> tuple[dict, dict, str]:
    """Read an action from the folder structure."""
    source = ""
    source_file = find_source_file(action_dir)
    if source_file and source_file.exists():
        source = source_file.read_text()
    
    pip_requirements = ""
    for pip_name in ["pip_requirements.txt", "requirements.txt"]:
        pip_file = action_dir / pip_name
        if pip_file.exists():
            pip_requirements = pip_file.read_text()
            break
    
    readme = ""
    readme_file = action_dir / "readme.md"
    if readme_file.exists():
        readme = readme_file.read_text()
    
    inputs = {}
    outputs = {}
    io_file = action_dir / "io.json"
    if io_file.exists():
        io_data = json.loads(io_file.read_text())
        inputs = io_data.get("inputs", {})
        outputs = io_data.get("outputs", {})
    
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
    """Read a flow from the folder structure."""
    readme = ""
    readme_file = flow_dir / "readme.md"
    if readme_file.exists():
        readme = readme_file.read_text()
    
    inputs = {}
    outputs = {}
    io_file = flow_dir / "io.json"
    if io_file.exists():
        io_data = json.loads(io_file.read_text())
        inputs = io_data.get("inputs", {})
        outputs = io_data.get("outputs", {})
    
    nodes = {}
    nodes_file = flow_dir / "nodes.json"
    if nodes_file.exists():
        nodes = json.loads(nodes_file.read_text())
    
    io_nodes = {"input": {"x": 0, "y": 0}, "output": {"x": 0, "y": 0}}
    io_nodes_file = flow_dir / "io_nodes.json"
    if io_nodes_file.exists():
        io_nodes = json.loads(io_nodes_file.read_text())
    
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
    """Read an agent from the folder structure."""
    readme = ""
    readme_file = agent_dir / "readme.md"
    if readme_file.exists():
        readme = readme_file.read_text()
    
    inputs = {}
    outputs = {}
    io_file = agent_dir / "io.json"
    if io_file.exists():
        io_data = json.loads(io_file.read_text())
        inputs = io_data.get("inputs", {})
        outputs = io_data.get("outputs", {})
    
    nodes = {}
    nodes_file = agent_dir / "nodes.json"
    if nodes_file.exists():
        nodes = json.loads(nodes_file.read_text())
    
    prompts = {"system": [], "user": []}
    prompts_file = agent_dir / "prompts.json"
    if prompts_file.exists():
        prompts = json.loads(prompts_file.read_text())
    
    model = "gemma-3-27b-it"
    settings = {}
    settings_file = agent_dir / "settings.json"
    if settings_file.exists():
        settings_data = json.loads(settings_file.read_text())
        model = settings_data.get("model", model)
        settings = settings_data.get("settings", {})
    
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


def read_component_folder(component_dir: Path) -> tuple[dict, dict, str, str]:
    """Read component. Returns (meta, spec, checksum, type)."""
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


def find_all_components(project_dir: Path) -> list[tuple[Path, Optional[str], str]]:
    """
    Find all component folders.
    Returns list of (path, component_id_or_none, component_type).
    
    component_id is None for new components that haven't been synced yet.
    """
    components = []
    
    def scan_dir(directory: Path, depth: int = 0):
        if depth > 10:  # Prevent infinite recursion
            return
        
        for item in directory.iterdir():
            if not item.is_dir():
                continue
            if item.name.startswith("."):
                continue
            if item.name == "triggers":
                continue
            
            comp_type = detect_component_type(item)
            if comp_type:
                # Check for .triform.json to get ID
                triform_data = read_triform_json(item)
                component_id = triform_data.get("id") if triform_data else None
                components.append((item, component_id, comp_type))
                
                # Scan for nested components
                scan_dir(item, depth + 1)
    
    scan_dir(project_dir)
    return components


def create_component(
    component_dir: Path,
    comp_type: str,
    api: TriformAPI
) -> Optional[str]:
    """
    Create a new component in Triform.
    Returns the new component ID.
    """
    meta, spec, _, _ = read_component_folder(component_dir)
    
    resource_map = {
        "action": "action/v1",
        "flow": "flow/v1",
        "agent": "agent/v1"
    }
    resource = resource_map.get(comp_type)
    if not resource:
        return None
    
    try:
        # For actions, only send essential spec fields
        if comp_type == "action":
            spec_to_send = {
                "source": spec.get("source", ""),
                "requirements": spec.get("requirements", ""),
                "readme": spec.get("readme", ""),
                "runtime": spec.get("runtime", "python-3.13")
            }
        else:
            spec_to_send = spec
        
        result = api.create_component(resource, meta, spec_to_send)
        return result.get("id")
    except APIError as e:
        print(f"  Error creating component: {e}")
        return None


def push_component(
    component_dir: Path,
    component_id: str,
    comp_type: str,
    api: TriformAPI,
    force: bool = False,
    stored_checksum: Optional[str] = None
) -> tuple[bool, str, Optional[str]]:
    """Push a single component. Returns (updated, message, new_checksum)."""
    meta, spec, new_checksum, _ = read_component_folder(component_dir)
    
    if not force and stored_checksum and new_checksum == stored_checksum:
        return False, "unchanged", new_checksum
    
    try:
        if comp_type == "action":
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
    force: bool = False,
    create_new: bool = False
) -> dict:
    """
    Push local changes to Triform.

    Component tracking:
    - Each component folder has a .triform.json with {"id": "uuid", "type": "..."}
    - Components with .triform.json are updated
    - Components without .triform.json are created (if create_new=True)

    Args:
        project_dir: Project directory (defaults to current dir)
        api: Optional API client instance
        force: Force push even if no changes detected
        create_new: Create new components that don't have .triform.json

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
    sync_state = SyncState.load(project_dir)

    print(f"Pushing changes for project '{project_config.project_name}'...")

    results = {
        "updated": [],
        "created": [],
        "errors": [],
        "skipped": [],
        "new_components": []  # Components that need create_new flag
    }

    # Update project metadata
    req_file = project_dir / "requirements.json"
    
    try:
        meta_update = {"name": project_config.project_name}
        
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
            requirements = {k: v for k, v in req_data.items() if k != "description"}
            if requirements:
                api.update_project_requirements(project_id, requirements)
                results["updated"].append("requirements.json")
                print("  Updated project requirements")
        except APIError as e:
            results["errors"].append(f"requirements.json: {e}")
            print(f"  Error updating requirements: {e}")

    # Find all components
    components = find_all_components(project_dir)
    
    # Build checksum map from .triform/state.json (for backwards compat)
    checksum_map = {}
    for node_key, state in sync_state.components.items():
        checksum_map[state.get("component_id")] = state.get("checksum")
    
    print(f"  Found {len(components)} components")
    
    for component_path, component_id, comp_type in components:
        rel_path = str(component_path.relative_to(project_dir))
        
        if component_id:
            # Existing component - update it
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
                # Update checksum in state
                for node_key, state in sync_state.components.items():
                    if state.get("component_id") == component_id:
                        sync_state.components[node_key]["checksum"] = new_checksum
                        break
            elif "error" in message:
                results["errors"].append(f"{rel_path}: {message}")
                print(f"  Error: {rel_path} - {message}")
            else:
                results["skipped"].append(rel_path)
            
            # Update component requirements
            comp_req_file = component_path / "requirements.json"
            if comp_req_file.exists():
                try:
                    comp_req_data = json.loads(comp_req_file.read_text())
                    comp_requirements = {k: v for k, v in comp_req_data.items() if k != "description"}
                    if comp_requirements:
                        api.update_component_requirements(component_id, comp_requirements)
                except APIError:
                    pass
        else:
            # New component - no .triform.json
            if create_new:
                print(f"  Creating: {rel_path}...")
                new_id = create_component(component_path, comp_type, api)
                if new_id:
                    # Write .triform.json with new ID
                    write_triform_json(component_path, new_id, comp_type)
                    results["created"].append(rel_path)
                    print(f"  Created: {rel_path} (id: {new_id[:8]}...)")
                else:
                    results["errors"].append(f"{rel_path}: Failed to create")
            else:
                results["new_components"].append(rel_path)

    # Save updated sync state
    sync_state.last_sync = datetime.utcnow().isoformat()
    sync_state.save(project_dir)

    # Print summary
    print("\nPush complete:")
    print(f"  - {len(results['updated'])} updated")
    print(f"  - {len(results['created'])} created")
    print(f"  - {len(results['skipped'])} unchanged")
    
    if results["errors"]:
        print(f"  - {len(results['errors'])} errors")
    
    if results["new_components"]:
        print(f"\n⚠️  {len(results['new_components'])} new component(s) found without .triform.json:")
        for path in results["new_components"]:
            print(f"     - {path}")
        print("  Run with --create-new to create them in Triform")

    return results
