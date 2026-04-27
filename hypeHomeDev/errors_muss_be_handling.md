cr
Starting CodeRabbit review in plain text mode...

Review directory: /home/karimodora/Documents/GitHub/hypeHomeDev

Connecting to review service
Setting up
Summarizing
Reviewing

============================================================================
File: com.github.hypedevhome.yml
Line: 16
Type: potential_issue

Comment:
Verify the need for broad systemd D-Bus access.

Adding --system-talk-name=org.freedesktop.systemd1 grants the sandboxed app access to the full systemd D-Bus interface on the system bus. This is a significant permission that allows the application to:
- Query status of all system services and units
- Potentially start/stop/restart services (subject to polkit authorization)
- Access system state and job management interfaces

Consider documenting why this permission is required. If only specific operations are needed (e.g., querying service status), the actual security boundary will depend on polkit policies, but the app will still have visibility into system-wide service information.



Flatpak systemd1 system-talk-name security best practices

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @com.github.hypedevhome.yml at line 16, The manifest currently adds a broad systemd D-Bus grant via the flag --system-talk-name=org.freedesktop.systemd1; verify whether full system-wide systemd access is required and either remove this flag or replace it with a more limited permission (e.g., use session bus access, a specific well-scoped D-Bus name, or a portal that exposes only needed operations), and add a brief justification comment/metadata explaining why org.freedesktop.systemd1 is required and what exact operations the app performs (e.g., querying service status vs. controlling units) so reviewers can confirm the minimum privilege is used.

============================================================================
File: src/ui/widgets/workstation/data/docker.json
Line: 25
Type: potential_issue

Comment:
Outdated version key in Docker Compose example.

The version key in Docker Compose files is deprecated and ignored by modern Docker Compose (V2). Consider removing it from the example to reflect current best practices.




Suggested fix

-{ "id": "basic", "title": "Basic Example", "description": "docker-compose.yml", "items": [ { "type": "code", "code": "version: '2'\n\nservices:\n  web:\n    build:\n      context: ./Path\n      dockerfile: Dockerfile\n    ports:\n      - \"5000:5000\"\n    volumes:\n      - .:/code\n  redis:\n    image: redis" } ] },
+{ "id": "basic", "title": "Basic Example", "description": "docker-compose.yml", "items": [ { "type": "code", "code": "services:\n  web:\n    build:\n      context: ./Path\n      dockerfile: Dockerfile\n    ports:\n      - \"5000:5000\"\n    volumes:\n      - .:/code\n  redis:\n    image: redis" } ] },




Docker Compose version key deprecated 2024

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/data/docker.json at line 25, The Docker Compose example in the "basic" widget uses the deprecated top-level "version" key inside the code property; remove the line "version: '2'" from the code string in the item with id "basic" so the example uses modern Compose V2 style (adjust any indentation if needed) and keep the rest of the service definitions (web, redis) unchanged.

============================================================================
File: src/ui/widgets/workstation/data/services.json
Line: 13
Type: potential_issue

Comment:
Fix typo in German translation.

The German word "Benotigt" should be "Benötigt" (with umlaut over the 'o').



📝 Proposed fix

-        "de": "Zero-Config-Mesh-VPN. Benotigt den tailscaled-Dienst.",
+        "de": "Zero-Config-Mesh-VPN. Benötigt den tailscaled-Dienst.",

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/data/services.json at line 13, Update the German translation value for the "de" entry in services.json by replacing the misspelled "Benotigt" with the correct "Benötigt" (use the umlaut over the 'o') so the string reads "Zero-Config-Mesh-VPN. Benötigt den tailscaled-Dienst."; locate the "de" key in the same JSON object shown in the diff to apply the change.

============================================================================
File: src/ui/widgets/workstation/data/bash.json
Line: 76
Type: potential_issue

Comment:
Critical: Incorrect escape sequences in IFS assignment.

