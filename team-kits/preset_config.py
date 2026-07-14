#!/usr/bin/env python3
"""Strict parser and resolver for team-kit presets.yaml files.

The scaffold scripts and repository validator deliberately share this implementation. Presets are
an enforcement input: accepting duplicate YAML keys, unknown roles, or the foreground lead as a
specialist would make the installed role set depend on the parser or invocation path.
"""
import argparse
import json
import os
import re
import sys

import yaml


SIMPLE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects duplicate mapping keys at every nesting level."""


def _construct_unique_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ValueError("unhashable YAML mapping key at line %d" %
                             (key_node.start_mark.line + 1)) from exc
        if duplicate:
            raise ValueError("duplicate YAML key %r at line %d" %
                             (key, key_node.start_mark.line + 1))
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _read_json_object(path):
    try:
        with open(path, encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ValueError("invalid settings/settings.json: %s" % exc) from exc
    if not isinstance(data, dict):
        raise ValueError("settings/settings.json must contain a JSON object")
    return data


def load_preset_catalog(kit_dir):
    """Return validated kit preset metadata.

    The returned mapping contains ``lead``, all known ``roles``, and an insertion-ordered
    ``presets`` mapping. Each preset resolves to ``None`` for ``all`` or a tuple of specialist
    roles. The lead is always installed separately and therefore must never appear in a preset.
    """
    kit_dir = os.path.abspath(kit_dir)
    agents_dir = os.path.join(kit_dir, "agents")
    presets_path = os.path.join(kit_dir, "presets.yaml")
    settings_path = os.path.join(kit_dir, "settings", "settings.json")

    if not os.path.isdir(agents_dir):
        raise ValueError("missing agents/ directory")
    role_files = [name for name in os.listdir(agents_dir)
                  if os.path.isfile(os.path.join(agents_dir, name)) and name.endswith(".md")]
    roles = [name[:-3] for name in sorted(role_files)]
    invalid_roles = [role for role in roles if not SIMPLE_NAME.fullmatch(role)]
    if invalid_roles:
        raise ValueError("agent filenames must use simple role names: %s" %
                         ", ".join(invalid_roles))
    if not roles:
        raise ValueError("agents/ contains no role files")

    settings = _read_json_object(settings_path)
    lead = settings.get("agent")
    if not isinstance(lead, str) or not SIMPLE_NAME.fullmatch(lead):
        raise ValueError("settings/settings.json agent must be a non-empty simple role name")
    if lead not in roles:
        raise ValueError("foreground lead %r has no matching agents/%s.md" % (lead, lead))

    try:
        with open(presets_path, encoding="utf-8-sig") as handle:
            source = handle.read()
        data = yaml.load(source, Loader=UniqueKeyLoader)
    except OSError as exc:
        raise ValueError("missing or unreadable presets.yaml: %s" % exc) from exc
    except (yaml.YAMLError, ValueError) as exc:
        raise ValueError("invalid presets.yaml: %s" % exc) from exc
    if not isinstance(data, dict) or not data:
        raise ValueError("presets.yaml must be a non-empty mapping")

    known = set(roles)
    presets = {}
    for name, raw_roles in data.items():
        if not isinstance(name, str) or not SIMPLE_NAME.fullmatch(name):
            raise ValueError("preset names must match [A-Za-z0-9_-]+")
        if not isinstance(raw_roles, str) or not raw_roles.strip():
            raise ValueError("preset %r must be 'all' or a space-separated role string" % name)
        value = raw_roles.strip()
        if value == "all":
            presets[name] = None
            continue
        selected = value.split()
        invalid = [role for role in selected if not SIMPLE_NAME.fullmatch(role)]
        if invalid:
            raise ValueError("preset %r contains invalid role name(s): %s" %
                             (name, ", ".join(invalid)))
        if len(set(selected)) != len(selected):
            raise ValueError("preset %r contains duplicate specialist roles" % name)
        if lead in selected:
            raise ValueError("preset %r must not list foreground lead %r as a specialist" %
                             (name, lead))
        unknown = sorted(set(selected) - known)
        if unknown:
            raise ValueError("preset %r references unknown role(s): %s" %
                             (name, ", ".join(unknown)))
        presets[name] = tuple(selected)

    return {"lead": lead, "roles": tuple(roles), "presets": presets}


def resolve_preset(kit_dir, preset, source="argument"):
    catalog = load_preset_catalog(kit_dir)
    if preset not in catalog["presets"]:
        available = ", ".join(catalog["presets"])
        raise ValueError("unknown preset %r (source: %s); available: %s" %
                         (preset, source, available))
    selected = catalog["presets"][preset]
    return {
        "preset": preset,
        "lead": catalog["lead"],
        "all": selected is None,
        "roles": [] if selected is None else list(selected),
        "available": list(catalog["presets"]),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--kit", required=True, help="team-kit directory")
    parser.add_argument("--preset", help="preset to resolve; omit for validation only")
    parser.add_argument("--source", default="argument", help="preset source for diagnostics")
    parser.add_argument("--format", choices=("json", "shell"), default="json")
    args = parser.parse_args(argv)
    try:
        if args.preset is None:
            catalog = load_preset_catalog(args.kit)
            result = {"lead": catalog["lead"],
                      "available": list(catalog["presets"])}
        else:
            result = resolve_preset(args.kit, args.preset, args.source)
    except ValueError as exc:
        print("Preset configuration error: %s. No scaffold files were changed." % exc,
              file=sys.stderr)
        return 1
    if args.format == "shell":
        if args.preset is None:
            print("%s\t%s" % (result["lead"], " ".join(result["available"])))
        else:
            selection = "all" if result["all"] else " ".join(result["roles"])
            print("%s\t%s" % (result["lead"], selection))
    else:
        print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
