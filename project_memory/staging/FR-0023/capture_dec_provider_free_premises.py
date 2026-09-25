"""Capture the user's four premise answers for FR-0023 (provider-free harness / own app), 2026-09-25 ~15:4x, given
on the two research files in this folder. A premise DEC, not a build order: it fixes what the planning round designs
against. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "FR-0023 Praemissen (anbieterfreie App): alles inkl. Chats ueberlebt einen Wechsel; Abos bleiben die "
             "Grundlage; Schutz darf je Anbieter abgestuft sein (sichtbar); erst nur fuer den Nutzer, Ziel: jeder "
             "Anbieter inkl. Kimi/Qwen/GLM/DeepSeek/Gemini und lokale Modelle, schnell wechselbar wenn Tarife sich "
             "aendern; Claude Code als Standard-Laufzeit wird geprueft",
    "context": "USER 2026-09-25 ~15:40, answers to four premise questions after the research of "
               "staging/FR-0023/research-claude-news-2026-09-25.md and research-provider-neutral-2026-09-25.md: "
               "(1) 'Alles inkl. Chats'; (2) 'Abos weiter nutzen'; (3) 'Abgestuft ok'; (4) verbatim: 'Erstmal nur "
               "fuer mich. Und wirklich komplett Anbieter unabhaengig spaeter und sogar mit lokalen Modellen. Also "
               "Kimi, qwen, glm, Claude, Codex, Gemini, und alles. Und lokale modelle das man schnell Anbieter "
               "wechseln kann wenn sich Tarife oder so aendern. Und welcher harness in Hintergrund? Claude code als "
               "standard? Aber wechselbar zwischen verschiedenen Anbietern? Und eigener harness und deepseek "
               "harness?' MEASURED by the research (sourced there): only AGENTS.md, Agent Skills (SKILL.md) and MCP "
               "are portable standards; hooks, subagents, approvals, chat history and memory have none; a Claude "
               "subscription is usable only inside Anthropic's own clients (third-party use needs Anthropic's "
               "permission); Anthropic does not SUPPORT Claude Code on non-Claude models, though it runs technically "
               "via ANTHROPIC_BASE_URL; Qwen Code, Goose, OpenHands and Codex adopted the Claude hook shape; "
               "DeepSeek ships no CLI of its own.",
    "decision": "PREMISES for the FR-0023 planning round (not a build order): (P1) CONTINUITY: a provider switch "
                "loses nothing -- state, rules, skills, tools AND the conversation. Since a live context cannot "
                "move between vendor clients, 'the chat survives' is designed as: every session's transcript is "
                "captured into a provider-neutral store the harness owns, and the next session on any provider "
                "resumes from it (state + condensed conversation), measured by a switch test. (P2) SUBSCRIPTIONS "
                "FIRST: a provider with a subscription runs in the client that subscription allows (Claude Code, "
                "Codex, Gemini CLI, Kimi/Qwen CLIs); pay-per-use APIs and local models are the supplement, not the "
                "base. This keeps way A (generate per client) as the spine; B/C are judged as supplements for "
                "providers without a client of their own (DeepSeek, GLM, local). (P3) TIERED PROTECTION is allowed: "
                "a client that cannot carry a gate class may run, but the gap is VISIBLE (a per-provider capability "
                "table, measured per provider like the Codex round; roles that need the missing guarantee are not "
                "dispatched there). (P4) FIRST USER is the maintainer; the target is every provider incl. local "
                "models, switchable quickly when prices change -- the app's first job is the switch. (P5) OPEN, to "
                "be measured before decided: Claude Code as the DEFAULT runtime with a swappable backend "
                "(ANTHROPIC_BASE_URL to Kimi/GLM/DeepSeek/Qwen/local endpoints -- unsupported by Anthropic, so a "
                "measured round: do all gates fire, do subagents and approvals hold); an own runtime (way C) only "
                "if the measurements show the clients cannot carry P1-P3. (P6) The 2026-07-14 source-format "
                "decision (kit source stays Claude-native) is re-opened by its own trip-wire (a third provider) "
                "in this round.",
    "consequences": "The planning round produces: a capability table per provider/client, the conversation-store "
                    "design (P1), the measured answer to P5, and a sliced goal (PR) converted from FR-0023 "
                    "(DEC-0066 (3)). Cost: P1+P2 together rule out the cheapest reading of either (neither 'chats "
                    "are lost' nor 'one API runtime for all'). Rejected for now: B as the spine (would move Claude "
                    "off the subscription).",
    "work": ["PR-0003"],
    "source": "user answers 2026-09-25 ~15:40; staging/FR-0023/research-claude-news-2026-09-25.md; "
              "staging/FR-0023/research-provider-neutral-2026-09-25.md; FR-0023, FR-0020, FR-0025; DEC-0066; "
              "HARNESS_LOG.md 2026-07-14 (source-format decision + trip-wire)",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr[-1500:])
sys.exit(result.returncode)
