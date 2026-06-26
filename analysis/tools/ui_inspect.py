"""ui_inspect.py — analysis_ui_inspect Tool-Handler.

UI-Element-Analyse einer Webseite mittels Chrome DevTools MCP.
Nutzt Accessibility Tree + DOM-Inspektion + Console/Network-Check.
Graceful Degradation: kein MCP -> Instructions.
"""

from __future__ import annotations

from scout._fmt import fmt_err, fmt_ok


def analysis_ui_inspect_tool(args: dict, **kwargs) -> str:
    """Handler fuer analysis_ui_inspect — UI-Element-Analyse einer Webseite."""
    url = args.get("url", "").strip()
    if not url:
        return fmt_err("url ist erforderlich")

    include_dom = args.get("include_dom", True)
    check_presence = args.get("check_presence", False)

    # Pruefen ob Chrome DevTools MCP verfuegbar ist
    try:
        from tools.registry import registry
        mcp_available = registry.get_entry(
            "mcp_chrome_devtools_list_console_messages"
        ) is not None
    except (ImportError, AttributeError):
        mcp_available = False

    if not mcp_available:
        return fmt_ok({
            "url": url,
            "mcp_available": False,
            "instruction": (
                "Chrome DevTools MCP ist nicht verfuegbar. "
                "Nutze manuell: browser_navigate(url), browser_snapshot(), "
                "browser_console(expression='...'), "
                "browser_vision(question='...').",
            ),
        })

    # MCP ist verfuegbar -> UI-Analyse durchfuehren
    try:
        result = _run_ui_inspection(url, include_dom, check_presence)
        return result
    except Exception as e:
        return fmt_err(f"UI-Inspektion fehlgeschlagen: {e}")


def _run_ui_inspection(url: str, include_dom: bool,
                       check_presence: bool) -> str:
    """Fuehrt die UI-Inspektion via MCP-Tools durch."""
    from tools.registry import registry

    # 1. Navigation zur URL
    nav_result = _call_mcp(registry, "mcp_chrome_devtools_navigate_page",
                           {"url": url})

    # 2. A11y Tree Snapshot (alle UI-Elemente)
    snapshot = _call_mcp(registry, "mcp_chrome_devtools_take_snapshot", {})

    # 3. Console Messages (Errors + Warnings)
    console = _call_mcp(registry,
                        "mcp_chrome_devtools_list_console_messages", {})

    # 4. Network Requests (4xx/5xx)
    network = _call_mcp(registry,
                        "mcp_chrome_devtools_list_network_requests", {})

    # 5. Optionale DOM-Inspektion
    dom_info = ""
    if include_dom:
        dom_info = _inspect_dom(registry)

    # 6. Optionale Presence-Checks
    presence_info = ""
    if check_presence:
        presence_info = _check_ui_presence(registry)

    return fmt_ok({
        "url": url,
        "mcp_available": True,
        "navigation": nav_result,
        "a11y_tree": snapshot,
        "console_messages": console,
        "network_requests": network,
        "dom_info": dom_info,
        "presence_check": presence_info,
        "instruction": (
            f"UI-Inspektion fuer {url} abgeschlossen.\n"
            f"A11y Tree: UI-Elemente mit Rollen und Hierarchie.\n"
            f"Console: {len(console or '')} Zeilen\n"
            f"Network: {len(network or '')} Requests\n"
        ),
    })


def _call_mcp(registry, tool_name: str, args: dict) -> str:
    """Ruft ein MCP-Tool via Registry-Dispatch auf.

    Args:
        registry: Hermes Tool Registry.
        tool_name: Name des MCP-Tools (mit mcp_ Prefix).
        args: Parameter fuer das Tool.

    Returns:
        Ergebnis-Text oder Fehlermeldung.
    """
    entry = registry.get_entry(tool_name)
    if entry is None:
        return f"{tool_name}: nicht verfuegbar"
    try:
        result = entry.handler(args)
        if isinstance(result, str):
            return result[:1000]  # Nicht zu lang
        return str(result)[:1000]
    except Exception as e:
        return f"{tool_name}: {e}"


def _inspect_dom(registry) -> str:
    """Fuehrt DOM-Inspektion per evaluate_script durch.

    Extrahiert: Anzahl Elemente pro Tag, sichtbare vs. versteckte,
    Inputs, Buttons, Links, Bilder, Ueberschriften.
    """
    js_code = """() => {
        const all = document.querySelectorAll('*');
        const tags = {};
        let visible = 0, hidden = 0;
        let inputs = 0, buttons = 0, links = 0, images = 0, headings = 0;

        for (const el of all) {
            const tag = el.tagName.toLowerCase();
            tags[tag] = (tags[tag] || 0) + 1;

            const style = window.getComputedStyle(el);
            const isVisible = style.display !== 'none' &&
                              style.visibility !== 'hidden' &&
                              el.offsetWidth > 0 && el.offsetHeight > 0;
            if (isVisible) visible++; else hidden++;

            if (tag === 'input' || tag === 'textarea' || tag === 'select') inputs++;
            else if (tag === 'button') buttons++;
            else if (tag === 'a') links++;
            else if (tag === 'img') images++;
            else if (/^h[1-6]$/.test(tag)) headings++;
        }

        return JSON.stringify({
            totalElements: all.length,
            visible, hidden, inputs, buttons, links, images, headings,
            topTags: Object.entries(tags)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 15)
                .map(([t, c]) => `${t}: ${c}`)
        });
    }"""

    entry = registry.get_entry("mcp_chrome_devtools_evaluate_script")
    if entry is None:
        return "DOM-Inspektion: evaluate_script nicht verfuegbar"
    try:
        result = entry.handler({"function": js_code})
        return str(result)[:1500] if result else ""
    except Exception as e:
        return f"DOM-Inspektion: {e}"


def _check_ui_presence(registry) -> str:
    """Prueft ob erwartete UI-Elemente auf der Seite vorhanden sind.

    Checkt: Navigation, Suche, Footer, Headings, CTA-Buttons.
    """
    js_code = """() => {
        const checks = {};

        checks.navigation = !!document.querySelector('nav, [role="navigation"]');
        checks.main = !!document.querySelector('main, [role="main"]');
        checks.footer = !!document.querySelector('footer, [role="contentinfo"]');
        checks.search = !!(
            document.querySelector('input[type="search"], [role="search"]') ||
            document.querySelector('[aria-label*="search" i]')
        );
        checks.headings = document.querySelectorAll('h1, h2, h3').length;
        checks.buttons = document.querySelectorAll(
            'button, a[role="button"], [type="submit"]'
        ).length;
        checks.links = document.querySelectorAll('a[href]').length;
        checks.images = document.querySelectorAll('img, svg').length;
        checks.forms = document.querySelectorAll('form').length;

        return JSON.stringify(checks);
    }"""

    entry = registry.get_entry("mcp_chrome_devtools_evaluate_script")
    if entry is None:
        return "Presence-Check: evaluate_script nicht verfuegbar"
    try:
        result = entry.handler({"function": js_code})
        return str(result)[:1500] if result else ""
    except Exception as e:
        return f"Presence-Check: {e}"