The IFS assignment uses quadruple backslashes (\\\\n\\\\t), which when parsed from JSON becomes \\n\\t in the resulting string. In Bash's ANSI-C quoting syntax $'...', this produces literal backslash characters followed by the letters 'n' and 't', rather than the intended newline and tab characters.

The "unofficial bash strict mode" pattern requires setting IFS to actual newline and tab characters to safely handle word splitting.





🐛 Proposed fix for correct escape sequences

Line 76 (English):
-            { "type": "code", "code": "set -euo pipefail\nIFS=$'\\\\n\\\\t'" },
+            { "type": "code", "code": "set -euo pipefail\nIFS=$'\\n\\t'" },


Line 148 (German):
-            { "type": "code", "code": "set -euo pipefail\nIFS=$'\\\\n\\\\t'" },
+            { "type": "code", "code": "set -euo pipefail\nIFS=$'\\n\\t'" },


Line 220 (Arabic):
-            { "type": "code", "code": "set -euo pipefail\nIFS=$'\\\\n\\\\t'" },
+            { "type": "code", "code": "set -euo pipefail\nIFS=$'\\n\\t'" },




To verify this issue, you can test the current code in a Bash shell:
# Test current (incorrect) version
IFS=$'\\n\\t'
printf '%q\n' "$IFS"  # Will show: $'\\n\\t' (literal backslashes)

# Test corrected version
IFS=$'\n\t'
printf '%q\n' "$IFS"  # Will show: $'\n\t' (actual newline and tab)



Also applies to: 148-148, 220-220

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/data/bash.json at line 76, The IFS assignment in the JSON entries uses incorrect escape sequences ("IFS=$'\\\\n\\\\t'") which end up as literal backslashes instead of newline and tab; locate the JSON objects containing the bash snippet (the entry with "type": "code" and code containing "set -euo pipefail" and "IFS=$'\\\\n\\\\t'") and replace the IFS value with the correct ANSI-C quoted escapes so it becomes IFS=$'\n\t' (apply the same fix to the other language variants shown by the reviewer).

============================================================================
File: src/ui/widgets/workstation/data/docker.json
Line: 30
Type: potential_issue

Comment:
Incorrect YAML structure for build args.

The args key must be nested under the build: block, not at the service level. The current example will cause a configuration error.




Suggested fix

-{ "id": "build", "title": "Service Configuration", "description": "Building", "items": [ { "type": "code", "code": "web:\n  build: .\n  args:\n    APP_HOME: app\n\nbuild:\n  context: ./dir\n  dockerfile: Dockerfile.dev" }, { "type": "text", "text": "build from Dockerfile" }, { "type": "code", "code": "image: ubuntu:14.04\nimage: tutum/influxdb" }, { "type": "text", "text": "build from image" } ] },
+{ "id": "build", "title": "Service Configuration", "description": "Building", "items": [ { "type": "code", "code": "web:\n  build:\n    context: .\n    args:\n      APP_HOME: app\n\nbuild:\n  context: ./dir\n  dockerfile: Dockerfile.dev" }, { "type": "text", "text": "build from Dockerfile" }, { "type": "code", "code": "image: ubuntu:14.04\nimage: tutum/influxdb" }, { "type": "text", "text": "build from image" } ] },

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/data/docker.json at line 30, The example under the widget with id "build" has the service-level "args" incorrectly placed; move the APP_HOME args into the service's build block so "web:" uses a nested "build:" object containing "context"/"dockerfile" and an "args" map (i.e., update the "web:" snippet and the later "build:" snippet references so args are nested under the build key for the service definition such as the "web" service in the code sample).

============================================================================
File: src/ui/widgets/workstation/data/docker.json
Line: 38
Type: potential_issue

Comment:
Invalid YAML: duplicate dns key in example.

The example shows two dns: keys at the same level, which is invalid YAML. This appears to demonstrate alternative syntaxes but will confuse users. Consider separating them with a comment or showing them as distinct examples.




Suggested fix

