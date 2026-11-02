"""Import one Lambda folder's flat modules without clashing with the other Lambdas'.

Every Lambda zip is flat, so they all have top-level modules with the same names
(main, orchestrator, config, response, ...). `isolated_lambda("lambda_x")` returns
two fixtures for a conftest.py:

  * a session fixture that imports lambda_x's modules once, with lambda_x/ first
    on sys.path, and keeps them aside;
  * an autouse fixture (named after the folder without the "lambda_" prefix,
    e.g. `ws_connect`) that swaps those modules into sys.modules for the test and
    restores whatever was there afterwards. It yields a namespace with the
    modules (`ws_connect.orchestrator`, ...), which is also how tests patch them.
"""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

API_DIR = Path(__file__).resolve().parents[1]

# Files in a Lambda folder that are not part of the function's module graph
NOT_MODULES = {"__init__", "run_local"}


def top_level_modules(lambda_dir) -> set:
    """Names of the modules and packages at the root of the folder (what the zip exposes)."""
    names = set()
    for path in lambda_dir.iterdir():
        if path.is_file() and path.suffix == ".py" and path.stem not in NOT_MODULES:
            names.add(path.stem)
        elif path.is_dir() and (path / "__init__.py").exists():
            names.add(path.name)
    return names


def pop_modules(names) -> dict:
    """Remove (and return) every sys.modules entry whose top-level name is in `names`."""
    popped = {}
    for name in list(sys.modules):
        if name.split(".")[0] in names:
            popped[name] = sys.modules.pop(name)
    return popped


def isolated_lambda(folder):
    lambda_dir = API_DIR / folder
    names = top_level_modules(lambda_dir)
    loaded_fixture = f"_{folder}_modules"
    active_fixture = folder.removeprefix("lambda_")

    @pytest.fixture(scope="session", name=loaded_fixture)
    def loaded():
        others = pop_modules(names)
        sys.path.insert(0, str(lambda_dir))
        try:
            for name in sorted(names):
                importlib.import_module(name)
            modules = pop_modules(names)
        finally:
            sys.path.remove(str(lambda_dir))
            sys.modules.update(others)
        return modules

    @pytest.fixture(autouse=True, name=active_fixture)
    def active(request):
        modules = request.getfixturevalue(loaded_fixture)
        others = pop_modules(names)
        sys.modules.update(modules)
        sys.path.insert(0, str(lambda_dir))  # keeps importlib.reload on our files
        try:
            yield SimpleNamespace(
                **{name: module for name, module in modules.items() if "." not in name}
            )
        finally:
            sys.path.remove(str(lambda_dir))
            pop_modules(names)
            sys.modules.update(others)

    return loaded, active
