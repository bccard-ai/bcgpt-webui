"""Tool and function module loader. SECURITY TRUST BOUNDARY: Code loaded here runs with full process privileges (no sandboxing). Authoring is admin-only by default; functions are always admin-only, and tools may be authored by users with the 'workspace.tools' permission ONLY when TOOLS_ALLOW_NON_ADMIN_CODE is explicitly enabled (see routers/tools.py and routers/functions.py)."""

import ast
import os
import re
import subprocess
import sys
from importlib import util
import types
import tempfile
import logging

from bcgpt.env import SRC_LOG_LEVELS, PIP_OPTIONS, PIP_PACKAGE_INDEX_OPTIONS
from bcgpt.models import Functions
from bcgpt.models import Tools

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

_DANGEROUS_AST_NODES = (
    ast.Import,
    ast.ImportFrom,
)

_DANGEROUS_ATTR_NAMES = frozenset(
    {
        "__import__",
        "__builtins__",
        "__code__",
        "__globals__",
        "__subclasses__",
        "__bases__",
        "__mro__",
        "__class__",
    }
)

_FORBIDDEN_CALL_NAMES = frozenset(
    {
        "exec",
        "eval",
        "compile",
        "__import__",
        "getattr",
        "setattr",
        "delattr",
        "globals",
        "locals",
        "breakpoint",
        "exit",
        "quit",
    }
)


def _validate_ast_safety(source: str) -> list[str]:
    """Walk the AST of *source* and return a list of policy violations."""
    violations: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"SyntaxError: {e}"]

    for node in ast.walk(tree):
        if isinstance(node, _DANGEROUS_AST_NODES):
            module_name = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                module_name = node.module
            elif isinstance(node, ast.Import) and node.names:
                module_name = node.names[0].name
            blocked = any(
                mod in module_name
                for mod in (
                    "os",
                    "subprocess",
                    "sys",
                    "importlib",
                    "ctypes",
                    "socket",
                    "shutil",
                )
            )
            if blocked:
                violations.append(f"Blocked import: {module_name}")

        if isinstance(node, ast.Attribute) and node.attr in _DANGEROUS_ATTR_NAMES:
            violations.append(f"Blocked dunder attribute access: {node.attr}")

        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _FORBIDDEN_CALL_NAMES:
                violations.append(f"Blocked call: {func.id}")
            if isinstance(func, ast.Attribute) and func.attr in _FORBIDDEN_CALL_NAMES:
                violations.append(f"Blocked method call: {func.attr}")

    return violations


def extract_frontmatter(content):
    """
    Extract frontmatter as a dictionary from the provided content string.
    """
    frontmatter = {}
    frontmatter_started = False
    frontmatter_ended = False
    frontmatter_pattern = re.compile(r"^\s*([a-z_]+):\s*(.*)\s*$", re.IGNORECASE)

    try:
        lines = content.splitlines()
        if len(lines) < 1 or lines[0].strip() != '"""':
            # The content doesn't start with triple quotes
            return {}

        frontmatter_started = True

        for line in lines[1:]:
            if '"""' in line:
                if frontmatter_started:
                    frontmatter_ended = True
                    break

            if frontmatter_started and not frontmatter_ended:
                match = frontmatter_pattern.match(line)
                if match:
                    key, value = match.groups()
                    frontmatter[key.strip()] = value.strip()

    except Exception as e:
        log.exception(f"Failed to extract frontmatter: {e}")
        return {}

    return frontmatter


def replace_imports(content):
    """
    Replace the import paths in the content.
    """
    replacements = {
        "from utils": "from bcgpt.utils",
        "from apps": "from bcgpt.apps",
        "from main": "from bcgpt.main",
        "from config": "from bcgpt.config",
    }

    for old, new in replacements.items():
        content = content.replace(old, new)

    return content


