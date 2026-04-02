"""
Code Compressor — Semantic compression of source code projects into .seif modules.

The "webpack for machines": browsers receive minified JS, AIs receive .seif compressed code.
Scans a project directory, extracts semantic topology (imports, exports, routes, state,
API surface), and compresses into a .seif module an AI can consume to understand the
entire project without reading every file.

Usage:
  from seif.context.code_compressor import compress_project
  module, path = compress_project("/path/to/project")

Supported languages:
  - Python: stdlib ast module (proper AST parsing)
  - JavaScript/TypeScript: regex-based extraction (no npm required)
  - Rust, Go, and others: generic regex fallback
"""

import ast
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from seif.constants import (
    CODE_MAX_FILE_SIZE,
    CODE_MAX_FILES,
    CODE_MAX_SIGNATURES,
    CODE_MAX_ROUTES,
    CODE_MAX_ADJACENCY,
    CODE_WATCH_INTERVAL,
    SENSITIVE_FILE_PATTERNS,
    SENSITIVE_CONTENT_PATTERNS,
)
from seif.context.git_context import IGNORE_DIRS


# === DATACLASSES ===

@dataclass
class FileSignature:
    """Semantic signature of a single source file."""
    path: str
    language: str
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    routes: list[str] = field(default_factory=list)
    state_patterns: list[str] = field(default_factory=list)
    loc: int = 0
    classification: str = "INTERNAL"


@dataclass
class CodeTopology:
    """Dependency graph and structural overview."""
    adjacency: dict[str, list[str]] = field(default_factory=dict)
    entry_points: list[str] = field(default_factory=list)
    packages: list[str] = field(default_factory=list)
    monorepo_projects: list[str] = field(default_factory=list)


@dataclass
class CompressedCode:
    """Complete compressed representation of a codebase."""
    project_name: str
    project_path: str
    languages: dict[str, int] = field(default_factory=dict)
    total_files: int = 0
    total_loc: int = 0
    topology: CodeTopology = field(default_factory=CodeTopology)
    signatures: list[FileSignature] = field(default_factory=list)
    route_map: list[str] = field(default_factory=list)
    state_architecture: list[str] = field(default_factory=list)
    api_surface: list[str] = field(default_factory=list)
    classification_summary: dict[str, list[str]] = field(default_factory=dict)
    compressed_at: str = ""


# === LANGUAGE DETECTION ===

LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".dart": "dart",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".hpp": "cpp", ".cc": "cpp",
}


def _detect_language(path: Path) -> str:
    return LANGUAGE_MAP.get(path.suffix.lower(), "generic")


# === SKIP LOGIC ===

SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Cargo.lock", "Gemfile.lock",
    "composer.lock", "Pipfile.lock",
}


def _should_skip(path: Path, project_root: Path) -> bool:
    """Determine if a file should be skipped."""
    # Skip directories in IGNORE_DIRS
    rel_parts = path.relative_to(project_root).parts
    for part in rel_parts[:-1]:  # check directories only (not the filename itself)
        if part in IGNORE_DIRS or part.startswith("."):
            return True
    # Skip hidden files EXCEPT sensitive config files we need to classify
    filename = rel_parts[-1] if rel_parts else path.name
    if filename.startswith(".") and not filename.startswith(".env"):
        return True

    # Skip lock files and binary-like extensions
    if path.name in SKIP_FILES:
        return True

    # Skip files too large
    try:
        if path.stat().st_size > CODE_MAX_FILE_SIZE:
            return True
    except OSError:
        return True

    # Skip non-text files (binary check)
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
                                 ".woff", ".woff2", ".ttf", ".eot",
                                 ".zip", ".tar", ".gz", ".bz2",
                                 ".pdf", ".exe", ".dll", ".so", ".dylib",
                                 ".pyc", ".pyo", ".class", ".o", ".obj",
                                 ".mp3", ".mp4", ".wav", ".avi", ".mov"}:
        return True

    return False


# === CLASSIFICATION ===

def _classify_file(path: Path, content: str) -> str:
    """Classify a file as PUBLIC, INTERNAL, or CONFIDENTIAL."""
    name_lower = path.name.lower()
    path_lower = str(path).lower()

    # CONFIDENTIAL: sensitive filenames
    for pattern in SENSITIVE_FILE_PATTERNS:
        if pattern in name_lower or pattern in path_lower:
            return "CONFIDENTIAL"

    # CONFIDENTIAL: sensitive content patterns
    for pattern in SENSITIVE_CONTENT_PATTERNS:
        if pattern in content[:2000]:
            return "CONFIDENTIAL"

    # PUBLIC: documentation and licenses
    if name_lower in {"readme.md", "readme.rst", "readme.txt", "readme",
                       "license", "license.md", "license.txt",
                       "changelog.md", "changelog.txt", "contributing.md"}:
        return "PUBLIC"
    if path_lower.startswith("docs/") or path_lower.startswith("doc/"):
        return "PUBLIC"

    return "INTERNAL"


# === PYTHON PARSER (AST-based) ===

