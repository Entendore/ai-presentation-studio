"""engine.py — All business logic: threading, workers, validators, exporters,
snippets, AI, spell check, SEO, and project management."""
import os
import re
import sys
import json
import time
import queue
import asyncio
import shutil
import tempfile
import traceback
import threading
import subprocess
import html
from typing import Any, Callable, Optional, List, Dict, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QObject, QThread, QProcess, Signal, Slot, Qt, QTimer,
    QMetaObject, Q_ARG
)

# =============================================================================
# SECTION 1: CORE INFRASTRUCTURE (Threading, Async, Logging, Cancellation)
# =============================================================================

class CancellationToken:
    def __init__(self):
        self._cancelled = False
        self._lock = threading.Lock()
        self._callbacks: List[Callable] = []

    def cancel(self):
        with self._lock:
            if self._cancelled: return
            self._cancelled = True
            for cb in self._callbacks:
                try: cb()
                except: pass

    @property
    def is_cancelled(self) -> bool:
        with self._lock: return self._cancelled

    def throw_if_cancelled(self):
        if self.is_cancelled:
            raise CancelledError("Operation cancelled")

class CancelledError(Exception): pass

class WorkerThread(QThread):
    started = Signal(str)
    progress = Signal(str, int, str)
    log = Signal(str, str)
    result_ready = Signal(str, object)
    error_occurred = Signal(str, str)
    finished = Signal(str, bool)

    def __init__(self, task_id: str = "", parent=None):
        super().__init__(parent)
        self.task_id = task_id or f"task_{id(self):x}"
        self._cancellation = CancellationToken()
        self._start_time = 0.0
        self._result = None
        self._error = None
        self._success = False

    def cancel(self):
        self._cancellation.cancel()
        self.log.emit(self.task_id, "⛔ Cancellation requested")

    def check_cancelled(self):
        self._cancellation.throw_if_cancelled()

    def report_progress(self, pct: int, msg: str = ""):
        self.progress.emit(self.task_id, pct, msg)

    def report_log(self, msg: str):
        self.log.emit(self.task_id, msg)

    def run(self):
        self._start_time = time.time()
        try:
            self.started.emit(self.task_id)
            self._result = self.do_work()
            self._success = True
            self.result_ready.emit(self.task_id, self._result)
        except CancelledError:
            self.report_log("⛔ Cancelled")
        except Exception as e:
            self._error = f"{e}\n{traceback.format_exc()}"
            self.error_occurred.emit(self.task_id, self._error)
        finally:
            self.finished.emit(self.task_id, self._success)

    def do_work(self) -> Any:
        raise NotImplementedError

class AsyncBridge(QObject):
    task_completed = Signal(str, object)
    task_failed = Signal(str, str)
    _instance = None
    _lock = threading.Lock()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    @classmethod
    def instance(cls):
        with cls._lock:
            if cls._instance is None: cls._instance = cls()
            return cls._instance

    def start(self):
        if self._running: return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        while self._loop is None: time.sleep(0.01)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try: self._loop.run_forever()
        finally:
            self._loop.close()
            self._loop = None

    def run_coroutine(self, coro, task_id: str = "") -> str:
        if not self._running: self.start()
        if not task_id: task_id = f"async_{id(coro):x}"
        async def _wrapper():
            try:
                result = await coro
                QMetaObject.invokeMethod(self, "_emit_result", Qt.QueuedConnection,
                    Q_ARG(str, task_id), Q_ARG(object, result))
            except Exception as e:
                QMetaObject.invokeMethod(self, "_emit_error", Qt.QueuedConnection,
                    Q_ARG(str, task_id), Q_ARG(str, f"{e}"))
        asyncio.run_coroutine_threadsafe(_wrapper(), self._loop)
        return task_id

    @Slot(str, object)
    def _emit_result(self, task_id, result):
        self.task_completed.emit(task_id, result)

    @Slot(str, str)
    def _emit_error(self, task_id, error):
        self.task_failed.emit(task_id, error)

    def shutdown(self):
        if self._loop and self._running:
            self._running = False
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread: self._thread.join(timeout=2.0)

class ThreadSafeLogger(QObject):
    message_logged = Signal(str, str)
    _instance = None
    _lock = threading.Lock()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: queue.Queue = queue.Queue()
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._flush)
        self._timer.start()

    @classmethod
    def instance(cls):
        with cls._lock:
            if cls._instance is None: cls._instance = cls()
            return cls._instance

    def log(self, msg: str, level: str = "info"):
        self._queue.put((level, msg))

    def info(self, m): self.log(m, "info")
    def success(self, m): self.log(m, "success")
    def warning(self, m): self.log(m, "warning")
    def error(self, m): self.log(m, "error")

    def _flush(self):
        try:
            while True:
                level, msg = self._queue.get_nowait()
                self.message_logged.emit(level, msg)
        except queue.Empty: pass

