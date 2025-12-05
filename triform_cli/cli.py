"""Triform CLI - Main entry point."""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from . import __version__
from .api import APIError, TriformAPI
from .config import Config, ProjectConfig, SyncState
from .execute.run import execute_component, execute_from_project, print_execution_events
from .sync import pull_project, push_project
from .sync.watch import watch_project

console = Console()


# ----- Main CLI Group -----

@click.group()
@click.version_option(version=__version__)
def cli():
    """Triform CLI - Sync and execute Triform projects from the command line."""
    pass


# ----- Auth Commands -----

@cli.group()
def auth():
    """Authentication commands."""
    pass


@auth.command("login")
@click.option("--token", "-t", help="Session token (from browser cookie)")
def auth_login(token: Optional[str]):
    """Login with your Triform session token."""
    if not token:
        console.print(
            "[yellow]To get your session token:[/]\n"
            "1. Login to https://app.triform.ai\n"
            "2. Open browser DevTools (F12)\n"
            "3. Go to Application > Cookies\n"
            "4. Copy the value of '__Secure-better-auth.session_token'\n"
        )
        token = click.prompt("Enter your session token", hide_input=True)

    config = Config.load()
    config.auth_token = token

    # Verify token works
    api = TriformAPI(config)
    try:
        if api.verify_auth():
            config.save()
            console.print("[green]✓ Successfully authenticated![/]")
        else:
            console.print("[red]✗ Invalid token. Please try again.[/]")
            sys.exit(1)
    except APIError as e:
        console.print(f"[red]✗ Authentication failed: {e}[/]")
        sys.exit(1)


@auth.command("logout")
def auth_logout():
    """Clear stored authentication."""
    config = Config.load()
    config.auth_token = None
    config.save()
    console.print("[green]✓ Logged out successfully[/]")


@auth.command("status")
def auth_status():
    """Check authentication status."""
    config = Config.load()

    if not config.auth_token:
        console.print("[yellow]Not authenticated. Run 'triform auth login'[/]")
        return

    api = TriformAPI(config)
    try:
        if api.verify_auth():
            console.print("[green]✓ Authenticated[/]")
            console.print(f"  API: {config.api_base_url}")
        else:
            console.print("[red]✗ Token expired or invalid[/]")
    except APIError as e:
        console.print(f"[red]✗ Error: {e}[/]")


@auth.command("whoami")
def auth_whoami():
    """Show current user and organization info."""
    api = TriformAPI()

    try:
        memberships = api.get_memberships()

        if not memberships:
            console.print("[yellow]No organization memberships found[/]")
            return

        console.print(Panel("[bold]Organization Memberships[/]"))

        table = Table()
        table.add_column("Organization", style="cyan")
        table.add_column("Role")
        table.add_column("Status")

        for m in memberships:
            org = m.get("organization", {})
            member = m.get("member", {})

            org_name = org.get("name", "Unknown")
            role = member.get("role", "member")

            # We can't easily determine which is "active" from this endpoint
            # but we can show all memberships
            table.add_row(
                org_name,
                role,
                "[dim]member[/]"
            )

        console.print(table)
        console.print("\n[dim]Note: Switch organizations in the Triform UI, then re-copy your session token with 'triform auth login'[/]")

    except APIError as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)


# ----- Projects Commands -----

@cli.group()
def projects():
    """Project management commands."""
    pass


@projects.command("list")
def projects_list():
    """List all projects."""
    api = TriformAPI()

    try:
        # Get memberships to determine active org
        memberships = api.get_memberships()
        projects = api.list_projects()
    except APIError as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)

    # Try to determine active org from memberships or projects
    org_name = None
    if memberships:
        # Show first org as hint (actual active org determined by session)
        for m in memberships:
            org = m.get("organization", {})
            if org.get("name"):
                org_name = org.get("name")
                break

    if not projects:
        console.print("[yellow]No projects found[/]")
        if org_name:
            console.print(f"[dim]Current organization context may be: {org_name}[/]")
        return

    title = "Projects"
    if org_name and len(memberships) > 1:
        title = f"Projects [dim](showing {len(projects)} from current org)[/]"

    table = Table(title=title)
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Description")

    for proj in projects:
        table.add_row(
            proj["id"][:8] + "...",
            proj["meta"]["name"],
            proj["meta"].get("intention", "")[:50]
        )

    console.print(table)