-{ "id": "dns", "title": "Advanced Features", "description": "DNS servers", "items": [ { "type": "code", "code": "services:\n  web:\n    dns: 8.8.8.8\n    dns:\n      - 8.8.8.8\n      - 8.8.4.4" } ] },
+{ "id": "dns", "title": "Advanced Features", "description": "DNS servers", "items": [ { "type": "code", "code": "services:\n  web:\n    # Single DNS server\n    dns: 8.8.8.8\n    # Or multiple DNS servers\n    # dns:\n    #   - 8.8.8.8\n    #   - 8.8.4.4" } ] },

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/data/docker.json at line 38, The DNS example under the "dns" item shows duplicate dns keys at the same level in the YAML code block; fix it by replacing that single code example with two clear, separate examples (e.g., "single-value" and "list-value") or separate YAML documents (using ---) so there is no duplicate key in one snippet, and update the "code" field in the item with those distinct examples; reference the JSON object with id "dns" / title "Advanced Features" to locate and modify the entry.

============================================================================
File: src/ui/widgets/workstation/session_info.py
Line: 49 to 53
Type: potential_issue

Comment:
Dead code: init_lua_cmd and init_vim_cmd are defined but never used.

Lines 49-50 define command strings that are never referenced. The actual commands are constructed inline at lines 52-53.

Either remove the unused variables or use them in the run_sync() calls.




🧹 Proposed fix: remove unused variables

     executor = HostExecutor()
 
-    # NOTE: use host-side $HOME expansion (HostExecutor will run via flatpak-spawn --host).
-    init_lua_cmd = 'sh -c \'test -f "$HOME/.config/nvim/init.lua" && echo yes || echo no\''
-    init_vim_cmd = 'sh -c \'test -f "$HOME/.config/nvim/init.vim" && echo yes || echo no\''
-
+    # NOTE: use host-side $HOME expansion (HostExecutor runs via flatpak-spawn --host).
     init_lua_res = executor.run_sync(["sh", "-c", 'test -f "$HOME/.config/nvim/init.lua" && echo yes || echo no'])
     init_vim_res = executor.run_sync(["sh", "-c", 'test -f "$HOME/.config/nvim/init.vim" && echo yes || echo no'])

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/session_info.py around lines 49 - 53, Remove the dead variables init_lua_cmd and init_vim_cmd (they are defined but never used) to avoid unused-code clutter; either delete those two variable definitions and keep the existing executor.run_sync([...]) calls as-is, or replace the inline command strings passed to executor.run_sync(...) with those variables (init_lua_cmd and init_vim_cmd) if you prefer named constants—update references around executor.run_sync to use the chosen approach so no unused symbols remain.

============================================================================
File: src/ui/widgets/workstation/data/nvim.json
Line: 167 to 180
Type: potential_issue

Comment:
German language has no cheatsheet content.

The German locale provides all UI strings but has an empty groups array. Users selecting German will see a localized interface but no actual cheatsheet commands. Consider either:
1. Adding translated groups with German command descriptions, or
2. Removing the German language option until content is available, or
3. Falling back to English content with German UI labels (if the UI supports this pattern)

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/data/nvim.json around lines 167 - 180, The German locale object "de" currently has an empty groups array, so users see localized UI labels but no cheatsheet commands; update the "de" entry by populating "groups" with translated command groups and descriptions (translate the existing English groups into German), or if translations aren't ready, remove/disable the "de" locale entry or implement a fallback to the English "groups" while keeping "de" UI labels—target the "de" object and its "groups" property in src/ui/widgets/workstation/data/nvim.json and apply one of these fixes consistently.

============================================================================
File: src/ui/widgets/workstation/data/nvim.json
Line: 181 to 194
Type: potential_issue

Comment:
Arabic language has no cheatsheet content.