def log_info(m): ThreadSafeLogger.instance().info(m)
def log_success(m): ThreadSafeLogger.instance().success(m)
def log_warning(m): ThreadSafeLogger.instance().warning(m)
def log_error(m): ThreadSafeLogger.instance().error(m)

def shutdown_threading():
    AsyncBridge.instance().shutdown()

# =============================================================================
# SECTION 2: STATE & PERSISTENCE (AutoSave, Templates, History, Recent Projects)
# =============================================================================

class AutoSaveManager(QObject):
    saved = Signal(str, str)
    _instance = None

    def __init__(self, interval_ms: int = 30000, parent=None):
        super().__init__(parent)
        self._interval = interval_ms
        self._documents: Dict[str, str] = {}
        self._dirty: Dict[str, bool] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._save_all)
        self._save_dir = os.path.join(os.path.expanduser("~"), ".ai_presentation_studio", "drafts")
        os.makedirs(self._save_dir, exist_ok=True)

    @classmethod
    def instance(cls):
        if cls._instance is None: cls._instance = cls()
        return cls._instance

    def start(self): self._timer.start()

    def register(self, doc_id: str, content: str):
        self._documents[doc_id] = content
        self._dirty[doc_id] = True

    def mark_clean(self, doc_id: str):
        self._dirty[doc_id] = False

    def _save_all(self):
        for doc_id, content in self._documents.items():
            if self._dirty.get(doc_id, False):
                try:
                    path = os.path.join(self._save_dir, f"{doc_id}.draft")
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(content)
                    self._dirty[doc_id] = False
                except Exception as e:
                    log_error(f"Auto-save failed: {e}")

    def shutdown(self):
        self._timer.stop()
        self._save_all()

@dataclass
class PromptTemplate:
    id: str
    name: str
    category: str
    topic: str
    style: str
    slide_count: int
    tone: str
    audience: str
    extra: str
    created_at: str
    use_count: int = 0

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

class TemplateLibrary:
    def __init__(self, path: str = None):
        self.path = path or os.path.join(os.path.expanduser("~"), ".ai_presentation_studio", "templates.json")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.templates: List[PromptTemplate] = []
        self._load()
        if not self.templates:
            self._seed_defaults()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.templates = [PromptTemplate.from_dict(d) for d in json.load(f)]
            except: self.templates = []

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump([t.to_dict() for t in self.templates], f, indent=2)

    def _seed_defaults(self):
        self.templates = [
            PromptTemplate("default_video_essay", "Video Essay (Provocative)", "video_essay",
                "", "video_essay", 9, "provocative, analytical, engaging",
                "YouTube viewers interested in deep analysis",
                "Use data and evidence. Address counterarguments fairly.",
                datetime.now().isoformat()),
            PromptTemplate("default_tutorial", "Tutorial (Step-by-Step)", "tutorial",
                "", "tutorial", 7, "educational, clear, encouraging",
                "Beginners learning the topic",
                "Include practical examples. End with actionable next steps.",
                datetime.now().isoformat()),
            PromptTemplate("default_debate", "Debate (Balanced)", "debate",
                "", "debate", 11, "balanced, fair, evidence-based",
                "Viewers seeking nuanced understanding",
                "Present both sides equally. Cite sources.",
                datetime.now().isoformat()),
        ]
        self._save()

    def add(self, t): self.templates.append(t); self._save()
    def remove(self, tid):
        self.templates = [t for t in self.templates if t.id != tid]; self._save()
    def increment_use(self, tid):
        for t in self.templates:
            if t.id == tid: t.use_count += 1; break
        self._save()
    def list_all(self): return sorted(self.templates, key=lambda t: (-t.use_count, t.name))

class RecentProjects:
    def __init__(self, path: str = None, max_items: int = 20):
        self.path = path or os.path.join(os.path.expanduser("~"), ".ai_presentation_studio", "recent.json")
        self.max_items = max_items
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.items: List[Dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.items = json.load(f)
            except: self.items = []

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.items, f, indent=2)

    def add(self, workspace: str, topic: str = "", slide_count: int = 0):
        self.items = [i for i in self.items if i.get("workspace") != workspace]
        self.items.insert(0, {
            "workspace": workspace, "topic": topic, "slide_count": slide_count,
            "opened_at": datetime.now().isoformat(),
        })
        self.items = self.items[:self.max_items]
        self._save()

    def remove(self, workspace):
        self.items = [i for i in self.items if i.get("workspace") != workspace]
        self._save()

    def list_all(self): return self.items

