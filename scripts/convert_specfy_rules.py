#!/usr/bin/env python3
"""
Convert specfy/stack-analyser rules to Hermes Scout YAML rule files.

Scans /tmp/specfy-rules/src/rules/ for TypeScript rule files,
extracts technology metadata (tech, name, type, files, dependencies, dotenv),
maps them to our category system, and appends to data/rules/*.yaml.
"""

import os
import re
from pathlib import Path
from typing import Any, Optional

# ── Paths ───────────────────────────────────────────────────────────────────
SPECFY_RULES_DIR = Path("/tmp/specfy-rules/src/rules")
SCOUT_DATA_DIR = Path(os.path.expanduser("~/.hermes/plugins/scout/data/rules"))

# ── Category mapping (specfy 'type' → loader-validated categories) ─────────
# Valid categories in the loader: backend, ci, database, frontend, infra,
# language, package_manager, testing, ui_library
TYPE_TO_CATEGORY = {
    "ai": "backend",
    "analytics": "infra",
    "app": "backend",
    "auth": "backend",
    "automation": "infra",
    "builder": "backend",
    "ci": "ci",
    "cms": "backend",
    "cloud": "infra",
    "collaboration": "infra",
    "communication": "infra",
    "crm": "infra",
    "db": "database",
    "etl": "infra",
    "framework": "backend",
    "hosting": "infra",
    "iac": "infra",
    "iconset": "frontend",
    "language": "language",
    "linter": "backend",
    "maps": "backend",
    "monitoring": "infra",
    "network": "infra",
    "notification": "infra",
    "orm": "backend",
    "package_manager": "package_manager",
    "payment": "backend",
    "queue": "infra",
    "runtime": "infra",
    "saas": "infra",
    "security": "backend",
    "ssg": "frontend",
    "storage": "infra",
    "test": "testing",
    "tool": "backend",
    "ui": "ui_library",
    "ui_framework": "frontend",
    "validation": "backend",
}

# Specfy types under 'framework/' that are actually frontend
FRONTEND_FRAMEWORKS = {
    "blitzjs", "gatsby", "nextjs", "nuxtjs", "remixrun", "remult",
    "sveltekit", "tanstackstart", "wasp",
}

# Dependency type → file mapping
DEP_TYPE_TO_FILE = {
    "npm": "package.json",
    "pip": "requirements.txt",
    "python": "requirements.txt",
    "pipenv": "requirements.txt",
    "poetry": "pyproject.toml",
    "go": "go.mod",
    "golang": "go.mod",
    "cargo": "Cargo.toml",
    "rust": "Cargo.toml",
    "docker": "Dockerfile",
    "dockercompose": "docker-compose.yml",
    "terraform": "*.tf",
    "terraform.resource": "*.tf",
    "ruby": "Gemfile",
    "php": "composer.json",
    "deno": "deno.json",
    "githubAction": ".github/workflows/*.yml",
    "gradle": "build.gradle",
    "maven": "pom.xml",
    "nuget": "*.csproj",
    "helm": "Chart.yaml",
}

# ── Parse helpers ───────────────────────────────────────────────────────────