@projects.command("pull")
@click.argument("project_id")
@click.option("--dir", "-d", "target_dir", help="Target directory (overrides default structure)")
@click.option("--flat", is_flag=True, help="Skip Triform/Org structure, just create project dir")
def projects_pull(project_id: str, target_dir: Optional[str], flat: bool):
    """Pull a project to local files.

    Default structure: Triform/OrgName/ProjectName/
    With --flat: ProjectName/
    With --dir: Specified directory
    """
    try:
        target = Path(target_dir) if target_dir else None
        # If explicit dir given, don't use org structure
        include_org = not flat and target is None
        result_dir = pull_project(project_id, target, include_org_structure=include_org)
        console.print(f"\n[green]✓ Project pulled to {result_dir}[/]")
    except APIError as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)


@projects.command("push")
@click.option("--force", "-f", is_flag=True, help="Force push all files")
@click.option("--dir", "-d", "project_dir", help="Project directory")
def projects_push(force: bool, project_dir: Optional[str]):
    """Push local changes to Triform."""
    try:
        target = Path(project_dir) if project_dir else None
        results = push_project(target, force=force)

        if results["errors"]:
            console.print(f"\n[yellow]⚠ Completed with {len(results['errors'])} errors[/]")
        else:
            console.print("\n[green]✓ Push complete[/]")
    except APIError as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)


@projects.command("watch")
@click.option("--dir", "-d", "project_dir", help="Project directory")
def projects_watch(project_dir: Optional[str]):
    """Watch for changes and auto-sync."""
    try:
        target = Path(project_dir) if project_dir else None
        watch_project(target)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)


@projects.command("deploy")
@click.option("--dir", "-d", "project_dir", help="Project directory")
def projects_deploy(project_dir: Optional[str]):
    """Deploy the current project."""
    target = Path(project_dir) if project_dir else Path.cwd()

    project_config = ProjectConfig.load(target)
    if not project_config:
        console.print("[red]Not a Triform project directory[/]")
        sys.exit(1)

    api = TriformAPI()
    try:
        result = api.deploy_project(project_config.project_id)
        console.print("[green]✓ Deployed successfully![/]")
        console.print(f"  Deployment ID: {result.get('id', 'N/A')}")
        console.print(f"  Checksum: {result.get('checksum', 'N/A')[:16]}...")
    except APIError as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)


@projects.command("restore")
@click.argument("project_id")
@click.option("--from-local", "-l", "local_dir", help="Restore from local .triform state")
def projects_restore(project_id: str, local_dir: Optional[str]):
    """Restore a project's nodes from local sync state."""
    api = TriformAPI()

    try:
        # Get the current project
        console.print(f"Fetching project {project_id}...")
        project = api.get_project(project_id)
        console.print(f"  Current project: {project['meta']['name']}")
        console.print(f"  Current nodes: {len(project['spec'].get('nodes', {}))}")

        # Try to restore from local state
        if local_dir:
            target = Path(local_dir)
        else:
            # Try current directory
            target = Path.cwd()

        sync_state = SyncState.load(target)

        if not sync_state.components:
            console.print("[yellow]No local sync state found[/]")
            console.print("  Looking for components we can add back...")

            # List all components owned by this org
            all_components = api.list_components()
            console.print(f"  Found {len(all_components)} components in your account")

            # Show them so user can manually restore
            for comp in all_components[:20]:
                console.print(f"    - {comp['id'][:8]}... : {comp['meta']['name']} ({comp['resource']})")

            console.print("\n[yellow]To restore, you'll need to manually add components back via the Triform UI[/]")
            console.print("  Or provide a local project directory with --from-local")
            return

        console.print(f"\nFound {len(sync_state.components)} components in local state:")

        # Build nodes from sync state
        nodes_to_restore = {}
        for node_key, state in sync_state.components.items():
            component_id = state.get("component_id")
            comp_type = state.get("type")
            comp_dir = state.get("dir")
            console.print(f"  - {node_key[:20]}... : {comp_type} ({comp_dir})")

            nodes_to_restore[node_key] = {
                "component_id": component_id,
                "order": len(nodes_to_restore)  # Simple ordering
            }

        if not click.confirm(f"\nRestore project with {len(nodes_to_restore)} nodes?"):
            console.print("Aborted")
            return

        # Get current spec to preserve other fields
        current_spec = project.get("spec", {})

        # Build new spec with restored nodes
        new_spec = {
            "nodes": nodes_to_restore,
            "readme": current_spec.get("readme", ""),
            "modifiers": current_spec.get("modifiers", {}),
            "environment": current_spec.get("environment", {"variables": []}),
            "triggers": current_spec.get("triggers", {"endpoints": {}, "scheduled": {}})
        }

        api.update_project(project_id, spec=new_spec)
        console.print("[green]✓ Project restored successfully![/]")
        console.print(f"  Restored {len(nodes_to_restore)} nodes")

    except APIError as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)