@dataclass
class WorkflowRun:
    id: str
    topic: str
    workspace: str
    created_at: str
    status: str = "pending"
    prompt: str = ""
    script: str = ""
    execution_log: str = ""
    validation_summary: str = ""
    versions: List[Dict] = field(default_factory=list)

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, data): return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

class WorkflowHistory:
    def __init__(self, path: str = None):
        self.path = path or os.path.join(os.path.expanduser("~"), ".ai_presentation_studio", "history.json")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.runs: Dict[str, WorkflowRun] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.runs = {k: WorkflowRun.from_dict(v) for k, v in json.load(f).items()}
            except: self.runs = {}

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({k: v.to_dict() for k, v in self.runs.items()}, f, indent=2)

    def create_run(self, topic: str, workspace: str) -> WorkflowRun:
        run = WorkflowRun(id=f"run_{int(time.time())}_{os.urandom(4).hex()}", topic=topic, workspace=workspace, created_at=datetime.now().isoformat())
        self.runs[run.id] = run
        self._save()
        return run

    def list_runs(self) -> List[WorkflowRun]: return sorted(self.runs.values(), key=lambda r: r.created_at, reverse=True)
    def load_run(self, run_id: str) -> Optional[WorkflowRun]: return self.runs.get(run_id)
    def delete_run(self, run_id: str):
        if run_id in self.runs: del self.runs[run_id]; self._save()

    def save_prompt(self, run: WorkflowRun, prompt: str): run.prompt = prompt; self._save()
    def save_script(self, run: WorkflowRun, script: str): run.script = script; self._save()
    def save_validation(self, run: WorkflowRun, summary: str): run.validation_summary = summary; self._save()
    def save_log(self, run: WorkflowRun, log: str): run.execution_log = log; self._save()
    def update_status(self, run: WorkflowRun, status: str, exit_code: int = 0):
        run.status = status
        if status == "failed": run.execution_log += f"\n[FAILED] Exit code: {exit_code}"
        self._save()
    def add_version(self, run: WorkflowRun, script: str, note: str):
        run.versions.append({"timestamp": datetime.now().isoformat(), "note": note, "script_length": len(script)})
        self._save()

# =============================================================================
# SECTION 3: AI & PROMPT ENGINEERING (Configs, Generators, Error Recovery)
# =============================================================================

@dataclass
class PromptConfig:
    topic: str
    style: str = "video_essay"
    slide_count: int = 9
    tone: str = "provocative, analytical, engaging"
    audience: str = "YouTube viewers"
    extra: str = ""
    output_format: str = "bash"
    project_name: str = ""

BASH_SCRIPT_TEMPLATE = """You are an expert presentation engineer. Produce a SINGLE bash script that creates an entire presentation project.
PROJECT TOPIC: {topic}
STYLE: {style}
SLIDE COUNT: {slide_count}
TONE: {tone}
AUDIENCE: {audience}
PROJECT NAME: {project_name}
EXTRA: {extra}

Produce ONLY a bash script (no markdown fences) that:
1. Creates: {project_name}/slides/, {project_name}/scripts/, {project_name}/youtube/
2. Each HTML slide: 1920x1080, dark theme, accent #ff3b3b/#ffcc00, bold typography
3. Each script: 150-300 words narration with [PAUSE]/[EMPHASIS] markers
4. YouTube metadata: description, tags, chapters, pinned comment
5. thumbnail.html: 1280x720 eye-catching design

Use heredocs. Idempotent. Progress echo "[1/N] Creating...".
End with: echo "✅ Project complete: {project_name}"
NO sudo, rm -rf, curl|bash. All writes relative to project root.
Generate the complete bash script NOW."""

class PromptGenerator:
    @staticmethod
    def generate_bash_prompt(config: PromptConfig) -> str:
        if not config.project_name:
            config.project_name = PromptGenerator._make_slug(config.topic)
        return BASH_SCRIPT_TEMPLATE.format(
            topic=config.topic, style=config.style,
            slide_count=config.slide_count, tone=config.tone,
            audience=config.audience, project_name=config.project_name,
            extra=config.extra or "None",
        )

    @staticmethod
    def generate_error_recovery_prompt(error_output: str, script: str, workspace: str) -> str:
        return f"""A bash script failed. Analyze and produce a FIXED version.
WORKSPACE: {workspace}
ORIGINAL SCRIPT:
```bash
{script}
```
ERROR OUTPUT:
```
{error_output}
```
Output ONLY the corrected bash script with comment: # FIXED: <description>"""

    @staticmethod
    def _make_slug(topic: str) -> str:
        try:
            from slugify import slugify
            return slugify(topic, max_length=50)
        except ImportError:
            slug = re.sub(r"[^\w\s-]", "", topic.lower())
            return re.sub(r"[-\s]+", "-", slug).strip("-")[:50] or "presentation"

