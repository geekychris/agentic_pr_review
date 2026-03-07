"""Discover and load custom analyzer plugins from a repository.

Plugins are Python modules placed in ``.codereview/plugins/`` in the target
repo.  Each module must define a class that subclasses ``BaseAnalyzer``.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

from code_review_agent.analyzers.base import BaseAnalyzer

logger = logging.getLogger(__name__)

PLUGIN_DIR_NAME = ".codereview/plugins"


def discover_plugins(workspace: Path) -> list[BaseAnalyzer]:
    """Scan the workspace for custom analyzer plugins and return instances.

    Each ``.py`` file in ``.codereview/plugins/`` is loaded.  The loader
    looks for classes that subclass ``BaseAnalyzer`` and instantiates them
    with no arguments.
    """
    plugin_dir = workspace / PLUGIN_DIR_NAME
    if not plugin_dir.is_dir():
        logger.debug("No plugin directory at %s", plugin_dir)
        return []

    analyzers: list[BaseAnalyzer] = []

    for py_file in sorted(plugin_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue

        logger.info("Loading plugin: %s", py_file.name)
        try:
            analyzer = _load_plugin_module(py_file)
            if analyzer:
                analyzers.append(analyzer)
        except Exception:
            logger.exception("Failed to load plugin %s", py_file.name)

    logger.info("Loaded %d custom plugin(s)", len(analyzers))
    return analyzers


def _load_plugin_module(path: Path) -> BaseAnalyzer | None:
    """Import a single plugin module and return a BaseAnalyzer instance."""
    module_name = f"codereview_plugin_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    # Find the first BaseAnalyzer subclass in the module
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, BaseAnalyzer)
            and attr is not BaseAnalyzer
        ):
            instance = attr()
            logger.info("Instantiated plugin analyzer: %s (%s)", attr_name, instance.name)
            return instance

    logger.warning("No BaseAnalyzer subclass found in %s", path.name)
    return None
