# Contributing to Triform CLI

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/triform/triform-cli.git
   cd triform-cli
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install in development mode**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify installation**
   ```bash
   triform --help
   ```

## Code Style

We use [ruff](https://github.com/astral-sh/ruff) for linting:

```bash
ruff check triform_cli/
ruff format triform_cli/
```

## Running Tests

```bash
# Verify CLI loads correctly
triform --help
triform auth --help
triform projects --help

# Run linter
ruff check triform_cli/
```

## Making Changes

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**

3. **Run linting**
   ```bash
   ruff check triform_cli/
   ```

4. **Commit with a descriptive message**
   ```bash
   git commit -m "Add feature: description of what you did"
   ```

5. **Push and create a PR**
   ```bash
   git push origin feature/your-feature-name
   ```

## Project Structure

```
triform-cli/
├── triform_cli/
│   ├── __init__.py
│   ├── cli.py              # Main CLI entry point (click)
│   ├── api.py              # Triform API client
│   ├── config.py           # Configuration management
│   ├── models.py           # Pydantic models
│   ├── sync/
│   │   ├── pull.py         # Pull from Triform → local
│   │   ├── push.py         # Push local → Triform
│   │   └── watch.py        # File watcher for auto-sync
│   └── execute/
│       └── run.py          # Execute components
├── pyproject.toml          # Package configuration
├── README.md
└── CONTRIBUTING.md
```

## Adding New Commands

Commands are defined in `triform_cli/cli.py` using [Click](https://click.palletsprojects.com/):

```python
@cli.command("my-command")
@click.argument("arg")
@click.option("--flag", "-f", is_flag=True, help="Description")
def my_command(arg: str, flag: bool):
    """Command description shown in --help."""
    # Implementation
    pass
```

## Questions?

Open an issue on GitHub or reach out at support@triform.ai.