class ErrorRecovery:
    @staticmethod
    def generate_fix_prompt(script: str, error_log: str, exit_code: int, workspace: str) -> str:
        return f"""A bash script failed with exit code {exit_code}. Analyze and produce a FIXED version.
WORKSPACE: {workspace}
ORIGINAL SCRIPT:
```bash
{script}
```
ERROR OUTPUT:
```
{error_log}
```
Output ONLY the corrected bash script. Add a comment at the top: # FIXED: <brief description of the fix>."""

class InlineAIEditor:
    @staticmethod
    def generate_edit_prompt(selection: str, instruction: str, context_before: str = "", context_after: str = "") -> str:
        return f"""You are an expert editor. Edit the following SELECTED text based on the INSTRUCTION.
Maintain the surrounding context and formatting. Output ONLY the replacement text, no markdown fences.

CONTEXT BEFORE: {context_before[-200:]}
SELECTED TEXT: {selection}
CONTEXT AFTER: {context_after[:200]}
INSTRUCTION: {instruction}
REPLACEMENT TEXT:"""

# =============================================================================
# SECTION 4: SCRIPT PROCESSING (Validation & Execution)
# =============================================================================

@dataclass
class ValidationIssue:
    severity: str
    category: str
    line: int
    message: str
    snippet: str = ""
    suggestion: str = ""

@dataclass
class ValidationResult:
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    detected_commands: List[str] = field(default_factory=list)
    estimated_files_created: int = 0

    @property
    def errors(self): return [i for i in self.issues if i.severity == "error"]
    @property
    def warnings(self): return [i for i in self.issues if i.severity == "warning"]
    @property
    def summary(self):
        e, w = len(self.errors), len(self.warnings)
        status = "❌ REJECTED" if e > 0 else ("⚠️  APPROVED WITH WARNINGS" if w > 0 else "✅ APPROVED")
        return f"{status} — {e} errors, {w} warnings"

DANGEROUS_PATTERNS = [
    (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f)\s+/\s*$", "Recursive delete of root", "error", "Remove the '/'"),
    (r"\bsudo\b", "Privilege escalation", "error", "Remove sudo"),
    (r"\bcurl\b.*\|\s*(ba)?sh", "Pipe curl to shell (RCE)", "error", "Download first, then execute"),
    (r"\bwget\b.*\|\s*(ba)?sh", "Pipe wget to shell (RCE)", "error", "Download first, then execute"),
    (r"\bmkfs\b", "Format filesystem", "error", "Remove this command"),
    (r"\b(shutdown|reboot|halt|poweroff)\b", "System power control", "error", "Remove"),
    (r"\bchmod\s+(-R\s+)?777\b", "Insecure permissions", "warning", "Use 755/644"),
    (r"\bchmod\s+\+s\b", "Set SUID/SGID bit", "error", "Remove +s"),
]

