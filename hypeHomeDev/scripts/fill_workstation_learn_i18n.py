#!/usr/bin/env python3
"""One-shot helper: populate de/ar groups in nvim.json and docker.json from en (Phase 7.5).

Run from repo root: python3 scripts/fill_workstation_learn_i18n.py
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _walk_nvim_groups(groups: list[Any], lang: str) -> None:
    """Translate titles, descriptions, and table *value* cells in place."""
    for g in groups:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id", "") or "")
        if lang == "de":
            _nvim_de_group(gid, g)
        else:
            _nvim_ar_group(gid, g)
        items = g.get("items")
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            t = str(it.get("type", "") or "")
            if t == "table":
                rows = it.get("rows")
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    if lang == "de":
                        _nvim_de_table_row(gid, row)
                    else:
                        _nvim_ar_table_row(gid, row)


def _nvim_de_group(gid: str, g: dict[str, Any]) -> None:
    m = _NVIM_DE_GROUPS.get(gid)
    if m:
        g["title"] = m[0]
        g["description"] = m[1]


def _nvim_ar_group(gid: str, g: dict[str, Any]) -> None:
    m = _NVIM_AR_GROUPS.get(gid)
    if m:
        g["title"] = m[0]
        g["description"] = m[1]


def _nvim_de_table_row(gid: str, row: dict[str, Any]) -> None:
    key = str(row.get("key", ""))
    v = _NVIM_DE_VALUES.get((gid, key))
    if v is not None:
        row["value"] = v


def _nvim_ar_table_row(gid: str, row: dict[str, Any]) -> None:
    key = str(row.get("key", ""))
    v = _NVIM_AR_VALUES.get((gid, key))
    if v is not None:
        row["value"] = v


_NVIM_DE_GROUPS = {
    "intro": ("Neovim-Spickzettel", "Komplette Befehlsreferenz — durchsuchbar, schnell, kostenlos."),
    "modes": ("Modi", "Modi betreten und verlassen"),
    "nav_basic": ("Navigation — Grundlagen", "Cursor bewegen"),
    "editing": ("Bearbeiten", "Text ändern und wiederholen"),
    "search_replace": ("Suchen und Ersetzen", "Muster mit / und :s"),
    "splits": ("Splits und Fenster", "Tastenfolge Strg+w"),
    "tabs": ("Tabs", "Tab-Seiten"),
    "files_buffers": ("Dateien und Puffer", "Bearbeiten, speichern, beenden"),
    "visual_mode": ("Visueller Modus", "Nach v, V oder Strg+v"),
    "nvim_specific": ("Neovim-spezifisch", "Eingebaute Funktionen und gängige Plugin-Einstiege"),
}

_NVIM_AR_GROUPS = {
    "intro": ("مفكرة Neovim", "مرجع أوامر كامل — قابل للبحث وسريع ومجاني."),
    "modes": ("الأوضاع", "دخول الأوضاع والخروج منها"),
    "nav_basic": ("التنقل — أساسيات", "تحريك المؤشر"),
    "editing": ("التحرير", "تغيير النص وتكرار العمليات"),
    "search_replace": ("البحث والاستبدال", "أنماط ‎/‎ و ‎:s‎"),
    "splits": ("النوافذ المقسّمة", "عائلة المفاتيح ‎Ctrl+w‎"),
    "tabs": ("العلامات", "صفحات التبويب"),
    "files_buffers": ("الملفات والمخازن المؤقتة", "تحرير وحفظ وخروج"),
    "visual_mode": ("الوضع المرئي", "بعد ‎v‎ أو ‎V‎ أو ‎Ctrl+v‎"),
    "nvim_specific": ("خاص بـ Neovim", "مدمجات ونقاط دخول شائعة للإضافات"),
}

_NVIM_DE_VALUES: dict[tuple[str, str], str] = {
    ("modes", "i"): "Vor Cursor einfügen",
    ("modes", "a"): "Nach Cursor einfügen",
    ("modes", "v / V / Ctrl+v"): "Visuell Zeichen / Zeile / Block",
    ("modes", ":"): "Befehlsmodus",
    ("modes", "Esc / Ctrl+["): "Zurück nach Normal",
    ("nav_basic", "h j k l"): "← ↓ ↑ →",
    ("nav_basic", "w / b / e"): "Wortbewegungen",
    ("nav_basic", "0 / ^ / $"): "Zeilenanfang / erstes Nicht-Leerzeichen / Ende",
    ("nav_basic", "gg / G"): "Dateianfang / Dateiende",
    ("nav_basic", "Ctrl+d / Ctrl+u"): "Halbe Seite runter / hoch",
    ("editing", "x / dd / dw"): "Zeichen / Zeile / Wort löschen",
    ("editing", "yy / yw / p"): "Zeile/Wort kopieren und einfügen",
    ("editing", "u / Ctrl+r"): "Rückgängig / Wiederholen",
    ("editing", "cc / cw / C"): "Zeile / Wort / bis Zeilenende ändern",
    ("editing", "."): "Letzte Änderung wiederholen",
    ("search_replace", "/pattern ?pattern"): "Vorwärts / rückwärts suchen",
    ("search_replace", "n / N"): "Nächster / vorheriger Treffer",
    ("search_replace", ":s/old/new/g"): "Alle auf aktueller Zeile ersetzen",
    ("search_replace", ":%s/old/new/gc"): "Alle mit Bestätigung ersetzen",
    ("search_replace", ":noh"): "Suchhervorhebung löschen",
    ("splits", ":sp / :vsp"): "Horizontal / vertikal teilen",
    ("splits", "Ctrl+w h/j/k/l"): "Zwischen Splits wechseln",
    ("splits", "Ctrl+w ="): "Split-Größen angleichen",
    ("splits", "Ctrl+w q"): "Split schließen",
    ("tabs", ":tabnew"): "Neuen Tab öffnen",
    ("tabs", "gt / gT"): "Nächster / vorheriger Tab",
    ("tabs", ":tabclose / :tabonly"): "Aktuellen / andere schließen",
    ("files_buffers", ":e {file}"): "Datei bearbeiten",
    ("files_buffers", ":w / :wq / :x"): "Speichern / speichern+beenden",
    ("files_buffers", ":q / :q!"): "Beenden / ohne Speichern beenden",
    ("files_buffers", ":ls / :buffers / :bd"): "Puffer auflisten / verwalten",
    ("visual_mode", "v / V / Ctrl+v + motion"): "Zeichen/Zeilen/Blöcke wählen",
    ("visual_mode", "d / y / c"): "Auswahl löschen / kopieren / ändern",
    ("visual_mode", "> / <"): "Einrücken / Ausrücken",
    ("visual_mode", "gv"): "Letzte visuelle Auswahl erneut",
    ("nvim_specific", ":checkhealth"): "Diagnose ausführen",
    ("nvim_specific", ":terminal"): "Integriertes Terminal öffnen",
    ("nvim_specific", ":Lazy / :Mason"): "Plugin-/LSP-Manager öffnen",
    ("nvim_specific", "gd / grr / gra"): "LSP: Definition / Referenzen / Code-Aktion",
    ("nvim_specific", "]d / [d"): "Nächste / vorherige Diagnose",
}

_NVIM_AR_VALUES: dict[tuple[str, str], str] = {
    ("modes", "i"): "إدراج قبل المؤشر",
    ("modes", "a"): "إدراج بعد المؤشر",
    ("modes", "v / V / Ctrl+v"): "مرئي حرف/سطر/كتلة",
    ("modes", ":"): "وضع الأوامر",
    ("modes", "Esc / Ctrl+["): "العودة إلى العادي",
    ("nav_basic", "h j k l"): "← ↓ ↑ →",
    ("nav_basic", "w / b / e"): "حركات الكلمات",
    ("nav_basic", "0 / ^ / $"): "بداية السطر / أول غير فراغ / النهاية",
    ("nav_basic", "gg / G"): "بداية الملف / نهاية الملف",
    ("nav_basic", "Ctrl+d / Ctrl+u"): "نصف صفحة لأسفل / لأعلى",
    ("editing", "x / dd / dw"): "حذف حرف / سطر / كلمة",
    ("editing", "yy / yw / p"): "نسخ سطر/كلمة ولصق",
    ("editing", "u / Ctrl+r"): "تراجع / إعادة",
    ("editing", "cc / cw / C"): "تغيير سطر / كلمة / حتى النهاية",
    ("editing", "."): "تكرار آخر تغيير",
    ("search_replace", "/pattern ?pattern"): "بحث للأمام / للخلف",
    ("search_replace", "n / N"): "التطابق التالي / السابق",
    ("search_replace", ":s/old/new/g"): "استبدال الكل في السطر الحالي",
    ("search_replace", ":%s/old/new/gc"): "استبدال الكل مع تأكيد",
    ("search_replace", ":noh"): "مسح تمييز البحث",
    ("splits", ":sp / :vsp"): "تقسيم أفقي / عمودي",
    ("splits", "Ctrl+w h/j/k/l"): "التنقل بين الأقسام",
    ("splits", "Ctrl+w ="): "تسوية أحجام الأقسام",
    ("splits", "Ctrl+w q"): "إغلاق القسم",
    ("tabs", ":tabnew"): "علامة تبويب جديدة",
    ("tabs", "gt / gT"): "التالي / السابق",
    ("tabs", ":tabclose / :tabonly"): "إغلاق الحالي / الباقي",
    ("files_buffers", ":e {file}"): "تحرير ملف",
    ("files_buffers", ":w / :wq / :x"): "حفظ / حفظ وخروج",
    ("files_buffers", ":q / :q!"): "خروج / خروج دون حفظ",
    ("files_buffers", ":ls / :buffers / :bd"): "عرض/إدارة المخازن",
    ("visual_mode", "v / V / Ctrl+v + motion"): "تحديد أحرف/أسطر/كتل",
    ("visual_mode", "d / y / c"): "حذف / نسخ / تغيير التحديد",
    ("visual_mode", "> / <"): "زيادة/إنقاص المسافة البادئة",
    ("visual_mode", "gv"): "إعادة تحديد آخر تحديد مرئي",
    ("nvim_specific", ":checkhealth"): "تشغيل فحوصات الصحة",
    ("nvim_specific", ":terminal"): "فتح طرفية مدمجة",
    ("nvim_specific", ":Lazy / :Mason"): "فتح مديري الإضافات/LSP",
    ("nvim_specific", "gd / grr / gra"): "LSP: تعريف/مراجع/إجراء كود",
    ("nvim_specific", "]d / [d"): "التشخيص التالي / السابق",
}


def _docker_translate_item(it: dict[str, Any], lang: str) -> None:
    t = str(it.get("type", "") or "")
    if t == "link":
        lab = str(it.get("label", "") or "")
        u = it.get("url", "")
        if lang == "de":
            x = _DOCKER_DE_LINKS.get(lab)
            if x:
                it["label"] = x
        else:
            x = _DOCKER_AR_LINKS.get(lab)
            if x:
                it["label"] = x
        _ = u
    elif t == "text":
        tx = str(it.get("text", "") or "")
        if lang == "de":
            y = _DOCKER_DE_TEXT.get(tx)
            if y:
                it["text"] = y
        else:
            y = _DOCKER_AR_TEXT.get(tx)
            if y:
                it["text"] = y
    elif t == "table":
        rows = it.get("rows")
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key", "") or "")
            if lang == "de":
                z = _DOCKER_DE_TABLE.get(key)
                if z:
                    row["value"] = z
            else:
                z = _DOCKER_AR_TABLE.get(key)
                if z:
                    row["value"] = z


_DOCKER_DE_LINKS = {
    "Docker Documentation": "Docker-Dokumentation",
    "Docker Compose Docs": "Docker-Compose-Dokumentation",
    "Migration Guide": "Migrationsleitfaden",
}

_DOCKER_AR_LINKS = {
    "Docker Documentation": "توثيق Docker",
    "Docker Compose Docs": "توثيق Docker Compose",
    "Migration Guide": "دليل الترحيل",
}

_DOCKER_DE_TEXT = {
    "Docker Compose is now integrated into Docker. V1: docker-compose ARG  |  V2: docker compose ARG": (
        "Docker Compose ist jetzt in Docker integriert. V1: docker-compose ARG  |  V2: docker compose ARG"
    ),
    "build from Dockerfile": "Build aus Dockerfile",
    "build from image": "Build aus Image",
    "ports: publish to host   |   expose: only to linked services": (
        "ports: auf Host veröffentlichen   |   expose: nur für verlinkte Services"
    ),
    "See docker create for full options list": "Alle Optionen: docker create",
    "restart: always | on-failure | no (default) | unless-stopped": (
        "restart: always | on-failure | no (Standard) | unless-stopped"
    ),
    "specifying user or user:group with ids": "Benutzer oder user:group mit IDs",
}

_DOCKER_AR_TEXT = {
    "Docker Compose is now integrated into Docker. V1: docker-compose ARG  |  V2: docker compose ARG": (
        "أصبح Docker Compose مدمجًا في Docker. V1: docker-compose ARG  |  V2: docker compose ARG"
    ),
    "build from Dockerfile": "بناء من Dockerfile",
    "build from image": "بناء من صورة",
    "ports: publish to host   |   expose: only to linked services": (
        "ports: نشر على المضيف   |   expose: للخدمات المرتبطة فقط"
    ),
    "See docker create for full options list": "راجع docker create لقائمة الخيارات",
    "restart: always | on-failure | no (default) | unless-stopped": (
        "restart: always | on-failure | no (افتراضي) | unless-stopped"
    ),
    "specifying user or user:group with ids": "تحديد مستخدم أو user:group بالمعرفات",
}

_DOCKER_DE_TABLE = {
    "docker compose version": "Version anzeigen",
    "docker compose config": "Konfiguration prüfen und anzeigen",
    "docker compose start": "Services starten",
    "docker compose stop": "Services stoppen",
    "docker compose restart": "Services neu starten",
    "docker compose run": "Einmaligen Befehl ausführen",
    "docker compose create": "Container erzeugen",
    "docker compose attach": "An laufenden Container anbinden",
    "docker compose pause": "Services anhalten",
    "docker compose unpause": "Services fortsetzen",
    "docker compose wait": "Auf Bereitschaft warten",
    "docker compose up": "Container erzeugen und starten",
    "docker compose down": "Container stoppen und entfernen",
    "docker compose ps": "Container auflisten",
    "docker compose top": "Laufende Prozesse anzeigen",
    "docker compose events": "Service-Ereignisse streamen",
    "docker compose logs": "Service-Logs anzeigen",
    "docker compose images": "Service-Images auflisten",
    "docker compose build": "Service-Images bauen",
    "docker compose push": "Service-Images pushen",
    "docker compose cp": "Dateien aus/ in Container kopieren",
    "docker compose exec": "Befehl im Container ausführen",
    "docker build -t 'app/name' .": "Image aus Dockerfile erstellen",
    "docker run [options] IMAGE": "Befehl im Image ausführen",
    "docker ps": "Laufende Container auflisten",
    "docker ps -a": "Alle Container auflisten",
    "docker logs $ID": "Container-Logs anzeigen",
    "docker logs -f $ID": "Log-Ausgabe folgen",
    "docker exec CONTAINER CMD": "Befehl im Container ausführen",
    "docker start [options] CONTAINER": "Container starten",
    "docker stop [options] CONTAINER": "Container stoppen",
    "docker kill $ID": "Container hart beenden",
    "docker images": "Images auflisten",
    "docker rmi IMAGE": "Image löschen",
}

_DOCKER_AR_TABLE = {
    "docker compose version": "عرض الإصدار",
    "docker compose config": "التحقق من الإعداد وعرضه",
    "docker compose start": "تشغيل الخدمات",
    "docker compose stop": "إيقاف الخدمات",
    "docker compose restart": "إعادة تشغيل الخدمات",
    "docker compose run": "تشغيل أمر لمرة واحدة",
    "docker compose create": "إنشاء الحاويات",
    "docker compose attach": "الاتصال بحاوية تعمل",
    "docker compose pause": "إيقاف الخدمات مؤقتًا",
    "docker compose unpause": "استئناف الخدمات",
    "docker compose wait": "انتظار الجاهزية",
    "docker compose up": "إنشاء الحاويات وتشغيلها",
    "docker compose down": "إيقاف الحاويات وإزالتها",
    "docker compose ps": "عرض الحاويات",
    "docker compose top": "عرض العمليات",
    "docker compose events": "بث أحداث الخدمة",
    "docker compose logs": "عرض سجلات الخدمة",
    "docker compose images": "عرض صور الخدمة",
    "docker compose build": "بناء صور الخدمة",
    "docker compose push": "دفع صور الخدمة",
    "docker compose cp": "نسخ ملفات من/إلى الحاوية",
    "docker compose exec": "تنفيذ أمر داخل الحاوية",
    "docker build -t 'app/name' .": "إنشاء صورة من Dockerfile",
    "docker run [options] IMAGE": "تشغيل أمر في الصورة",
    "docker ps": "عرض الحاويات العاملة",
    "docker ps -a": "عرض كل الحاويات",
    "docker logs $ID": "عرض سجلات الحاوية",
    "docker logs -f $ID": "متابعة السجل",
    "docker exec CONTAINER CMD": "تنفيذ أمر في الحاوية",
    "docker start [options] CONTAINER": "تشغيل الحاوية",
    "docker stop [options] CONTAINER": "إيقاف الحاوية",
    "docker kill $ID": "إيقاف قسري",
    "docker images": "عرض الصور",
    "docker rmi IMAGE": "حذف الصورة",
}

_DOCKER_DE_GROUPS = {
    "intro": ("Docker-Compose-Spickzettel", "Kurzreferenz für Compose-Befehle und Konfiguration."),
    "basic": ("Einfaches Beispiel", "docker-compose.yml"),
    "version": ("Version", "Migration v1 → v2"),
    "cmds1": ("Befehle", "Häufige Operationen"),
    "cmds2": ("Befehle", "Weitere Operationen"),
    "build": ("Dienst-Konfiguration", "Build"),
    "ports": ("Dienst-Konfiguration", "Ports & Freigabe"),
    "commands": ("Dienst-Konfiguration", "Befehle"),
    "environment": ("Dienst-Konfiguration", "Umgebungsvariablen"),
    "dependencies": ("Dienst-Konfiguration", "Abhängigkeiten"),
    "other_options": ("Dienst-Konfiguration", "Weitere Optionen"),
    "labels": ("Erweiterte Funktionen", "Labels"),
    "dns": ("Erweiterte Funktionen", "DNS-Server"),
    "devices": ("Erweiterte Funktionen", "Geräte"),
    "ext_links": ("Erweiterte Funktionen", "Externe Links"),
    "healthcheck": ("Erweiterte Funktionen", "Healthcheck"),
    "hosts": ("Erweiterte Funktionen", "Hosts & Netzwerk"),
    "volumes": ("Erweiterte Funktionen", "Volumes"),
    "user": ("Erweiterte Funktionen", "Benutzer"),
    "docker_cli": ("Docker-CLI", "Kernbefehle"),
    "create_run": ("Docker-CLI", "Erzeugen & ausführen"),
    "manage": ("Docker-CLI", "Container verwalten"),
    "cleanup": ("Docker-CLI", "Aufräumen"),
}

_DOCKER_AR_GROUPS = {
    "intro": ("مفكرة Docker Compose", "مرجع سريع لأوامر وإعدادات Compose."),
    "basic": ("مثال أساسي", "docker-compose.yml"),
    "version": ("الإصدار", "الترحيل من v1 إلى v2"),
    "cmds1": ("الأوامر", "عمليات شائعة"),
    "cmds2": ("الأوامر", "المزيد من العمليات"),
    "build": ("إعداد الخدمة", "البناء"),
    "ports": ("إعداد الخدمة", "المنافذ والتعرّض"),
    "commands": ("إعداد الخدمة", "الأوامر"),
    "environment": ("إعداد الخدمة", "متغيرات البيئة"),
    "dependencies": ("إعداد الخدمة", "التبعيات"),
    "other_options": ("إعداد الخدمة", "خيارات أخرى"),
    "labels": ("ميزات متقدمة", "التسميات"),
    "dns": ("ميزات متقدمة", "خوادم DNS"),
    "devices": ("ميزات متقدمة", "الأجهزة"),
    "ext_links": ("ميزات متقدمة", "روابط خارجية"),
    "healthcheck": ("ميزات متقدمة", "فحص الصحة"),
    "hosts": ("ميزات متقدمة", "المضيفون والشبكة"),
    "volumes": ("ميزات متقدمة", "المجلدات المستمرة"),
    "user": ("ميزات متقدمة", "المستخدم"),
    "docker_cli": ("واجهة Docker", "أوامر أساسية"),
    "create_run": ("واجهة Docker", "إنشاء وتشغيل"),
    "manage": ("واجهة Docker", "إدارة الحاويات"),
    "cleanup": ("واجهة Docker", "تنظيف"),
}


def _docker_apply(groups: list[Any], lang: str) -> None:
    for g in groups:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id", "") or "")
        if lang == "de":
            meta = _DOCKER_DE_GROUPS.get(gid)
        else:
            meta = _DOCKER_AR_GROUPS.get(gid)
        if meta:
            g["title"] = meta[0]
            g["description"] = meta[1]
        items = g.get("items")
        if not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, dict):
                _docker_translate_item(it, lang)


def main() -> None:
    nvim_path = ROOT / "src/ui/widgets/workstation/data/nvim.json"
    data = json.loads(nvim_path.read_text(encoding="utf-8"))
    en = data["i18n"]["en"]["groups"]
    data["i18n"]["de"]["groups"] = copy.deepcopy(en)
    _walk_nvim_groups(data["i18n"]["de"]["groups"], "de")
    data["i18n"]["ar"]["groups"] = copy.deepcopy(en)
    _walk_nvim_groups(data["i18n"]["ar"]["groups"], "ar")
    nvim_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    docker_path = ROOT / "src/ui/widgets/workstation/data/docker.json"
    ddata = json.loads(docker_path.read_text(encoding="utf-8"))
    eng = ddata["i18n"]["en"]["groups"]
    ddata["i18n"]["de"]["groups"] = copy.deepcopy(eng)
    _docker_apply(ddata["i18n"]["de"]["groups"], "de")
    ddata["i18n"]["ar"]["groups"] = copy.deepcopy(eng)
    _docker_apply(ddata["i18n"]["ar"]["groups"], "ar")
    docker_path.write_text(json.dumps(ddata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Updated nvim.json and docker.json (de/ar groups).")


if __name__ == "__main__":
    main()
