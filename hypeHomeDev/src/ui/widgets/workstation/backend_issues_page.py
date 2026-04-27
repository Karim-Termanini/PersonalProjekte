"""Backend JVM/Spring deploy tips (Tools → Install → Backend; EN/DE/AR)."""

from __future__ import annotations

from typing import Any

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

from ui.utility_feedback import emit_utility_toast  # noqa: E402
from ui.widgets.workstation.nav_helper import copy_plain_text_to_clipboard  # noqa: E402

_LANG_CODES = ("en", "de", "ar")

_UI: dict[str, dict[str, str]] = {
    "en": {
        "lang_row_title": "Language",
        "intro_title": "Backend and deploy issues",
        "intro_desc": (
            "Quick fixes you can paste into your project or terminal. "
            "Typical case: Spring Boot fails on startup with two beans of the same name "
            "(for example passwordEncoder) because two @Configuration classes both register one."
        ),
        "spring_title": "Spring Boot — duplicate @Bean (profiles)",
        "spring_desc": (
            "Load only one security configuration per profile. "
            "Put production/default beans on @Profile(\"!dev\") and dev-only beans on @Profile(\"dev\")."
        ),
        "spring_main_java": "SecurityConfig (non-dev)",
        "spring_main_sub": "@Profile(\"!dev\") + passwordEncoder bean",
        "spring_dev_java": "SecurityConfigDev (dev)",
        "spring_dev_sub": "@Profile(\"dev\") + passwordEncoder bean",
        "override_title": "Spring — allow bean overriding (use sparingly)",
        "override_desc": (
            "If you intentionally want one definition to replace another, you can enable overriding. "
            "Prefer fixing duplicate @Bean definitions when possible."
        ),
        "prop_row": "application.properties",
        "prop_sub": "spring.main.allow-bean-definition-overriding=true",
        "yml_row": "application.yml",
        "yml_sub": "spring.main.allow-bean-definition-overriding: true",
        "docker_title": "Docker Compose — rebuild and restart one service",
        "docker_desc": "After changing Java code, rebuild the image and recreate the container.",
        "docker_row_title": "docker compose",
        "docker_row_sub": "build + up --force-recreate (replace service name)",
        "k8s_title": "Kubernetes — stop / start a deployment",
        "k8s_desc": "Scale to zero, then back up, or roll out a new image after CI builds it.",
        "k8s_row_title": "kubectl scale",
        "k8s_row_sub": "Edit deployment name and namespace before running.",
    },
    "de": {
        "lang_row_title": "Sprache",
        "intro_title": "Backend und Deployment — typische Probleme",
        "intro_desc": (
            "Schnelle Fixes zum Einfügen ins Projekt oder Terminal. "
            "Häufiger Fall: Spring Boot startet nicht, weil zwei Beans gleichen Namens existieren "
            "(z. B. passwordEncoder), weil zwei @Configuration-Klassen jeweils eines anlegen."
        ),
        "spring_title": "Spring Boot — doppeltes @Bean (Profile)",
        "spring_desc": (
            "Pro Profil nur eine Security-Konfiguration laden. "
            "Produktion/Default mit @Profile(\"!dev\"), nur-Dev mit @Profile(\"dev\")."
        ),
        "spring_main_java": "SecurityConfig (nicht-dev)",
        "spring_main_sub": "@Profile(\"!dev\") + passwordEncoder-Bean",
        "spring_dev_java": "SecurityConfigDev (dev)",
        "spring_dev_sub": "@Profile(\"dev\") + passwordEncoder-Bean",
        "override_title": "Spring — Bean-Überschreibung erlauben (sparsam nutzen)",
        "override_desc": (
            "Wenn eine Definition absichtlich eine andere ersetzen soll, kann man Überschreiben aktivieren. "
            "Besser sind saubere @Bean-Definitionen ohne Duplikate."
        ),
        "prop_row": "application.properties",
        "prop_sub": "spring.main.allow-bean-definition-overriding=true",
        "yml_row": "application.yml",
        "yml_sub": "spring.main.allow-bean-definition-overriding: true",
        "docker_title": "Docker Compose — Image neu bauen und Dienst neu starten",
        "docker_desc": "Nach Java-Änderungen Image bauen und Container neu erstellen.",
        "docker_row_title": "docker compose",
        "docker_row_sub": "build + up --force-recreate (Servicenamen anpassen)",
        "k8s_title": "Kubernetes — Deployment stoppen / starten",
        "k8s_desc": "Auf null skalieren und wieder hoch, oder nach neuem Image ausrollen.",
        "k8s_row_title": "kubectl scale",
        "k8s_row_sub": "Deployment-Name und Namespace vor dem Ausführen anpassen.",
    },
    "ar": {
        "lang_row_title": "اللغة",
        "intro_title": "مشاكل الخلفية والنشر",
        "intro_desc": (
            "إصلاحات جاهزة للنسخ إلى المشروع أو الطرفية. "
            "حالة شائعة: فشل تشغيل Spring Boot بسبب تعريفين لنفس الاسم "
            "(مثل passwordEncoder) لأن صنفي @Configuration يسجّلان واحداً."
        ),
        "spring_title": "Spring Boot — تعريف @Bean مكرر (الملفات الشخصية)",
        "spring_desc": (
            "حمّل تكوين أمان واحداً لكل ملف شخصي. "
            "ضع الإنتاج/الافتراضي على @Profile(\"!dev\") ووضع التطوير على @Profile(\"dev\")."
        ),
        "spring_main_java": "SecurityConfig (غير dev)",
        "spring_main_sub": "@Profile(\"!dev\") + تعريف passwordEncoder",
        "spring_dev_java": "SecurityConfigDev (dev)",
        "spring_dev_sub": "@Profile(\"dev\") + تعريف passwordEncoder",
        "override_title": "Spring — السماح بتجاوز التعريف (بحذر)",
        "override_desc": (
            "إذا أردت عمداً أن يستبدل تعريف آخر، يمكن تفعيل التجاوز. "
            "الأفضل إصلاح التعريفات المكررة عند الإمكان."
        ),
        "prop_row": "application.properties",
        "prop_sub": "spring.main.allow-bean-definition-overriding=true",
        "yml_row": "application.yml",
        "yml_sub": "spring.main.allow-bean-definition-overriding: true",
        "docker_title": "Docker Compose — إعادة البناء وإعادة تشغيل خدمة",
        "docker_desc": "بعد تعديل كود Java، أعد بناء الصورة وأعد إنشاء الحاوية.",
        "docker_row_title": "docker compose",
        "docker_row_sub": "build + up --force-recreate (غيّر اسم الخدمة)",
        "k8s_title": "Kubernetes — إيقاف / تشغيل نشر",
        "k8s_desc": "تصغير النسخ إلى صفر ثم الرفع، أو نشر صورة جديدة بعد البناء.",
        "k8s_row_title": "kubectl scale",
        "k8s_row_sub": "عدّل اسم النشر والمساحة الاسمية قبل التشغيل.",
    },
}

