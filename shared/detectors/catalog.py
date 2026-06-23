from __future__ import annotations

from typing import List

from .base import _TechDetector

# ── Backend Frameworks ──────────────────────────────────────────────

MEDUSA_V2_DETECTOR = type("_MedusaV2Detector", (_TechDetector,), {
    "name": "medusa-v2",
    "category": "backend",
    "markers": [
        ("medusa-config.ts", "defineConfig", "high"),
        ("medusa-config.js", "defineConfig", "high"),
        ("medusa-config.ts", "modules", "high"),
        ("package.json", '"@medusajs/medusa"', "high"),
        ("src/modules/*/index.ts", "export default Module", "medium"),
        ("src/admin/routes/**/page.tsx", "@medusajs/ui", "medium"),
    ],
})()

NEXTJS_DETECTOR = type("_NextJSDetector", (_TechDetector,), {
    "name": "nextjs",
    "category": "frontend",
    "markers": [
        ("next.config.ts", "", "high"),
        ("next.config.mjs", "", "high"),
        ("next.config.js", "", "high"),
        ("package.json", '"next"', "high"),
        ("app/**/page.tsx", "export default", "medium"),
        ("src/app/**/page.tsx", "export default", "medium"),
    ],
})()

EXPRESS_DETECTOR = type("_ExpressDetector", (_TechDetector,), {
    "name": "express",
    "category": "backend",
    "markers": [
        ("package.json", '"express"', "high"),
    ],
})()

FASTIFY_DETECTOR = type("_FastifyDetector", (_TechDetector,), {
    "name": "fastify",
    "category": "backend",
    "markers": [
        ("package.json", '"fastify"', "high"),
    ],
})()

GO_DETECTOR = type("_GoDetector", (_TechDetector,), {
    "name": "go",
    "category": "language",
    "markers": [
        ("go.mod", "module ", "high"),
    ],
})()

GO_CHI_DETECTOR = type("_GoChiDetector", (_TechDetector,), {
    "name": "go-chi",
    "category": "backend",
    "markers": [
        ("go.mod", "chi", "medium"),
        ("**/*.go", "chi.NewRouter", "high"),
        ("**/*.go", "chi.NewMux", "high"),
    ],
})()

GO_FIBER_DETECTOR = type("_GoFiberDetector", (_TechDetector,), {
    "name": "go-fiber",
    "category": "backend",
    "markers": [
        ("go.mod", "fiber", "medium"),
        ("**/*.go", "fiber.New", "high"),
    ],
})()

FASTAPI_DETECTOR = type("_FastAPIDetector", (_TechDetector,), {
    "name": "fastapi",
    "category": "backend",
    "markers": [
        ("requirements.txt", "fastapi", "high"),
        ("pyproject.toml", '"fastapi"', "high"),
        ("**/*.py", "from fastapi import", "high"),
    ],
})()

DJANGO_DETECTOR = type("_DjangoDetector", (_TechDetector,), {
    "name": "django",
    "category": "backend",
    "markers": [
        ("requirements.txt", "django", "high"),
        ("manage.py", "django", "high"),
        ("**/settings.py", "django", "medium"),
    ],
})()

# ── Frontend Frameworks ────────────────────────────────────────────

REACT_DETECTOR = type("_ReactDetector", (_TechDetector,), {
    "name": "react",
    "category": "frontend",
    "markers": [
        ("package.json", '"react"', "high"),
        ("**/*.tsx", "from 'react'", "medium"),
        ("**/*.tsx", 'from "react"', "medium"),
    ],
})()

VUE_DETECTOR = type("_VueDetector", (_TechDetector,), {
    "name": "vue",
    "category": "frontend",
    "markers": [
        ("package.json", '"vue"', "high"),
        ("**/*.vue", "<template>", "medium"),
    ],
})()

SVELTE_DETECTOR = type("_SvelteDetector", (_TechDetector,), {
    "name": "svelte",
    "category": "frontend",
    "markers": [
        ("package.json", '"svelte"', "high"),
        ("**/*.svelte", "<script", "medium"),
    ],
})()

VITE_DETECTOR = type("_ViteDetector", (_TechDetector,), {
    "name": "vite",
    "category": "frontend",
    "markers": [
        ("vite.config.ts", "", "high"),
        ("vite.config.js", "", "high"),
        ("package.json", '"vite"', "high"),
    ],
})()

TAILWIND_DETECTOR = type("_TailwindDetector", (_TechDetector,), {
    "name": "tailwindcss",
    "category": "ui_library",
    "markers": [
        ("tailwind.config.ts", "", "high"),
        ("tailwind.config.js", "", "high"),
        ("package.json", '"tailwindcss"', "high"),
        ("**/*.css", "@tailwind", "medium"),
    ],
})()

SHADCN_DETECTOR = type("_ShadcnDetector", (_TechDetector,), {
    "name": "shadcn-ui",
    "category": "ui_library",
    "markers": [
        ("components.json", "", "high"),
        ("package.json", '"shadcn-ui"', "high"),
        ("package.json", '"@radix-ui/react-"', "medium"),
    ],
})()

