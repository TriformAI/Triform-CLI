"""Watch for file changes and auto-sync."""

import time
from pathlib import Path
from typing import Optional, Callable

from ..api import TriformAPI
from ..config import ProjectConfig
from .push import push_project


class FileWatcher:
    """Watch for file changes and trigger sync."""
    
    def __init__(
        self,
        project_dir: Path,
        api: Optional[TriformAPI] = None,
        debounce_seconds: float = 1.0
    ):
        self.project_dir = Path(project_dir)
        self.api = api or TriformAPI()
        self.debounce_seconds = debounce_seconds
        self._last_mtimes: dict[str, float] = {}
        self._pending_sync = False
        self._last_sync_time = 0.0
    
    def _get_tracked_files(self) -> list[Path]:
        """Get list of files to watch."""
        files = []
        
        # Project files
        for name in ["project.json", "requirements.json"]:
            f = self.project_dir / name
            if f.exists():
                files.append(f)
        
        # Action files
        actions_dir = self.project_dir / "actions"
        if actions_dir.exists():
            for action_dir in actions_dir.iterdir():
                if action_dir.is_dir():
                    for name in ["source.py", "requirements.txt", "readme.md", "meta.json"]:
                        f = action_dir / name
                        if f.exists():
                            files.append(f)
        
        # Flow files
        flows_dir = self.project_dir / "flows"
        if flows_dir.exists():
            for flow_dir in flows_dir.iterdir():
                if flow_dir.is_dir():
                    for name in ["flow.json", "readme.md", "meta.json"]:
                        f = flow_dir / name
                        if f.exists():
                            files.append(f)
        
        # Agent files
        agents_dir = self.project_dir / "agents"
        if agents_dir.exists():
            for agent_dir in agents_dir.iterdir():
                if agent_dir.is_dir():
                    for name in ["agent.json", "readme.md", "meta.json"]:
                        f = agent_dir / name
                        if f.exists():
                            files.append(f)
        
        return files
    
    def _check_changes(self) -> bool:
        """Check if any tracked files have changed."""
        files = self._get_tracked_files()
        changed = False
        
        for f in files:
            try:
                mtime = f.stat().st_mtime
                key = str(f)
                
                if key not in self._last_mtimes:
                    self._last_mtimes[key] = mtime
                elif self._last_mtimes[key] != mtime:
                    self._last_mtimes[key] = mtime
                    changed = True
            except OSError:
                pass
        
        return changed
    
    def _do_sync(self) -> None:
        """Perform the sync."""
        print("\n🔄 Changes detected, syncing...")
        try:
            push_project(self.project_dir, self.api)
        except Exception as e:
            print(f"❌ Sync error: {e}")
    
    def watch(self, callback: Optional[Callable[[], None]] = None) -> None:
        """
        Start watching for changes.
        
        Args:
            callback: Optional callback to run after each sync
        """
        project_config = ProjectConfig.load(self.project_dir)
        if not project_config:
            raise ValueError("Not a Triform project directory")
        
        print(f"👀 Watching project '{project_config.project_name}' for changes...")
        print("   Press Ctrl+C to stop\n")
        
        # Initialize mtimes
        self._get_tracked_files()
        self._check_changes()
        
        try:
            while True:
                if self._check_changes():
                    current_time = time.time()
                    
                    # Debounce - wait for debounce period after last change
                    if current_time - self._last_sync_time >= self.debounce_seconds:
                        self._do_sync()
                        self._last_sync_time = current_time
                        
                        if callback:
                            callback()
                
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n\n👋 Stopped watching")


def watch_project(
    project_dir: Optional[Path] = None,
    api: Optional[TriformAPI] = None
) -> None:
    """
    Watch a project directory for changes and auto-sync.
    
    Args:
        project_dir: Project directory (defaults to current dir)
        api: Optional API client instance
    """
    project_dir = Path(project_dir) if project_dir else Path.cwd()
    watcher = FileWatcher(project_dir, api)
    watcher.watch()

