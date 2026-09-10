#!/usr/bin/env python3
"""
validate.py — structural self-check for the agents-and-skills repo (dogfooding).

Compiles every shipped hook/script, parses every YAML (templates, registry, agent + skill frontmatter)
and JSON (kit settings), and checks the wiring: each agent's `skills:` resolve to a skill dir, and every
registry role has an agent file. Exit 1 on any failure. Run locally or in CI: python tools/validate.py
"""
import glob
import json
import os
import re
import sys

import yaml

# The in-memory compile below states the rule ("validation must never create __pycache__ that the
# installer could accidentally carry into the shared team-kit staging tree") and this script broke it
# with the imports it really performs: `preset_config` and `kernel.hashing` come from `team-kits/`, so
# every run left `team-kits/__pycache__` and `team-kits/kernel/__pycache__` behind — measured. A
# one-shot validator gains nothing from a bytecode cache, so it writes none.
sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "team-kits"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from preset_config import UniqueKeyLoader, load_preset_catalog  # noqa: E402
import lead_package  # noqa: E402  — the budget and its subject, defined once
# The one reader of `model_tiers.yaml`, borrowed rather than re-implemented: which model values a
# kit source may carry is a property of that file (see `provider_neutral_model`).
from gen_provider_artifacts import (  # noqa: E402
    load_tiers, provider_neutral_model, table_places, unplaceable_pin_sentence)

_MODEL_TIERS, _MODEL_ALIASES = load_tiers()

fails = []
# THERE IS NO WARNING CHANNEL ANY MORE, and its removal is the point rather than tidying. It
# existed for exactly one check — the lead-package budget — on the argument that phase 2 must not
# fail its own build on work phase 3 owns. Three releases later all three kits were still over it,
# the warning had been read and stepped over every time, and II.11/3 was still promising to make it
# hard "later". The budget is now a per-kit RECORD (`tools/lead_package_sizes.json`) that starts
# satisfied, so the check can be a failure today; anything else this file learns to measure should
# be a failure too, or it should not be here.


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def frontmatter(text):
    if not text.startswith("---"):
        return None
    return yaml.load(text.split("---", 2)[1], Loader=UniqueKeyLoader)


# 1) compile python
for p in glob.glob(ROOT + "/team-kits/*.py") + \
         glob.glob(ROOT + "/team-kits/**/hooks/*.py", recursive=True) + \
         glob.glob(ROOT + "/team-kits/**/templates/repo/scripts/*.py", recursive=True) + \
         glob.glob(ROOT + "/tools/*.py"):
    try:
        # Compile in memory: validation must never create __pycache__ that the installer could
        # accidentally carry into the shared team-kit staging tree.
        compile(open(p, "rb").read(), p, "exec")
    except Exception as e:
        fails.append("compile %s: %s" % (rel(p), e))

# 2) parse YAML (templates + registry)
for p in glob.glob(ROOT + "/team-kits/**/templates/project_memory/*.yaml", recursive=True) + \
         [ROOT + "/team-kits/registry.yaml"]:
    try:
        yaml.load(open(p, encoding="utf-8").read(), Loader=UniqueKeyLoader)
    except Exception as e:
        fails.append("yaml %s: %s" % (rel(p), e))

# 3) parse kit settings.json
for p in glob.glob(ROOT + "/team-kits/*/settings/settings.json"):
    try:
        json.load(open(p, encoding="utf-8"))
    except Exception as e:
        fails.append("json %s: %s" % (rel(p), e))

# 4) agent frontmatter + skills wiring
for p in glob.glob(ROOT + "/team-kits/**/agents/*.md", recursive=True):
    fm = None
    try:
        fm = frontmatter(open(p, encoding="utf-8").read())
    except Exception as e:
        fails.append("frontmatter %s: %s" % (rel(p), e))
        continue
    if not fm:
        continue
    kit_dir = os.path.dirname(os.path.dirname(p))
    for sk in (fm.get("skills") or []):
        if not os.path.isdir(os.path.join(kit_dir, "skills", sk)):
            fails.append("%s: skills:[%s] has no skill dir" % (rel(p), sk))

# 5) skill frontmatter
for p in glob.glob(ROOT + "/team-kits/**/skills/**/SKILL.md", recursive=True):
    try:
        frontmatter(open(p, encoding="utf-8").read())
    except Exception as e:
        fails.append("skill frontmatter %s: %s" % (rel(p), e))

