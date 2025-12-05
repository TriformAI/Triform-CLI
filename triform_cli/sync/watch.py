"""Watch for file changes and auto-sync."""

import time
from pathlib import Path
from typing import Callable, Optional

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

        # Project-level files
        for pattern in ["*.env", "readme.md", "requirements.json"]:
            files.extend(self.project_dir.glob(pattern))

        # Triggers folder
        triggers_dir = self.project_dir / "triggers"
        if triggers_dir.exists():
            files.extend(triggers_dir.glob("*.json"))

        # Component files - find all meta.json and track their sibling files
        for meta_file in self.project_dir.rglob("meta.json"):
            if ".triform" in str(meta_file):
                continue
            
            component_dir = meta_file.parent
            files.append(meta_file)
            
            # Track all relevant component files
            for pattern in [
                "*.py",           # Source code
                "readme.md",
                "requirements.json",
                "pip_requirements.txt",
                "io.json",
                "nodes.json",
                "io_nodes.json",
                "prompts.json",
                "settings.json",
                "modifiers.json"
            ]:
                files.extend(component_dir.glob(pattern))

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