class ScriptValidator:
    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)

    def validate(self, script: str) -> ValidationResult:
        result = ValidationResult(valid=True)
        self._check_syntax(script, result)
        self._check_dangerous(script, result)
        self._check_paths(script, result)
        self._check_workspace(script, result)
        self._check_deps(script, result)
        self._collect_stats(script, result)
        result.valid = len(result.errors) == 0
        return result

    def _check_syntax(self, script, result):
        bash = shutil.which("bash")
        if not bash: return
        try:
            proc = subprocess.run([bash, "-n"], input=script,
                capture_output=True, text=True, timeout=5)
            if proc.returncode != 0:
                for line in proc.stderr.split("\n"):
                    m = re.search(r"line\s+(\d+):\s*(.+)", line)
                    if m:
                        result.issues.append(ValidationIssue(
                            "error", "syntax", int(m.group(1)), m.group(2),
                            suggestion="Check unclosed quotes or missing semicolons"))
        except Exception as e:
            result.issues.append(ValidationIssue("warning", "syntax", 0, f"Syntax check failed: {e}"))

    def _check_dangerous(self, script, result):
        for ln, line in enumerate(script.split("\n"), 1):
            if line.strip().startswith("#"): continue
            for pattern, desc, sev, suggestion in DANGEROUS_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    result.issues.append(ValidationIssue(
                        sev, "security", ln, f"🚨 {desc}", line.strip()[:100], suggestion))

    def _check_paths(self, script, result):
        sensitive = [
            (r"/etc/(passwd|shadow|sudoers)", "Sensitive system file", "error", "Don't access"),
            (r"/var/log", "System log access", "warning", "Use workspace-relative paths"),
            (r"/proc/", "Proc filesystem", "warning", "Avoid /proc access"),
        ]
        for ln, line in enumerate(script.split("\n"), 1):
            if line.strip().startswith("#"): continue
            for pattern, desc, sev, suggestion in sensitive:
                if re.search(pattern, line):
                    result.issues.append(ValidationIssue(
                        sev, "path", ln, desc, line.strip()[:100], suggestion))

    def _check_workspace(self, script, result):
        abs_pattern = r"(?:>\s*|tee\s+|cp\s+.*\s+|mv\s+.*\s+)(/[^\s;|&]+)"
        for ln, line in enumerate(script.split("\n"), 1):
            if line.strip().startswith("#"): continue
            for m in re.finditer(abs_pattern, line):
                path = m.group(1)
                try:
                    resolved = os.path.abspath(path)
                    if not resolved.startswith(self.workspace):
                        result.issues.append(ValidationIssue(
                            "error", "path", ln, f"Write outside workspace: {path}",
                            line.strip()[:100], f"Write inside {self.workspace}"))
                except: pass

    def _check_deps(self, script, result):
        cmd_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_-]*)\s"
        builtins = {"echo", "cd", "export", "if", "then", "else", "fi", "for", "do",
            "done", "while", "case", "esac", "function", "return", "exit",
            "set", "cat", "mkdir", "rm", "cp", "mv", "ls", "pwd", "printf"}
        commands = set()
        for m in re.finditer(cmd_pattern, script):
            cmd = m.group(1)
            if cmd not in builtins: commands.add(cmd)
        result.detected_commands = sorted(commands)
        for cmd in commands:
            if not shutil.which(cmd):
                hint = {"curl": "apt install curl", "wget": "apt install wget",
                    "jq": "apt install jq"}.get(cmd, f"Install {cmd}")
                result.issues.append(ValidationIssue("warning", "dependency", 0,
                    f"Command not found: {cmd}", suggestion=hint))

    def _collect_stats(self, script, result):
        heredoc_count = len(re.findall(r"<<\s*['\"]?\w+['\"]?", script))
        redirect_count = len(re.findall(r">\s*[^\s>]", script))
        result.estimated_files_created = max(heredoc_count, redirect_count)

class ScriptExecutor(QObject):
    output_line = Signal(str)
    progress = Signal(int, str)
    started = Signal()
    finished = Signal(int)
    error = Signal(str)
    file_created = Signal(str)

    def __init__(self, workspace: str, parent=None):
        super().__init__(parent)
        self.workspace = os.path.abspath(workspace)
        self.process: Optional[QProcess] = None
        self._buffer = ""
        self._output_lines: list = []
        self._start_time = 0.0
        self._cancellation = CancellationToken()

    def execute(self, script: str, timeout_seconds: int = 600) -> bool:
        if self.process and self.process.state() != QProcess.NotRunning:
            self.error.emit("Another script is running")
            return False

        os.makedirs(self.workspace, exist_ok=True)
        script_path = os.path.join(self.workspace, ".run_script.sh")
        with open(script_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("#!/usr/bin/env bash\n")
            f.write(f"cd {self.workspace}\n")
            f.write("set -e\n")
            f.write(script)
        try: os.chmod(script_path, 0o755)
        except: pass

        self._output_lines = []
        self._buffer = ""
        self._start_time = time.time()
        self._cancellation = CancellationToken()

        self.process = QProcess(self)
        self.process.setWorkingDirectory(self.workspace)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        env = self.process.processEnvironment()
        env.insert("WORKSPACE", self.workspace)
        env.insert("PYTHONUNBUFFERED", "1")
        self.process.setProcessEnvironment(env)

        self.process.readyReadStandardOutput.connect(self._on_output)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_error)

        self.process.start("bash", [script_path])
        if not self.process.waitForStarted(5000):
            self.error.emit("Failed to start bash")
            return False

        self.started.emit()
        self.output_line.emit(f"▶ Started in: {self.workspace}")
        self._start_monitor(timeout_seconds)
        return True

    def _start_monitor(self, timeout):
        def _check():
            if not self.process or self.process.state() == QProcess.NotRunning: return
            if self._cancellation.is_cancelled:
                self.process.kill()
                self.output_line.emit("⛔ Script cancelled")
                return
            if time.time() - self._start_time > timeout:
                self.process.kill()
                self.output_line.emit(f"⏱️  Timed out after {timeout}s")
                return
            QTimer.singleShot(500, _check)
        QTimer.singleShot(500, _check)

    def stop(self):
        self._cancellation.cancel()
        if self.process and self.process.state() != QProcess.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(2000):
                self.process.kill()
                self.process.waitForFinished(1000)
            self.output_line.emit("⛔ Script stopped")

    def is_running(self):
        return self.process is not None and self.process.state() != QProcess.NotRunning

    def get_full_output(self): return "\n".join(self._output_lines)
    def get_elapsed_time(self): return time.time() - self._start_time if self._start_time else 0

    def _on_output(self):
        if not self.process: return
        data = self.process.readAllStandardOutput()
        try: text = bytes(data).decode("utf-8", errors="replace")
        except: text = str(data)
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._process_line(line)

    def _process_line(self, line: str):
        self._output_lines.append(line)
        if len(self._output_lines) > 5000:
            self._output_lines = self._output_lines[-5000:]
        self.output_line.emit(line)
        m = re.search(r"\[(\d+)/(\d+)\]", line)
        if m:
            pct = int((int(m.group(1)) / int(m.group(2))) * 100)
            self.progress.emit(pct, line)
        if "✅" in line or "complete" in line.lower():
            self.progress.emit(100, line)
        fm = re.search(r"(?:created|wrote|saved):\s*([^\s]+)", line, re.IGNORECASE)
        if fm:
            path = fm.group(1)
            if not os.path.isabs(path): path = os.path.join(self.workspace, path)
            self.file_created.emit(path)

    def _on_finished(self, exit_code, exit_status=None):
        if self._buffer:
            self._process_line(self._buffer)
            self._buffer = ""
        elapsed = self.get_elapsed_time()
        if exit_code == 0:
            self.output_line.emit(f"\n✅ Completed ({elapsed:.1f}s)")
        else:
            self.output_line.emit(f"\n❌ Failed with exit {exit_code} ({elapsed:.1f}s)")
        self.finished.emit(exit_code)

    def _on_error(self, error):
        msgs = {QProcess.FailedToStart: "Failed to start",
                QProcess.Crashed: "Process crashed",
                QProcess.Timedout: "Timed out"}
        self.error.emit(msgs.get(error, f"Error: {error}"))

