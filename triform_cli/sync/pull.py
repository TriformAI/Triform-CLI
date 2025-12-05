"""Pull Triform project to local file structure."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..api import APIError, TriformAPI
from ..config import ProjectConfig, SyncState


def compute_checksum(content: str) -> str:
    """Compute SHA256 checksum of content."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def sanitize_name(name: str) -> str:
    """Convert component name to safe directory name."""
    # Replace spaces and special chars with underscores
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    return safe.lower().strip("_") or "unnamed"


def get_unique_dir_name(base_dir: Path, name: str, existing_dirs: set) -> str:
    """Get a unique directory name, adding suffix if needed."""
    dir_name = sanitize_name(name)

    # Check if this name already exists
    if dir_name not in existing_dirs and not (base_dir / dir_name).exists():
        existing_dirs.add(dir_name)
        return dir_name

    # Add numeric suffix to make unique
    counter = 2
    while True:
        unique_name = f"{dir_name}_{counter}"
        if unique_name not in existing_dirs and not (base_dir / unique_name).exists():
            existing_dirs.add(unique_name)
            return unique_name
        counter += 1


def write_action(component: dict, base_dir: Path, node_key: str, existing_dirs: set, api: Optional[TriformAPI] = None) -> dict:
    """Write an action component to local files."""
    meta = component["meta"]
    spec = component["spec"]

    actions_base = base_dir / "actions"
    dir_name = get_unique_dir_name(actions_base, meta["name"], existing_dirs)
    action_dir = actions_base / dir_name
    action_dir.mkdir(parents=True, exist_ok=True)

    # Write source code
    source_file = action_dir / "source.py"
    source_file.write_text(spec.get("source", ""))

    # Write requirements.txt (pip dependencies)
    pip_requirements_file = action_dir / "requirements.txt"
    pip_requirements_file.write_text(spec.get("requirements", ""))

    # Write readme
    readme_file = action_dir / "readme.md"
    readme_file.write_text(spec.get("readme", ""))

    # Write meta.json
    meta_file = action_dir / "meta.json"
    meta_file.write_text(json.dumps({
        "name": meta["name"],
        "intention": meta.get("intention", ""),
        "starred": meta.get("starred", False),
        "runtime": spec.get("runtime", "python-3.13"),
        "checksum": spec.get("checksum", ""),
        "inputs": spec.get("inputs", {}),
        "outputs": spec.get("outputs", {})
    }, indent=2))

    # Fetch and write component requirements (context, stories, etc.)
    if api:
        try:
            requirements = api.get_component_requirements(component["id"])
            if requirements:
                requirements_file = action_dir / "requirements.json"
                requirements_file.write_text(json.dumps(requirements, indent=2))
        except APIError:
            pass  # Requirements might not exist

    return {
        "component_id": component["id"],
        "type": "action",
        "dir": str(action_dir.relative_to(base_dir)),
        "checksum": compute_checksum(spec.get("source", ""))
    }


