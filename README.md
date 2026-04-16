# molecule-ai-workspace-runtime

Shared Python runtime infrastructure for all Molecule AI agent adapters.

This package provides the core machinery that every Molecule AI workspace container needs:

- **A2A server** — Registers with the platform, heartbeats, serves A2A JSON-RPC
- **Adapter interface** — `BaseAdapter` / `AdapterConfig` / `SetupResult`
- **Built-in tools** — delegation, memory, approvals, sandbox, telemetry
- **Skill loader** — loads and hot-reloads skill modules from `/configs/skills/`
- **Plugin system** — per-workspace + shared plugin discovery and install
- **Config / preflight** — YAML config loading with validation

## Installation

```bash
pip install molecule-ai-workspace-runtime
```

## Adapter Discovery

The runtime discovers adapters in two ways:

1. **`ADAPTER_MODULE` env var** (standalone adapter repos):
   ```bash
   ADAPTER_MODULE=my_adapter molecule-runtime
   ```
   The module must export an `Adapter` class extending `BaseAdapter`.

2. **Built-in subdirectory scan** (monorepo local dev):
   Scans `molecule_runtime/adapters/` subdirectories for `Adapter` classes.

## Writing an Adapter

```python
from molecule_runtime.adapters.base import BaseAdapter, AdapterConfig
from a2a.server.agent_execution import AgentExecutor

class Adapter(BaseAdapter):
    @staticmethod
    def name() -> str:
        return "my-runtime"

    @staticmethod
    def display_name() -> str:
        return "My Runtime"

    @staticmethod
    def description() -> str:
        return "My custom agent runtime"

    async def setup(self, config: AdapterConfig) -> None:
        result = await self._common_setup(config)
        # Store result attributes for create_executor

    async def create_executor(self, config: AdapterConfig) -> AgentExecutor:
        # Return an AgentExecutor instance
        ...
```

Set `ADAPTER_MODULE=my_package.adapter` and run `molecule-runtime`.

## License

BSL-1.1 — see LICENSE for details.