# =============================================================================
# SECTION 5: BACKGROUND WORKERS (File System, TTS, Export)
# =============================================================================

class FileSystemScanWorker(WorkerThread):
    def __init__(self, workspace: str, parent=None):
        super().__init__("fs_scan", parent)
        self.workspace = workspace

    def do_work(self) -> dict:
        result = {
            "total_files": 0, "total_size": 0,
            "by_category": {"slides": [], "scripts": [], "youtube": [], "images": [], "audio": [], "video": [], "other": []}
        }
        if not os.path.isdir(self.workspace): return result
        
        for root, _, files in os.walk(self.workspace):
            for file in files:
                self.check_cancelled()
                path = os.path.join(root, file)
                try:
                    size = os.path.getsize(path)
                    ext = os.path.splitext(file)[1].lower()
                    entry = {"name": file, "path": path, "ext": ext, "size": size, "rel_path": os.path.relpath(path, self.workspace)}
                    result["total_files"] += 1
                    result["total_size"] += size
                    
                    if ext in [".html", ".htm"]: result["by_category"]["slides"].append(entry)
                    elif ext in [".txt", ".md"]: result["by_category"]["scripts"].append(entry)
                    elif ext in [".json"]: result["by_category"]["youtube"].append(entry)
                    elif ext in [".png", ".jpg", ".jpeg", ".svg", ".webp"]: result["by_category"]["images"].append(entry)
                    elif ext in [".mp3", ".wav", ".ogg"]: result["by_category"]["audio"].append(entry)
                    elif ext in [".mp4", ".webm", ".mov"]: result["by_category"]["video"].append(entry)
                    else: result["by_category"]["other"].append(entry)
                except Exception: pass
        return result

class TTSPreviewWorker(WorkerThread):
    def __init__(self, text: str, voice: str = "en-US-GuyNeural", rate: str = "+0%", parent=None):
        super().__init__("tts_preview", parent)
        self.text = text
        self.voice = voice
        self.rate = rate

    def do_work(self) -> str:
        try:
            import edge_tts
            async def _generate():
                communicate = edge_tts.Communicate(self.text, self.voice, rate=self.rate)
                fd, path = tempfile.mkstemp(suffix=".mp3")
                os.close(fd)
                await communicate.save(path)
                return path
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try: return loop.run_until_complete(_generate())
            finally: loop.close()
        except ImportError:
            fd, path = tempfile.mkstemp(suffix=".txt")
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(f"[TTS MOCK] Voice: {self.voice}, Rate: {self.rate}\n\n{self.text}")
            return path
        except Exception as e:
            raise Exception(f"TTS generation failed: {e}")