def write_flow(component: dict, base_dir: Path, node_key: str, existing_dirs: set, api: Optional[TriformAPI] = None) -> dict:
    """Write a flow component to local files."""
    meta = component["meta"]
    spec = component["spec"]

    flows_base = base_dir / "flows"
    dir_name = get_unique_dir_name(flows_base, meta["name"], existing_dirs)
    flow_dir = flows_base / dir_name
    flow_dir.mkdir(parents=True, exist_ok=True)

    # Write meta.json
    meta_file = flow_dir / "meta.json"
    meta_file.write_text(json.dumps({
        "name": meta["name"],
        "intention": meta.get("intention", ""),
        "starred": meta.get("starred", False)
    }, indent=2))

    # Write readme
    readme_file = flow_dir / "readme.md"
    readme_file.write_text(spec.get("readme", ""))

    # Fetch and write component requirements
    if api:
        try:
            requirements = api.get_component_requirements(component["id"])
            if requirements:
                requirements_file = flow_dir / "requirements.json"
                requirements_file.write_text(json.dumps(requirements, indent=2))
        except APIError:
            pass

    # Process nodes - extract resolved component specs
    nodes_for_file = {}
    nested_components = {}

    for nkey, node in spec.get("nodes", {}).items():
        node_copy = {
            "component_id": node["component_id"],
            "inputs": node.get("inputs", {}),
            "position": node.get("position", {"x": 0, "y": 0}),
            "loop": node.get("loop", {"enabled": False})
        }
        nodes_for_file[nkey] = node_copy

        # If node has resolved spec, save it
        if "spec" in node and node["spec"]:
            nested_components[nkey] = node["spec"]

    # Write flow.json (without resolved specs)
    flow_file = flow_dir / "flow.json"
    flow_file.write_text(json.dumps({
        "nodes": nodes_for_file,
        "outputs": spec.get("outputs", {}),
        "inputs": spec.get("inputs", {}),
        "io_nodes": spec.get("io_nodes", {
            "input": {"x": 0, "y": 0},
            "output": {"x": 0, "y": 0}
        })
    }, indent=2))

    # Write nested components to separate files
    if nested_components:
        components_dir = flow_dir / "components"
        components_dir.mkdir(exist_ok=True)
        for nkey, nested_spec in nested_components.items():
            nested_file = components_dir / f"{nkey}.json"
            nested_file.write_text(json.dumps(nested_spec, indent=2))

    return {
        "component_id": component["id"],
        "type": "flow",
        "dir": str(flow_dir.relative_to(base_dir)),
        "checksum": compute_checksum(json.dumps(spec))
    }


def write_agent(component: dict, base_dir: Path, node_key: str, existing_dirs: set, api: Optional[TriformAPI] = None) -> dict:
    """Write an agent component to local files."""
    meta = component["meta"]
    spec = component["spec"]

    agents_base = base_dir / "agents"
    dir_name = get_unique_dir_name(agents_base, meta["name"], existing_dirs)
    agent_dir = agents_base / dir_name
    agent_dir.mkdir(parents=True, exist_ok=True)

    # Write meta.json
    meta_file = agent_dir / "meta.json"
    meta_file.write_text(json.dumps({
        "name": meta["name"],
        "intention": meta.get("intention", ""),
        "starred": meta.get("starred", False)
    }, indent=2))

    # Write readme
    readme_file = agent_dir / "readme.md"
    readme_file.write_text(spec.get("readme", ""))

    # Fetch and write component requirements
    if api:
        try:
            requirements = api.get_component_requirements(component["id"])
            if requirements:
                requirements_file = agent_dir / "requirements.json"
                requirements_file.write_text(json.dumps(requirements, indent=2))
        except APIError:
            pass

    # Process nodes
    nodes_for_file = {}
    nested_components = {}

    for nkey, node in spec.get("nodes", {}).items():
        node_copy = {
            "component_id": node["component_id"],
            "inputs": node.get("inputs", {}),
            "order": node.get("order", 0)
        }
        nodes_for_file[nkey] = node_copy

        if "spec" in node and node["spec"]:
            nested_components[nkey] = node["spec"]

    # Write agent.json
    agent_file = agent_dir / "agent.json"
    agent_file.write_text(json.dumps({
        "model": spec.get("model", "gemma-3-27b-it"),
        "prompts": spec.get("prompts", {"system": [], "user": []}),
        "settings": spec.get("settings", {}),
        "nodes": nodes_for_file,
        "inputs": spec.get("inputs", {}),
        "outputs": spec.get("outputs", {})
    }, indent=2))

    # Write nested components
    if nested_components:
        components_dir = agent_dir / "components"
        components_dir.mkdir(exist_ok=True)
        for nkey, nested_spec in nested_components.items():
            nested_file = components_dir / f"{nkey}.json"
            nested_file.write_text(json.dumps(nested_spec, indent=2))

    return {
        "component_id": component["id"],
        "type": "agent",
        "dir": str(agent_dir.relative_to(base_dir)),
        "checksum": compute_checksum(json.dumps(spec))
    }


