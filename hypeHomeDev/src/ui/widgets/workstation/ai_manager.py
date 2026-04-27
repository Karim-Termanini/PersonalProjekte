"""Workstation → AI Tools: Ollama, LM Studio, Open WebUI, GitHub Copilot CLI.

Each AI tool gets a full panel with subsection tabs, mirroring the Services panel pattern.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from core.setup.host_executor import HostExecutor  # noqa: E402
from core.setup.package_installer import PackageInstaller  # noqa: E402
from core.setup.systemd_manager import SystemdManager  # noqa: E402
from ui.utility_feedback import emit_utility_toast  # noqa: E402
from ui.widgets.workstation.docker_manager import (  # noqa: E402
    docker_container_start,
    docker_container_status,
    docker_container_stop,
)
from ui.widgets.workstation.service_manager import (  # noqa: E402
    ServiceFactoryRow,
    _load_service_catalog,
)
from ui.widgets.workstation.subsection_bar import WorkstationSubsectionBar  # noqa: E402
from ui.widgets.workstation.workstation_utils import (  # noqa: E402
    PACKAGE_MANAGER,
    _add_row,
    _add_tty_row,
    _bg,
    _distro_cmd,
    _distro_remove,
    _run_check,
    _run_cmd,
)

log = logging.getLogger(__name__)

OPEN_WEBUI_CONTAINER_NAME = "open-webui"
_AI_DEPS_PATH = Path(__file__).with_name("data") / "ai_dependencies.json"
_ai_deps_cache: dict[str, Any] | None = None


def _load_ai_dependencies() -> dict[str, Any]:
    global _ai_deps_cache
    if _ai_deps_cache is not None:
        return _ai_deps_cache
    try:
        raw = json.loads(_AI_DEPS_PATH.read_text(encoding="utf-8"))
        _ai_deps_cache = raw if isinstance(raw, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        log.exception("Failed to load AI dependency catalog: %s", _AI_DEPS_PATH)
        _ai_deps_cache = {}
    return _ai_deps_cache


def _ai_stack_command(stack_key: str) -> str:
    stacks = _load_ai_dependencies().get("stacks") or {}
    row = stacks.get(stack_key) or {}
    if isinstance(row, dict):
        return str(
            row.get(PACKAGE_MANAGER)
            or row.get("unknown")
            or f"# {stack_key}: add entry to data/ai_dependencies.json",
        )
    return f"# {stack_key}: invalid catalog entry"


def _ai_stack_check_cmd(stack_key: str) -> str | None:
    checks = _load_ai_dependencies().get("checks") or {}
    raw = checks.get(stack_key)
    return str(raw) if raw else None


class _LMStudioHubStatusRow(Adw.ActionRow):
    """LM Studio / lms summary line for the AI hub."""

    def __init__(self) -> None:
        super().__init__(title="LM Studio", subtitle="checking…")
        btn = Gtk.Button(icon_name="view-refresh-symbolic")
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect("clicked", lambda _b: self.refresh())
        self.add_suffix(btn)
        GLib.idle_add(self.refresh)

    def refresh(self, *_a: Any) -> None:
        def _work() -> None:
            cli_ok, _c, _e = _run_check("command -v lms >/dev/null 2>&1")
            if not cli_ok:
                GLib.idle_add(
                    self.set_subtitle,
                    "CLI (lms) not found — install from the LM Studio tab.",
                )
                return
            ok, out, _e = _run_check("lms server status 2>/dev/null | head -1")
            line = (out or "").strip().split("\n")[0] if ok else "server status unknown"
            GLib.idle_add(self.set_subtitle, line or "lms present")

        _bg(_work)


class _OpenWebUIContainerRow(Adw.ActionRow):
    """Start/stop an existing Open WebUI container (same name as Install tab recipes)."""

    def __init__(self) -> None:
        super().__init__(
            title="Open WebUI (Docker)",
            subtitle="checking…",
        )
        self._busy = False
        self._updating_switch = False
        self._toggle = Gtk.Switch()
        self._toggle.set_valign(Gtk.Align.CENTER)
        self._toggle.set_tooltip_text("Start or stop the named container (create it from the Open WebUI tab).")
        self._toggle.connect("notify::active", self._on_toggle)
        btn = Gtk.Button(icon_name="view-refresh-symbolic")
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect("clicked", lambda _b: self.refresh())
        self.add_suffix(btn)
        self.add_suffix(self._toggle)
        GLib.idle_add(self.refresh)

    def refresh(self, *_a: Any) -> None:
        def _work() -> None:
            st = docker_container_status(OPEN_WEBUI_CONTAINER_NAME)
            GLib.idle_add(self._apply_status, st)

        _bg(_work)

    def _apply_status(self, st: str) -> bool:
        if not st:
            self.set_subtitle("no container — use Open WebUI → Install (docker run …)")
            self._updating_switch = True
            self._toggle.set_active(False)
            self._updating_switch = False
            self._toggle.set_sensitive(False)
            return False  # GLib idle callback
        self._toggle.set_sensitive(True)
        running = st == "running"
        self._updating_switch = True
        self._toggle.set_active(running)
        self._updating_switch = False
        self.set_subtitle(st)
        return False

    def _on_toggle(self, sw: Gtk.Switch, _pspec: Any) -> None:
        if self._busy or self._updating_switch:
            return
        want = sw.get_active()
        self._busy = True
        sw.set_sensitive(False)

        def _work() -> None:
            ok = (
                docker_container_start(OPEN_WEBUI_CONTAINER_NAME)
                if want
                else docker_container_stop(OPEN_WEBUI_CONTAINER_NAME)
            )
            GLib.idle_add(self._after_toggle, ok)

        _bg(_work)

    def _after_toggle(self, ok: bool) -> bool:
        self._busy = False
        self._toggle.set_sensitive(True)
        emit_utility_toast(
            "Container updated." if ok else "Docker action failed (create the container first).",
            "info" if ok else "error",
        )
        self.refresh()
        return False


class _CopilotHubRow(Adw.ActionRow):
    """Minimal Copilot / gh status for the AI hub."""

    def __init__(self) -> None:
        super().__init__(title="GitHub Copilot CLI", subtitle="checking…")
        btn = Gtk.Button(icon_name="view-refresh-symbolic")
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect("clicked", lambda _b: self.refresh())
        self.add_suffix(btn)
        GLib.idle_add(self.refresh)

    def refresh(self, *_a: Any) -> None:
        def _work() -> None:
            ok, out, _e = _run_check("gh --version")
            ver = out.strip().split("\n")[0] if ok else "gh not installed"
            ok2, out2, _e2 = _run_check("gh extension list 2>/dev/null | grep -i copilot || true")
            ext = "copilot ext OK" if ok2 and out2.strip() else "no copilot extension"
            GLib.idle_add(self.set_subtitle, f"{ver} · {ext}")

        _bg(_work)


class WorkstationAIHubPanel(Gtk.Box):
    """Overview of local AI stack: Ollama (systemd), LM Studio, Open WebUI, Copilot hints."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self._executor = HostExecutor()
        self._installer = PackageInstaller(self._executor)
        self._systemd = SystemdManager()
        self._rows: list[Any] = []

        page = Adw.PreferencesPage()
        grp = Adw.PreferencesGroup(
            title="AI Hub",
            description=(
                "Ollama uses D-Bus + PolKit like the Services hub. "
                "Open WebUI toggles only an existing Docker container named "
                f"{OPEN_WEBUI_CONTAINER_NAME!r}."
            ),
        )
        ollama = next((s for s in _load_service_catalog() if str(s.get("id", "")) == "ollama"), None)
        if ollama is not None:
            row = ServiceFactoryRow(
                ollama,
                systemd=self._systemd,
                installer=self._installer,
                executor=self._executor,
            )
            self._rows.append(row)
            grp.add(row)
        else:
            grp.add(
                Adw.ActionRow(
                    title="Ollama",
                    subtitle="Service definition missing from services.json",
                ),
            )

        self._lm = _LMStudioHubStatusRow()
        self._web = _OpenWebUIContainerRow()
        self._cop = _CopilotHubRow()
        for r in (self._lm, self._web, self._cop):
            self._rows.append(r)
            grp.add(r)

        page.add(grp)
        page.set_vexpand(False)

        scroll = Gtk.ScrolledWindow(
            hexpand=True,
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        try:
            scroll.set_overlay_scrolling(False)
        except (AttributeError, TypeError):
            pass
        scroll.set_child(page)
        self.append(scroll)

        self._timer_id = GLib.timeout_add_seconds(5, self._refresh_loop)

    def do_unrealize(self) -> None:
        if getattr(self, "_timer_id", 0):
            GLib.source_remove(self._timer_id)
            self._timer_id = 0
        Gtk.Box.do_unrealize(self)

    def _refresh_loop(self) -> bool:
        for row in self._rows:
            ref = getattr(row, "refresh", None)
            if callable(ref):
                ref()
        return True

    def reset_subsections(self) -> None:
        for row in self._rows:
            ref = getattr(row, "refresh", None)
            if callable(ref):
                ref()


# ═══════════════════════════════════════════════════════════════
#  OLLAMA
# ═══════════════════════════════════════════════════════════════


class _OllamaInstallPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        status_grp = Adw.PreferencesGroup(
            title="Status",
            description="Check whether Ollama is installed and its service is running.",
        )
        self._status_row = Adw.ActionRow(title="Ollama", subtitle="Checking…")
        refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh.set_valign(Gtk.Align.CENTER)
        refresh.connect("clicked", lambda _b: self._refresh())
        self._status_row.add_suffix(refresh)
        status_grp.add(self._status_row)

        self._svc_row = Adw.ActionRow(title="ollama service", subtitle="Checking…")
        status_grp.add(self._svc_row)
        self.append(status_grp)

        install = Adw.PreferencesGroup(
            title="Install",
            description="Ollama runs LLMs locally with GPU acceleration. Models stored in ~/.ollama.",
        )
        _add_row(install, "Install (official script)", "curl -fsSL https://ollama.com/install.sh | sh",
                 check_cmd="ollama --version")
        _add_row(install, "Install via snap", "sudo snap install ollama",
                 check_cmd="ollama --version")
        self.append(install)

        nvidia = Adw.PreferencesGroup(
            title="NVIDIA GPU",
            description="Driver/CUDA install lines come from data/ai_dependencies.json (distro-specific).",
        )
        _nv_chk = _ai_stack_check_cmd("nvidia_driver")
        _add_row(
            nvidia,
            "Install driver",
            _ai_stack_command("nvidia_driver"),
            check_cmd=_nv_chk,
        )
        _add_row(nvidia, "Check GPU", "nvidia-smi")
        _cuda_chk = _ai_stack_check_cmd("nvidia_cuda")
        _add_row(
            nvidia,
            "CUDA toolkit",
            _ai_stack_command("nvidia_cuda"),
            check_cmd=_cuda_chk,
        )
        self.append(nvidia)

        amd = Adw.PreferencesGroup(
            title="AMD GPU (ROCm)",
            description="Open-source ROCm stack for AMD GPU acceleration.",
        )
        _rocm_chk = _ai_stack_check_cmd("amd_rocm")
        _add_row(amd, "Install ROCm", _ai_stack_command("amd_rocm"), check_cmd=_rocm_chk)
        _add_row(amd, "Check GPU", "rocm-smi")
        _add_row(amd, "List AMD GPUs", "lspci | grep -i amd | grep -iE 'vga|display'")
        self.append(amd)

        intel = Adw.PreferencesGroup(
            title="Intel GPU",
            description="Intel compute runtime for oneAPI / OpenVINO acceleration.",
        )
        _intel_chk = _ai_stack_check_cmd("intel_gpu")
        _add_row(
            intel,
            "Install compute runtime",
            _ai_stack_command("intel_gpu"),
            check_cmd=_intel_chk,
        )
        _add_row(intel, "Check Intel GPU", "lspci | grep -i intel | grep -iE 'vga|display'")
        _add_row(intel, "Install clinfo", _distro_cmd("clinfo"),
                 check_cmd="which clinfo")
        self.append(intel)

        GLib.idle_add(self._refresh)

    def _refresh(self) -> None:
        def _work() -> None:
            ok, out, _e = _run_cmd(["ollama", "--version"], timeout=5)
            ver = out.strip().split("\n")[0] if ok else "not installed"
            GLib.idle_add(self._status_row.set_subtitle, ver)

            ok2, _o, _e2 = _run_cmd(["systemctl", "is-active", "ollama"], timeout=5)
            svc = "running" if ok2 else "stopped / not found"
            GLib.idle_add(self._svc_row.set_subtitle, svc)

        _bg(_work)


class _OllamaServicePage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        self._executor = HostExecutor()
        self._installer = PackageInstaller(self._executor)
        self._systemd = SystemdManager()

        svc = Adw.PreferencesGroup(
            title="Daemon",
            description="Start/stop/enable/disable via systemd D-Bus + PolKit (same pattern as the Services hub).",
        )
        ollama = next((s for s in _load_service_catalog() if str(s.get("id", "")) == "ollama"), None)
        if ollama is not None:
            svc.add(
                ServiceFactoryRow(
                    ollama,
                    systemd=self._systemd,
                    installer=self._installer,
                    executor=self._executor,
                ),
            )
        else:
            svc.add(
                Adw.ActionRow(
                    title="Ollama",
                    subtitle="Service definition missing from services.json",
                ),
            )
        _add_tty_row(svc, "Service status (terminal)", "systemctl status ollama")
        self.append(svc)

        manual = Adw.PreferencesGroup(
            title="Manual Start",
            description="Run Ollama in foreground (useful for debugging).",
        )
        _add_tty_row(manual, "Serve (foreground)", "ollama serve")
        self.append(manual)

        env_grp = Adw.PreferencesGroup(
            title="Environment Variables",
            description="Configure Ollama behavior via environment.",
        )
        _add_row(env_grp, "Set custom models dir",
                 "sudo systemctl edit ollama --force --full  # add Environment=\"OLLAMA_MODELS=/path/to/models\"")
        _add_row(env_grp, "Set listen address",
                 "sudo systemctl edit ollama --force --full  # add Environment=\"OLLAMA_HOST=0.0.0.0:11434\"")
        _add_row(env_grp, "Check API health", "curl -s http://localhost:11434")
        self.append(env_grp)


class _OllamaModelsPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        popular = Adw.PreferencesGroup(
            title="Popular Models",
            description="Pull models from the Ollama library.",
        )
        _add_row(popular, "Llama 3.1 (8B)", "ollama pull llama3.1")
        _add_row(popular, "Llama 3.1 (70B)", "ollama pull llama3.1:70b")
        _add_row(popular, "Mistral (7B)", "ollama pull mistral")
        _add_row(popular, "Mixtral (8x7B)", "ollama pull mixtral")
        _add_row(popular, "Phi-3 (3.8B)", "ollama pull phi3")
        _add_row(popular, "Gemma 2 (9B)", "ollama pull gemma2")
        _add_row(popular, "Qwen 2.5 (7B)", "ollama pull qwen2.5")
        self.append(popular)

        code = Adw.PreferencesGroup(
            title="Code Models",
            description="Specialized for code generation and understanding.",
        )
        _add_row(code, "CodeLlama (7B)", "ollama pull codellama")
        _add_row(code, "CodeLlama (34B)", "ollama pull codellama:34b")
        _add_row(code, "DeepSeek Coder V2", "ollama pull deepseek-coder-v2")
        _add_row(code, "StarCoder 2 (15B)", "ollama pull starcoder2:15b")
        self.append(code)

        manage = Adw.PreferencesGroup(
            title="Manage Models",
            description="List, inspect, copy and remove local models.",
        )
        _add_row(manage, "List models", "ollama list")
        _add_row(manage, "Show model info", "ollama show MODEL_NAME")
        _add_row(manage, "Copy model", "ollama cp SOURCE_MODEL NEW_NAME")
        _add_row(manage, "Remove model", "ollama rm MODEL_NAME")
        _add_row(manage, "Check disk usage", "du -sh ~/.ollama/models")
        self.append(manage)


class _OllamaUsagePage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        chat = Adw.PreferencesGroup(
            title="Interactive Chat",
            description="Chat with a model from the terminal.",
        )
        _add_tty_row(chat, "Chat with Llama 3.1", "ollama run llama3.1")
        _add_tty_row(chat, "Chat with Mistral", "ollama run mistral")
        _add_tty_row(chat, "Chat with CodeLlama", "ollama run codellama")
        self.append(chat)

        api = Adw.PreferencesGroup(
            title="REST API",
            description="Ollama exposes an OpenAI-compatible API on port 11434.",
        )
        _add_row(api, "Generate (curl)",
                 "curl http://localhost:11434/api/generate -d '{\"model\":\"llama3.1\",\"prompt\":\"Hello\"}'")
        _add_row(api, "Chat (curl)",
                 "curl http://localhost:11434/api/chat -d '{\"model\":\"llama3.1\",\"messages\":[{\"role\":\"user\",\"content\":\"Hi\"}]}'")
        _add_row(api, "List models (API)", "curl http://localhost:11434/api/tags")
        _add_row(api, "Show model (API)", "curl http://localhost:11434/api/show -d '{\"name\":\"llama3.1\"}'")
        self.append(api)

        custom = Adw.PreferencesGroup(
            title="Custom Models (Modelfile)",
            description="Create fine-tuned or customized model variants.",
        )
        _add_row(custom, "Create from Modelfile", "ollama create my-model -f ./Modelfile")
        _add_row(custom, "Push to registry", "ollama push USERNAME/MODEL_NAME")
        self.append(custom)


class _OllamaUninstallPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        rm = Adw.PreferencesGroup(
            title="Uninstall",
            description="Stop/disable and remove the package from the Service tab. Deep cleanup only here.",
        )
        _add_row(rm, "Remove binary", "sudo rm /usr/local/bin/ollama")
        _add_row(rm, "Remove service file", "sudo rm /etc/systemd/system/ollama.service")
        _add_row(rm, "Remove models", "rm -rf ~/.ollama")
        _add_row(rm, "Remove user (optional)", "sudo userdel ollama")
        _add_row(rm, "Remove group (optional)", "sudo groupdel ollama")
        self.append(rm)


class WorkstationOllamaPanel(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self._bar = WorkstationSubsectionBar([
            ("install", "Install", _OllamaInstallPage()),
            ("service", "Service", _OllamaServicePage()),
            ("models", "Models", _OllamaModelsPage()),
            ("usage", "Usage", _OllamaUsagePage()),
            ("uninstall", "Uninstall", _OllamaUninstallPage()),
        ])
        self.append(self._bar)

    def reset_subsections(self) -> None:
        self._bar.reset_to_first()


# ═══════════════════════════════════════════════════════════════
#  LM STUDIO
# ═══════════════════════════════════════════════════════════════


class _LMStudioInstallPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        status_grp = Adw.PreferencesGroup(
            title="Status",
            description="Check whether LM Studio CLI (lms) is available.",
        )
        self._status_row = Adw.ActionRow(title="LM Studio", subtitle="Checking…")
        refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh.set_valign(Gtk.Align.CENTER)
        refresh.connect("clicked", lambda _b: self._refresh())
        self._status_row.add_suffix(refresh)
        status_grp.add(self._status_row)
        self.append(status_grp)

        install = Adw.PreferencesGroup(
            title="Install",
            description="LM Studio GUI as AppImage. Default path is $HOME/Downloads — change if you save elsewhere.",
        )
        _add_row(
            install,
            "Download AppImage",
            "mkdir -p \"$HOME/Downloads\" && curl -fsSL https://releases.lmstudio.ai/linux/x86/latest "
            "-o \"$HOME/Downloads/lmstudio.AppImage\" && chmod +x \"$HOME/Downloads/lmstudio.AppImage\"",
            check_cmd="which lms",
        )
        _add_row(
            install,
            "Make executable",
            "chmod +x \"$HOME/Downloads/lmstudio.AppImage\"",
        )
        _add_row(install, "Install CLI (lms)",
                 "~/.cache/lm-studio/bin/lms bootstrap")
        self.append(install)

        deps = Adw.PreferencesGroup(
            title="Dependencies",
            description="Required system libraries.",
        )
        _add_row(deps, "Install FUSE (Fedora)", "sudo dnf install -y fuse fuse-libs")
        _add_row(deps, "Install FUSE (Ubuntu)", "sudo apt install -y fuse libfuse2")
        self.append(deps)

        GLib.idle_add(self._refresh)

    def _refresh(self) -> None:
        def _work() -> None:
            ok, out, _e = _run_check("which lms")
            status = out.strip() if ok else "not installed"
            GLib.idle_add(self._status_row.set_subtitle, status)

        _bg(_work)


class _LMStudioServerPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        server = Adw.PreferencesGroup(
            title="Local Server",
            description="Run LM Studio as an OpenAI-compatible API server.",
        )
        _add_row(server, "Start server", "lms server start")
        _add_row(server, "Stop server", "lms server stop")
        _add_row(server, "Server status", "lms server status")
        _add_row(server, "Set port", "lms server start --port 1234")
        _add_row(server, "Enable CORS", "lms server start --cors")
        self.append(server)

        api = Adw.PreferencesGroup(
            title="API Usage",
            description="Send requests to the local server (compatible with OpenAI SDK).",
        )
        _add_row(api, "List loaded models",
                 "curl http://localhost:1234/v1/models")
        _add_row(api, "Chat completion",
                 "curl http://localhost:1234/v1/chat/completions -H 'Content-Type: application/json' "
                 "-d '{\"model\":\"MODEL_NAME\",\"messages\":[{\"role\":\"user\",\"content\":\"Hello\"}]}'")
        _add_row(api, "Text completion",
                 "curl http://localhost:1234/v1/completions -H 'Content-Type: application/json' "
                 "-d '{\"model\":\"MODEL_NAME\",\"prompt\":\"Hello\"}'")
        self.append(api)


class _LMStudioModelsPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        manage = Adw.PreferencesGroup(
            title="Model Management",
            description="Download and manage models via the lms CLI.",
        )
        _add_row(manage, "Search models", "lms search MODEL_NAME")
        _add_row(manage, "Download model", "lms get MODEL_NAME")
        _add_row(manage, "List downloaded", "lms ls")
        _add_row(manage, "Load model", "lms load MODEL_NAME")
        _add_row(manage, "Unload model", "lms unload MODEL_NAME")
        _add_row(manage, "Delete model", "lms rm MODEL_NAME")
        self.append(manage)

        storage = Adw.PreferencesGroup(
            title="Storage",
            description="Check and manage model storage.",
        )
        _add_row(storage, "Models directory", "ls -lh ~/.cache/lm-studio/models/")
        _add_row(storage, "Disk usage", "du -sh ~/.cache/lm-studio/models/")
        self.append(storage)


class _LMStudioUninstallPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        rm = Adw.PreferencesGroup(
            title="Uninstall",
            description="Remove LM Studio artifacts. AppImage name may vary — adjust paths if needed.",
        )
        _add_row(
            rm,
            "Remove AppImage(s) in Downloads",
            "rm -f \"$HOME/Downloads/lmstudio.AppImage\" \"$HOME/Downloads/lmstudio.appimage\" "
            "\"$HOME/Downloads\"/LM-Studio*.AppImage 2>/dev/null || true",
        )
        _add_row(rm, "Remove config", "rm -rf ~/.cache/lm-studio")
        _add_row(rm, "Remove CLI", "rm -f ~/.local/bin/lms")
        self.append(rm)


class WorkstationLMStudioPanel(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self._bar = WorkstationSubsectionBar([
            ("install", "Install", _LMStudioInstallPage()),
            ("server", "Server", _LMStudioServerPage()),
            ("models", "Models", _LMStudioModelsPage()),
            ("uninstall", "Uninstall", _LMStudioUninstallPage()),
        ])
        self.append(self._bar)

    def reset_subsections(self) -> None:
        self._bar.reset_to_first()


# ═══════════════════════════════════════════════════════════════
#  OPEN WEBUI
# ═══════════════════════════════════════════════════════════════


class _OpenWebUIInstallPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        status_grp = Adw.PreferencesGroup(
            title="Status",
            description="Check whether the Open WebUI container is running.",
        )
        self._status_row = Adw.ActionRow(title="Open WebUI container", subtitle="Checking…")
        refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh.set_valign(Gtk.Align.CENTER)
        refresh.connect("clicked", lambda _b: self._refresh())
        self._status_row.add_suffix(refresh)
        status_grp.add(self._status_row)
        self.append(status_grp)

        install = Adw.PreferencesGroup(
            title="Install (Docker)",
            description="Open WebUI is a ChatGPT-style interface for local LLMs. Requires Docker.",
        )
        _add_row(install, "Run Open WebUI",
                 "docker run -d -p 3000:8080 --add-host=host.docker.internal:host-gateway "
                 "-v open-webui:/app/backend/data --name open-webui --restart always "
                 "ghcr.io/open-webui/open-webui:main")
        _add_row(install, "Run with GPU (NVIDIA)",
                 "docker run -d -p 3000:8080 --gpus all --add-host=host.docker.internal:host-gateway "
                 "-v open-webui:/app/backend/data --name open-webui --restart always "
                 "ghcr.io/open-webui/open-webui:cuda")
        _add_row(install, "Run with bundled Ollama",
                 "docker run -d -p 3000:8080 --gpus all "
                 "-v ollama:/root/.ollama -v open-webui:/app/backend/data "
                 "--name open-webui --restart always "
                 "ghcr.io/open-webui/open-webui:ollama")
        self.append(install)

        pip_install = Adw.PreferencesGroup(
            title="Install (pip)",
            description="Run without Docker using pip. Requires Python 3.11+.",
        )
        _add_row(pip_install, "Install via pip", "pip install open-webui",
                 check_cmd="which open-webui")
        _add_tty_row(pip_install, "Start server", "open-webui serve")
        self.append(pip_install)

        GLib.idle_add(self._refresh)

    def _refresh(self) -> None:
        def _work() -> None:
            st = docker_container_status(OPEN_WEBUI_CONTAINER_NAME)
            status = st if st else "not running / not found"
            GLib.idle_add(self._status_row.set_subtitle, status)

        _bg(_work)


class _OpenWebUIManagePage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        managed = Adw.PreferencesGroup(
            title="Container lifecycle",
            description=(
                f"Start/stop the existing Docker container ({OPEN_WEBUI_CONTAINER_NAME!r}) "
                "without shell wrappers. Create it first from the Install tab."
            ),
        )
        managed.add(_OpenWebUIContainerRow())
        self.append(managed)

        container = Adw.PreferencesGroup(
            title="Advanced (docker CLI)",
            description="Optional terminal commands for logs and inspection.",
        )
        _add_tty_row(
            container,
            "View logs",
            f"docker logs -f {OPEN_WEBUI_CONTAINER_NAME} --tail 100",
        )
        _add_row(
            container,
            "Inspect container",
            f"docker inspect -f '{{{{.State.Status}}}}' {OPEN_WEBUI_CONTAINER_NAME}",
        )
        self.append(container)

        access = Adw.PreferencesGroup(
            title="Access",
            description="Open WebUI listens on port 3000 by default.",
        )
        _add_row(access, "Open in browser", "xdg-open http://localhost:3000")
        _add_row(access, "Check port", "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000")
        self.append(access)

        update = Adw.PreferencesGroup(
            title="Update",
            description="Pull latest image and recreate the container.",
        )
        _add_row(update, "Pull latest image", "docker pull ghcr.io/open-webui/open-webui:main")
        _add_row(update, "Recreate container",
                 "docker stop open-webui && docker rm open-webui && "
                 "docker run -d -p 3000:8080 --add-host=host.docker.internal:host-gateway "
                 "-v open-webui:/app/backend/data --name open-webui --restart always "
                 "ghcr.io/open-webui/open-webui:main")
        self.append(update)


class _OpenWebUIConfigPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        ollama_cfg = Adw.PreferencesGroup(
            title="Ollama Connection",
            description="Connect Open WebUI to your Ollama instance.",
        )
        _add_row(ollama_cfg, "Set Ollama URL (env)",
                 "docker run -d -p 3000:8080 -e OLLAMA_BASE_URL=http://host.docker.internal:11434 "
                 "-v open-webui:/app/backend/data --name open-webui --restart always "
                 "ghcr.io/open-webui/open-webui:main")
        _add_row(ollama_cfg, "Test Ollama connection",
                 "curl http://localhost:11434/api/tags")
        self.append(ollama_cfg)

        openai_cfg = Adw.PreferencesGroup(
            title="OpenAI API",
            description="Use cloud models alongside local ones.",
        )
        _add_row(openai_cfg, "Set OpenAI key (env)",
                 "docker run -d -p 3000:8080 -e OPENAI_API_KEY=sk-... "
                 "-v open-webui:/app/backend/data --name open-webui --restart always "
                 "ghcr.io/open-webui/open-webui:main")
        self.append(openai_cfg)

        data = Adw.PreferencesGroup(
            title="Data and backup",
            description="Manage persistent data stored in Docker volumes.",
        )
        _add_row(data, "List volumes", "docker volume ls | grep open-webui")
        _add_row(data, "Backup volume",
                 "docker run --rm -v open-webui:/data -v $(pwd):/backup alpine tar czf /backup/open-webui-backup.tar.gz /data")
        _add_row(data, "Inspect volume", "docker volume inspect open-webui")
        self.append(data)


class _OpenWebUIUninstallPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        rm = Adw.PreferencesGroup(
            title="Uninstall",
            description="Remove Open WebUI container and data.",
        )
        _add_row(rm, "Stop container", "docker stop open-webui")
        _add_row(rm, "Remove container", "docker rm open-webui")
        _add_row(rm, "Remove image", "docker rmi ghcr.io/open-webui/open-webui:main")
        _add_row(rm, "Remove volume (data)", "docker volume rm open-webui")
        _add_row(rm, "Uninstall pip version", "pip uninstall open-webui")
        self.append(rm)


class WorkstationOpenWebUIPanel(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self._bar = WorkstationSubsectionBar([
            ("install", "Install", _OpenWebUIInstallPage()),
            ("manage", "Manage", _OpenWebUIManagePage()),
            ("config", "Config", _OpenWebUIConfigPage()),
            ("uninstall", "Uninstall", _OpenWebUIUninstallPage()),
        ])
        self.append(self._bar)

    def reset_subsections(self) -> None:
        self._bar.reset_to_first()


# ═══════════════════════════════════════════════════════════════
#  GITHUB COPILOT CLI
# ═══════════════════════════════════════════════════════════════


class _CopilotInstallPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        status_grp = Adw.PreferencesGroup(
            title="Status",
            description="Check GitHub CLI and Copilot extension status.",
        )
        self._gh_row = Adw.ActionRow(title="GitHub CLI (gh)", subtitle="Checking…")
        self._cop_row = Adw.ActionRow(title="Copilot extension", subtitle="Checking…")
        self._auth_row = Adw.ActionRow(title="Auth status", subtitle="Checking…")
        refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh.set_valign(Gtk.Align.CENTER)
        refresh.connect("clicked", lambda _b: self._refresh())
        self._gh_row.add_suffix(refresh)
        status_grp.add(self._gh_row)
        status_grp.add(self._cop_row)
        status_grp.add(self._auth_row)
        self.append(status_grp)

        install = Adw.PreferencesGroup(
            title="Install",
            description="GitHub Copilot CLI requires GitHub CLI (gh) and a Copilot subscription.",
        )
        _add_row(install, "Install GitHub CLI", _distro_cmd("gh"),
                 check_cmd="gh --version")
        _add_row(install, "Install (official script)",
                 "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /usr/share/keyrings/githubcli-archive-keyring.gpg > /dev/null && "
                 "echo \"deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main\" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null && "
                 "sudo apt update && sudo apt install -y gh",
                 check_cmd="gh --version")
        _add_row(install, "Install Copilot extension",
                 "gh extension install github/gh-copilot")
        _add_row(install, "Upgrade Copilot extension",
                 "gh extension upgrade github/gh-copilot")
        self.append(install)

        auth = Adw.PreferencesGroup(
            title="Authentication",
            description="Log in to your GitHub account.",
        )
        _add_tty_row(auth, "Log in (browser)", "gh auth login")
        _add_tty_row(auth, "Log in (token)", "gh auth login --with-token")
        _add_row(auth, "Auth status", "gh auth status")
        _add_row(auth, "Log out", "gh auth logout")
        self.append(auth)

        GLib.idle_add(self._refresh)

    def _refresh(self) -> None:
        def _work() -> None:
            ok, out, _e = _run_check("gh --version")
            ver = out.strip().split("\n")[0] if ok else "not installed"
            GLib.idle_add(self._gh_row.set_subtitle, ver)

            ok2, out2, _e2 = _run_check("gh extension list 2>/dev/null | grep copilot")
            cop = out2.strip().split("\n")[0] if ok2 else "not installed"
            GLib.idle_add(self._cop_row.set_subtitle, cop)

            ok3, out3, _e3 = _run_check("gh auth status 2>&1 | head -1")
            auth = out3.strip() if ok3 else "not authenticated"
            GLib.idle_add(self._auth_row.set_subtitle, auth)

        _bg(_work)


class _CopilotUsagePage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        suggest = Adw.PreferencesGroup(
            title="Suggest",
            description="Ask Copilot to suggest a shell command for a task.",
        )
        _add_tty_row(suggest, "Suggest a command", "gh copilot suggest \"how to find large files\"")
        _add_tty_row(suggest, "Suggest (shell)", "gh copilot suggest -t shell \"compress a folder\"")
        _add_tty_row(suggest, "Suggest (git)", "gh copilot suggest -t git \"undo last commit\"")
        _add_tty_row(suggest, "Suggest (gh)", "gh copilot suggest -t gh \"list my repos\"")
        self.append(suggest)

        explain = Adw.PreferencesGroup(
            title="Explain",
            description="Ask Copilot to explain a command.",
        )
        _add_tty_row(explain, "Explain a command", "gh copilot explain \"find / -name '*.log' -mtime +30 -delete\"")
        _add_tty_row(explain, "Explain (git)", "gh copilot explain \"git rebase -i HEAD~3\"")
        _add_tty_row(explain, "Explain (awk)", "gh copilot explain \"awk '{print $1}' file.txt\"")
        self.append(explain)

        aliases = Adw.PreferencesGroup(
            title="Shell Aliases",
            description="Set up shell aliases for faster access.",
        )
        _add_row(aliases, "Add bash aliases",
                 "echo 'eval \"$(gh copilot alias -- bash)\"' >> ~/.bashrc && source ~/.bashrc")
        _add_row(aliases, "Add zsh aliases",
                 "echo 'eval \"$(gh copilot alias -- zsh)\"' >> ~/.zshrc && source ~/.zshrc")
        _add_row(aliases, "Use alias (suggest)", "ghcs \"find large files\"")
        _add_row(aliases, "Use alias (explain)", "ghce \"tar -xzf archive.tar.gz\"")
        self.append(aliases)


class _CopilotGHCliPage(Gtk.Box):
    """Useful GitHub CLI commands that complement Copilot."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        repos = Adw.PreferencesGroup(
            title="Repositories",
            description="Common gh repo operations.",
        )
        _add_row(repos, "Clone a repo", "gh repo clone OWNER/REPO")
        _add_row(repos, "Create repo", "gh repo create REPO_NAME --public")
        _add_row(repos, "Fork repo", "gh repo fork OWNER/REPO")
        _add_row(repos, "List repos", "gh repo list")
        _add_row(repos, "View repo", "gh repo view OWNER/REPO")
        self.append(repos)

        prs = Adw.PreferencesGroup(
            title="Pull Requests",
            description="Create and manage PRs from the terminal.",
        )
        _add_row(prs, "Create PR", "gh pr create --title \"Title\" --body \"Description\"")
        _add_row(prs, "List PRs", "gh pr list")
        _add_row(prs, "Checkout PR", "gh pr checkout PR_NUMBER")
        _add_row(prs, "Merge PR", "gh pr merge PR_NUMBER")
        _add_row(prs, "View PR", "gh pr view PR_NUMBER")
        self.append(prs)

        issues = Adw.PreferencesGroup(
            title="Issues",
            description="Manage issues from the terminal.",
        )
        _add_row(issues, "Create issue", "gh issue create --title \"Bug\" --body \"Description\"")
        _add_row(issues, "List issues", "gh issue list")
        _add_row(issues, "View issue", "gh issue view ISSUE_NUMBER")
        _add_row(issues, "Close issue", "gh issue close ISSUE_NUMBER")
        self.append(issues)

        extensions = Adw.PreferencesGroup(
            title="Extensions",
            description="Extend gh with community extensions.",
        )
        _add_row(extensions, "List extensions", "gh extension list")
        _add_row(extensions, "Search extensions", "gh extension search QUERY")
        _add_row(extensions, "Install extension", "gh extension install OWNER/EXTENSION")
        _add_row(extensions, "Upgrade all", "gh extension upgrade --all")
        self.append(extensions)


class _CopilotUninstallPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        rm = Adw.PreferencesGroup(
            title="Uninstall",
            description="Remove Copilot extension and GitHub CLI.",
        )
        _add_row(rm, "Remove Copilot extension", "gh extension remove github/gh-copilot")
        _add_row(rm, "Uninstall GitHub CLI", _distro_remove("gh"))
        _add_row(rm, "Remove config", "rm -rf ~/.config/gh")
        self.append(rm)


class WorkstationCopilotPanel(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self._bar = WorkstationSubsectionBar([
            ("install", "Install", _CopilotInstallPage()),
            ("usage", "Usage", _CopilotUsagePage()),
            ("gh-cli", "GH CLI", _CopilotGHCliPage()),
            ("uninstall", "Uninstall", _CopilotUninstallPage()),
        ])
        self.append(self._bar)

    def reset_subsections(self) -> None:
        self._bar.reset_to_first()


# ═══════════════════════════════════════════════════════════════
#  COMBINED AI PANEL
# ═══════════════════════════════════════════════════════════════


_AI_TABS: list[tuple[str, str, type]] = [
    ("hub", "Overview", WorkstationAIHubPanel),
    ("ollama", "Ollama", WorkstationOllamaPanel),
    ("lmstudio", "LM Studio", WorkstationLMStudioPanel),
    ("openwebui", "Open WebUI", WorkstationOpenWebUIPanel),
    ("copilot", "Copilot CLI", WorkstationCopilotPanel),
]


class WorkstationAIPanel(Gtk.Box):
    """Top-level AI Tools panel: Ollama | LM Studio | Open WebUI | Copilot CLI.

    Each tab shows a full sub-panel with its own subsection bar, so we do NOT
    wrap children in ScrolledWindow (the inner bars handle their own scrolling).
    """

    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self._stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT,
            transition_duration=180,
            hexpand=True,
            vexpand=True,
        )

        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self._stack)
        switcher.set_margin_top(6)
        switcher.set_margin_bottom(4)
        switcher.set_margin_start(16)
        switcher.set_margin_end(16)
        switcher.set_halign(Gtk.Align.CENTER)
        switcher.add_css_class("workstation-subsection-switcher")

        self._children: list[Gtk.Widget] = []
        for sid, title, cls in _AI_TABS:
            child = cls()
            self._children.append(child)
            self._stack.add_titled(child, sid, title)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)

        self.append(switcher)
        self.append(sep)
        self.append(self._stack)

    def reset_subsections(self) -> None:
        self._stack.set_visible_child_name("hub")
        for child in self._children:
            reset = getattr(child, "reset_subsections", None)
            if callable(reset):
                reset()