# 6) presets are executable policy: parse them strictly and prove that every explicit specialist
#    is a real kit role, while the foreground lead remains outside every specialist list. The same
#    implementation is called by both scaffold scripts, so CI and direct usage cannot disagree.
preset_catalogs = {}
for kit_dir in sorted(glob.glob(ROOT + "/team-kits/*")):
    if not os.path.isdir(os.path.join(kit_dir, "agents")):
        continue
    kit = os.path.basename(kit_dir)
    try:
        preset_catalogs[kit] = load_preset_catalog(kit_dir)
    except Exception as e:
        fails.append("%s/presets.yaml: %s" % (rel(kit_dir), e))

# 7) registry roles -> agent files exist, and its advertised presets exactly match the executable
#    kit policy (otherwise the entry gate can offer a preset that the scaffold cannot resolve).
reg = yaml.load(open(ROOT + "/team-kits/registry.yaml", encoding="utf-8").read(),
                Loader=UniqueKeyLoader)
for team in reg.get("teams", []):
    kit = team["key"]
    for role in team.get("roles", []):
        if not os.path.isfile(ROOT + "/team-kits/%s/agents/%s.md" % (kit, role)):
            fails.append("registry: %s role '%s' has no agent file" % (kit, role))
    catalog = preset_catalogs.get(kit)
    advertised = team.get("presets")
    registry_roles = team.get("roles")
    if catalog is not None:
        if team.get("lead") != catalog["lead"]:
            fails.append("registry: %s lead %r does not match settings agent %r" %
                         (kit, team.get("lead"), catalog["lead"]))
        expected_specialists = set(catalog["roles"]) - {catalog["lead"]}
        if (not isinstance(registry_roles, list)
                or any(not isinstance(role, str) for role in registry_roles)
                or len(registry_roles) != len(set(registry_roles))
                or set(registry_roles) != expected_specialists):
            fails.append("registry: %s roles must list every specialist exactly once and exclude "
                         "foreground lead %r" % (kit, catalog["lead"]))
    if (not isinstance(advertised, list)
            or any(not isinstance(name, str) for name in advertised)
            or len(advertised) != len(set(advertised))):
        fails.append("registry: %s presets must be a unique string list" % kit)
    elif catalog is not None and advertised != list(catalog["presets"]):
        fails.append("registry: %s presets %r do not match presets.yaml %r" %
                     (kit, advertised, list(catalog["presets"])))