def load_tools_module_by_id(toolkit_id, content=None):
    # SECURITY TRUST BOUNDARY: Unsandboxed code execution.
    # Tool code runs with full process privileges (no sandboxing).
    # Authoring is gated in routers/tools.py: admin-only by default, and
    # extendable to users with the 'workspace.tools' permission ONLY when
    # TOOLS_ALLOW_NON_ADMIN_CODE is explicitly enabled. Any broader authorship
    # REQUIRES OS-level sandboxing first.

    if content is None:
        tool = Tools.get_tool_by_id(toolkit_id)
        if not tool:
            raise Exception(f"Toolkit not found: {toolkit_id}")

        content = tool.content

        content = replace_imports(content)
        Tools.update_tool_by_id(toolkit_id, {"content": content})
    else:
        frontmatter = extract_frontmatter(content)
        # Install required packages found within the frontmatter
        install_frontmatter_requirements(frontmatter.get("requirements", ""))

    module_name = f"tool_{toolkit_id}"
    module = types.ModuleType(module_name)
    sys.modules[module_name] = module

    # Create a temporary file and use it to define `__file__` so
    # that it works as expected from the module's perspective.
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.close()
    try:
        with open(temp_file.name, "w", encoding="utf-8") as f:
            f.write(content)
        module.__dict__["__file__"] = temp_file.name

        # Executing the modified content in the created module's namespace
        log.warning(
            "SECURITY: Executing plugin code — id=%s, content_length=%d",
            toolkit_id,
            len(content),
        )
        exec(content, module.__dict__)
        frontmatter = extract_frontmatter(content)
        log.info(f"Loaded module: {module.__name__}")

        # Create and return the object if the class 'Tools' is found in the module
        if hasattr(module, "Tools"):
            return module.Tools(), frontmatter
        else:
            raise Exception("No Tools class found in the module")
    except Exception as e:
        log.error(f"Error loading module: {toolkit_id}: {e}")
        del sys.modules[module_name]  # Clean up
        raise e
    finally:
        os.unlink(temp_file.name)


def load_function_module_by_id(function_id, content=None):
    # SECURITY TRUST BOUNDARY: Unsandboxed code execution. Function authoring is
    # admin-only (routers/functions.py). See load_tools_module_by_id.
    if content is None:
        function = Functions.get_function_by_id(function_id)
        if not function:
            raise Exception(f"Function not found: {function_id}")
        content = function.content

        content = replace_imports(content)
        Functions.update_function_by_id(function_id, {"content": content})
    else:
        frontmatter = extract_frontmatter(content)
        install_frontmatter_requirements(frontmatter.get("requirements", ""))

    module_name = f"function_{function_id}"
    module = types.ModuleType(module_name)
    sys.modules[module_name] = module

    # Create a temporary file and use it to define `__file__` so
    # that it works as expected from the module's perspective.
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.close()
    try:
        with open(temp_file.name, "w", encoding="utf-8") as f:
            f.write(content)
        module.__dict__["__file__"] = temp_file.name

        # Execute the modified content in the created module's namespace
        violations = _validate_ast_safety(content)
        if violations:
            raise Exception(
                f"Function blocked by AST safety check: {'; '.join(violations)}"
            )
        log.warning(
            "SECURITY: Executing plugin code — id=%s, content_length=%d",
            function_id,
            len(content),
        )
        exec(content, module.__dict__)
        frontmatter = extract_frontmatter(content)
        log.info(f"Loaded module: {module.__name__}")

        # Create appropriate object based on available class type in the module
        if hasattr(module, "Pipe"):
            return module.Pipe(), "pipe", frontmatter
        elif hasattr(module, "Filter"):
            return module.Filter(), "filter", frontmatter
        elif hasattr(module, "Action"):
            return module.Action(), "action", frontmatter
        else:
            raise Exception("No Pipe, Filter, or Action class found in the module")
    except Exception as e:
        log.error(f"Error loading module: {function_id}: {e}")
        del sys.modules[module_name]  # Cleanup by removing the module in case of error

        Functions.update_function_by_id(function_id, {"is_active": False})
        raise e
    finally:
        os.unlink(temp_file.name)


def install_frontmatter_requirements(requirements: str):
    if requirements:
        try:
            req_list = [req.strip() for req in requirements.split(",")]
            log.info(f"Installing requirements: {' '.join(req_list)}")
            log.warning(
                "SECURITY: Installing plugin requirements — packages=%s", req_list
            )
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install"]
                + PIP_OPTIONS
                + req_list
                + PIP_PACKAGE_INDEX_OPTIONS
            )
        except Exception as e:
            log.error(f"Error installing packages: {' '.join(req_list)}")
            raise e

    else:
        log.info("No requirements found in frontmatter.")