class ExportPresentationWorker(WorkerThread):
    def __init__(self, workspace: str, format: str, output_path: str, parent=None):
        super().__init__("export_pres", parent)
        self.workspace = workspace
        self.format = format
        self.output_path = os.path.abspath(output_path)

    def do_work(self) -> str:
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        if self.format == "html": self._export_html()
        elif self.format == "pdf": self._export_pdf()
        elif self.format == "pptx": self._export_pptx()
        else: raise ValueError(f"Unsupported format: {self.format}")
        return self.output_path

    def _export_html(self):
        self.report_progress(10, "Gathering slides...")
        slides_dir = os.path.join(self.workspace, "slides")
        if not os.path.isdir(slides_dir): raise FileNotFoundError("No slides directory found.")
        html_files = sorted([f for f in os.listdir(slides_dir) if f.endswith(".html")])
        if not html_files: raise FileNotFoundError("No HTML slides found.")
            
        self.report_progress(30, "Combining HTML...")
        combined = ["<!DOCTYPE html>", "<html><head><meta charset='utf-8'><title>Combined Presentation</title>",
                    "<style>body{background:#1e1e1e;color:#fff;font-family:sans-serif;margin:0;padding:0;}",
                    ".slide{width:100vw;height:100vh;display:flex;align-items:center;justify-content:center;border-bottom:1px solid #333;}</style>",
                    "</head><body>"]
        for i, fname in enumerate(html_files):
            self.report_progress(30 + int((i / len(html_files)) * 60), f"Processing {fname}...")
            with open(os.path.join(slides_dir, fname), "r", encoding="utf-8") as f:
                content = f.read()
                body_match = re.search(r"<body[^>]*>(.*?)</body>", content, re.IGNORECASE | re.DOTALL)
                combined.append(f"<div class='slide' id='slide-{i+1}'>{body_match.group(1) if body_match else content}</div>")
        combined.append("</body></html>")
        with open(self.output_path, "w", encoding="utf-8") as f: f.write("\n".join(combined))
        self.report_progress(100, "HTML export complete.")

    def _export_pdf(self):
        self.report_progress(10, "Preparing PDF export...")
        try:
            from weasyprint import HTML
            self.report_progress(30, "Rendering to PDF...")
            HTML(string=f"<h1>PDF Export of {self.workspace}</h1><p>Generated by AI Presentation Studio</p>").write_pdf(self.output_path)
        except ImportError:
            fallback = self.output_path.replace(".pdf", ".txt")
            with open(fallback, "w", encoding="utf-8") as f:
                f.write("PDF export requires 'weasyprint'. Install via: pip install weasyprint")
            self.output_path = fallback
        self.report_progress(100, "PDF export complete.")

    def _export_pptx(self):
        self.report_progress(10, "Preparing PPTX export...")
        try:
            from pptx import Presentation
            slides_dir = os.path.join(self.workspace, "slides")
            html_files = sorted([f for f in os.listdir(slides_dir) if f.endswith(".html")]) if os.path.isdir(slides_dir) else []
            prs = Presentation()
            for i, fname in enumerate(html_files):
                self.report_progress(30 + int((i / max(1, len(html_files))) * 60), f"Adding slide {fname}...")
                with open(os.path.join(slides_dir, fname), "r", encoding="utf-8") as f:
                    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", f.read())).strip()
                slide = prs.slides.add_slide(prs.slide_layouts[1])
                slide.shapes.title.text = f"Slide {i+1}"
                slide.shapes.placeholders[1].text_frame.text = text[:1000]
            prs.save(self.output_path)
        except ImportError:
            fallback = self.output_path.replace(".pptx", ".txt")
            with open(fallback, "w", encoding="utf-8") as f:
                f.write("PPTX export requires 'python-pptx'. Install via: pip install python-pptx")
            self.output_path = fallback
        self.report_progress(100, "PPTX export complete.")

# =============================================================================
# SECTION 6: TEXT & CONTENT UTILITIES (Snippets, Emmet, Spell Check, SEO, ANSI)
# =============================================================================

@dataclass
class Snippet:
    trigger: str
    description: str
    body: str