def pull_project(
    project_id: str,
    target_dir: Optional[Path] = None,
    api: Optional[TriformAPI] = None,
    include_org_structure: bool = True
) -> Path:
    """
    Pull a Triform project to local file structure.

    Args:
        project_id: The project ID to pull
        target_dir: Target directory (defaults to Triform/OrgName/ProjectName)
        api: Optional API client instance
        include_org_structure: If True, creates Triform/Org/Project structure

    Returns:
        Path to the created project directory
    """
    api = api or TriformAPI()

    # Fetch the project with resolved spec
    print(f"Fetching project {project_id}...")
    project = api.get_project(project_id)

    if not project:
        raise ValueError(f"Project {project_id} not found")

    project_name = project["meta"]["name"]

    # Get organization info
    org_name = "default"
    org_id = None
    try:
        memberships = api.get_memberships()
        # Find the org that owns this project (ownedBy field)
        project_owner = project.get("ownedBy")
        for m in memberships:
            org = m.get("organization", {})
            if org.get("id") == project_owner:
                org_name = org.get("name", "default")
                org_id = org.get("id")
                break
        # If we couldn't match by ownedBy, use the first org
        if org_id is None and memberships:
            org = memberships[0].get("organization", {})
            org_name = org.get("name", "default")
            org_id = org.get("id")
    except APIError:
        pass  # Fall back to "default" org name

    # Determine target directory
    if target_dir is None:
        if include_org_structure:
            # Structure: Triform/OrgName/ProjectName
            target_dir = Path.cwd() / "Triform" / sanitize_name(org_name) / sanitize_name(project_name)
        else:
            target_dir = Path.cwd() / sanitize_name(project_name)
    else:
        target_dir = Path(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"Pulling project '{project_name}' from org '{org_name}' to {target_dir}")

    # Write project.json
    project_file = target_dir / "project.json"
    project_file.write_text(json.dumps({
        "name": project["meta"]["name"],
        "intention": project["meta"].get("intention", ""),
        "readme": project["spec"].get("readme", ""),
        "environment": project["spec"].get("environment", {"variables": []})
    }, indent=2))

    # Fetch and write project requirements
    try:
        requirements = api.get_project_requirements(project_id)
        requirements_file = target_dir / "requirements.json"
        requirements_file.write_text(json.dumps(requirements, indent=2))
    except APIError:
        # Requirements might not exist
        pass

    # Track components for sync state
    components_state = {}

    # Track existing directory names to handle duplicates
    existing_action_dirs: set = set()
    existing_flow_dirs: set = set()
    existing_agent_dirs: set = set()

    # Process each top-level node
    spec = project["spec"]
    for node_key, node in spec.get("nodes", {}).items():
        component_id = node.get("component_id")
        if not component_id:
            continue

        # Fetch full component with deep resolution
        print(f"  Fetching component {component_id}...")
        try:
            component = api.get_component(component_id, depth=999)
        except APIError as e:
            print(f"  Warning: Could not fetch component {component_id}: {e}")
            continue

        if not component:
            continue

        resource = component.get("resource", "")

        # Write component based on type (pass existing_dirs to handle duplicates)
        if resource == "action/v1":
            state_entry = write_action(component, target_dir, node_key, existing_action_dirs, api)
        elif resource == "flow/v1":
            state_entry = write_flow(component, target_dir, node_key, existing_flow_dirs, api)
        elif resource == "agent/v1":
            state_entry = write_agent(component, target_dir, node_key, existing_agent_dirs, api)
        else:
            print(f"  Warning: Unknown resource type {resource}")
            continue

        components_state[node_key] = state_entry
        print(f"  Wrote {state_entry['type']}: {state_entry['dir']}")

    # Save project config
    project_config = ProjectConfig(
        project_id=project_id,
        project_name=project_name,
        organization_id=org_id,
        organization_name=org_name
    )
    project_config.save(target_dir)

    # Save sync state
    sync_state = SyncState(
        components=components_state,
        last_sync=datetime.utcnow().isoformat()
    )
    sync_state.save(target_dir)

    print(f"\nProject pulled successfully to {target_dir}")
    print(f"  - {len(components_state)} components")

    return target_dir