# 8) model_map/effort_map <-> specialist agent frontmatter (catch tier drift in the shipped kit)
for cfg in glob.glob(ROOT + "/team-kits/*/templates/project_memory/project_config.yaml"):
    kit_dir = os.path.dirname(os.path.dirname(os.path.dirname(cfg)))   # -> team-kits/<kit>
    try:
        conf = yaml.load(open(cfg, encoding="utf-8").read(), Loader=UniqueKeyLoader) or {}
    except Exception:
        continue  # YAML parse already reported in step 2
    lead = "project-manager"  # the session lead is excluded from the maps
    sp = os.path.join(kit_dir, "settings", "settings.json")
    if os.path.isfile(sp):
        try:
            lead = json.load(open(sp, encoding="utf-8")).get("agent") or lead
        except Exception:
            pass
    specialists = {os.path.splitext(os.path.basename(a))[0]
                   for a in glob.glob(os.path.join(kit_dir, "agents", "*.md"))} - {lead}
    field_of = {"model_map": "model", "effort_map": "effort"}
    for mapname, field in field_of.items():
        m = conf.get(mapname) or {}
        keys = set(m)
        for missing in sorted(specialists - keys):
            fails.append("%s: %s missing specialist '%s'" % (rel(cfg), mapname, missing))
        for stray in sorted(keys - specialists):
            fails.append("%s: %s has key '%s' with no matching agent" % (rel(cfg), mapname, stray))
        if lead in keys:
            fails.append("%s: %s must NOT list the session lead '%s'" % (rel(cfg), mapname, lead))
        # each specialist MUST carry the field, and it must equal the map value
        for role in sorted(specialists):
            ap = os.path.join(kit_dir, "agents", role + ".md")
            try:
                afm = frontmatter(open(ap, encoding="utf-8").read()) or {}
            except Exception:
                continue
            if field not in afm:
                fails.append("%s: specialist missing '%s:' frontmatter" % (rel(ap), field))
            elif role in keys and str(afm[field]) != str(m[role]):
                fails.append("%s: %s:%s != %s '%s' (%s)" % (rel(ap), field, afm[field], mapname, m[role], role))
    # the session lead carries model: + effort: but is NOT in the maps
    lp = os.path.join(kit_dir, "agents", lead + ".md")
    if os.path.isfile(lp):
        lfm = frontmatter(open(lp, encoding="utf-8").read()) or {}
        for field in ("model", "effort"):
            if field not in lfm:
                fails.append("%s: session lead missing '%s:' frontmatter" % (rel(lp), field))
    # kit SOURCES are provider-neutral: a value in agent frontmatter must be one that still
    # resolves to a model on every provider. WHICH values those are is ASKED of `model_tiers.yaml`
    # through the generator that reads it, not spelled out here: the three tier aliases plus any
    # value the generator carries across providers without being a concrete reference-platform name
    # of its own -- today that second half is `fable`, the §11 escalation pin the tiers file
    # documents and `gen_provider_artifacts.provider_model` maps to every other provider's LEAD
    # tier. The enumeration that stood here ("lead/worker/light") failed the day FR-0051 pinned the
    # two PMs to fable: a legitimate, generator-supported value refused by a list that had never
    # heard of it. `test_the_neutral_model_values_are_the_ones_the_generator_can_carry` (in
    # `tools/test_hooks.py`) measures both ends of the derivation.
    for ap in glob.glob(os.path.join(kit_dir, "agents", "*.md")):
        try:
            afm = frontmatter(open(ap, encoding="utf-8").read()) or {}
        except Exception:
            continue
        if "model" in afm and not provider_neutral_model(str(afm["model"]),
                                                         _MODEL_TIERS, _MODEL_ALIASES):
            # The generator's own sentence when the TABLE cannot place the value at all (a retired
            # rung: the DEC-0076 case); the neutrality sentence when it can but a source may not
            # carry it (an alias target such as `opus`).
            if not table_places(str(afm["model"]), _MODEL_TIERS, _MODEL_ALIASES):
                fails.append("%s: %s" % (rel(ap), unplaceable_pin_sentence(
                    "the role", afm["model"], _MODEL_TIERS, _MODEL_ALIASES)))
            else:
                fails.append("%s: model '%s' — a kit source carries a provider-NEUTRAL model value: a "
                             "rung alias (%s) or a value model_tiers.yaml maps per provider without "
                             "being an alias target"
                             % (rel(ap), afm["model"], "/".join(sorted(_MODEL_ALIASES))))

# 9) kit VERSION stamps must match the kit content (forgetting a bump is a CI failure), and the
#    constitution marker must sit on line 1 (session_status parses only the first line for the kit key —
#    if it ever moved, update detection would go blind silently).
sys.path.insert(0, os.path.join(ROOT, "tools"))
from bump_kit_version import discover_kits, kit_hash  # noqa: E402