def parse_ts_file(filepath: Path) -> Optional[dict[str, Any]]:
    """Parse a specfy TypeScript rule file and extract the register() call data."""
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    # Extract register({...}) call body
    # Match: register({ ... });
    m = re.search(r"register\(\s*\{([\s\S]*?)\}\s*\)\s*;", text)
    if not m:
        return None

    body = m.group(1)

    # Extract key fields using simple regex (since the structure is relatively flat)
    result = {}

    # tech (required)
    tech_m = re.search(r'\btech\s*:\s*["\']([^"\']+)["\']', body)
    if tech_m:
        result["tech"] = tech_m.group(1)
    else:
        return None  # tech is required

    # name (optional, fall back to tech)
    name_m = re.search(r'\bname\s*:\s*["\']([^"\']+)["\']', body)
    result["name"] = name_m.group(1) if name_m else result["tech"]

    # type (required for category mapping)
    type_m = re.search(r'\btype\s*:\s*["\']([^"\']+)["\']', body)
    result["type"] = type_m.group(1) if type_m else "unknown"

    # dotenv (array of strings)
    dotenv = []
    dotenv_section = re.search(r'\bdotenv\s*:\s*\[(.*?)\]', body, re.DOTALL)
    if dotenv_section:
        for m in re.finditer(r'["\']([^"\']+)["\']', dotenv_section.group(1)):
            dotenv.append(m.group(1))
    result["dotenv"] = dotenv

    # files (can be regex literal or array of strings)
    files = []
    files_section = re.search(r'\bfiles\s*:\s*(.*?)(?=\n\s+\w+\s*:|\n\}|$)', body, re.DOTALL)
    if files_section:
        files_text = files_section.group(1).strip()
        if files_text.startswith("/") and not files_text.startswith("//"):
            # RegEx literal like /tsconfig(.[a-zA-Z0-9_-]+)?.json/
            # Extract the pattern between leading / and trailing /flags
            slash_end = files_text.rfind("/")
            if slash_end > 0:
                pattern = files_text[1:slash_end]
                # Convert regex to a glob-like pattern where possible
                files.append(("regex", pattern))
        elif files_text.startswith("["):
            # Array of strings
            for m in re.finditer(r'["\']([^"\']+)["\']', files_text):
                files.append(("string", m.group(1)))
    result["files"] = files

    # extensions
    extensions = []
    ext_section = re.search(r'\bextensions\s*:\s*\[(.*?)\]', body, re.DOTALL)
    if ext_section:
        for m in re.finditer(r'["\']([^"\']+)["\']', ext_section.group(1)):
            extensions.append(m.group(1))
    result["extensions"] = extensions

    # dependencies
    deps = []
    deps_section = re.search(r'\bdependencies\s*:\s*\[([\s\S]*?)\]', body)
    if deps_section:
        # Find each {...} block
        dep_text = deps_section.group(1)
        depth = 0
        start = -1
        for i, ch in enumerate(dep_text):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start >= 0:
                    block = dep_text[start : i + 1]
                    start = -1
                    dep = {}
                    # type
                    dt = re.search(r'\btype\s*:\s*["\']([^"\']+)["\']', block)
                    if dt:
                        dep["type"] = dt.group(1)
                    # name (string or regex)
                    nm = re.search(r'\bname\s*:\s*(/\^?(?:[^/]|\\/)+/?[gimsu]*)', block)
                    if nm:
                        # RegEx
                        raw = nm.group(1).strip()
                        dep["name"] = raw  # keep as raw regex pattern
                    else:
                        nm2 = re.search(r'\bname\s*:\s*["\']([^"\']+)["\']', block)
                        if nm2:
                            dep["name"] = nm2.group(1)
                    # example
                    ex = re.search(r'\bexample\s*:\s*["\']([^"\']+)["\']', block)
                    if ex:
                        dep["example"] = ex.group(1)
                    if "type" in dep and "name" in dep:
                        deps.append(dep)
    result["dependencies"] = deps

    return result


def regex_to_pattern(regex_str: str) -> str:
    """Convert a JavaScript regex pattern to a reasonable file-glob or substring."""
    # Remove leading ^ and trailing $, and common flags
    pattern = regex_str.strip()
    if pattern.startswith("^"):
        pattern = pattern[1:]
    if pattern.endswith("/") and "/" in pattern[:-1]:
        # Remove flags: /pattern/gim → split on last /
        last_slash = pattern.rfind("/")
        if last_slash > 0:
            pattern = pattern[:last_slash]

    # Common conversions
    # /^@google-cloud\// → @google-cloud/  (just use as substring)
    pattern = pattern.replace("\\/", "/").replace("\\.", ".").replace("\\-", "-").replace("\\_", "_")
    pattern = pattern.replace("\\s", " ").replace("\\d", "[0-9]").replace("\\w", "[a-zA-Z0-9_]")

    # Remove grouping constructs that are too complex
    # For simple patterns that match a prefix, just use that prefix
    if re.match(r'^[a-zA-Z0-9@/\-_.]+', pattern):
        simple = re.match(r'^[a-zA-Z0-9@/\-_.]+', pattern)
        if simple and len(simple.group()) >= 3:
            return simple.group()

    # If it has character classes or complex regex, return a reasonable substring
    # Try extracting a meaningful prefix
    simple_prefix = re.match(r'^[\^]?([a-zA-Z0-9@_/\-]+)', pattern)
    if simple_prefix:
        prefix = simple_prefix.group(1).rstrip("\\^$.*+?[](){}|")
        if len(prefix) >= 2:
            return prefix

    return pattern[:30]  # truncate very long patterns


def resolve_regex_name(name_raw: str, example: Optional[str] = None) -> str:
    """Convert a regex dependency name to a searchable string."""
    if name_raw.startswith("/"):
        # Extract pattern: /pattern/flags
        slash_end = name_raw.rfind("/")
        if slash_end > 0:
            pattern = name_raw[1:slash_end]
        else:
            pattern = name_raw[1:]
        # If example is available, use that as search string
        if example:
            return example
        return regex_to_pattern(pattern)
    return name_raw