The Arabic locale provides all UI strings but has an empty groups array. Users selecting Arabic will see a localized interface but no actual cheatsheet commands. Consider either:
1. Adding translated groups with Arabic command descriptions, or
2. Removing the Arabic language option until content is available, or
3. Falling back to English content with Arabic UI labels (if the UI supports this pattern)

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/data/nvim.json around lines 181 - 194, The Arabic locale object ("ar") currently has an empty "groups" array so users get a localized UI with no cheatsheet content; fix by populating "ar.groups" with translated group entries following the same structure used by other locales (each group should include title and commands with name/keys/description), or if translations aren't ready remove the "ar" entry entirely or implement a fallback so when "ar.groups" is empty the UI uses "en.groups" while keeping Arabic UI labels (refer to the "ar" object, its "groups" array, and related keys like "chip_labels" and "chip_tooltips" when making the change).

============================================================================
File: src/ui/widgets/workstation/docker_manager.py
Line: 692 to 699
Type: potential_issue

Comment:
Silent exception swallowing loses diagnostic information.

When installation fails with an exception, the error is silently discarded. Consider logging the exception for debugging purposes.




🔧 Proposed fix to log the exception

             try:
                 ok = asyncio.run(_install())
-            except Exception:
+            except Exception as exc:
+                log.warning("Docker install failed: %s", exc)
                 ok = False

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/docker_manager.py around lines 692 - 699, The except block around asyncio.run(_install()) swallows exceptions; catch the exception as a variable (e.g., except Exception as e:) and log it before setting ok = False so diagnostics are preserved. Use the instance logger if available (self._logger.exception(...) or self._logger.error(..., exc_info=True)) or the module logging.exception(...) to record the exception and traceback, then proceed to disable/leave ok=False and call GLib.idle_add(self._after_action, ok, "Installed." if ok else "Install failed.").

============================================================================
File: src/ui/widgets/workstation/apps_panel.py
Line: 201 to 213
Type: potential_issue

Comment:
Pending debounce timeout not cleaned up on widget destruction.

If the widget is destroyed while a debounce timeout is pending, _apply_search_debounced will execute on a destroyed widget, potentially causing GTK warnings or undefined behavior. Consider connecting to the destroy signal to cancel any pending timeout.



🛡️ Proposed fix in __init__

Add cleanup in the constructor:

self.connect("destroy", self._on_destroy)


And add the handler:

+    def _on_destroy(self, _widget: Gtk.Widget) -> None:
+        if self._search_debounce_source_id is not None:
+            GLib.source_remove(self._search_debounce_source_id)
+            self._search_debounce_source_id = None

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/apps_panel.py around lines 201 - 213, The debounce timeout isn't cancelled on widget teardown; in the class constructor (__init__) connect the widget to the "destroy" signal (e.g. self.connect("destroy", self._on_destroy)) and implement an _on_destroy method that checks _search_debounce_source_id, calls GLib.source_remove(self._search_debounce_source_id) if not None, and sets _search_debounce_source_id to None so _apply_search_debounced won't run against a destroyed widget; ensure the handler uses the same _search_debounce_source_id and cleans up any other related state.

============================================================================
File: src/ui/widgets/workstation/docker_manager.py
Line: 696 to 699
Type: potential_issue

Comment:
Post-install enable/start failures are not reported to the user.

If enable_unit or start_unit fails after a successful install, the user sees "Installed." but the service may not be running. Consider checking return values and adjusting the toast message.




🔧 Proposed fix to report enable/start status

             if ok:
-                self._systemd.enable_unit("docker.service")
-                self._systemd.start_unit("docker.service")
-            GLib.idle_add(self._after_action, ok, "Installed." if ok else "Install failed.")
+                enabled = self._systemd.enable_unit("docker.service")
+                started = self._systemd.start_unit("docker.service")
+                if enabled and started:
+                    msg = "Installed and started."
+                elif enabled:
+                    msg = "Installed and enabled, but failed to start."
+                else:
+                    msg = "Installed, but failed to enable/start service."
+            else:
+                msg = "Install failed."
+            GLib.idle_add(self._after_action, ok, msg)

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/docker_manager.py around lines 696 - 699, The post-install path reports "Installed." even if enabling or starting the docker.service fails; update the block after a successful install to check the return values (or catch exceptions) from self._systemd.enable_unit and self._systemd.start_unit, build a final status message reflecting any failures (e.g., "Installed, but failed to enable service" / "Installed, but failed to start service"), and pass that message into GLib.idle_add(self._after_action, ok, message). Ensure you reference self._systemd.enable_unit, self._systemd.start_unit and the _after_action call when implementing the checks and message construction.

