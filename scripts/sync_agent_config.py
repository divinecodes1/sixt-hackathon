"""Mirror the Claude Code agent setup to Codex. Source of truth: .claude/skills/ and .claude/agents/.

    python3 scripts/sync_agent_config.py

- .claude/skills/<name>/  -> .agents/skills/<name>/   (Codex repo skills location; same SKILL.md format)
- .claude/agents/<name>.md -> .codex/agents/<name>.toml (Codex custom agents: name, description,
  developer_instructions). Preloaded skills become "$skill" references; a read-only tool list becomes a
  no-edit instruction (Codex agents can't override the sandbox, so it is enforced by instruction only).
Re-run after every skill or agent edit. Stdlib only.
"""
from __future__ import annotations

import pathlib
import re
import shutil
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_SKILLS, DST_SKILLS = ROOT / ".claude/skills", ROOT / ".agents/skills"
SRC_AGENTS, DST_AGENTS = ROOT / ".claude/agents", ROOT / ".codex/agents"


def frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, flags=re.S)
    if not m:
        raise ValueError("missing frontmatter")
    meta: dict = {}
    key = None
    for line in m.group(1).splitlines():
        if re.match(r"^\s+-\s+", line) and key:
            meta.setdefault(key, []).append(line.split("-", 1)[1].strip())
        elif ":" in line:
            key, val = (s.strip() for s in line.split(":", 1))
            meta[key] = val if val else []
    return meta, m.group(2).strip()


def toml_basic(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def agent_toml(meta: dict, body: str) -> str:
    extra = []
    if meta.get("skills"):
        extra.append("Use these skills (read their SKILL.md and follow them): "
                     + ", ".join(f"${s}" for s in meta["skills"]) + ". They live in .agents/skills/.")
    disallowed = meta.get("disallowedTools", "")
    if "Edit" in str(disallowed) or "Write" in str(disallowed):
        extra.append("You are READ-ONLY: never create, edit or delete files, and never commit or push. "
                     "Running read-only commands and tests is fine.")
    instructions = body + ("\n\n" + "\n".join(extra) if extra else "")
    if "'''" in instructions:
        raise ValueError("instructions contain ''' which a TOML literal string can't hold")
    name = meta["name"]
    return (f"# Generated from .claude/agents/{name}.md by scripts/sync_agent_config.py. Edit the source, not this file.\n"
            f"name = {toml_basic(name)}\n"
            f"description = {toml_basic(meta['description'])}\n"
            f"developer_instructions = '''\n{instructions}\n'''\n")


def main() -> None:
    if (ROOT / ".codex/skills").exists():   # wrong location used earlier: Codex reads .agents/skills
        shutil.rmtree(ROOT / ".codex/skills")
    if DST_SKILLS.exists():
        shutil.rmtree(DST_SKILLS)
    shutil.copytree(SRC_SKILLS, DST_SKILLS, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    skills = sorted(p.parent.name for p in DST_SKILLS.glob("*/SKILL.md"))
    for name in skills:
        meta, _ = frontmatter((DST_SKILLS / name / "SKILL.md").read_text(encoding="utf-8"))
        if meta.get("name") != name or not meta.get("description"):
            sys.exit(f"skill {name}: frontmatter name must equal the folder name and description must be set")

    DST_AGENTS.mkdir(parents=True, exist_ok=True)
    for old in DST_AGENTS.glob("*.toml"):
        if old.read_text(encoding="utf-8").startswith("# Generated from .claude/agents/"):
            old.unlink()
    agents = []
    for src in sorted(SRC_AGENTS.glob("*.md")):
        meta, body = frontmatter(src.read_text(encoding="utf-8"))
        for s in meta.get("skills") or []:
            if s not in skills:
                sys.exit(f"agent {meta['name']}: preloads unknown skill {s}")
        out = DST_AGENTS / f"{meta['name']}.toml"
        out.write_text(agent_toml(meta, body), encoding="utf-8")
        parsed = tomllib.loads(out.read_text(encoding="utf-8"))
        assert {"name", "description", "developer_instructions"} <= parsed.keys()
        agents.append(meta["name"])
    print(f"skills -> .agents/skills: {', '.join(skills)}")
    print(f"agents -> .codex/agents: {', '.join(agents)}")


if __name__ == "__main__":
    main()