@projects.command("status")
@click.option("--dir", "-d", "project_dir", help="Project directory")
def projects_status(project_dir: Optional[str]):
    """Show project sync status."""
    target = Path(project_dir) if project_dir else Path.cwd()

    project_config = ProjectConfig.load(target)
    if not project_config:
        console.print("[red]Not a Triform project directory[/]")
        sys.exit(1)

    sync_state = SyncState.load(target)

    console.print(Panel(f"[bold]{project_config.project_name}[/]"))
    console.print(f"  Project ID: {project_config.project_id}")
    console.print(f"  Last sync: {sync_state.last_sync or 'Never'}")
    console.print(f"  Components: {len(sync_state.components)}")

    if sync_state.components:
        table = Table()
        table.add_column("Node Key", style="cyan")
        table.add_column("Type")
        table.add_column("Directory")

        for node_key, state in sync_state.components.items():
            table.add_row(
                node_key[:20],
                state.get("type", "unknown"),
                state.get("dir", "")
            )

        console.print(table)


# ----- Component Commands -----

@cli.group()
def component():
    """Component operations."""
    pass


@component.command("get")
@click.argument("component_id")
@click.option("--depth", "-d", default=0, help="Resolution depth")
def component_get(component_id: str, depth: int):
    """Get a component by ID."""
    api = TriformAPI()

    try:
        comp = api.get_component(component_id, depth)
        console.print(Syntax(json.dumps(comp, indent=2), "json"))
    except APIError as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)


@component.command("build")
@click.argument("component_id")
def component_build(component_id: str):
    """Build an action's dependencies."""
    api = TriformAPI()

    console.print(f"Building component {component_id}...")
    try:
        result = api.build_component(component_id)
        console.print("[green]✓ Build complete[/]")
        if result.get("spec", {}).get("checksum"):
            console.print(f"  Checksum: {result['spec']['checksum'][:16]}...")
    except APIError as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)


# ----- Execute Commands -----

