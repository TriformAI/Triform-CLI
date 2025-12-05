"""Triform CLI - Main entry point."""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from . import __version__
from .config import Config, ProjectConfig, SyncState
from .api import TriformAPI, APIError
from .sync import pull_project, push_project
from .sync.watch import watch_project
from .execute.run import (
    execute_component,
    execute_from_project,
    print_execution_events
)

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
        projects = api.list_projects()
    except APIError as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)
    
    if not projects:
        console.print("[yellow]No projects found[/]")
        return
    
    table = Table(title="Projects")
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
@click.option("--dir", "-d", "target_dir", help="Target directory")
def projects_pull(project_id: str, target_dir: Optional[str]):
    """Pull a project to local files."""
    try:
        target = Path(target_dir) if target_dir else None
        result_dir = pull_project(project_id, target)
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
            console.print(f"\n[green]✓ Push complete[/]")
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
        console.print(f"[green]✓ Deployed successfully![/]")
        console.print(f"  Deployment ID: {result.get('id', 'N/A')}")
        console.print(f"  Checksum: {result.get('checksum', 'N/A')[:16]}...")
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
        console.print(f"[green]✓ Build complete[/]")
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
            
            if trace:
                events = execute_component(component_id, payload_dict, environment, trace=True, api=api)
                result = print_execution_events(events)
            else:
                result = execute_component(component_id, payload_dict, environment, api=api)
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
    
    # Import here to avoid circular
    from .sync.push import read_action, read_flow, read_agent
    
    changes = []
    
    # Check each tracked component
    for node_key, state in sync_state.components.items():
        comp_type = state.get("type")
        comp_dir = target / state.get("dir", "")
        
        if not comp_dir.exists():
            changes.append((node_key, comp_type, "deleted"))
            continue
        
        if comp_type == "action":
            _, _, checksum = read_action(comp_dir)
        elif comp_type == "flow":
            _, _, checksum = read_flow(comp_dir)
        elif comp_type == "agent":
            _, _, checksum = read_agent(comp_dir)
        else:
            continue
        
        if checksum != state.get("checksum"):
            changes.append((node_key, comp_type, "modified"))
    
    if not changes:
        console.print("[green]✓ No changes detected[/]")
        return
    
    table = Table(title="Changes")
    table.add_column("Component", style="cyan")
    table.add_column("Type")
    table.add_column("Status")
    
    for node_key, comp_type, status in changes:
        status_color = {"modified": "yellow", "deleted": "red"}.get(status, "white")
        table.add_row(node_key, comp_type, f"[{status_color}]{status}[/]")
    
    console.print(table)


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()

