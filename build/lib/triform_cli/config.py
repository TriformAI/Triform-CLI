"""Configuration management for Triform CLI."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

# Global config directory
CONFIG_DIR = Path.home() / ".triform"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Config:
    """Global CLI configuration."""
    auth_token: Optional[str] = None
    api_base_url: str = "https://app.triform.ai/api"

    def save(self) -> None:
        """Save config to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls) -> "Config":
        """Load config from disk."""
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                return cls(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()


@dataclass
class ProjectConfig:
    """Project-specific configuration stored in .triform/config.json."""
    project_id: str
    project_name: str
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None

    @classmethod
    def load(cls, project_dir: Path) -> Optional["ProjectConfig"]:
        """Load project config from .triform directory."""
        config_file = project_dir / ".triform" / "config.json"
        if config_file.exists():
            try:
                data = json.loads(config_file.read_text())
                # Handle old configs without organization_name
                if "organization_name" not in data:
                    data["organization_name"] = None
                return cls(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return None

    def save(self, project_dir: Path) -> None:
        """Save project config to .triform directory."""
        triform_dir = project_dir / ".triform"
        triform_dir.mkdir(parents=True, exist_ok=True)
        config_file = triform_dir / "config.json"
        config_file.write_text(json.dumps(asdict(self), indent=2))


@dataclass
class SyncState:
    """Sync state tracking component IDs and checksums."""
    components: dict  # node_key -> {component_id, checksum, type}
    last_sync: Optional[str] = None

    @classmethod
    def load(cls, project_dir: Path) -> "SyncState":
        """Load sync state from .triform directory."""
        state_file = project_dir / ".triform" / "state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                return cls(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls(components={})

    def save(self, project_dir: Path) -> None:
        """Save sync state to .triform directory."""
        triform_dir = project_dir / ".triform"
        triform_dir.mkdir(parents=True, exist_ok=True)
        state_file = triform_dir / "state.json"
        state_file.write_text(json.dumps(asdict(self), indent=2))