============================================================================
File: src/ui/widgets/workstation/docker_manager.py
Line: 320 to 328
Type: potential_issue

Comment:
Unused log level tags in InstallDialog.

The tags log_error, log_warn, etc. are created but never applied. The _append() method (lines 384-389) inserts text without ANSI stripping or tag application, unlike _DockerLogDialog._append_text() which properly uses its tags.

Either apply the same pattern used in _DockerLogDialog (strip ANSI + apply level tag), or remove these unused tags.




🔧 Proposed fix to use the tags

     def _append(self, text: str) -> None:
         end = self._buffer.get_end_iter()
-        self._buffer.insert(end, text)
+        clean = _ANSI_ESCAPE_RE.sub("", text).replace("\r", "")
+        m = _LOG_LEVEL_RE.search(clean)
+        tag = None
+        if m:
+            level = m.group(1)
+            tag = {
+                "ERROR": self._tag_error,
+                "WARN": self._tag_warn,
+                "INFO": self._tag_info,
+                "DEBUG": self._tag_debug,
+                "TRACE": self._tag_trace,
+            }.get(level)
+        if tag is not None:
+            self._buffer.insert_with_tags(end, clean, tag)
+        else:
+            self._buffer.insert(end, clean)
         mark = self._buffer.create_mark(None, self._buffer.get_end_iter(), False)
         self._textview.scroll_mark_onscreen(mark)
         self._buffer.delete_mark(mark)

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/docker_manager.py around lines 320 - 328, InstallDialog creates GTK text tags (_tag_error, _tag_warn, _tag_info, _tag_debug, _tag_trace) but never applies them because InstallDialog._append() just inserts raw text; update InstallDialog._append() to mirror _DockerLogDialog._append_text(): strip ANSI escape sequences from incoming lines, determine log level (error/warn/info/debug/trace) for the line, and insert the text with the corresponding tag (use the existing _tag_ attributes) so colors are applied, or if you prefer remove the unused _tag_ attributes; locate InstallDialog and its _append() method and either implement the ANSI-strip + tag-application logic referencing the same helpers used by _DockerLogDialog._append_text(), or delete the unused tag creation in the constructor.

============================================================================
File: src/ui/widgets/workstation/learn_factory.py
Line: 239 to 240
Type: potential_issue

Comment:
Synchronous shell execution blocks UI thread.

run_sync is called on the main thread during widget initialization. If multiple host checks are configured or commands are slow, this will freeze the UI. Consider running checks asynchronously and updating badges when results arrive.

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/learn_factory.py around lines 239 - 240, The synchronous call to self._executor.run_sync during widget initialization blocks the UI; change the host-command checks to run asynchronously (e.g., use self._executor.run_async or schedule run_sync on a background thread/future) and avoid calling run_sync directly on the main thread in the widget constructor. Replace the direct assignment using res and ok with an async task that performs the same command invocation and then updates the widget badge/state on the main thread when the result arrives (ensure stdout check logic remains: success and stdout.strip().lower() == "yes"). Keep the same command string construction but move it into the background task and emit or call a UI-safe update method to set the badge once the async result is available.

============================================================================
File: src/ui/widgets/workstation/learn_factory.py
Line: 506 to 512
Type: potential_issue

Comment:
Fragile widget structure traversal.

Using get_first_child() and checking hasattr(row, "get_child") to access internal Adw.ActionRow structure is brittle. The internal widget hierarchy may change between Adwaita versions, causing CSS classes to silently fail to apply.

