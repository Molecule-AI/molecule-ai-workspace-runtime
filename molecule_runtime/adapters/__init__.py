"""Adapter registry — discovers and loads agent infrastructure adapters."""

import importlib
import logging
import os
from .base import BaseAdapter, AdapterConfig, SetupResult

logger = logging.getLogger(__name__)

_ADAPTER_CACHE: dict[str, type[BaseAdapter]] = {}


def discover_adapters() -> dict[str, type[BaseAdapter]]:
    """Scan subdirectories for adapter modules. Each must export an Adapter class.

    This is used for local development inside the monorepo where adapters
    live as subdirectories. In standalone adapter repos, use ADAPTER_MODULE
    env var instead.
    """
    if _ADAPTER_CACHE:
        return _ADAPTER_CACHE

    from pathlib import Path
    adapters_dir = Path(__file__).parent
    for entry in sorted(adapters_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"molecule_runtime.adapters.{entry.name}")
            adapter_cls = getattr(mod, "Adapter", None)
            if adapter_cls and issubclass(adapter_cls, BaseAdapter):
                _ADAPTER_CACHE[adapter_cls.name()] = adapter_cls
                logger.debug(f"Loaded adapter: {adapter_cls.name()} ({adapter_cls.display_name()})")
        except Exception as e:
            # Log but don't crash — adapter may have uninstalled deps
            logger.debug(f"Skipped adapter {entry.name}: {e}")

    return _ADAPTER_CACHE


def get_adapter(runtime: str) -> type[BaseAdapter]:
    """Get adapter class by runtime name.

    Resolution order:
    1. ADAPTER_MODULE env var — used by standalone adapter repos to register
       their adapter without modifying the runtime package.
    2. Built-in discovery — scans subdirectories (for local monorepo dev).

    Raises KeyError if the adapter cannot be found.
    """
    # First check env override (standalone adapter repos set this)
    adapter_module = os.environ.get("ADAPTER_MODULE")
    if adapter_module:
        try:
            mod = importlib.import_module(adapter_module)
            cls = getattr(mod, "Adapter")
            if cls and issubclass(cls, BaseAdapter):
                return cls
        except Exception as e:
            raise KeyError(
                f"ADAPTER_MODULE={adapter_module!r} could not be loaded: {e}"
            ) from e

    # Fall back to built-in discovery (for local dev / monorepo)
    adapters = discover_adapters()
    if runtime not in adapters:
        available = ", ".join(sorted(adapters.keys()))
        raise KeyError(f"Unknown runtime '{runtime}'. Available: {available}")
    return adapters[runtime]


def list_adapters() -> list[dict]:
    """Return metadata for all discovered adapters (for API/UI)."""
    adapters = discover_adapters()
    return [
        {
            "name": cls.name(),
            "display_name": cls.display_name(),
            "description": cls.description(),
            "config_schema": cls.get_config_schema(),
        }
        for cls in adapters.values()
    ]


__all__ = ["BaseAdapter", "AdapterConfig", "SetupResult", "get_adapter", "list_adapters", "discover_adapters"]