_SNIPPETS: dict[str, dict[str, str]] = {
    "spring_main_java": """@Configuration
@EnableWebSecurity
@Profile("!dev")
public class SecurityConfig {
    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}""",
    "spring_dev_java": """@Configuration
@EnableWebSecurity
@Profile("dev")
public class SecurityConfigDev {
    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}""",
    "prop": "spring.main.allow-bean-definition-overriding=true",
    "yml": """spring:
  main:
    allow-bean-definition-overriding: true""",
    "docker": """docker compose build --no-cache app
docker compose up -d --force-recreate app""",
    "k8s": """kubectl scale deployment hrms-api --replicas=0 -n your-namespace
kubectl scale deployment hrms-api --replicas=1 -n your-namespace""",
}


def _copy_text(text: str) -> None:
    if copy_plain_text_to_clipboard(text):
        emit_utility_toast("Copied to clipboard.", "info", timeout=3)
    else:
        emit_utility_toast("Could not copy to clipboard.", "error")


def _add_copy_row(group: Adw.PreferencesGroup, title: str, subtitle: str, copy_text: str) -> None:
    row = Adw.ActionRow(title=title, subtitle=subtitle)
    btn = Gtk.Button(label="Copy")
    btn.connect("clicked", lambda _b, t=copy_text: _copy_text(t))
    row.add_suffix(btn)
    group.add(row)


class BackendIssuesPage(Gtk.Box):
    """Copyable fixes for duplicate Spring beans, overrides, Docker, and Kubernetes."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14, **kwargs)
        self.add_css_class("workstation-learn-colored-titles")
        self.set_margin_start(14)
        self.set_margin_end(14)
        self.set_margin_top(10)
        self.set_margin_bottom(18)

        self._lang = "en"
        self._main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self._lang_row = Adw.ComboRow()
        self._lang_row.set_title(_UI["en"]["lang_row_title"])
        self._lang_row.set_model(Gtk.StringList.new(["English", "Deutsch", "العربية"]))
        self._lang_row.set_selected(0)
        lang_group = Adw.PreferencesGroup()
        lang_group.add_css_class("bash-cheatsheet-group")
        lang_group.add(self._lang_row)

        self.append(lang_group)
        self.append(self._main)
        self._lang_row.connect("notify::selected", self._on_lang_selected)
        self._rebuild()

    def _on_lang_selected(self, row: Adw.ComboRow, *_args: Any) -> None:
        i = row.get_selected()
        if i < 0 or i >= len(_LANG_CODES):
            return
        lang = _LANG_CODES[i]
        if lang == self._lang:
            return
        self._lang = lang
        self._rebuild()

    def _rebuild(self) -> None:
        while self._main.get_first_child():
            self._main.remove(self._main.get_first_child())
        t = _UI[self._lang]

        intro = Adw.PreferencesGroup(title=t["intro_title"], description=t["intro_desc"])
        self._main.append(intro)

        spring = Adw.PreferencesGroup(title=t["spring_title"], description=t["spring_desc"])
        _add_copy_row(
            spring,
            t["spring_main_java"],
            t["spring_main_sub"],
            _SNIPPETS["spring_main_java"],
        )
        _add_copy_row(
            spring,
            t["spring_dev_java"],
            t["spring_dev_sub"],
            _SNIPPETS["spring_dev_java"],
        )
        self._main.append(spring)

        ov = Adw.PreferencesGroup(title=t["override_title"], description=t["override_desc"])
        _add_copy_row(ov, t["prop_row"], t["prop_sub"], _SNIPPETS["prop"])
        _add_copy_row(ov, t["yml_row"], t["yml_sub"], _SNIPPETS["yml"])
        self._main.append(ov)

        docker = Adw.PreferencesGroup(title=t["docker_title"], description=t["docker_desc"])
        _add_copy_row(
            docker,
            t["docker_row_title"],
            t["docker_row_sub"],
            _SNIPPETS["docker"],
        )
        self._main.append(docker)

        k8s = Adw.PreferencesGroup(title=t["k8s_title"], description=t["k8s_desc"])
        _add_copy_row(
            k8s,
            t["k8s_row_title"],
            t["k8s_row_sub"],
            _SNIPPETS["k8s"],
        )
        self._main.append(k8s)

        self._lang_row.set_title(t["lang_row_title"])