def _parse_python(rel_path: str, content: str) -> FileSignature:
    """Parse Python file using stdlib ast module."""
    sig = FileSignature(path=rel_path, language="python")
    sig.loc = sum(1 for line in content.splitlines()
                  if line.strip() and not line.strip().startswith("#"))

    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Fallback: regex for broken Python
        return _parse_python_regex(rel_path, content, sig)

    for node in ast.walk(tree):
        # Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                sig.imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                sig.imports.append(node.module)

        # Functions (top-level and class methods)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
            args = []
            for arg in node.args.args:
                arg_str = arg.arg
                if arg.annotation:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                args.append(arg_str)
            ret = ""
            if node.returns:
                ret = f" -> {ast.unparse(node.returns)}"
            sig.functions.append(f"{prefix}fn {node.name}({', '.join(args)}){ret}")

            # Detect route decorators
            for dec in node.decorator_list:
                dec_str = ast.unparse(dec)
                sig.decorators.append(f"@{dec_str}")
                # Flask/FastAPI routes
                if "route(" in dec_str or ".get(" in dec_str or ".post(" in dec_str:
                    _extract_route_from_decorator(dec_str, sig.routes)

        # Classes
        elif isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            base_str = f"({', '.join(bases)})" if bases else ""
            sig.classes.append(f"class {node.name}{base_str}")
            for dec in node.decorator_list:
                sig.decorators.append(f"@{ast.unparse(dec)}")

        # Django URL patterns
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "urlpatterns":
                    sig.routes.append("Django urlpatterns detected")

    return sig


def _parse_python_regex(rel_path: str, content: str, sig: FileSignature) -> FileSignature:
    """Fallback regex parser for syntactically invalid Python."""
    for m in re.finditer(r'^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))', content, re.MULTILINE):
        sig.imports.append(m.group(1) or m.group(2))
    for m in re.finditer(r'^(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)', content, re.MULTILINE):
        sig.functions.append(f"fn {m.group(1)}({m.group(2)})")
    for m in re.finditer(r'^class\s+(\w+)(?:\(([^)]*)\))?', content, re.MULTILINE):
        bases = f"({m.group(2)})" if m.group(2) else ""
        sig.classes.append(f"class {m.group(1)}{bases}")
    return sig


def _extract_route_from_decorator(dec_str: str, routes: list[str]):
    """Extract HTTP route from a decorator string."""
    # Match patterns like: route("/path"), get("/path"), post("/path")
    m = re.search(r'\.(get|post|put|delete|patch|route)\s*\(\s*["\']([^"\']+)', dec_str)
    if m:
        method = m.group(1).upper()
        path = m.group(2)
        if method == "ROUTE":
            routes.append(f"ALL {path}")
        else:
            routes.append(f"{method} {path}")


# === JAVASCRIPT / TYPESCRIPT PARSER (regex-based) ===