def resolve_regex_file(pattern: str) -> str:
    """Convert a regex file pattern to a glob."""
    # Common cases:
    # /tsconfig(.[a-zA-Z0-9_-]+)?.json/ → tsconfig*.json
    # /jest.config.(js|ts|mjs|cjs|json)/ → jest.config.*

    # Simple conversions
    if re.match(r"^[a-zA-Z0-9_.-]+$", pattern):
        return pattern

    # Try to extract a base filename before the regex group
    m = re.match(r'^([a-zA-Z0-9_.-]+)\(', pattern)
    if m:
        return m.group(1) + "*"

    m = re.match(r'^([a-zA-Z0-9_.-]+)\[', pattern)
    if m:
        return m.group(1) + "*"

    # Remove regex special chars for a reasonable glob
    glob_pattern = pattern
    # Replace common regex patterns with glob equivalents
    glob_pattern = re.sub(r'\(\?[^)]*\)', '*', glob_pattern)  # (?...)
    glob_pattern = re.sub(r'\([^|)]+\|[^)]+\)', '*', glob_pattern)  # (a|b)
    glob_pattern = re.sub(r'\([^)]+\)\?', '*', glob_pattern)  # (...)？
    glob_pattern = re.sub(r'\[^[^\]]+\]', '*', glob_pattern)  # [^...]
    glob_pattern = re.sub(r'\[[a-zA-Z0-9_-]+\]', '*', glob_pattern)  # [a-z]
    glob_pattern = re.sub(r'\?', '*', glob_pattern)
    glob_pattern = re.sub(r'\.\+\?', '*', glob_pattern)  # .+?
    glob_pattern = re.sub(r'\.\+', '*', glob_pattern)  # .+
    glob_pattern = re.sub(r'\.\*', '*', glob_pattern)  # .*
    glob_pattern = re.sub(r'\\', '', glob_pattern)

    # If we got something reasonable, use it
    glob_pattern = glob_pattern.strip()
    if glob_pattern and glob_pattern != "*":
        return glob_pattern

    return pattern[:40]  # fallback


def confidence_for_dep(dep_type: str) -> str:
    """Determine confidence level for a dependency marker."""
    if dep_type in ("docker", "terraform", "githubAction"):
        return "medium"
    return "high"


def confidence_for_file() -> str:
    return "high"


def confidence_for_dotenv() -> str:
    return "medium"


def build_markers_for_dep(dep_type: str, dep_name: str) -> Optional[dict]:
    """Build a single marker dict from a dependency entry."""
    dep_file = DEP_TYPE_TO_FILE.get(dep_type)
    if not dep_file:
        return None  # unknown dependency type, skip

    return {
        "file": dep_file,
        "search": dep_name,
        "confidence": confidence_for_dep(dep_type),
    }


# ── Category helpers ────────────────────────────────────────────────────────

def get_category(rule_data: dict) -> str:
    """Determine the output category for a rule."""
    specfy_type = rule_data.get("type", "unknown")
    tech = rule_data.get("tech", "")

    # Special handling: framework type might be frontend
    if specfy_type == "framework" and tech in FRONTEND_FRAMEWORKS:
        return "frontend"

    return TYPE_TO_CATEGORY.get(specfy_type, "infra")


def get_category_file(category: str) -> str:
    """Map category to YAML filename."""
    return f"{category}.yaml"


# ── YAML generation ─────────────────────────────────────────────────────────

def build_rule_entry(rule_data: dict) -> Optional[dict]:
    """
    Convert parsed rule data to our YAML format.
    Returns None if the rule has no usable markers.
    """
    markers = []

    # 1. Files → file existence markers
    for file_type, file_val in rule_data.get("files", []):
        if file_type == "string":
            markers.append({
                "file": file_val,
                "search": "",
                "confidence": "high",
            })
        elif file_type == "regex":
            glob_pattern = resolve_regex_file(file_val)
            markers.append({
                "file": glob_pattern,
                "search": "",
                "confidence": "high",
            })

    # 2. Extensions → file existence markers
    for ext in rule_data.get("extensions", []):
        markers.append({
            "file": f"**/*{ext}",
            "search": "",
            "confidence": "medium",
        })

    # 3. Dependencies → package registry markers
    for dep in rule_data.get("dependencies", []):
        dep_type = dep.get("type", "")
        dep_name_raw = dep.get("name", "")
        dep_example = dep.get("example")

        # Resolve regex names
        dep_name = resolve_regex_name(dep_name_raw, dep_example)

        marker = build_markers_for_dep(dep_type, dep_name)
        if marker:
            markers.append(marker)

    # 4. Dotenv → env file markers
    for prefix in rule_data.get("dotenv", []):
        markers.append({
            "file": ".env",
            "search": prefix,
            "confidence": "medium",
        })

    if not markers:
        return None

    name = rule_data.get("tech", "")
    category = get_category(rule_data)

    return {
        "name": name,
        "category": category,
        "markers": markers,
    }


# ── Deduplication ───────────────────────────────────────────────────────────

