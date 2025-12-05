"""Pull Triform project to local file structure with granular files."""

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
    """Convert component name to safe directory/file name."""
    safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name)
    while "  " in safe:
        safe = safe.replace("  ", " ")
    return safe.strip() or "unnamed"


def sanitize_filename(name: str) -> str:
    """Convert name to safe filename (no spaces, lowercase for .py files)."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_").lower() or "unnamed"


def get_unique_dir_name(base_dir: Path, name: str, existing_dirs: set) -> str:
    """Get a unique directory name, adding suffix if needed."""
    dir_name = sanitize_name(name)

    if dir_name not in existing_dirs and not (base_dir / dir_name).exists():
        existing_dirs.add(dir_name)
        return dir_name

    counter = 2
    while True:
        unique_name = f"{dir_name} {counter}"
        if unique_name not in existing_dirs and not (base_dir / unique_name).exists():
            existing_dirs.add(unique_name)
            return unique_name
        counter += 1


def build_requirements_json(requirements: dict, description: str = "") -> dict:
    """Build requirements JSON with description included."""
    result = {}
    
    if description:
        result["description"] = description
    
    # Only include non-empty sections
    for key in ["context", "userStories", "outcomes", "guidelines", "dependencies", "boundaries", "safety"]:
        if requirements.get(key):
            result[key] = requirements[key]
    
    return result


def generate_env_file(environment: dict) -> str:
    """Generate .env file content from project environment variables."""
    lines = ["# Environment variables for Triform project", ""]
    
    variables = environment.get("variables", [])
    
    regular_vars = [v for v in variables if not v.get("secret", False)]
    secret_vars = [v for v in variables if v.get("secret", False)]
    
    if regular_vars:
        lines.append("# Variables")
        for var in regular_vars:
            key = var.get("key", "")
            value = var.get("value", "")
            if key:
                if value and ('"' in value or '\n' in value or ' ' in value):
                    value = f'"{value}"'
                lines.append(f"{key}={value}")
        lines.append("")
    
    if secret_vars:
        lines.append("# Secrets (fill in actual values)")
        for var in secret_vars:
            key = var.get("key", "")
            value = var.get("value", "")
            if key:
                display_value = value if value else "# Add your secret here"
                lines.append(f"{key}={display_value}")
        lines.append("")
    
    return "\n".join(lines)


# Global tracking for node_key -> folder path mapping (used for modifier distribution)
_node_folder_map: dict[str, Path] = {}


def write_action_folder(
    component: dict,
    parent_dir: Path,
    existing_dirs: set,
    api: Optional[TriformAPI] = None,
    depth: int = 0,
    node_key: str = ""
) -> dict:
    """Write an action component to folder with granular files."""
    meta = component.get("meta", {})
    spec = component.get("spec", {})
    component_id = component.get("id", "")
    name = meta.get("name", "unnamed")
    
    # Create folder
    dir_name = get_unique_dir_name(parent_dir, name, existing_dirs)
    component_dir = parent_dir / dir_name
    component_dir.mkdir(parents=True, exist_ok=True)
    
    # Track node key -> folder mapping for modifiers
    if node_key:
        _node_folder_map[node_key] = component_dir
    
    indent = "  " * depth
    print(f"{indent}Writing action: {dir_name}/")
    
    # Write source code as {name}.py
    source = spec.get("source", "")
    if source:
        py_filename = sanitize_filename(name) + ".py"
        source_file = component_dir / py_filename
        source_file.write_text(source)
    
    # Write pip requirements as requirements.txt (if any)
    pip_requirements = spec.get("requirements", "")
    if pip_requirements.strip():
        pip_file = component_dir / "pip_requirements.txt"
        pip_file.write_text(pip_requirements)
    
    # Write readme.md
    readme = spec.get("readme", "")
    if not readme:
        readme = f"# {name}\n"
    readme_file = component_dir / "readme.md"
    readme_file.write_text(readme)
    
    # Write io.json (inputs and outputs)
    inputs = spec.get("inputs", {})
    outputs = spec.get("outputs", {})
    if inputs or outputs:
        io_data = {}
        if inputs:
            io_data["inputs"] = inputs
        if outputs:
            io_data["outputs"] = outputs
        io_file = component_dir / "io.json"
        io_file.write_text(json.dumps(io_data, indent=2))
    
    # Fetch and write requirements.json (with description)
    intention = meta.get("intention", "")
    requirements = {}
    if api and component_id:
        try:
            requirements = api.get_component_requirements(component_id) or {}
        except APIError:
            pass
    
    req_json = build_requirements_json(requirements, intention)
    if req_json:
        requirements_file = component_dir / "requirements.json"
        requirements_file.write_text(json.dumps(req_json, indent=2))

    return {
        "component_id": component_id,
        "type": "action",
        "dir": dir_name,
        "checksum": compute_checksum(source),
        "runtime": spec.get("runtime", "python-3.13"),
        "starred": meta.get("starred", False)
    }


def write_flow_folder(
    component: dict,
    parent_dir: Path,
    existing_dirs: set,
    api: Optional[TriformAPI] = None,
    depth: int = 0,
    node_key: str = ""
) -> dict:
    """Write a flow component to folder with granular files."""
    meta = component.get("meta", {})
    spec = component.get("spec", {})
    component_id = component.get("id", "")
    name = meta.get("name", "unnamed")
    
    # Create folder
    dir_name = get_unique_dir_name(parent_dir, name, existing_dirs)
    component_dir = parent_dir / dir_name
    component_dir.mkdir(parents=True, exist_ok=True)
    
    # Track node key -> folder mapping
    if node_key:
        _node_folder_map[node_key] = component_dir
    
    indent = "  " * depth
    print(f"{indent}Writing flow: {dir_name}/")
    
    # Write readme.md
    readme = spec.get("readme", "")
    if not readme:
        readme = f"# {name}\n"
    readme_file = component_dir / "readme.md"
    readme_file.write_text(readme)
    
    # Write io.json (flow inputs and outputs)
    inputs = spec.get("inputs", {})
    outputs = spec.get("outputs", {})
    if inputs or outputs:
        io_data = {}
        if inputs:
            io_data["inputs"] = inputs
        if outputs:
            io_data["outputs"] = outputs
        io_file = component_dir / "io.json"
        io_file.write_text(json.dumps(io_data, indent=2))
    
    # Write nodes.json (node definitions without resolved specs)
    nodes = spec.get("nodes", {})
    nodes_clean = {}
    nested_specs = {}
    
    for nkey, node in nodes.items():
        nodes_clean[nkey] = {
            "component_id": node.get("component_id"),
            "inputs": node.get("inputs", {}),
            "position": node.get("position", {"x": 0, "y": 0}),
            "loop": node.get("loop", {"enabled": False})
        }
        if "spec" in node and node["spec"]:
            nested_specs[nkey] = node["spec"]
    
    if nodes_clean:
        nodes_file = component_dir / "nodes.json"
        nodes_file.write_text(json.dumps(nodes_clean, indent=2))
    
    # Write io_nodes.json
    io_nodes = spec.get("io_nodes", {})
    if io_nodes:
        io_nodes_file = component_dir / "io_nodes.json"
        io_nodes_file.write_text(json.dumps(io_nodes, indent=2))
    
    # Fetch and write requirements.json
    intention = meta.get("intention", "")
    requirements = {}
    if api and component_id:
        try:
            requirements = api.get_component_requirements(component_id) or {}
        except APIError:
            pass
    
    req_json = build_requirements_json(requirements, intention)
    if req_json:
        requirements_file = component_dir / "requirements.json"
        requirements_file.write_text(json.dumps(req_json, indent=2))
    
    # Process nested components
    nested_existing_dirs = set()
    for nkey, nested_spec in nested_specs.items():
        # Build full node path for nested components
        full_node_key = f"{node_key}/{nkey}" if node_key else nkey
        write_component_folder(
            nested_spec,
            component_dir,
            nested_existing_dirs,
            api,
            depth + 1,
            full_node_key
        )

    return {
        "component_id": component_id,
        "type": "flow",
        "dir": dir_name,
        "checksum": compute_checksum(json.dumps(nodes_clean)),
        "starred": meta.get("starred", False)
    }


def write_agent_folder(
    component: dict,
    parent_dir: Path,
    existing_dirs: set,
    api: Optional[TriformAPI] = None,
    depth: int = 0,
    node_key: str = ""
) -> dict:
    """Write an agent component to folder with granular files."""
    meta = component.get("meta", {})
    spec = component.get("spec", {})
    component_id = component.get("id", "")
    name = meta.get("name", "unnamed")
    
    # Create folder
    dir_name = get_unique_dir_name(parent_dir, name, existing_dirs)
    component_dir = parent_dir / dir_name
    component_dir.mkdir(parents=True, exist_ok=True)
    
    # Track node key -> folder mapping
    if node_key:
        _node_folder_map[node_key] = component_dir
    
    indent = "  " * depth
    print(f"{indent}Writing agent: {dir_name}/")
    
    # Write readme.md
    readme = spec.get("readme", "")
    if not readme:
        readme = f"# {name}\n"
    readme_file = component_dir / "readme.md"
    readme_file.write_text(readme)
    
    # Write io.json
    inputs = spec.get("inputs", {})
    outputs = spec.get("outputs", {})
    if inputs or outputs:
        io_data = {}
        if inputs:
            io_data["inputs"] = inputs
        if outputs:
            io_data["outputs"] = outputs
        io_file = component_dir / "io.json"
        io_file.write_text(json.dumps(io_data, indent=2))
    
    # Write nodes.json (tool definitions)
    nodes = spec.get("nodes", {})
    nodes_clean = {}
    nested_specs = {}
    
    for nkey, node in nodes.items():
        nodes_clean[nkey] = {
            "component_id": node.get("component_id"),
            "inputs": node.get("inputs", {}),
            "order": node.get("order", 0)
        }
        if "spec" in node and node["spec"]:
            nested_specs[nkey] = node["spec"]
    
    if nodes_clean:
        nodes_file = component_dir / "nodes.json"
        nodes_file.write_text(json.dumps(nodes_clean, indent=2))
    
    # Write prompts.json
    prompts = spec.get("prompts", {})
    if prompts and (prompts.get("system") or prompts.get("user")):
        prompts_file = component_dir / "prompts.json"
        prompts_file.write_text(json.dumps(prompts, indent=2))
    
    # Write settings.json
    model = spec.get("model", "")
    settings = spec.get("settings", {})
    if model or settings:
        settings_data = {"model": model}
        if settings:
            settings_data["settings"] = settings
        settings_file = component_dir / "settings.json"
        settings_file.write_text(json.dumps(settings_data, indent=2))
    
    # Fetch and write requirements.json
    intention = meta.get("intention", "")
    requirements = {}
    if api and component_id:
        try:
            requirements = api.get_component_requirements(component_id) or {}
        except APIError:
            pass
    
    req_json = build_requirements_json(requirements, intention)
    if req_json:
        requirements_file = component_dir / "requirements.json"
        requirements_file.write_text(json.dumps(req_json, indent=2))
    
    # Process nested components (tools)
    nested_existing_dirs = set()
    for nkey, nested_spec in nested_specs.items():
        full_node_key = f"{node_key}/{nkey}" if node_key else nkey
        write_component_folder(
            nested_spec,
            component_dir,
            nested_existing_dirs,
            api,
            depth + 1,
            full_node_key
        )

    return {
        "component_id": component_id,
        "type": "agent",
        "dir": dir_name,
        "checksum": compute_checksum(json.dumps(nodes_clean)),
        "starred": meta.get("starred", False)
    }


def write_component_folder(
    component: dict,
    parent_dir: Path,
    existing_dirs: set,
    api: Optional[TriformAPI] = None,
    depth: int = 0,
    node_key: str = ""
) -> dict:
    """Route to appropriate writer based on component type."""
    resource = component.get("resource", "")
    
    if resource == "action/v1":
        return write_action_folder(component, parent_dir, existing_dirs, api, depth, node_key)
    elif resource == "flow/v1":
        return write_flow_folder(component, parent_dir, existing_dirs, api, depth, node_key)
    elif resource == "agent/v1":
        return write_agent_folder(component, parent_dir, existing_dirs, api, depth, node_key)
    else:
        print(f"{'  ' * depth}Warning: Unknown resource type {resource}")
        return {}


def distribute_modifiers(modifiers: dict, target_dir: Path) -> None:
    """
    Distribute modifiers to the component folders where they are connected.
    Modifier keys are in format 'nodeKey/toolNodeKey' which maps to nested components.
    """
    global _node_folder_map
    
    for modifier_path, modifier_list in modifiers.items():
        if not modifier_list:
            continue
        
        # Find the folder for this modifier path
        target_folder = None
        
        # Try exact match first
        if modifier_path in _node_folder_map:
            target_folder = _node_folder_map[modifier_path]
        else:
            # Try to find parent path match
            parts = modifier_path.split("/")
            for i in range(len(parts), 0, -1):
                partial_path = "/".join(parts[:i])
                if partial_path in _node_folder_map:
                    target_folder = _node_folder_map[partial_path]
                    break
        
        if target_folder and target_folder.exists():
            modifiers_file = target_folder / "modifiers.json"
            modifiers_file.write_text(json.dumps(modifier_list, indent=2))
            print(f"  Wrote modifiers to {target_folder.relative_to(target_dir)}/")


def write_triggers_folder(triggers: dict, target_dir: Path) -> None:
    """Write triggers to separate files in triggers/ folder."""
    has_triggers = False
    
    # Check if any triggers have meaningful content
    for key in ["endpoints", "chat", "scheduled"]:
        trigger = triggers.get(key, {})
        if trigger and (trigger.get("enabled") or trigger.get("nodes")):
            has_triggers = True
            break
    
    if not has_triggers:
        return
    
    triggers_dir = target_dir / "triggers"
    triggers_dir.mkdir(exist_ok=True)
    
    # Endpoints trigger
    endpoints = triggers.get("endpoints", {})
    if endpoints and (endpoints.get("enabled") or endpoints.get("nodes")):
        endpoints_file = triggers_dir / "endpoints.json"
        endpoints_file.write_text(json.dumps(endpoints, indent=2))
    
    # Chat trigger
    chat = triggers.get("chat", {})
    if chat and chat.get("enabled"):
        chat_file = triggers_dir / "chat.json"
        chat_file.write_text(json.dumps(chat, indent=2))
    
    # Scheduled trigger
    scheduled = triggers.get("scheduled", {})
    if scheduled and (scheduled.get("enabled") or scheduled.get("nodes")):
        scheduled_file = triggers_dir / "scheduled.json"
        scheduled_file.write_text(json.dumps(scheduled, indent=2))


def pull_project(
    project_id: str,
    target_dir: Optional[Path] = None,
    api: Optional[TriformAPI] = None,
    include_org_structure: bool = True
) -> Path:
    """
    Pull a Triform project to local file structure with granular files.

    Structure:
    ProjectName/
      {project_name}.env          - Environment variables
      readme.md                   - Project readme
      requirements.json           - Project requirements + description
      triggers/
        endpoints.json            - HTTP endpoint triggers
        chat.json                 - Chat trigger config
        scheduled.json            - Scheduled/cron triggers
      .triform/
        config.json               - CLI sync config
        state.json                - Sync state (includes component IDs)
      ComponentName/              - Each component in its own folder
        {name}.py                 - Source code (actions only)
        readme.md                 - Documentation
        requirements.json         - Requirements + description
        io.json                   - Inputs and outputs
        nodes.json                - Node definitions (flows/agents)
        prompts.json              - Prompts (agents only)
        settings.json             - Model settings (agents only)
        pip_requirements.txt      - Pip dependencies (actions only)
        modifiers.json            - OAuth/storage modifiers (if connected)
        NestedComponent/          - Nested components as subfolders

    Args:
        project_id: The project ID to pull
        target_dir: Target directory (defaults to Triform/OrgName/ProjectName)
        api: Optional API client instance
        include_org_structure: If True, creates Triform/Org/Project structure

    Returns:
        Path to the created project directory
    """
    global _node_folder_map
    _node_folder_map = {}  # Reset mapping
    
    api = api or TriformAPI()

    # Fetch the project
    print(f"Fetching project {project_id}...")
    project = api.get_project(project_id)

    if not project:
        raise ValueError(f"Project {project_id} not found")

    project_name = project["meta"]["name"]
    safe_project_name = sanitize_name(project_name)

    # Get organization info
    org_name = "default"
    org_id = None
    try:
        memberships = api.get_memberships()
        project_owner = project.get("ownedBy")
        for m in memberships:
            org = m.get("organization", {})
            if org.get("id") == project_owner:
                org_name = org.get("name", "default")
                org_id = org.get("id")
                break
        if org_id is None and memberships:
            org = memberships[0].get("organization", {})
            org_name = org.get("name", "default")
            org_id = org.get("id")
    except APIError:
        pass

    # Determine target directory
    if target_dir is None:
        if include_org_structure:
            target_dir = Path.cwd() / "Triform" / sanitize_name(org_name) / safe_project_name
        else:
            target_dir = Path.cwd() / safe_project_name
    else:
        target_dir = Path(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"Pulling project '{project_name}' from org '{org_name}' to {target_dir}")

    spec = project["spec"]

    # Write {project_name}.env
    environment = spec.get("environment", {"variables": []})
    env_content = generate_env_file(environment)
    env_filename = sanitize_filename(project_name) + ".env"
    env_file = target_dir / env_filename
    env_file.write_text(env_content)
    print(f"  Wrote {env_filename} with {len(environment.get('variables', []))} variables")

    # Write readme.md
    readme = spec.get("readme", "")
    if not readme:
        readme = f"# {project_name}\n"
    readme_file = target_dir / "readme.md"
    readme_file.write_text(readme)

    # Fetch and write requirements.json
    intention = project["meta"].get("intention", "")
    requirements = {}
    try:
        requirements = api.get_project_requirements(project_id) or {}
    except APIError:
        pass
    
    req_json = build_requirements_json(requirements, intention)
    if req_json:
        requirements_file = target_dir / "requirements.json"
        requirements_file.write_text(json.dumps(req_json, indent=2))

    # Write triggers/ folder
    triggers = spec.get("triggers", {})
    if triggers:
        write_triggers_folder(triggers, target_dir)
        if (target_dir / "triggers").exists():
            print(f"  Wrote triggers/")

    # Track components for sync state
    components_state = {}
    existing_dirs: set = set()

    # Process each top-level node (component)
    for node_key, node in spec.get("nodes", {}).items():
        component_id = node.get("component_id")
        if not component_id:
            continue

        print(f"Fetching component {component_id}...")
        try:
            component = api.get_component(component_id, depth=999)
        except APIError as e:
            print(f"  Warning: Could not fetch component {component_id}: {e}")
            continue

        if not component:
            continue

        state_entry = write_component_folder(
            component,
            target_dir,
            existing_dirs,
            api,
            depth=0,
            node_key=node_key
        )
        if state_entry:
            components_state[node_key] = state_entry

    # Distribute modifiers to component folders
    modifiers = spec.get("modifiers", {})
    if modifiers:
        distribute_modifiers(modifiers, target_dir)

    # Save project config
    project_config = ProjectConfig(
        project_id=project_id,
        project_name=project_name,
        organization_id=org_id,
        organization_name=org_name
    )
    project_config.save(target_dir)

    # Save sync state (includes component IDs for push)
    sync_state = SyncState(
        components=components_state,
        last_sync=datetime.utcnow().isoformat()
    )
    sync_state.save(target_dir)

    print(f"\nProject pulled successfully to {target_dir}")
    print(f"  - {len(components_state)} top-level components")

    return target_dir