def _parse_javascript(rel_path: str, content: str) -> FileSignature:
    """Parse JS/TS file using regex patterns."""
    sig = FileSignature(path=rel_path, language="typescript" if rel_path.endswith((".ts", ".tsx")) else "javascript")
    sig.loc = sum(1 for line in content.splitlines()
                  if line.strip() and not line.strip().startswith("//"))

    # Strip single-line comments for cleaner regex
    clean = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
    # Strip multi-line comments
    clean = re.sub(r'/\*[\s\S]*?\*/', '', clean)

    # ES6 imports
    for m in re.finditer(r'import\s+.*?\s+from\s+["\']([^"\']+)["\']', clean):
        sig.imports.append(m.group(1))
    # require()
    for m in re.finditer(r'(?:const|let|var)\s+.*?=\s*require\s*\(\s*["\']([^"\']+)["\']', clean):
        sig.imports.append(m.group(1))

    # Named exports
    for m in re.finditer(r'export\s+(?:default\s+)?(?:function|class|const|let|var|type|interface)\s+(\w+)', clean):
        sig.exports.append(m.group(1))

    # Regular functions
    for m in re.finditer(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)', clean):
        prefix = "async " if "async" in clean[max(0, m.start()-10):m.start()] else ""
        sig.functions.append(f"{prefix}fn {m.group(1)}({m.group(2)[:80]})")

    # Arrow functions (const name = (...) =>)
    for m in re.finditer(r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*\w+(?:<[^>]+>)?\s*)?=>', clean):
        sig.functions.append(f"fn {m.group(1)}()")

    # Classes
    for m in re.finditer(r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?', clean):
        base = f"({m.group(2)})" if m.group(2) else ""
        sig.classes.append(f"class {m.group(1)}{base}")

    # React components (function components returning JSX)
    for m in re.finditer(r'(?:export\s+(?:default\s+)?)?(?:const|function)\s+([A-Z]\w+).*?(?:=>|{)', clean):
        name = m.group(1)
        if name not in [f.split("(")[0].replace("fn ", "").replace("async fn ", "") for f in sig.functions]:
            sig.exports.append(f"Component:{name}")

    # React hooks usage
    for m in re.finditer(r'(use[A-Z]\w+)\s*\(', clean):
        sig.state_patterns.append(f"Hook:{m.group(1)}")

    # Express/Koa/Hono routes
    for m in re.finditer(r'(?:app|router|server)\.(get|post|put|delete|patch|all)\s*\(\s*["\']([^"\']+)', clean):
        sig.routes.append(f"{m.group(1).upper()} {m.group(2)}")

    # Next.js: detect from file path (pages/ or app/ directory)
    if "/pages/" in rel_path or rel_path.startswith("pages/"):
        route = _nextjs_pages_route(rel_path)
        if route:
            sig.routes.append(route)
    elif "/app/" in rel_path or rel_path.startswith("app/"):
        route = _nextjs_app_route(rel_path)
        if route:
            sig.routes.append(route)

    # Redux patterns
    for m in re.finditer(r'(?:createSlice|createStore|configureStore)\s*\(\s*{[^}]*name\s*:\s*["\'](\w+)', clean):
        sig.state_patterns.append(f"Redux:{m.group(1)}")
    # Context API
    for m in re.finditer(r'(?:createContext|React\.createContext)\s*[<(]', clean):
        sig.state_patterns.append("Context:provider")

    # Remove duplicate hooks
    sig.state_patterns = list(dict.fromkeys(sig.state_patterns))

    return sig


def _nextjs_pages_route(rel_path: str) -> Optional[str]:
    """Convert Next.js pages/ path to route."""
    # pages/index.tsx -> GET /
    # pages/users/[id].tsx -> GET /users/:id
    # pages/api/auth.ts -> API /api/auth
    parts = rel_path.split("pages/", 1)
    if len(parts) < 2:
        return None
    route_part = parts[1]
    # Remove extension
    route_part = re.sub(r'\.(tsx?|jsx?)$', '', route_part)
    # Remove index (standalone or trailing)
    route_part = re.sub(r'(^|/)index$', '', route_part)
    if not route_part:
        route_part = "/"
    else:
        route_part = "/" + route_part
    # Convert [param] to :param
    route_part = re.sub(r'\[([^\]]+)\]', r':\1', route_part)
    # Detect API routes
    prefix = "API" if route_part.startswith("/api") else "GET"
    return f"{prefix} {route_part}"


def _nextjs_app_route(rel_path: str) -> Optional[str]:
    """Convert Next.js app/ path to route."""
    parts = rel_path.split("app/", 1)
    if len(parts) < 2:
        return None
    route_part = parts[1]
    # Only page.tsx and route.ts are routes
    if not re.search(r'(page|route)\.(tsx?|jsx?)$', route_part):
        return None
    is_api = "route." in route_part
    # Remove page.tsx or route.ts (with or without leading /)
    route_part = re.sub(r'/?(page|route)\.(tsx?|jsx?)$', '', route_part)
    if not route_part:
        route_part = "/"
    else:
        route_part = "/" + route_part
    route_part = re.sub(r'\[([^\]]+)\]', r':\1', route_part)
    prefix = "API" if is_api else "GET"
    return f"{prefix} {route_part}"


# === GO PARSER (dedicated) ===

def _parse_go(rel_path: str, content: str) -> FileSignature:
    """Parse Go source files with support for multi-import, Gin/Echo/Chi routes."""
    sig = FileSignature(path=rel_path, language="go")
    sig.loc = sum(1 for line in content.splitlines()
                  if line.strip() and not line.strip().startswith("//"))

    # Strip comments
    clean = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
    clean = re.sub(r'/\*[\s\S]*?\*/', '', clean)

    # Multi-line imports: import ( "fmt" \n "net/http" )
    for block in re.finditer(r'import\s*\(\s*([\s\S]*?)\)', clean):
        for m in re.finditer(r'"([^"]+)"', block.group(1)):
            sig.imports.append(m.group(1))
    # Single-line imports: import "fmt"
    for m in re.finditer(r'import\s+"([^"]+)"', clean):
        if m.group(1) not in sig.imports:
            sig.imports.append(m.group(1))

    # Functions: func Name(...) or func (receiver) Name(...)
    for m in re.finditer(r'func\s+(?:\(\s*\w+\s+\*?(\w+)\s*\)\s+)?(\w+)\s*\(([^)]*)\)(?:\s*\(?\s*([^){]*)\)?)?', clean):
        receiver = m.group(1)
        name = m.group(2)
        params = m.group(3).strip()[:80]
        returns = (m.group(4) or "").strip()[:40]
        prefix = f"({receiver}) " if receiver else ""
        ret_str = f" -> {returns}" if returns else ""
        sig.functions.append(f"fn {prefix}{name}({params}){ret_str}")

    # Structs and interfaces
    for m in re.finditer(r'type\s+(\w+)\s+struct\b', clean):
        sig.classes.append(f"struct {m.group(1)}")
    for m in re.finditer(r'type\s+(\w+)\s+interface\b', clean):
        sig.classes.append(f"interface {m.group(1)}")
    # Type aliases and custom types
    for m in re.finditer(r'type\s+(\w+)\s+(?!struct\b|interface\b)(\w+)', clean):
        sig.classes.append(f"type {m.group(1)} = {m.group(2)}")

    # Gin routes: r.GET("/path", handler), router.POST("/path", handler)
    for m in re.finditer(r'(?:\w+)\.(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS|Any|Handle)\s*\(\s*"([^"]+)"', clean):
        method = m.group(1).upper()
        if method in ("ANY", "HANDLE"):
            method = "ALL"
        sig.routes.append(f"{method} {m.group(2)}")

    # Echo routes: e.GET("/path", handler)
    for m in re.finditer(r'(?:\w+)\.(Get|Post|Put|Delete|Patch)\s*\(\s*"([^"]+)"', clean):
        sig.routes.append(f"{m.group(1).upper()} {m.group(2)}")

    # Chi routes: r.Get("/path", handler), r.Route("/group", func...)
    for m in re.finditer(r'(?:\w+)\.(Get|Post|Put|Delete|Patch|Route)\s*\(\s*"([^"]+)"', clean):
        method = m.group(1).upper()
        if method == "ROUTE":
            sig.routes.append(f"GROUP {m.group(2)}")
        else:
            sig.routes.append(f"{method} {m.group(2)}")

    # http.HandleFunc("/path", handler)
    for m in re.finditer(r'http\.HandleFunc\s*\(\s*"([^"]+)"', clean):
        sig.routes.append(f"ALL {m.group(1)}")

    # Gorilla mux: r.HandleFunc("/path", handler).Methods("GET")
    for m in re.finditer(r'HandleFunc\s*\(\s*"([^"]+)"[^)]*\)\.Methods\s*\(\s*"([^"]+)"', clean):
        sig.routes.append(f"{m.group(2).upper()} {m.group(1)}")

    # Deduplicate routes
    sig.routes = list(dict.fromkeys(sig.routes))

    return sig


# === DART / FLUTTER PARSER (dedicated) ===

def _parse_dart(rel_path: str, content: str) -> FileSignature:
    """Parse Dart/Flutter files with widget, route, and state management detection."""
    sig = FileSignature(path=rel_path, language="dart")
    sig.loc = sum(1 for line in content.splitlines()
                  if line.strip() and not line.strip().startswith("//"))

    # Strip comments
    clean = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
    clean = re.sub(r'/\*[\s\S]*?\*/', '', clean)

    # Imports: import 'package:flutter/material.dart';
    for m in re.finditer(r"import\s+['\"]([^'\"]+)['\"]", clean):
        sig.imports.append(m.group(1))

    # Classes with optional extends/implements/with
    for m in re.finditer(r'class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+with\s+([\w,\s]+))?(?:\s+implements\s+([\w,\s]+))?', clean):
        name = m.group(1)
        extends = m.group(2)
        with_mixins = m.group(3)
        implements = m.group(4)
        parts = []
        if extends:
            parts.append(extends)
        if with_mixins:
            parts.append(f"with {with_mixins.strip()}")
        if implements:
            parts.append(f"impl {implements.strip()}")
        base = f"({', '.join(parts)})" if parts else ""
        sig.classes.append(f"class {name}{base}")

        # Detect widget types
        if extends in ("StatelessWidget", "StatefulWidget", "HookWidget",
                        "ConsumerWidget", "ConsumerStatefulWidget"):
            sig.exports.append(f"Widget:{name}")
        elif extends and "State<" in content[m.start():m.start()+200]:
            sig.exports.append(f"State:{name}")

    # Top-level functions
    for m in re.finditer(r'^(?:Future<[^>]+>|void|String|int|double|bool|dynamic|List<[^>]+>|Map<[^>]+>|\w+)\s+(\w+)\s*\(([^)]*)\)', clean, re.MULTILINE):
        name = m.group(1)
        params = m.group(2).strip()[:80]
        # Skip if inside a class (indented)
        line_start = content.rfind('\n', 0, m.start()) + 1
        indent = len(content[line_start:m.start()]) - len(content[line_start:m.start()].lstrip())
        if indent <= 2:  # top-level or minimal indent
            sig.functions.append(f"fn {name}({params})")

    # Enums
    for m in re.finditer(r'enum\s+(\w+)', clean):
        sig.classes.append(f"enum {m.group(1)}")

    # Mixins
    for m in re.finditer(r'mixin\s+(\w+)(?:\s+on\s+(\w+))?', clean):
        on = f"(on {m.group(2)})" if m.group(2) else ""
        sig.classes.append(f"mixin {m.group(1)}{on}")

    # Extensions
    for m in re.finditer(r'extension\s+(\w+)\s+on\s+(\w+)', clean):
        sig.classes.append(f"extension {m.group(1)} on {m.group(2)}")

    # Flutter routes: MaterialPageRoute, GoRouter, auto_route
    # GoRouter: GoRoute(path: '/users', builder: ...)
    for m in re.finditer(r"GoRoute\s*\([^)]*path\s*:\s*['\"]([^'\"]+)['\"]", clean):
        sig.routes.append(f"GET {m.group(1)}")
    # Navigator named routes: '/settings', '/home'
    for m in re.finditer(r"(?:pushNamed|pushReplacementNamed)\s*\([^,]+,\s*['\"]([^'\"]+)['\"]", clean):
        sig.routes.append(f"NAV {m.group(1)}")
    # Route map: case '/path':
    for m in re.finditer(r"case\s+['\"](/[^'\"]+)['\"]", clean):
        sig.routes.append(f"GET {m.group(1)}")
    # onGenerateRoute pattern
    if "onGenerateRoute" in clean:
        sig.routes.append("onGenerateRoute (dynamic)")

    # State management patterns
    # Provider / Riverpod
    for m in re.finditer(r'(?:ChangeNotifierProvider|Provider|StateNotifierProvider|FutureProvider|StreamProvider)(?:<[^>]+>)?\s*\(', clean):
        sig.state_patterns.append("Provider")
    for m in re.finditer(r'(?:final|var)\s+(\w+Provider)\s*=', clean):
        sig.state_patterns.append(f"Riverpod:{m.group(1)}")
    # Bloc / Cubit
    for m in re.finditer(r'class\s+(\w+)\s+extends\s+(?:Bloc|Cubit)<', clean):
        sig.state_patterns.append(f"Bloc:{m.group(1)}")
    # GetX
    for m in re.finditer(r'class\s+(\w+)\s+extends\s+GetxController', clean):
        sig.state_patterns.append(f"GetX:{m.group(1)}")
    # MobX
    for m in re.finditer(r'@observable|@action|@computed', clean):
        sig.state_patterns.append("MobX")
        break

    # Annotations / decorators
    for m in re.finditer(r'@(\w+)(?:\(|$)', clean, re.MULTILINE):
        anno = m.group(1)
        if anno in ("override", "required", "protected", "visibleForTesting",
                     "immutable", "freezed", "JsonSerializable", "HiveType",
                     "riverpod", "RoutePage"):
            sig.decorators.append(f"@{anno}")

    # Deduplicate
    sig.state_patterns = list(dict.fromkeys(sig.state_patterns))
    sig.routes = list(dict.fromkeys(sig.routes))
    sig.decorators = list(dict.fromkeys(sig.decorators))

    return sig


# === GENERIC PARSER (regex fallback) ===

def _parse_generic(rel_path: str, content: str) -> FileSignature:
    """Minimal regex parser for Rust, Java, Kotlin, and other languages."""
    sig = FileSignature(path=rel_path, language=_detect_language(Path(rel_path)))
    sig.loc = sum(1 for line in content.splitlines()
                  if line.strip() and not line.strip().startswith("//"))

    # Rust
    if sig.language == "rust":
        for m in re.finditer(r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)', content):
            sig.functions.append(f"fn {m.group(1)}")
        for m in re.finditer(r'(?:pub\s+)?struct\s+(\w+)', content):
            sig.classes.append(f"struct {m.group(1)}")
        for m in re.finditer(r'(?:pub\s+)?enum\s+(\w+)', content):
            sig.classes.append(f"enum {m.group(1)}")
        for m in re.finditer(r'use\s+([\w:]+)', content):
            sig.imports.append(m.group(1))

    # Java/Kotlin
    elif sig.language in ("java", "kotlin"):
        for m in re.finditer(r'(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)?(\w+)\s*\([^)]*\)\s*{', content):
            sig.functions.append(f"fn {m.group(1)}")
        for m in re.finditer(r'class\s+(\w+)(?:\s+extends\s+(\w+))?', content):
            base = f"({m.group(2)})" if m.group(2) else ""
            sig.classes.append(f"class {m.group(1)}{base}")
        for m in re.finditer(r'import\s+([\w.]+)', content):
            sig.imports.append(m.group(1))

    # Fallback: catch generic function/class patterns
    else:
        for m in re.finditer(r'(?:def|func|fn|function)\s+(\w+)', content):
            sig.functions.append(f"fn {m.group(1)}")
        for m in re.finditer(r'class\s+(\w+)', content):
            sig.classes.append(f"class {m.group(1)}")

    return sig


# === TOPOLOGY BUILDER ===

def _resolve_import(imp: str, file_path: str, all_files: set[str],
                    project_root: Path) -> Optional[str]:
    """Try to resolve an import string to a file in the project."""
    # Skip external packages
    if imp.startswith((".", "/")):
        # Relative import
        base = str(Path(file_path).parent)
        imp_clean = imp.lstrip(".")
    else:
        base = ""
        imp_clean = imp

    # Convert dots to path separators
    imp_path = imp_clean.replace(".", "/")

    # Try common resolutions
    candidates = [
        f"{base}/{imp_path}.py" if base else f"{imp_path}.py",
        f"{base}/{imp_path}/__init__.py" if base else f"{imp_path}/__init__.py",
        f"{imp_path}.js", f"{imp_path}.ts", f"{imp_path}.tsx", f"{imp_path}.jsx",
        f"{imp_path}/index.js", f"{imp_path}/index.ts", f"{imp_path}/index.tsx",
    ]

    # For relative JS imports, resolve from file's directory
    if imp.startswith("./") or imp.startswith("../"):
        rel_dir = str(Path(file_path).parent)
        rel_imp = str(Path(rel_dir) / imp.lstrip("./"))
        candidates.extend([
            f"{rel_imp}.js", f"{rel_imp}.ts", f"{rel_imp}.tsx", f"{rel_imp}.jsx",
            f"{rel_imp}/index.js", f"{rel_imp}/index.ts", f"{rel_imp}/index.tsx",
        ])

    # Normalize and check
    for candidate in candidates:
        normalized = str(Path(candidate))
        if normalized in all_files:
            return normalized

    return None


def _build_topology(signatures: list[FileSignature], project_root: Path) -> CodeTopology:
    """Build dependency graph from file signatures."""
    topo = CodeTopology()
    all_files = {sig.path for sig in signatures}

    # Build adjacency
    for sig in signatures:
        deps = []
        for imp in sig.imports:
            resolved = _resolve_import(imp, sig.path, all_files, project_root)
            if resolved and resolved != sig.path:
                deps.append(resolved)
        if deps:
            topo.adjacency[sig.path] = sorted(set(deps))

    # Detect entry points
    imported_files = set()
    for deps in topo.adjacency.values():
        imported_files.update(deps)

    for sig in signatures:
        name_lower = Path(sig.path).stem.lower()
        # Files that are never imported = likely entry points
        if sig.path not in imported_files and sig.functions:
            topo.entry_points.append(sig.path)
        # Explicit main files
        elif name_lower in ("main", "index", "app", "__main__"):
            if sig.path not in topo.entry_points:
                topo.entry_points.append(sig.path)

    # Detect packages (directories with __init__.py or package.json)
    packages = set()
    for sig in signatures:
        parts = Path(sig.path).parts
        if len(parts) > 1:
            packages.add(parts[0])
    topo.packages = sorted(packages)

    # Detect monorepo
    monorepo_markers = {"nx.json", "turbo.json", "lerna.json"}
    for sig in signatures:
        if Path(sig.path).name in monorepo_markers:
            # Look for sub-projects
            for other in signatures:
                parts = Path(other.path).parts
                if len(parts) > 2 and parts[0] in ("packages", "apps", "libs"):
                    if parts[1] not in topo.monorepo_projects:
                        topo.monorepo_projects.append(parts[1])

    return topo


# === SUMMARY FORMATTER ===

def _format_summary(compressed: CompressedCode) -> str:
    """Format CompressedCode into compact markdown for the .seif summary field."""
    lines = []

    # Header
    lang_str = ", ".join(f"{lang}: {count}" for lang, count in
                          sorted(compressed.languages.items(), key=lambda x: -x[1]))
    lines.append(f"## {compressed.project_name} (code-compressed)")
    lines.append(f"Languages: {lang_str} | Files: {compressed.total_files} | LOC: {compressed.total_loc:,}")
    lines.append("")

    # Topology
    adj = compressed.topology.adjacency
    if adj:
        lines.append("### Topology")
        shown = 0
        for src, deps in sorted(adj.items(), key=lambda x: -len(x[1])):
            if shown >= CODE_MAX_ADJACENCY:
                remaining = len(adj) - shown
                lines.append(f"  ... and {remaining} more files")
                break
            lines.append(f"  {src}: [{', '.join(deps[:5])}]")
            shown += 1
        lines.append("")

    # Entry points
    if compressed.topology.entry_points:
        lines.append(f"Entry points: {', '.join(compressed.topology.entry_points[:10])}")
        lines.append("")

    # Monorepo
    if compressed.topology.monorepo_projects:
        lines.append(f"Monorepo projects: {', '.join(compressed.topology.monorepo_projects)}")
        lines.append("")

    # Signatures (top N by complexity)
    sigs = sorted(compressed.signatures,
                  key=lambda s: len(s.functions) + len(s.classes), reverse=True)
    if sigs:
        lines.append("### Signatures")
        shown = 0
        for sig in sigs:
            if shown >= CODE_MAX_SIGNATURES:
                remaining = len(sigs) - shown
                lines.append(f"  ... and {remaining} more files")
                break
            if not sig.functions and not sig.classes:
                continue
            lines.append(f"{sig.path}:")
            for cls in sig.classes[:5]:
                lines.append(f"  - {cls}")
            for fn in sig.functions[:8]:
                lines.append(f"  - {fn}")
            for dec in sig.decorators[:3]:
                lines.append(f"  - {dec}")
            shown += 1
        lines.append("")

    # Routes
    if compressed.route_map:
        lines.append("### Routes")
        for route in compressed.route_map[:CODE_MAX_ROUTES]:
            lines.append(f"  {route}")
        if len(compressed.route_map) > CODE_MAX_ROUTES:
            lines.append(f"  ... and {len(compressed.route_map) - CODE_MAX_ROUTES} more routes")
        lines.append("")

    # State architecture
    if compressed.state_architecture:
        lines.append("### State Architecture")
        for pattern in compressed.state_architecture[:20]:
            lines.append(f"  {pattern}")
        lines.append("")

    # API surface
    if compressed.api_surface:
        lines.append("### API Surface")
        for endpoint in compressed.api_surface[:CODE_MAX_ROUTES]:
            lines.append(f"  {endpoint}")
        lines.append("")

    # Classification summary
    if compressed.classification_summary:
        lines.append("### Classification")
        for level in ("CONFIDENTIAL", "INTERNAL", "PUBLIC"):
            files = compressed.classification_summary.get(level, [])
            if files:
                shown_files = files[:5]
                extra = f" ... +{len(files) - 5}" if len(files) > 5 else ""
                lines.append(f"  {level}: [{', '.join(shown_files)}{extra}]")
        lines.append("")

    # Packages
    if compressed.topology.packages:
        lines.append(f"Packages: {', '.join(compressed.topology.packages[:15])}")

    return "\n".join(lines)


# === MAIN ENTRY POINTS ===

def compress_project(
    project_path: str,
    author: str = "code-compressor",
    via: str = "seif-compress",
    max_files: int = CODE_MAX_FILES,
    target_path: str = None,
) -> tuple:
    """Compress a source code project into a .seif module.

    Args:
        project_path: Path to project root directory.
        author: Author name for provenance.
        via: Tool identifier for provenance.
        max_files: Maximum files to scan (default 500).
        target_path: Override output path (for SCR mode).

    Returns:
        Tuple of (SeifModule, Path) — the compressed module and where it was saved.
    """
    from seif.context.context_manager import create_module, save_module

    root = Path(project_path).resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    project_name = root.name

    # Scan all source files
    signatures = []
    files_scanned = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in-place
        dirnames[:] = [d for d in dirnames
                       if d not in IGNORE_DIRS and not d.startswith(".")]

        for fname in sorted(filenames):
            if files_scanned >= max_files:
                break

            fpath = Path(dirpath) / fname
            if _should_skip(fpath, root):
                continue

            lang = _detect_language(fpath)
            if lang == "generic" and fpath.suffix.lower() not in LANGUAGE_MAP:
                # Allow common config files and sensitive files (for classification)
                is_sensitive = any(p in fpath.name.lower() for p in SENSITIVE_FILE_PATTERNS)
                is_config = fpath.suffix.lower() in {".json", ".yaml", ".yml", ".toml",
                                                      ".md", ".txt", ".cfg", ".ini"}
                if not is_sensitive and not is_config:
                    continue

            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except (OSError, UnicodeDecodeError):
                continue

            rel_path = str(fpath.relative_to(root))
            classification = _classify_file(fpath, content)

            # Parse based on language
            if lang == "python":
                sig = _parse_python(rel_path, content)
            elif lang in ("javascript", "typescript"):
                sig = _parse_javascript(rel_path, content)
            elif lang == "go":
                sig = _parse_go(rel_path, content)
            elif lang == "dart":
                sig = _parse_dart(rel_path, content)
            else:
                sig = _parse_generic(rel_path, content)

            sig.classification = classification
            signatures.append(sig)
            files_scanned += 1

    # Build topology
    topology = _build_topology(signatures, root)

    # Consolidate routes, state, and API surface
    route_map = []
    state_arch = []
    api_surface = []
    for sig in signatures:
        for route in sig.routes:
            route_entry = f"{route} -> {sig.path}"
            if route.startswith("API") or route.startswith("POST") or route.startswith("PUT") or route.startswith("DELETE"):
                api_surface.append(route_entry)
            route_map.append(route_entry)
        state_arch.extend(sig.state_patterns)

    # Deduplicate
    route_map = list(dict.fromkeys(route_map))
    state_arch = list(dict.fromkeys(state_arch))
    api_surface = list(dict.fromkeys(api_surface))

    # Classification summary
    class_summary: dict[str, list[str]] = {}
    for sig in signatures:
        class_summary.setdefault(sig.classification, []).append(sig.path)

    # Language distribution
    languages: dict[str, int] = {}
    total_loc = 0
    for sig in signatures:
        languages[sig.language] = languages.get(sig.language, 0) + 1
        total_loc += sig.loc

    # Build CompressedCode
    compressed = CompressedCode(
        project_name=project_name,
        project_path=str(root),
        languages=languages,
        total_files=len(signatures),
        total_loc=total_loc,
        topology=topology,
        signatures=signatures,
        route_map=route_map,
        state_architecture=state_arch,
        api_surface=api_surface,
        classification_summary=class_summary,
        compressed_at=datetime.now(timezone.utc).isoformat(),
    )

    # Format summary
    summary = _format_summary(compressed)

    # Create .seif module via existing infrastructure
    module = create_module(
        source_name=f"{project_name} (code-compressed)",
        original_words=total_loc,
        summary=summary,
        author=author,
        via=via,
    )

    # Set classification to highest found
    if "CONFIDENTIAL" in class_summary:
        module.classification = "CONFIDENTIAL"
    elif "INTERNAL" in class_summary:
        module.classification = "INTERNAL"
    else:
        module.classification = "PUBLIC"

    # Save
    if target_path:
        save_path = Path(target_path)
    else:
        seif_dir = root / ".seif"
        seif_dir.mkdir(parents=True, exist_ok=True)
        save_path = seif_dir / "code.seif"

    saved = save_module(module, target_path=save_path)
    return module, saved


def compress_incremental(
    project_path: str,
    existing_seif: str,
    author: str = "code-compressor",
) -> tuple:
    """Incrementally update an existing code.seif by re-compressing changed files.

    Compares file modification times against the module's compressed_at timestamp.
    Only re-parses changed files, merges with existing data.

    Args:
        project_path: Path to project root directory.
        existing_seif: Path to existing code.seif file.
        author: Author name for provenance.

    Returns:
        Tuple of (SeifModule, Path).
    """
    from seif.context.context_manager import load_module, contribute_to_module

    module = load_module(existing_seif)

    # Extract timestamp from summary
    compressed_at = module.updated_at or module.contributors[0]["at"] if module.contributors else None
    if not compressed_at:
        # No timestamp — do full recompress
        return compress_project(project_path, author=author, target_path=existing_seif)

    try:
        ref_time = datetime.fromisoformat(compressed_at).timestamp()
    except (ValueError, TypeError):
        return compress_project(project_path, author=author, target_path=existing_seif)

    # Find changed files
    root = Path(project_path).resolve()
    changed_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in IGNORE_DIRS and not d.startswith(".")]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if _should_skip(fpath, root):
                continue
            try:
                if fpath.stat().st_mtime > ref_time:
                    changed_files.append(fpath)
            except OSError:
                continue

    if not changed_files:
        return module, Path(existing_seif)

    # Re-parse only changed files
    new_sigs = []
    for fpath in changed_files:
        lang = _detect_language(fpath)
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue

        rel_path = str(fpath.relative_to(root))
        if lang == "python":
            sig = _parse_python(rel_path, content)
        elif lang in ("javascript", "typescript"):
            sig = _parse_javascript(rel_path, content)
        elif lang == "go":
            sig = _parse_go(rel_path, content)
        elif lang == "dart":
            sig = _parse_dart(rel_path, content)
        else:
            sig = _parse_generic(rel_path, content)
        sig.classification = _classify_file(fpath, content)
        new_sigs.append(sig)

    # Build delta summary
    delta_lines = [f"\n### Incremental update ({len(changed_files)} files changed)"]
    for sig in new_sigs:
        if sig.functions or sig.classes:
            delta_lines.append(f"{sig.path}:")
            for fn in sig.functions[:5]:
                delta_lines.append(f"  - {fn}")
            for cls in sig.classes[:3]:
                delta_lines.append(f"  - {cls}")

    delta_text = "\n".join(delta_lines)

    updated_module, path = contribute_to_module(
        module_path=existing_seif,
        contribution_text=delta_text,
        author=author,
        via="seif-compress-incremental",
    )
    return updated_module, path


