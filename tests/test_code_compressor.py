"""
Tests for the Code Compressor — semantic compression of source code projects.

Tests cover: Python parser (AST), JS/TS parser (regex), classification,
topology building, and full project compression integration.
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from seif.context.code_compressor import (
    _parse_python, _parse_javascript, _parse_go, _parse_dart, _parse_generic,
    _classify_file, _build_topology, _format_summary,
    _detect_language, _should_skip, _nextjs_pages_route, _nextjs_app_route,
    FileSignature, CodeTopology, CompressedCode,
    compress_project,
)


class TestLanguageDetection(unittest.TestCase):
    def test_python(self):
        assert _detect_language(Path("app.py")) == "python"

    def test_javascript(self):
        assert _detect_language(Path("app.js")) == "javascript"
        assert _detect_language(Path("app.jsx")) == "javascript"

    def test_typescript(self):
        assert _detect_language(Path("app.ts")) == "typescript"
        assert _detect_language(Path("app.tsx")) == "typescript"

    def test_rust(self):
        assert _detect_language(Path("main.rs")) == "rust"

    def test_go(self):
        assert _detect_language(Path("main.go")) == "go"

    def test_generic(self):
        assert _detect_language(Path("data.csv")) == "generic"


class TestPythonParser(unittest.TestCase):
    def test_extracts_functions(self):
        code = '''
def greet(name: str) -> str:
    return f"Hello {name}"

async def fetch_data(url: str, timeout: int = 30) -> dict:
    pass
'''
        sig = _parse_python("app.py", code)
        assert len(sig.functions) == 2
        assert "fn greet(name: str) -> str" in sig.functions
        assert any("async" in f and "fetch_data" in f for f in sig.functions)

    def test_extracts_classes(self):
        code = '''
class User(BaseModel):
    name: str

class Admin(User):
    role: str = "admin"
'''
        sig = _parse_python("models.py", code)
        assert len(sig.classes) == 2
        assert "class User(BaseModel)" in sig.classes
        assert "class Admin(User)" in sig.classes

    def test_extracts_imports(self):
        code = '''
import os
from pathlib import Path
from seif.core.resonance_gate import evaluate
'''
        sig = _parse_python("app.py", code)
        assert "os" in sig.imports
        assert "pathlib" in sig.imports
        assert "seif.core.resonance_gate" in sig.imports

    def test_extracts_decorators(self):
        code = '''
from flask import Flask
app = Flask(__name__)

@app.route("/users", methods=["GET"])
def list_users():
    pass

@app.post("/users")
def create_user():
    pass
'''
        sig = _parse_python("routes.py", code)
        assert any("@app.route" in d for d in sig.decorators)
        assert any("@app.post" in d for d in sig.decorators)

    def test_extracts_flask_routes(self):
        code = '''
@app.route("/api/users")
def users():
    pass

@app.get("/api/items")
def items():
    pass
'''
        sig = _parse_python("api.py", code)
        assert any("/api/users" in r for r in sig.routes)
        assert any("/api/items" in r for r in sig.routes)

    def test_handles_syntax_errors(self):
        code = '''
def broken(
    # missing closing paren
class Also{Broken}:
'''
        sig = _parse_python("broken.py", code)
        # Should not raise, fallback to regex
        assert sig.language == "python"

    def test_counts_loc(self):
        code = '''# comment
def foo():
    pass

# another comment
'''
        sig = _parse_python("simple.py", code)
        assert sig.loc == 2  # def foo(): and pass


class TestJavaScriptParser(unittest.TestCase):
    def test_extracts_imports(self):
        code = '''
import React from 'react';
import { useState, useEffect } from 'react';
const express = require('express');
'''
        sig = _parse_javascript("app.js", code)
        assert "react" in sig.imports
        assert "express" in sig.imports

    def test_extracts_exports(self):
        code = '''
export default function App() { return <div /> }
export const API_URL = "http://example.com";
export class UserService {}
'''
        sig = _parse_javascript("app.js", code)
        assert "App" in sig.exports
        assert "API_URL" in sig.exports
        assert "UserService" in sig.exports

    def test_extracts_react_components(self):
        code = '''
import React from 'react';

export default function UserProfile({ user }) {
    return <div>{user.name}</div>;
}

const Sidebar = () => {
    return <nav />;
};
'''
        sig = _parse_javascript("UserProfile.jsx", code)
        assert any("UserProfile" in f or "UserProfile" in e
                    for f in sig.functions for e in sig.exports)

    def test_extracts_hooks(self):
        code = '''
const [count, setCount] = useState(0);
useEffect(() => {}, []);
const data = useMemo(() => compute(), [deps]);
'''
        sig = _parse_javascript("component.js", code)
        hooks = [p for p in sig.state_patterns if p.startswith("Hook:")]
        assert any("useState" in h for h in hooks)
        assert any("useEffect" in h for h in hooks)
        assert any("useMemo" in h for h in hooks)

    def test_extracts_express_routes(self):
        code = '''
app.get('/api/users', (req, res) => {});
app.post('/api/users', (req, res) => {});
router.delete('/api/users/:id', handler);
'''
        sig = _parse_javascript("routes.js", code)
        assert any("GET /api/users" in r for r in sig.routes)
        assert any("POST /api/users" in r for r in sig.routes)
        assert any("DELETE /api/users/:id" in r for r in sig.routes)

    def test_extracts_redux(self):
        code = '''
const userSlice = createSlice({
    name: 'user',
    initialState: {},
});
'''
        sig = _parse_javascript("store.js", code)
        assert any("Redux:user" in p for p in sig.state_patterns)

    def test_nextjs_pages_routes(self):
        assert _nextjs_pages_route("pages/index.tsx") == "GET /"
        assert _nextjs_pages_route("pages/users/[id].tsx") == "GET /users/:id"
        assert _nextjs_pages_route("pages/api/auth.ts") == "API /api/auth"

    def test_nextjs_app_routes(self):
        assert _nextjs_app_route("app/page.tsx") == "GET /"
        assert _nextjs_app_route("app/users/[id]/page.tsx") == "GET /users/:id"
        assert _nextjs_app_route("app/api/auth/route.ts") == "API /api/auth"
        assert _nextjs_app_route("app/layout.tsx") is None


class TestGoParser(unittest.TestCase):
    def test_extracts_functions(self):
        code = '''
package main

func main() {
    fmt.Println("hello")
}

func (s *Server) HandleRequest(w http.ResponseWriter, r *http.Request) error {
    return nil
}

func createUser(name string, email string) (*User, error) {
    return nil, nil
}
'''
        sig = _parse_go("main.go", code)
        assert any("main" in f for f in sig.functions)
        assert any("HandleRequest" in f for f in sig.functions)
        assert any("createUser" in f for f in sig.functions)
        # Method receiver should be captured
        assert any("Server" in f for f in sig.functions)

    def test_extracts_multi_imports(self):
        code = '''
import (
    "fmt"
    "net/http"
    "github.com/gin-gonic/gin"
    "myproject/internal/models"
)
'''
        sig = _parse_go("main.go", code)
        assert "fmt" in sig.imports
        assert "net/http" in sig.imports
        assert "github.com/gin-gonic/gin" in sig.imports
        assert "myproject/internal/models" in sig.imports

    def test_extracts_single_import(self):
        code = 'import "fmt"\n'
        sig = _parse_go("main.go", code)
        assert "fmt" in sig.imports

    def test_extracts_structs_interfaces(self):
        code = '''
type User struct {
    ID   int
    Name string
}

type Repository interface {
    FindAll() ([]User, error)
}

type UserID int
'''
        sig = _parse_go("models.go", code)
        assert any("struct User" in c for c in sig.classes)
        assert any("interface Repository" in c for c in sig.classes)
        assert any("type UserID" in c for c in sig.classes)

    def test_gin_routes(self):
        code = '''
func setupRoutes(r *gin.Engine) {
    r.GET("/api/users", listUsers)
    r.POST("/api/users", createUser)
    r.PUT("/api/users/:id", updateUser)
    r.DELETE("/api/users/:id", deleteUser)
}
'''
        sig = _parse_go("routes.go", code)
        assert any("GET /api/users" in r for r in sig.routes)
        assert any("POST /api/users" in r for r in sig.routes)
        assert any("PUT /api/users/:id" in r for r in sig.routes)
        assert any("DELETE /api/users/:id" in r for r in sig.routes)

    def test_echo_routes(self):
        code = '''
func setupRoutes(e *echo.Echo) {
    e.Get("/users", listUsers)
    e.Post("/users", createUser)
}
'''
        sig = _parse_go("routes.go", code)
        assert any("GET /users" in r for r in sig.routes)
        assert any("POST /users" in r for r in sig.routes)

    def test_stdlib_http_routes(self):
        code = '''
func main() {
    http.HandleFunc("/health", healthCheck)
    http.HandleFunc("/api/data", dataHandler)
}
'''
        sig = _parse_go("main.go", code)
        assert any("/health" in r for r in sig.routes)
        assert any("/api/data" in r for r in sig.routes)

    def test_counts_loc(self):
        code = '// comment\nfunc main() {\n    fmt.Println("hi")\n}\n'
        sig = _parse_go("main.go", code)
        assert sig.loc == 3


class TestDartParser(unittest.TestCase):
    def test_extracts_imports(self):
        code = '''
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'dart:async';
'''
        sig = _parse_dart("lib/main.dart", code)
        assert "package:flutter/material.dart" in sig.imports
        assert "package:provider/provider.dart" in sig.imports
        assert "dart:async" in sig.imports

    def test_extracts_classes_with_inheritance(self):
        code = '''
class MyApp extends StatelessWidget {
  Widget build(BuildContext context) => MaterialApp();
}

class HomeScreen extends StatefulWidget {
  _HomeScreenState createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  void initState() {}
}
'''
        sig = _parse_dart("lib/main.dart", code)
        assert any("class MyApp(StatelessWidget)" in c for c in sig.classes)
        assert any("class HomeScreen(StatefulWidget)" in c for c in sig.classes)
        # Widgets detected
        assert any("Widget:MyApp" in e for e in sig.exports)
        assert any("Widget:HomeScreen" in e for e in sig.exports)

    def test_extracts_enums_and_mixins(self):
        code = '''
enum AppTheme { light, dark, system }

mixin LoggingMixin on StatefulWidget {
  void log(String msg) {}
}
'''
        sig = _parse_dart("lib/theme.dart", code)
        assert any("enum AppTheme" in c for c in sig.classes)
        assert any("mixin LoggingMixin" in c for c in sig.classes)

    def test_detects_bloc_pattern(self):
        code = '''
class AuthBloc extends Bloc<AuthEvent, AuthState> {
  AuthBloc() : super(AuthInitial());
}

class CounterCubit extends Cubit<int> {
  void increment() => emit(state + 1);
}
'''
        sig = _parse_dart("lib/bloc/auth_bloc.dart", code)
        assert any("Bloc:AuthBloc" in p for p in sig.state_patterns)

    def test_detects_riverpod(self):
        code = '''
final userProvider = StateNotifierProvider<UserNotifier, UserState>((ref) {
  return UserNotifier();
});
'''
        sig = _parse_dart("lib/providers.dart", code)
        assert any("Riverpod:userProvider" in p for p in sig.state_patterns)

    def test_detects_getx(self):
        code = '''
class HomeController extends GetxController {
  var count = 0.obs;
  void increment() => count++;
}
'''
        sig = _parse_dart("lib/controllers/home.dart", code)
        assert any("GetX:HomeController" in p for p in sig.state_patterns)

    def test_gorouter_routes(self):
        code = '''
final router = GoRouter(routes: [
  GoRoute(path: '/', builder: (ctx, state) => HomeScreen()),
  GoRoute(path: '/users/:id', builder: (ctx, state) => UserScreen()),
  GoRoute(path: '/settings', builder: (ctx, state) => SettingsScreen()),
]);
'''
        sig = _parse_dart("lib/router.dart", code)
        assert any("GET /" == r for r in sig.routes)
        assert any("/users/:id" in r for r in sig.routes)
        assert any("/settings" in r for r in sig.routes)

    def test_navigator_routes(self):
        code = '''
Navigator.pushNamed(context, '/profile');
Navigator.pushReplacementNamed(context, '/login');
'''
        sig = _parse_dart("lib/nav.dart", code)
        assert any("/profile" in r for r in sig.routes)
        assert any("/login" in r for r in sig.routes)

    def test_decorators(self):
        code = '''
@freezed
class User with _$User {
  const factory User({required String name}) = _User;
}

@JsonSerializable()
class ApiResponse {}

@riverpod
Future<List<User>> fetchUsers(FetchUsersRef ref) async {}
'''
        sig = _parse_dart("lib/models.dart", code)
        assert any("@freezed" in d for d in sig.decorators)
        assert any("@JsonSerializable" in d for d in sig.decorators)
        assert any("@riverpod" in d for d in sig.decorators)


class TestGenericParser(unittest.TestCase):
    def test_rust(self):
        code = '''
use std::io;
pub fn main() {}
pub struct Config { name: String }
pub enum Status { Active, Inactive }
'''
        sig = _parse_generic("main.rs", code)
        assert sig.language == "rust"
        assert any("main" in f for f in sig.functions)
        assert any("Config" in c for c in sig.classes)
        assert any("Status" in c for c in sig.classes)

    def test_go_generic_fallback(self):
        """Go has a dedicated parser; generic fallback catches func keyword."""
        code = 'func main() {}\ntype Server struct {}\n'
        sig = _parse_generic("main.go", code)
        assert sig.language == "go"
        assert any("main" in f for f in sig.functions)


class TestClassification(unittest.TestCase):
    def test_env_is_confidential(self):
        assert _classify_file(Path(".env"), "FOO=bar") == "CONFIDENTIAL"
        assert _classify_file(Path(".env.local"), "X=1") == "CONFIDENTIAL"

    def test_secrets_in_content(self):
        assert _classify_file(Path("config.py"), "API_KEY=abc123") == "CONFIDENTIAL"
        assert _classify_file(Path("keys.txt"), "-----BEGIN PRIVATE KEY") == "CONFIDENTIAL"

    def test_readme_is_public(self):
        assert _classify_file(Path("README.md"), "# Project") == "PUBLIC"
        assert _classify_file(Path("LICENSE"), "MIT") == "PUBLIC"

    def test_default_is_internal(self):
        assert _classify_file(Path("app.py"), "def main(): pass") == "INTERNAL"
        assert _classify_file(Path("utils.js"), "export default {}") == "INTERNAL"


class TestTopology(unittest.TestCase):
    def test_adjacency_graph(self):
        sigs = [
            FileSignature(path="app.py", language="python",
                          imports=["models", "utils"]),
            FileSignature(path="models.py", language="python", imports=[]),
            FileSignature(path="utils.py", language="python", imports=[]),
        ]
        topo = _build_topology(sigs, Path("/project"))
        assert "app.py" in topo.adjacency
        assert "models.py" in topo.adjacency["app.py"]
        assert "utils.py" in topo.adjacency["app.py"]

    def test_entry_points(self):
        sigs = [
            FileSignature(path="main.py", language="python",
                          functions=["fn main()"]),
            FileSignature(path="lib.py", language="python",
                          functions=["fn helper()"]),
        ]
        topo = _build_topology(sigs, Path("/project"))
        assert "main.py" in topo.entry_points

    def test_packages_detected(self):
        sigs = [
            FileSignature(path="src/app.py", language="python"),
            FileSignature(path="tests/test_app.py", language="python"),
        ]
        topo = _build_topology(sigs, Path("/project"))
        assert "src" in topo.packages
        assert "tests" in topo.packages


class TestCompressProject(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create a minimal Python project
        src = Path(self.tmpdir) / "src"
        src.mkdir()
        (Path(self.tmpdir) / "pyproject.toml").write_text(
            '[project]\nname = "test-project"\nversion = "0.1.0"\n'
        )
        (src / "app.py").write_text(
            'from models import User\n\n'
            'def create_user(name: str) -> dict:\n'
            '    return {"name": name}\n\n'
            'def list_users() -> list:\n'
            '    return []\n'
        )
        (src / "models.py").write_text(
            'class User:\n'
            '    def __init__(self, name: str):\n'
            '        self.name = name\n'
        )
        (Path(self.tmpdir) / "README.md").write_text("# Test Project\n")
        (Path(self.tmpdir) / ".env").write_text("SECRET_KEY=abc123\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_produces_valid_seif(self):
        module, path = compress_project(self.tmpdir)
        assert path.exists()
        assert path.suffix == ".seif"
        # Load and verify JSON
        data = json.loads(path.read_text())
        assert data["protocol"] == "SEIF-MODULE-v1"
        assert data["summary"]
        assert data["integrity_hash"]

    def test_compression_ratio(self):
        module, _ = compress_project(self.tmpdir)
        assert module.compression_ratio > 0
        assert module.compressed_words > 0

    def test_resonance_present(self):
        module, _ = compress_project(self.tmpdir)
        assert "ascii_root" in module.resonance
        assert "coherence" in module.resonance
        assert "gate" in module.resonance

    def test_classification_detected(self):
        module, _ = compress_project(self.tmpdir)
        # .env file should trigger CONFIDENTIAL
        assert module.classification == "CONFIDENTIAL"

    def test_summary_contains_signatures(self):
        module, _ = compress_project(self.tmpdir)
        assert "code-compressed" in module.summary
        assert "create_user" in module.summary or "User" in module.summary

    def test_source_name(self):
        module, _ = compress_project(self.tmpdir)
        assert "code-compressed" in module.source


class TestCompressJSProject(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        (Path(self.tmpdir) / "package.json").write_text(
            '{"name": "test-app", "version": "1.0.0"}\n'
        )
        src = Path(self.tmpdir) / "src"
        src.mkdir()
        (src / "App.tsx").write_text(
            "import React from 'react';\n"
            "import { UserList } from './components/UserList';\n\n"
            "export default function App() {\n"
            "  const [users, setUsers] = useState([]);\n"
            "  return <UserList users={users} />;\n"
            "}\n"
        )
        comp = src / "components"
        comp.mkdir()
        (comp / "UserList.tsx").write_text(
            "import React from 'react';\n\n"
            "export function UserList({ users }) {\n"
            "  return <ul>{users.map(u => <li>{u.name}</li>)}</ul>;\n"
            "}\n"
        )
        pages = Path(self.tmpdir) / "pages"
        pages.mkdir()
        (pages / "index.tsx").write_text("export default function Home() { return <div />; }\n")
        api = pages / "api"
        api.mkdir()
        (api / "users.ts").write_text("export default function handler(req, res) { res.json([]); }\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_detects_react_and_nextjs(self):
        module, _ = compress_project(self.tmpdir)
        summary = module.summary
        # Should detect routes from pages/
        assert "Routes" in summary or "pages" in summary

    def test_detects_hooks(self):
        module, _ = compress_project(self.tmpdir)
        assert "useState" in module.summary or "Hook" in module.summary or "State" in module.summary


class TestSkipLogic(unittest.TestCase):
    def test_skips_node_modules(self):
        root = Path("/project")
        assert _should_skip(Path("/project/node_modules/react/index.js"), root)

    def test_skips_dot_dirs(self):
        root = Path("/project")
        assert _should_skip(Path("/project/.git/config"), root)

    def test_skips_lock_files(self):
        tmpdir = tempfile.mkdtemp()
        lock = Path(tmpdir) / "package-lock.json"
        lock.write_text("{}")
        assert _should_skip(lock, Path(tmpdir))
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


class TestFormatSummary(unittest.TestCase):
    def test_formats_header(self):
        compressed = CompressedCode(
            project_name="my-app",
            project_path="/tmp/my-app",
            languages={"python": 10, "javascript": 5},
            total_files=15,
            total_loc=3000,
        )
        summary = _format_summary(compressed)
        assert "my-app (code-compressed)" in summary
        assert "Files: 15" in summary
        assert "LOC: 3,000" in summary


# === Runner ===

if __name__ == "__main__":
    passed = 0
    failed = 0
    errors = []

    # Collect test classes
    test_classes = [v for k, v in sorted(globals().items())
                    if isinstance(v, type) and issubclass(v, unittest.TestCase) and v is not unittest.TestCase]

    for test_class in test_classes:
        suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
        for test in suite:
            try:
                test.debug()
                passed += 1
            except Exception as e:
                failed += 1
                errors.append(f"  FAIL: {test}: {e}")

    for err in errors:
        print(err)

    total = passed + failed
    print(f"\ntest_code_compressor: {passed}/{total} passed, {failed} failed")