def load_existing_rules(yaml_path: Path) -> set[str]:
    """Load existing rule names from a YAML file. Returns set of names."""
    names: set[str] = set()
    if not yaml_path.exists():
        return names

    try:
        text = yaml_path.read_text(encoding="utf-8")
        # Match both '- name: foo' and indented '  name: foo'
        for m in re.finditer(r'(?:^|\n)\s*-?\s*name:\s+(\S+)', text):
            names.add(m.group(1))
    except Exception:
        pass

    return names


YAML_SPECIAL_STARTS = (
    "'", '"', "-", " ", "~", "!", "&", "*", "|", ">", "%", "@", "`",
    "[", "{", "?", "true", "false", "True", "False", "null", "Null",
    "yes", "no", "Yes", "No", "on", "off", "On", "Off",
)


def yaml_escape(value: str) -> str:
    """Escape a YAML string value if needed."""
    if not value:
        return '""'

    needs_quoting = any(c in value for c in ":{}[]&*!|>?'\"%@`#,")
    starts_bad = any(value.startswith(s) for s in YAML_SPECIAL_STARTS) if value else False

    if needs_quoting or starts_bad:
        # Use single quotes, escape interior single quotes
        escaped = value.replace("'", "''")
        return f"'{escaped}'"

    return value


def rule_to_yaml(rule: dict) -> str:
    """Serialize a single rule to YAML string."""
    lines = [f"- name: {rule['name']}"]
    lines.append(f"  category: {rule['category']}")
    lines.append("  markers:")

    for marker in rule["markers"]:
        file_val = yaml_escape(marker["file"])
        search_val = yaml_escape(marker["search"])
        lines.append(f"    - file: {file_val}")
        lines.append(f"      search: {search_val}")
        lines.append(f"      confidence: {marker['confidence']}")

    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    # Ensure output directory exists
    SCOUT_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Group rules by category
    category_rules: dict[str, list[dict]] = {}
    skipped = 0
    converted = 0
    no_markers = 0

    # Walk all .ts files in specfy rules dir
    ts_files = sorted(SPECFY_RULES_DIR.rglob("*.ts"))

    for filepath in ts_files:
        # Skip index files, test files, and spec/
        rel_path = filepath.relative_to(SPECFY_RULES_DIR)
        parts = rel_path.parts

        if filepath.name == "index.ts":
            continue
        if filepath.name.endswith(".test.ts"):
            continue
        if "spec" in parts:
            continue  # Skip custom matchers in spec/

        rule_data = parse_ts_file(filepath)
        if not rule_data:
            skipped += 1
            continue

        entry = build_rule_entry(rule_data)
        if not entry:
            no_markers += 1
            continue

        cat = entry["category"]
        if cat not in category_rules:
            category_rules[cat] = []
        category_rules[cat].append(entry)
        converted += 1

    print(f"✅ Parsed {converted} rules from {len(ts_files)} .ts files")
    print(f"   Skipped: {skipped} (parse failures)")
    print(f"   No markers: {no_markers}")
    print(f"   Categories: {sorted(category_rules.keys())}")

    # Append to category YAML files (deduplicating across ALL files)
    total_new = 0
    total_skipped_existing = 0

    # Load ALL existing rule names globally (to avoid same name in different files)
    global_existing_names: set[str] = set()
    for yaml_path in sorted(SCOUT_DATA_DIR.glob("*.yaml")):
        global_existing_names.update(load_existing_rules(yaml_path))

    for cat, rules in sorted(category_rules.items()):
        yaml_name = get_category_file(cat)
        yaml_path = SCOUT_DATA_DIR / yaml_name

        new_rules = [r for r in rules if r["name"] not in global_existing_names]
        duplicate_names = [r["name"] for r in rules if r["name"] in global_existing_names]

        if not new_rules:
            if duplicate_names:
                print(f"   [{yaml_name}] All {len(rules)} rules already exist (skipped {len(duplicate_names)} duplicates)")
            continue

        yaml_content = "\n".join(rule_to_yaml(r) for r in new_rules) + "\n"

        if yaml_path.exists():
            with open(yaml_path, "a", encoding="utf-8") as f:
                f.write("\n")
                f.write(yaml_content)
        else:
            with open(yaml_path, "w", encoding="utf-8") as f:
                f.write(yaml_content)

        total_new += len(new_rules)
        total_skipped_existing += len(duplicate_names)

        dup_info = f" ({len(duplicate_names)} duplicates skipped)" if duplicate_names else ""
        print(f"   [{yaml_name}] Appended {len(new_rules)} new rules{dup_info}")

    print(f"\n{'='*50}")
    print(f"✅ DONE: {total_new} new rules appended across {len(category_rules)} categories")
    if total_skipped_existing:
        print(f"   {total_skipped_existing} duplicate rules skipped (already exist)")
    print(f"   Categories: {sorted(category_rules.keys())}")


if __name__ == "__main__":
    main()