MEDUSAJ_UI_DETECTOR = type("_MedusaJSUIDetector", (_TechDetector,), {
    "name": "@medusajs/ui",
    "category": "ui_library",
    "markers": [
        ("package.json", '"@medusajs/ui"', "high"),
        ("**/admin/**/*.tsx", "@medusajs/ui", "medium"),
    ],
})()

# ── Datenbanken ────────────────────────────────────────────────────

POSTGRESQL_DETECTOR = type("_PostgreSQLDetector", (_TechDetector,), {
    "name": "postgresql",
    "category": "database",
    "markers": [
        ("package.json", '"pg"', "high"),
        ("package.json", '"postgres"', "medium"),
        ("**/*.ts", "createConnection.*postgres", "medium"),
        ("docker-compose.yml", "postgres:", "medium"),
        ("docker-compose.yaml", "postgres:", "medium"),
    ],
})()

REDIS_DETECTOR = type("_RedisDetector", (_TechDetector,), {
    "name": "redis",
    "category": "database",
    "markers": [
        ("package.json", '"redis"', "high"),
        ("package.json", '"ioredis"', "high"),
        ("docker-compose.yml", "redis:", "medium"),
        ("docker-compose.yaml", "redis:", "medium"),
    ],
})()

# ── Sprachen ───────────────────────────────────────────────────────

TYPESCRIPT_DETECTOR = type("_TypeScriptDetector", (_TechDetector,), {
    "name": "typescript",
    "category": "language",
    "markers": [
        ("tsconfig.json", "", "high"),
        ("package.json", '"typescript"', "high"),
        ("**/*.ts", "", "medium"),
    ],
})()

JAVASCRIPT_DETECTOR = type("_JavaScriptDetector", (_TechDetector,), {
    "name": "javascript",
    "category": "language",
    "markers": [
        ("package.json", "", "high"),
    ],
})()

PYTHON_DETECTOR = type("_PythonDetector", (_TechDetector,), {
    "name": "python",
    "category": "language",
    "markers": [
        ("**/*.py", "", "medium"),
        ("requirements.txt", "", "medium"),
        ("pyproject.toml", "", "medium"),
        ("setup.py", "", "medium"),
    ],
})()

RUST_DETECTOR = type("_RustDetector", (_TechDetector,), {
    "name": "rust",
    "category": "language",
    "markers": [
        ("Cargo.toml", "", "high"),
        ("**/*.rs", "", "medium"),
    ],
})()

# ── Testing ────────────────────────────────────────────────────────

JEST_DETECTOR = type("_JestDetector", (_TechDetector,), {
    "name": "jest",
    "category": "testing",
    "markers": [
        ("package.json", '"jest"', "high"),
        ("jest.config.ts", "", "high"),
        ("jest.config.js", "", "high"),
    ],
})()

VITEST_DETECTOR = type("_VitestDetector", (_TechDetector,), {
    "name": "vitest",
    "category": "testing",
    "markers": [
        ("package.json", '"vitest"', "high"),
        ("vitest.config.ts", "", "high"),
    ],
})()

PLAYWRIGHT_DETECTOR = type("_PlaywrightDetector", (_TechDetector,), {
    "name": "playwright",
    "category": "testing",
    "markers": [
        ("package.json", '@playwright', "high"),
        ("playwright.config.ts", "", "high"),
        ("**/*.spec.ts", "playwright", "medium"),
    ],
})()

# ── Infrastructure ─────────────────────────────────────────────────

DOCKER_DETECTOR = type("_DockerDetector", (_TechDetector,), {
    "name": "docker",
    "category": "infra",
    "markers": [
        ("Dockerfile", "FROM", "high"),
        ("docker-compose.yml", "", "high"),
        ("docker-compose.yaml", "", "high"),
        (".dockerignore", "", "medium"),
    ],
})()

SYSTEMD_DETECTOR = type("_SystemdDetector", (_TechDetector,), {
    "name": "systemd",
    "category": "infra",
    "markers": [
        ("**/*.service", "[Unit]", "high"),
        ("**/*.service", "[Service]", "high"),
    ],
})()

NGINX_DETECTOR = type("_NginxDetector", (_TechDetector,), {
    "name": "nginx",
    "category": "infra",
    "markers": [
        ("**/nginx.conf", "server", "high"),
        ("**/nginx/*.conf", "server", "high"),
        (".nginx.conf", "", "medium"),
    ],
})()

# ── CI / CD ────────────────────────────────────────────────────────

GITHUB_ACTIONS_DETECTOR = type("_GitHubActionsDetector", (_TechDetector,), {
    "name": "github-actions",
    "category": "ci",
    "markers": [
        (".github/workflows/*.yml", "on:", "high"),
        (".github/workflows/*.yaml", "on:", "high"),
    ],
})()