for kit in discover_kits(ROOT):
    kit_dir = os.path.join(ROOT, "team-kits", kit)
    vfile = os.path.join(kit_dir, "VERSION")
    if not os.path.isfile(vfile):
        fails.append("%s: missing team-kits/%s/VERSION — run python tools/bump_kit_version.py" % (kit, kit))
    elif ("content: %s" % kit_hash(kit_dir)) not in open(vfile, encoding="utf-8").read():
        fails.append("%s: kit files changed but VERSION not bumped — run python tools/bump_kit_version.py" % kit)
    cpath = os.path.join(kit_dir, "constitution", "AGENTS.md")
    if not os.path.isfile(cpath):
        fails.append("%s: missing constitution/AGENTS.md (renamed from CLAUDE.md — the source file "
                     "carries the vendor-neutral name it ships under)" % kit)
    else:
        lines = open(cpath, encoding="utf-8", errors="ignore").read().splitlines()
        first = lines[0].lstrip("\ufeff") if lines else ""
        # DEC-0039: session_status reads the marker only in the SHIM FORM on line 1
        # (`<!-- agents-and-skills:team-kit <team> -->`), not as a bare occurrence anywhere on it.
        # The constitution's line 1 IS the shim source scaffold_team copies, so it must match that
        # exact form — otherwise a real install detects no kit and update detection goes blind.
        if not re.match(r"\s*<!--\s*agents-and-skills:team-kit\s+[\w-]+\s*-->\s*$", first):
            fails.append("%s: constitution line 1 is not the kit shim marker "
                         "`<!-- agents-and-skills:team-kit <team> -->` — session_status reads only "
                         "that shim form on line 1 (DEC-0039)" % kit)
        # THE ONE SIZE STATEMENT ABOUT A CONSTITUTION — through the package it is part of, and in
        # BYTES. What stood here was a 220-LINE ceiling on the constitution and a second one on the
        # lead SKILL, and measured they said nothing about size: all three constitutions held the
        # limit only because 31 to 46 of their lines ran 110-1899 characters (reflowed to 100
        # columns: 383/368/394 lines), while a compaction pilot cut 24.9 % of the bytes and RAISED
        # its line count from 20 to 36. A line ceiling beside a byte budget is a ceiling that pushes
        # against it. Removed rather than replaced by a per-file byte number: nothing derives one.
        #
        # AND THE CEILING IS NO LONGER A CONSTANT EITHER (2026-08-03, spec II.5). 25 600 was "25 KB"
        # read at 1024 B — typography, not a computation — it was missed by all three kits by 6 to
        # 10 KB even after de-duplication, and it only WARNED. A limit every subject misses forever
        # and that warns is a number people step over. What is derivable is the measurement, so the
        # ceiling per kit IS the recorded measurement in `tools/lead_package_sizes.json`, this is a
        # FAILURE rather than a warning (II.11/3 asked for hard; it can be hard because the record
        # starts satisfied), and the record moves only through
        # `python tools/record_lead_package_sizes.py --write --note "<reason>"`.
        #
        # IT NAMES WHAT IT WEIGHED, from the same derivation it weighed it with. The sentence used
        # to read "agent.md + Lead-SKILL + constitution all load at every session start", and one
        # third of that was false: the lead SKILL is registered on demand, not injected (measured
        # 2026-08-02 — `lead_package.files` carries the measurement). A message that misnames its
        # own subject sends the shortening at the wrong file.
        total = lead_package.size(kit_dir)
        recorded = lead_package.ceiling(kit_dir)
        weighed = " + ".join(os.path.relpath(path, kit_dir).replace(os.sep, "/")
                             for path in lead_package.files(kit_dir))
        if recorded is None:
            # NO RECORD IS NOT PERMISSION. A kit the recorder has never seen would otherwise be the
            # one place a package could grow without limit, which is the hole a ratchet exists to
            # not have.
            fails.append("%s: lead instruction package is %d bytes and has no recorded size "
                         "(spec II.5) — %s load at every session start. Run "
                         "python tools/record_lead_package_sizes.py --write --note \"...\"."
                         % (kit, total, weighed))
        elif total > recorded:
            fails.append("%s: lead instruction package is %d bytes (> %d recorded, spec II.5) — %s "
                         "load at every session start. Shorten it, or raise the record with a "
                         "reason: python tools/record_lead_package_sizes.py --write --note \"...\"."
                         % (kit, total, recorded, weighed))

# 10) intended-identical hooks/scripts must stay byte-identical across kits (audit finding: a fix
#    applied in one kit silently diverges the others — exactly the drift class this repo hunts).
MIRROR_DEV_RESEARCH = [
    "hooks/guard_yaml_valid.py", "hooks/guard_agent_spawn.py", "hooks/notify_agent_events.py",
    "hooks/guard_scratchpad_ref.py", "hooks/gate_subagent_output.py", "hooks/guard_harness_selfmod.py",
    "hooks/guard_pm_scope.py", "hooks/guard_no_adhoc.py", "hooks/guard_question_context.py",
    "hooks/gate_memory_complete.py", "hooks/gate_pipeline.py", "hooks/guard_guidelines.py",
    "hooks/_root.py", "hooks/_audit.py", "hooks/_compat.py",
    "templates/repo/scripts/quality.py", "templates/repo/scripts/kit_checks.py",
    "templates/repo/scripts/kit_browser_checks.py", "templates/repo/scripts/retro.py",
    # kit-NEUTRAL by content (it names project_memory/** and generic source dirs, nothing dev- or
    # research-specific), so the two copies have always been identical and a fix to one belongs in
    # both. It was carried along in the phase-2 lockstep on that reasoning while nothing held it —
    # the office copy is deliberately different (a document workspace, not a code repo) and stays
    # out of every mirror set.
    "templates/repo/.claude/claude-security-guidance.md",
]
MIRROR_DEV_OFFICE = [
    "hooks/guard_yaml_valid.py", "hooks/guard_agent_spawn.py", "hooks/notify_agent_events.py",
    "hooks/guard_scratchpad_ref.py", "hooks/gate_subagent_output.py", "hooks/guard_harness_selfmod.py",
    "hooks/guard_question_context.py", "hooks/guard_pm_scope.py", "hooks/guard_no_adhoc.py",
    "hooks/_root.py", "hooks/_audit.py", "hooks/_compat.py",
]
for other, names in (("research-team", MIRROR_DEV_RESEARCH), ("office-team", MIRROR_DEV_OFFICE)):
    for name in names:
        a = os.path.join(ROOT, "team-kits", "dev-team", name)
        b = os.path.join(ROOT, "team-kits", other, name)
        if not (os.path.isfile(a) and os.path.isfile(b)):
            fails.append("mirror: %s missing in dev-team or %s" % (name, other))
        elif open(a, "rb").read() != open(b, "rb").read():
            fails.append("mirror: %s diverged between dev-team and %s — copy the fixed file" % (name, other))