Consider using the row's add_css_class() directly or accepting that per-child styling may not be possible without custom widgets.

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/learn_factory.py around lines 506 - 512, The traversal using row.get_first_child() and hasattr(row, "get_child") is brittle; remove the attempts to reach internal children (title_widget and child) and instead apply styling to the row itself or replace with a custom widget: call row.add_css_class("bash-link-title") and row.add_css_class("bash-link-url") (or create a custom Adw.ActionRow subclass that exposes styled title/url widgets) rather than relying on get_first_child/get_child in learn_factory.py.

============================================================================
File: src/ui/widgets/workstation/learn_factory.py
Line: 48 to 53
Type: potential_issue

Comment:
Consider adding error handling for file I/O and JSON parsing.

The function validates the JSON root type but doesn't handle FileNotFoundError, PermissionError, or json.JSONDecodeError. These exceptions will propagate uncaught and may crash the UI or show unhelpful error messages.


🛡️ Proposed fix to add error handling

 def _load_json(path: Path) -> dict[str, Any]:
-    raw = path.read_text(encoding="utf-8")
-    data = json.loads(raw)
+    try:
+        raw = path.read_text(encoding="utf-8")
+    except (FileNotFoundError, PermissionError) as e:
+        raise ValueError(f"Cannot read cheatsheet JSON: {path}") from e
+    try:
+        data = json.loads(raw)
+    except json.JSONDecodeError as e:
+        raise ValueError(f"Invalid JSON in cheatsheet file: {path}") from e
     if not isinstance(data, dict):
         raise ValueError(f"Invalid cheatsheet JSON root (expected object): {path}")
     return data

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/learn_factory.py around lines 48 - 53, The _load_json function should guard against file I/O and JSON parse errors: wrap the path.read_text and json.loads calls in a try/except that catches FileNotFoundError, PermissionError, OSError and json.JSONDecodeError; on error, raise a ValueError (or a custom exception) that includes the offending Path and the original exception message (use exception chaining) so callers of _load_json receive a clear, contextual error instead of an uncaught traceback.

============================================================================
File: src/ui/widgets/workstation/service_manager.py
Line: 1429 to 1443
Type: potential_issue

Comment:
Silent failure when start/stop command is not configured.

If start_cmd or stop_cmd is empty in the service config, the toggle handler silently returns without user feedback. Consider showing a toast to inform the user.



🔧 Proposed fix to add user feedback

     def _on_toggle(self, sw: Gtk.Switch, _pspec: Any) -> None:
         if self._updating_switch or self._busy:
             return
         cmd = str(self._service.get("start_cmd", "") or "") if sw.get_active() else str(self._service.get("stop_cmd", "") or "")
         if not cmd:
+            emit_utility_toast("No start/stop command configured for this service.", "warning")
+            # Revert the switch to previous state
+            self._updating_switch = True
+            sw.set_active(not sw.get_active())
+            self._updating_switch = False
             return

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/service_manager.py around lines 1429 - 1443, _in _on_toggle the handler silently returns when the selected service has no start_cmd/stop_cmd configured; instead, detect the missing cmd and provide user feedback by calling the existing UI notification flow (e.g. invoke _after_action with success=False and a message like "No start/stop command configured for this service" via GLib.idle_add) and ensure the switch state and _busy/_toggle sensitivity are left consistent; locate the logic in _on_toggle and replace the bare return when cmd is empty with an idle_add that calls _after_action(False, "") so the user sees a toast instead of a silent failure.

============================================================================
File: src/ui/widgets/workstation/learn_factory.py
Line: 94
Type: potential_issue

Comment:
Validate columns value before conversion.

If the JSON contains a non-numeric string for "columns" (e.g., "columns": "two"), int() will raise an unhandled ValueError.


🛡️ Proposed fix to add validation