@cli.command("execute")
@click.argument("target")
@click.option("--payload", "-p", help="JSON payload")
@click.option("--trace", "-t", is_flag=True, help="Stream execution events")
@click.option("--dir", "-d", "project_dir", help="Project directory (for node key execution)")
def execute(target: str, payload: Optional[str], trace: bool, project_dir: Optional[str]):
    """
    Execute a component.

    TARGET can be:
    - A component UUID
    - A node key from a local project (use with --dir)
    - A path like "project_id/node_key"
    """
    # Parse payload
    if payload:
        try:
            payload_dict = json.loads(payload)
        except json.JSONDecodeError:
            console.print("[red]Invalid JSON payload[/]")
            sys.exit(1)
    else:
        payload_dict = {}

    api = TriformAPI()

    try:
        # Determine if target is UUID or node key
        if "/" in target:
            # Path format: project_id/node_key
            parts = target.split("/")
            project_id = parts[0]
            node_key = parts[1] if len(parts) > 1 else None

            # Get project and find component
            project = api.get_project(project_id)
            if node_key and node_key in project["spec"]["nodes"]:
                component_id = project["spec"]["nodes"][node_key]["component_id"]
            else:
                console.print(f"[red]Node '{node_key}' not found in project[/]")
                sys.exit(1)

            # Get environment from project
            environment = project["spec"].get("environment", {}).get("variables", [])

            # Get modifiers relevant to this node
            all_modifiers = project["spec"].get("modifiers", {})
            modifiers = {k: v for k, v in all_modifiers.items() if k.startswith(node_key)}
            if modifiers:
                console.print(f"[dim]📎 Found {len(modifiers)} modifier mapping(s)[/]")

            if trace:
                events = execute_component(component_id, payload_dict, environment, modifiers, trace=True, api=api)
                result = print_execution_events(events)
            else:
                result = execute_component(component_id, payload_dict, environment, modifiers, api=api)
                console.print(Syntax(json.dumps(result, indent=2), "json"))

        elif project_dir or ProjectConfig.load(Path.cwd()):
            # Node key from local project
            target_dir = Path(project_dir) if project_dir else None

            if trace:
                events = execute_from_project(target, payload_dict, target_dir, trace=True, api=api)
                result = print_execution_events(events)
            else:
                result = execute_from_project(target, payload_dict, target_dir, api=api)
                console.print(Syntax(json.dumps(result, indent=2), "json"))

        else:
            # Assume UUID
            if trace:
                events = execute_component(target, payload_dict, trace=True, api=api)
                result = print_execution_events(events)
            else:
                result = execute_component(target, payload_dict, api=api)
                console.print(Syntax(json.dumps(result, indent=2), "json"))

    except APIError as e:
        console.print(f"[red]Execution error: {e}[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)


# ----- Executions History -----

@cli.command("executions")
@click.option("--limit", "-l", default=20, help="Number of executions to show")
def executions_list(limit: int):
    """List recent executions."""
    api = TriformAPI()

    try:
        execs = api.list_executions(limit)
    except APIError as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)

    if not execs:
        console.print("[yellow]No executions found[/]")
        return

    table = Table(title="Recent Executions")
    table.add_column("ID", style="dim")
    table.add_column("State")
    table.add_column("Source")
    table.add_column("Created")

    for ex in execs:
        state = ex.get("state", "unknown")
        state_color = {
            "completed": "green",
            "failed": "red",
            "running": "yellow",
            "pending": "dim"
        }.get(state, "white")

        table.add_row(
            ex["id"][:8] + "...",
            f"[{state_color}]{state}[/]",
            ex.get("source", ""),
            str(ex.get("createdAt", ""))[:19]
        )

    console.print(table)


# ----- Diff/Status Helpers -----

@cli.command("diff")
@click.option("--dir", "-d", "project_dir", help="Project directory")
def diff_cmd(project_dir: Optional[str]):
    """Show local vs remote differences."""
    target = Path(project_dir) if project_dir else Path.cwd()

    project_config = ProjectConfig.load(target)
    if not project_config:
        console.print("[red]Not a Triform project directory[/]")
        sys.exit(1)

    sync_state = SyncState.load(target)

    from .sync.push import read_component_folder, find_all_components

    changes = []

    # Find all components (new granular structure with meta.json files)
    components = find_all_components(target)
    
    if components:
        # Build checksum map from sync state
        checksum_map = {}
        for node_key, state in sync_state.components.items():
            checksum_map[state.get("component_id")] = (node_key, state.get("checksum"), state.get("type"))
        
        for comp_path, component_id, comp_type in components:
            rel_path = str(comp_path.relative_to(target))
            
            if component_id not in checksum_map:
                changes.append((rel_path, comp_type, "untracked"))
                continue
            
            node_key, stored_checksum, _ = checksum_map[component_id]
            _, _, current_checksum, _ = read_component_folder(comp_path)
            
            if current_checksum != stored_checksum:
                changes.append((rel_path, comp_type, "modified"))
    else:
        # No components found
        console.print("[yellow]No components found in project[/]")
        return

    if not changes:
        console.print("[green]✓ No changes detected[/]")
        return

    table = Table(title="Changes")
    table.add_column("Component", style="cyan")
    table.add_column("Type")
    table.add_column("Status")

    for name, comp_type, status in changes:
        status_color = {"modified": "yellow", "deleted": "red", "untracked": "blue"}.get(status, "white")
        table.add_row(name, comp_type, f"[{status_color}]{status}[/]")

    console.print(table)


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()