class SnippetManager:
    def __init__(self, path: str = None):
        self.path = path or os.path.join(os.path.expanduser("~"), ".ai_presentation_studio", "snippets.json")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.snippets: List[Snippet] = []
        self._load()
        if not self.snippets: self._seed_defaults()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f: self.snippets = [Snippet(**d) for d in json.load(f)]
            except: self.snippets = []

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f: json.dump([asdict(s) for s in self.snippets], f, indent=2)

    def _seed_defaults(self):
        self.snippets = [
            Snippet("slide", "Basic HTML Slide", "<div class='slide'>\n  <h1>${1:Title}</h1>\n  <p>${2:Content}</p>\n</div>"),
            Snippet("pause", "TTS Pause", "[PAUSE — ${1:1s}]"),
            Snippet("emphasis", "TTS Emphasis", "[EMPHASIS] ${1:text} [/EMPHASIS]"),
        ]
        self._save()

    def get_matches(self, prefix: str) -> List[Snippet]: return [s for s in self.snippets if s.trigger.startswith(prefix.lower())]
    def expand(self, trigger: str) -> Optional[str]:
        for s in self.snippets:
            if s.trigger == trigger.lower(): return s.body
        return None

class EmmetExpander:
    @staticmethod
    def expand(emmet_str: str) -> str:
        if not emmet_str: return ""
        match = re.match(r"(\w+)\*(\d+)", emmet_str)
        if match:
            tag, count = match.groups()
            return "\n".join([f"<{tag}></{tag}>" for _ in range(int(count))])
        if ">" in emmet_str:
            parts = emmet_str.split(">")
            indent, result = 0, []
            for part in parts:
                result.append("  " * indent + f"<{part}>")
                indent += 1
            for part in reversed(parts):
                indent -= 1
                result.append("  " * indent + f"</{part}>")
            return "\n".join(result)
        return f"<{emmet_str}></{emmet_str}>"

class SpellChecker:
    def __init__(self):
        self._checker = None
        try:
            from spellchecker import SpellChecker
            self._checker = SpellChecker()
        except ImportError: pass

    def check(self, text: str) -> List[Dict]:
        issues = []
        if not self._checker: return issues
        for i, word in enumerate(text.split()):
            clean_word = re.sub(r"[^\w']", "", word)
            if clean_word and self._checker.unknown([clean_word]):
                issues.append({"word": clean_word, "suggestions": list(self._checker.candidates(clean_word)), "index": i})
        return issues

class SEOAnalyzer:
    @staticmethod
    def analyze(html_content: str) -> Dict:
        issues, score = [], 100
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
        if not title_match:
            issues.append({"type": "error", "msg": "Missing <title> tag"}); score -= 20
        elif len(title_match.group(1).strip()) > 60:
            issues.append({"type": "warning", "msg": "Title is too long (>60 chars)"}); score -= 5
            
        h1_count = len(re.findall(r"<h1[^>]*>.*?</h1>", html_content, re.IGNORECASE | re.DOTALL))
        if h1_count == 0: issues.append({"type": "error", "msg": "Missing <h1> tag"}); score -= 15
        elif h1_count > 1: issues.append({"type": "warning", "msg": "Multiple <h1> tags found"}); score -= 5
            
        for img in re.findall(r"<img[^>]*>", html_content, re.IGNORECASE):
            if "alt=" not in img.lower(): issues.append({"type": "warning", "msg": "Image missing 'alt' attribute"}); score -= 5
        return {"score": max(0, score), "issues": issues}

class AnsiParser:
    ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    
    @staticmethod
    def strip(text: str) -> str: return AnsiParser.ANSI_ESCAPE.sub('', text)
        
    @staticmethod
    def to_html(text: str) -> str:
        text = html.escape(text)
        text = re.sub(r'\x1b\[31m', '<span style="color:#f48771">', text)
        text = re.sub(r'\x1b\[32m', '<span style="color:#4ec9b0">', text)
        text = re.sub(r'\x1b\[33m', '<span style="color:#dcdcaa">', text)
        text = re.sub(r'\x1b\[34m', '<span style="color:#75beff">', text)
        text = re.sub(r'\x1b\[0m', '</span>', text)
        return AnsiParser.ANSI_ESCAPE.sub('', text)

# =============================================================================
# SECTION 7: PROJECT SEARCH & INDEXING
# =============================================================================

class ProjectSearchIndex:
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.index: List[Dict] = []
        self._build_index()

    def _build_index(self):
        self.index = []
        if not os.path.isdir(self.workspace): return
        for root, _, files in os.walk(self.workspace):
            for file in files:
                if file.endswith((".html", ".txt", ".md", ".json", ".sh")):
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            self.index.append({"path": os.path.relpath(path, self.workspace), "content": f.read().lower()})
                    except: pass

    def search(self, query: str) -> List[Dict]:
        query = query.lower()
        results = []
        for item in self.index:
            if query in item["content"]:
                lines = item["content"].split("\n")
                results.append({"file": item["path"], "matches": [i+1 for i, line in enumerate(lines) if query in line][:5]})
        return results
