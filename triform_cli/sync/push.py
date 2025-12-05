"""Push local changes to Triform."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..api import APIError, TriformAPI
from ..config import ProjectConfig, SyncState
from .pull import compute_checksum


def read_action(action_dir: Path) -> tuple[dict, dict, str]:
    """
    Read an action from local files.

    Returns:
        tuple of (meta, spec, checksum)
    """
    # Read source code
    source_file = action_dir / "source.py"
    source = source_file.read_text() if source_file.exists() else ""

    # Read requirements.txt
    requirements_file = action_dir / "requirements.txt"
    requirements = requirements_file.read_text() if requirements_file.exists() else ""

    # Read readme
    readme_file = action_dir / "readme.md"
    readme = readme_file.read_text() if readme_file.exists() else ""

    # Read meta.json
    meta_file = action_dir / "meta.json"
    if meta_file.exists():
        meta_data = json.loads(meta_file.read_text())
    else:
        meta_data = {"name": action_dir.name}

    meta = {
        "name": meta_data.get("name", action_dir.name),
        "intention": meta_data.get("intention", ""),
        "starred": meta_data.get("starred", False)
    }

    spec = {
        "source": source,
        "requirements": requirements,
        "readme": readme,
        "runtime": meta_data.get("runtime", "python-3.13"),
        "checksum": meta_data.get("checksum", ""),
        "inputs": meta_data.get("inputs", {}),
        "outputs": meta_data.get("outputs", {})
    }

    return meta, spec, compute_checksum(source)


def read_flow(flow_dir: Path) -> tuple[dict, dict, str]:
    """
    Read a flow from local files.

    Returns:
        tuple of (meta, spec, checksum)
    """
    # Read meta.json
    meta_file = flow_dir / "meta.json"
    if meta_file.exists():
        meta_data = json.loads(meta_file.read_text())
    else:
        meta_data = {"name": flow_dir.name}

    meta = {
        "name": meta_data.get("name", flow_dir.name),
        "intention": meta_data.get("intention", ""),
        "starred": meta_data.get("starred", False)
    }

    # Read readme
    readme_file = flow_dir / "readme.md"
    readme = readme_file.read_text() if readme_file.exists() else ""

    # Read flow.json
    flow_file = flow_dir / "flow.json"
    if flow_file.exists():
        flow_data = json.loads(flow_file.read_text())
    else:
        flow_data = {}

    spec = {
        "readme": readme,
        "nodes": flow_data.get("nodes", {}),
        "outputs": flow_data.get("outputs", {}),
        "inputs": flow_data.get("inputs", {}),
        "io_nodes": flow_data.get("io_nodes", {
            "input": {"x": 0, "y": 0},
            "output": {"x": 0, "y": 0}
        })
    }

    return meta, spec, compute_checksum(json.dumps(spec))


def read_agent(agent_dir: Path) -> tuple[dict, dict, str]:
    """
    Read an agent from local files.

    Returns:
        tuple of (meta, spec, checksum)
    """
    # Read meta.json
    meta_file = agent_dir / "meta.json"
    if meta_file.exists():
        meta_data = json.loads(meta_file.read_text())
    else:
        meta_data = {"name": agent_dir.name}

    meta = {
        "name": meta_data.get("name", agent_dir.name),
        "intention": meta_data.get("intention", ""),
        "starred": meta_data.get("starred", False)
    }

    # Read readme
    readme_file = agent_dir / "readme.md"
    readme = readme_file.read_text() if readme_file.exists() else ""

    # Read agent.json
    agent_file = agent_dir / "agent.json"
    if agent_file.exists():
        agent_data = json.loads(agent_file.read_text())
    else:
        agent_data = {}

    spec = {
        "readme": readme,
        "model": agent_data.get("model", "gemma-3-27b-it"),
        "prompts": agent_data.get("prompts", {"system": [], "user": []}),
        "settings": agent_data.get("settings", {}),
        "nodes": agent_data.get("nodes", {}),
        "inputs": agent_data.get("inputs", {}),
        "outputs": agent_data.get("outputs", {})
    }

    return meta, spec, compute_checksum(json.dumps(spec))


def find_component_by_dir(sync_state: SyncState, dir_path: str) -> Optional[tuple[str, dict]]:
    """Find component in sync state by directory path."""
    for node_key, state in sync_state.components.items():
        if state.get("dir") == dir_path:
            return node_key, state
    return None


def push_project(
    project_dir: Optional[Path] = None,
    api: Optional[TriformAPI] = None,
    force: bool = False
) -> dict:
    """
    Push local changes to Triform.

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

    # Update project.json if changed
    # NOTE: We only update meta (name, intention), NOT spec
    # Updating spec would overwrite nodes, triggers, etc.
    # Environment should be managed via Triform UI or a separate command
    project_file = project_dir / "project.json"
    if project_file.exists():
        project_data = json.loads(project_file.read_text())
        try:
            meta = {
                "name": project_data.get("name", project_config.project_name),
                "intention": project_data.get("intention", "")
            }
            # Only update meta, never spec (to avoid wiping nodes)
            api.update_project(project_id, meta=meta, spec=None)
            results["updated"].append("project.json (meta only)")
            print("  Updated project metadata (name, intention)")
        except APIError as e:
            results["errors"].append(f"project.json: {e}")
            print(f"  Error updating project: {e}")

    # Update project requirements if changed
    requirements_file = project_dir / "requirements.json"
    if requirements_file.exists():
        try:
            requirements = json.loads(requirements_file.read_text())
            api.update_project_requirements(project_id, requirements)
            results["updated"].append("requirements.json")
            print("  Updated project requirements")
        except APIError as e:
            results["errors"].append(f"requirements.json: {e}")
            print(f"  Error updating requirements: {e}")

    # Process actions
    actions_dir = project_dir / "actions"
    if actions_dir.exists():
        for action_dir in actions_dir.iterdir():
            if not action_dir.is_dir():
                continue

            rel_path = str(action_dir.relative_to(project_dir))
            result = find_component_by_dir(sync_state, rel_path)

            if not result:
                print(f"  Skipping {rel_path}: not tracked (pull first)")
                results["skipped"].append(rel_path)
                continue

            node_key, state = result
            component_id = state["component_id"]

            meta, spec, new_checksum = read_action(action_dir)

            # Check if changed
            if not force and new_checksum == state.get("checksum"):
                results["skipped"].append(rel_path)
                continue

            try:
                # Don't send inputs/outputs - they're computed server-side from source
                spec_to_send = {
                    "source": spec["source"],
                    "requirements": spec["requirements"],
                    "readme": spec["readme"],
                    "runtime": spec["runtime"]
                }
                api.update_component(component_id, meta=meta, spec=spec_to_send)

                # Update state
                sync_state.components[node_key]["checksum"] = new_checksum
                results["updated"].append(rel_path)
                print(f"  Updated action: {rel_path}")
            except APIError as e:
                results["errors"].append(f"{rel_path}: {e}")
                print(f"  Error updating {rel_path}: {e}")

    # Process flows
    flows_dir = project_dir / "flows"
    if flows_dir.exists():
        for flow_dir in flows_dir.iterdir():
            if not flow_dir.is_dir():
                continue

            rel_path = str(flow_dir.relative_to(project_dir))
            result = find_component_by_dir(sync_state, rel_path)

            if not result:
                print(f"  Skipping {rel_path}: not tracked")
                results["skipped"].append(rel_path)
                continue

            node_key, state = result
            component_id = state["component_id"]

            meta, spec, new_checksum = read_flow(flow_dir)

            if not force and new_checksum == state.get("checksum"):
                results["skipped"].append(rel_path)
                continue

            try:
                api.update_component(component_id, meta=meta, spec=spec)
                sync_state.components[node_key]["checksum"] = new_checksum
                results["updated"].append(rel_path)
                print(f"  Updated flow: {rel_path}")
            except APIError as e:
                results["errors"].append(f"{rel_path}: {e}")
                print(f"  Error updating {rel_path}: {e}")

    # Process agents
    agents_dir = project_dir / "agents"
    if agents_dir.exists():
        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue

            rel_path = str(agent_dir.relative_to(project_dir))
            result = find_component_by_dir(sync_state, rel_path)

            if not result:
                print(f"  Skipping {rel_path}: not tracked")
                results["skipped"].append(rel_path)
                continue

            node_key, state = result
            component_id = state["component_id"]

            meta, spec, new_checksum = read_agent(agent_dir)

            if not force and new_checksum == state.get("checksum"):
                results["skipped"].append(rel_path)
                continue

            try:
                api.update_component(component_id, meta=meta, spec=spec)
                sync_state.components[node_key]["checksum"] = new_checksum
                results["updated"].append(rel_path)
                print(f"  Updated agent: {rel_path}")
            except APIError as e:
                results["errors"].append(f"{rel_path}: {e}")
                print(f"  Error updating {rel_path}: {e}")

    # Save updated sync state
    sync_state.last_sync = datetime.utcnow().isoformat()
    sync_state.save(project_dir)

    print("\nPush complete:")
    print(f"  - {len(results['updated'])} updated")
    print(f"  - {len(results['skipped'])} unchanged")
    if results["errors"]:
        print(f"  - {len(results['errors'])} errors")

    return results