-        self._columns_n: int = int(self._data.get("columns", 2))
+        raw_columns = self._data.get("columns", 2)
+        try:
+            self._columns_n: int = int(raw_columns)
+        except (ValueError, TypeError):
+            log.warning("Invalid 'columns' value %r, defaulting to 2", raw_columns)
+            self._columns_n = 2

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/learn_factory.py at line 94, self._columns_n initialization can raise ValueError if self._data.get("columns") returns a non-numeric string; update the code that sets _columns_n to validate and safely convert the value from self._data.get("columns", 2) before calling int(). For example, read the raw value into a local (e.g., raw_columns), check for None, numeric string, or int type (or attempt int() inside a try/except), and on failure fall back to the default 2 (or clamp/validate bounds) and log or handle the bad input; change the assignment of self._columns_n so it never lets a ValueError bubble up from int().

============================================================================
File: src/ui/widgets/workstation/learn_factory.py
Line: 236 to 240
Type: potential_issue

Comment:
Command injection vulnerability via unescaped shell command.

The cmd value from JSON is interpolated directly into a shell command without sanitization. A malicious or malformed JSON file with "command": "foo; rm -rf /" would execute arbitrary commands.


🔒 Proposed fix using shlex.quote

+import shlex
+
 # ... in _build_host_checks_if_any:
             if check_type == "command_exists":
                 cmd = str(item.get("command", "") or "")
                 if cmd:
-                    res = self._executor.run_sync(["sh", "-lc", f"command -v {cmd} >/dev/null 2>&1 && echo yes || echo no"])
+                    safe_cmd = shlex.quote(cmd)
+                    res = self._executor.run_sync(["sh", "-lc", f"command -v {safe_cmd} >/dev/null 2>&1 && echo yes || echo no"])
                     ok = bool(res.success and res.stdout.strip().lower() == "yes")

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/learn_factory.py around lines 236 - 240, The code interpolates unescaped JSON into a shell string in the check for "command_exists" (variable cmd) and calls self._executor.run_sync with a shell that can be exploited; change this to a safe check by using Python's safe API instead of shell interpolation — e.g., call shutil.which(cmd) (import shutil) to test existence or, if you must keep running via shell, escape cmd with shlex.quote before embedding, and update the logic around self._executor.run_sync/res to rely on the safe check (look for the block handling check_type == "command_exists" and the variables cmd and res).

============================================================================
File: src/ui/widgets/workstation/service_manager.py
Line: 1564 to 1575
Type: potential_issue

Comment:
Timer not cleaned up on widget destruction (resource leak).

The refresh timer created at line 1564 is never removed when the panel is destroyed. This causes the timer to continue firing, potentially calling refresh() on destroyed widgets which could cause crashes or warnings.



🔧 Proposed fix to clean up timer

         self._refresh_timer_id = GLib.timeout_add_seconds(5, self._refresh_loop)
 
+    def do_unrealize(self) -> None:
+        if self._refresh_timer_id:
+            GLib.source_remove(self._refresh_timer_id)
+            self._refresh_timer_id = 0
+        # Chain up to parent
+        Gtk.Box.do_unrealize(self)
+
     def _refresh_loop(self) -> bool:
         for row in self._rows:
             row.refresh()
         return True


Alternatively, check if the widget is still mapped in the refresh loop:

     def _refresh_loop(self) -> bool:
+        if not self.get_mapped():
+            self._refresh_timer_id = 0
+            return False  # Stop the timer
         for row in self._rows:
             row.refresh()
         return True

Prompt for AI Agent:
Verify each finding against the current code and only fix it if needed.

In @src/ui/widgets/workstation/service_manager.py around lines 1564 - 1575, The GLib timeout started in __init__ (stored in self._refresh_timer_id) is never removed, causing _refresh_loop to call row.refresh() after widget teardown; fix by removing the timer when the widget/panel is destroyed—attach a destroy handler or override the widget's destroy/do_destroy and call GLib.source_remove(self._refresh_timer_id) (and set self._refresh_timer_id = None/0) to cancel it, and optionally guard _refresh_loop to return False if timer id is missing; update references in the class where _refresh_timer_id, _refresh_loop, and reset_subsections are defined.

Review completed: 20 findings ✔