FORGEJO_ACTIONS_DETECTOR = type("_ForgejoActionsDetector", (_TechDetector,), {
    "name": "forgejo-actions",
    "category": "ci",
    "markers": [
        (".forgejo/workflows/*.yml", "on:", "high"),
        (".forgejo/workflows/*.yaml", "on:", "high"),
    ],
})()

# ── Package Manager ────────────────────────────────────────────────

NPM_DETECTOR = type("_NpmDetector", (_TechDetector,), {
    "name": "npm",
    "category": "package_manager",
    "markers": [
        ("package-lock.json", "", "high"),
        ("package.json", "", "medium"),
    ],
})()

YARN_DETECTOR = type("_YarnDetector", (_TechDetector,), {
    "name": "yarn",
    "category": "package_manager",
    "markers": [
        ("yarn.lock", "", "high"),
        ("package.json", '"yarn"', "medium"),
    ],
})()

PNPM_DETECTOR = type("_PnpmDetector", (_TechDetector,), {
    "name": "pnpm",
    "category": "package_manager",
    "markers": [
        ("pnpm-lock.yaml", "", "high"),
    ],
})()

# ── Monorepo ───────────────────────────────────────────────────────

MONOREPO_NPM_DETECTOR = type("_MonorepoNpmDetector", (_TechDetector,), {
    "name": "npm-workspaces",
    "category": "infra",
    "markers": [
        ("package.json", '"workspaces"', "high"),
    ],
})()

MONOREPO_TURBO_DETECTOR = type("_MonorepoTurboDetector", (_TechDetector,), {
    "name": "turborepo",
    "category": "infra",
    "markers": [
        ("turbo.json", "", "high"),
        ("package.json", '"turbo"', "high"),
    ],
})()

# ── AWS / Cloud ────────────────────────────────────────────────────

TF_DETECTOR = type("_TerraformDetector", (_TechDetector,), {
    "name": "terraform",
    "category": "infra",
    "markers": [
        ("*.tf", 'terraform {', "high"),
        ("**/*.tf", 'required_providers', "high"),
    ],
})()

# ── Definierte Detectors ───────────────────────────────────────────

# Java
JAVA_DETECTOR = type("_JavaDetector", (_TechDetector,), {
    "name": "java",
    "category": "language",
    "markers": [
        ("pom.xml", "<project", "high"),
        ("build.gradle", "apply plugin", "high"),
        ("**/*.java", "class ", "medium"),
    ],
})()

# C / C++
CPP_DETECTOR = type("_CppDetector", (_TechDetector,), {
    "name": "cpp",
    "category": "language",
    "markers": [
        ("CMakeLists.txt", "cmake_minimum_required", "high"),
        ("Makefile", "CC=", "medium"),
        ("**/*.cpp", "#include", "medium"),
        ("**/*.c", "#include <", "medium"),
        ("**/*.h", "#ifndef", "medium"),
    ],
})()

# Ruby
RUBY_DETECTOR = type("_RubyDetector", (_TechDetector,), {
    "name": "ruby",
    "category": "language",
    "markers": [
        ("Gemfile", "source ", "high"),
        ("**/*.rb", "class ", "medium"),
        ("**/*.rb", "def ", "medium"),
        ("Rakefile", "task ", "medium"),
    ],
})()

ALL_DETECTORS: List[_TechDetector] = [
    # Backend
    MEDUSA_V2_DETECTOR,
    NEXTJS_DETECTOR,
    EXPRESS_DETECTOR,
    FASTIFY_DETECTOR,
    GO_CHI_DETECTOR,
    GO_FIBER_DETECTOR,
    FASTAPI_DETECTOR,
    DJANGO_DETECTOR,
    # Frontend
    REACT_DETECTOR,
    VUE_DETECTOR,
    SVELTE_DETECTOR,
    VITE_DETECTOR,
    # UI Libs
    TAILWIND_DETECTOR,
    SHADCN_DETECTOR,
    MEDUSAJ_UI_DETECTOR,
    # DB
    POSTGRESQL_DETECTOR,
    REDIS_DETECTOR,
    # Languages
    TYPESCRIPT_DETECTOR,
    JAVASCRIPT_DETECTOR,
    PYTHON_DETECTOR,
    RUST_DETECTOR,
    GO_DETECTOR,
    JAVA_DETECTOR,
    CPP_DETECTOR,
    RUBY_DETECTOR,
    # Testing
    JEST_DETECTOR,
    VITEST_DETECTOR,
    PLAYWRIGHT_DETECTOR,
    # Infra
    DOCKER_DETECTOR,
    SYSTEMD_DETECTOR,
    NGINX_DETECTOR,
    TF_DETECTOR,
    MONOREPO_NPM_DETECTOR,
    MONOREPO_TURBO_DETECTOR,
    # CI
    GITHUB_ACTIONS_DETECTOR,
    FORGEJO_ACTIONS_DETECTOR,
    # Package Manager
    NPM_DETECTOR,
    YARN_DETECTOR,
    PNPM_DETECTOR,
]
