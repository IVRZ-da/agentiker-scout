from __future__ import annotations

from typing import List, Optional

from .loader import FrameworkDetector


def detect_frameworks(
    project_root: str,
    categories: Optional[List[str]] = None,
    fast: bool = False,
) -> dict:
    """Einzige öffentliche Funktion — erkennt Frameworks und gibt Dict zurück.

    Args:
        project_root: Pfad zum Projekt-Root
        categories: Optionale Kategorie-Filter (["backend", "frontend", ...])
        fast: Wenn True, nur High-Confidence-Marker scannen

    Returns:
        Dict mit Framework-Profil (kann direkt an Bug-Hunt übergeben werden)
    """
    detector = FrameworkDetector(project_root)
    profile = detector.detect_fast() if fast else detector.detect(categories)
    return profile.to_dict()


def format_profile_summary(profile: dict) -> str:
    """Formatiert ein Framework-Profil als lesbaren String."""
    if not profile or not profile.get("frameworks"):
        return "Keine Frameworks erkannt."

    lines = [f"Framework-Profil: {profile['project_root']}"]
    lines.append(f"Confidence: {profile.get('overall_confidence', 0):.0%}")
    lines.append("")

    for category, fw_list in sorted(profile.get("frameworks", {}).items()):
        lines.append(f"  [{category}]")
        for fw in fw_list:
            ver = f" v{fw['version']}" if fw.get("version") else ""
            conf_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(
                fw.get("confidence", ""), "⚪"
            )
            lines.append(f"    {conf_icon} {fw['name']}{ver}")
            for ev in fw.get("evidence", []):
                lines.append(f"      → {ev['source']} ({ev['confidence']})")
    lines.append("")

    return "\n".join(lines)