def watch_project(
    project_path: str,
    callback=None,
    interval: float = CODE_WATCH_INTERVAL,
):
    """Watch a project for file changes and incrementally compress.

    Simple polling loop using os.stat() mtimes. Runs until Ctrl+C.

    Args:
        project_path: Path to project root.
        callback: Optional function called after each compression.
        interval: Seconds between polls (default 2.0).
    """
    root = Path(project_path).resolve()
    seif_path = root / ".seif" / "code.seif"

    # Initial compression if no .seif exists
    if not seif_path.exists():
        print(f"  Initial compression of {root.name}...")
        module, path = compress_project(str(root))
        print(f"  Created: {path} ({module.compressed_words} words, {module.compression_ratio}:1)")
        if callback:
            callback(module, path)

    # Track mtimes
    last_mtimes = _collect_mtimes(root)

    try:
        while True:
            time.sleep(interval)
            current_mtimes = _collect_mtimes(root)

            if current_mtimes != last_mtimes:
                changed = set(current_mtimes.keys()) - set(last_mtimes.keys())
                changed.update(k for k in current_mtimes
                               if k in last_mtimes and current_mtimes[k] != last_mtimes[k])
                print(f"  {len(changed)} file(s) changed — recompressing...")

                try:
                    module, path = compress_incremental(str(root), str(seif_path))
                    print(f"  Updated: {path} (v{module.version}, {module.compressed_words} words)")
                    if callback:
                        callback(module, path)
                except Exception as e:
                    print(f"  Error: {e}")

                last_mtimes = current_mtimes
    except KeyboardInterrupt:
        print("\n  Watch stopped.")


def _collect_mtimes(root: Path) -> dict[str, float]:
    """Collect modification times for all source files in project."""
    mtimes = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in IGNORE_DIRS and not d.startswith(".")]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if not _should_skip(fpath, root):
                try:
                    mtimes[str(fpath.relative_to(root))] = fpath.stat().st_mtime
                except OSError:
                    pass
    return mtimes