# 11) every §-reference in hooks/skills/agents AND in the constitution itself must resolve to a
#     heading (## N.) or a bold anchor (**Na.) in that kit's constitution — a block message citing
#     a deleted paragraph teaches the agent to look for nothing (audit finding after the
#     constitution diet). The constitution is in the list because it cites itself more than any
#     other file does, and an unchecked self-reference is exactly how four office `(§8)` pointers
#     shipped aiming at a section that did not carry the rule they cited.
import re as _re  # noqa: E402
for kit_dir_name in os.listdir(os.path.join(ROOT, "team-kits")):
    cpath = os.path.join(ROOT, "team-kits", kit_dir_name, "constitution", "AGENTS.md")
    if not os.path.isfile(cpath):
        continue
    cons = open(cpath, encoding="utf-8", errors="ignore").read()
    anchors = set(_re.findall(r"(?m)^##+\s*(\d+[a-z]?)\.", cons))
    anchors |= set(_re.findall(r"(?m)^\*\*(\d+[a-z]?)\.", cons))
    for pattern in ("constitution/AGENTS.md", "hooks/*.py", "skills/*/SKILL.md", "agents/*.md"):
        for p in glob.glob(os.path.join(ROOT, "team-kits", kit_dir_name, pattern)):
            txt = open(p, encoding="utf-8", errors="ignore").read()
            for m in _re.finditer(r"§(\d+[a-z]?)", txt):
                # a `§2.7`-style sub-reference resolves to its PARENT section, so the parent is
                # what has to exist. Skipping the whole reference (the earlier behaviour) let
                # `§99.1` through, which is the same dead pointer one level down.
                if m.group(1) not in anchors:
                    fails.append("%s: references §%s which does not exist in %s's constitution"
                                 % (rel(p), m.group(1), kit_dir_name))
                    break  # one finding per file is enough

# 12) every file the kit hash covers must be git-tracked. An ignored-but-present file makes
#     VERSION true only on THIS machine: a real .gitignore'd office seed kept local validate green
#     while CI was red and fresh clones could not install (the hash walks the FILESYSTEM).
import subprocess as _sp  # noqa: E402
# READ THE HASH'S OWN ENUMERATION, do not re-walk the tree beside it. This check used to walk the
# kit directory with its own copy of the skip rules, which meant it covered the kit's half of the
# subject and not the SHARED half -- an untracked file at the team-kits root is hashed into every
# kit and was reported by nobody. `kit_hash_inputs` is what `kit_hash` iterates, so "hashed into
# VERSION" is answered by the thing that does the hashing.
sys.path.insert(0, os.path.join(ROOT, "team-kits"))  # noqa: E402
from kernel.hashing import kit_hash_inputs  # noqa: E402
try:
    _git = _sp.run(["git", "ls-files", "team-kits"], cwd=ROOT, capture_output=True,
                   text=True, timeout=30)
    _tracked = set(_git.stdout.splitlines()) if _git.returncode == 0 else None
except Exception:
    _tracked = None  # no git available (e.g. an exported tree) — hash/track parity is then moot
if _tracked is not None:
    _untracked = set()
    for kit in discover_kits(ROOT):
        for _name, _path in kit_hash_inputs(os.path.join(ROOT, "team-kits", kit)):
            if _path is None:
                # a directory link contributes its NAME to the hash and no content (see
                # `_kit_files`); there is no file here to ask git about
                continue
            relp = os.path.relpath(_path, ROOT).replace("\\", "/")
            if relp not in _tracked:
                # deduplicated across kits: a shared input is in all three hashes and one finding
                # per file is what a reader can act on
                _untracked.add(relp)
    for relp in sorted(_untracked):
        fails.append("%s is hashed into a kit VERSION but not git-tracked "
                     "(check .gitignore) — CI and fresh clones will disagree "
                     "with the local hash" % relp)

if fails:
    print("VALIDATION FAILED (%d):" % len(fails))
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("validate.py: all structural checks passed.")
