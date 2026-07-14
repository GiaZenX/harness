#!/usr/bin/env python3
"""
merge_settings.py <ours.json> <target.json>

Adds missing agents-and-skills global defaults (<ours.json>) to the user's
<target.json>. Existing user values always win, including personal settings such as
theme and statusLine. permissions.allow and permissions.deny are the exception: valid
lists are unioned without duplicates while preserving the user's order. Keys starting
with '_' (comments) are skipped. The previous target is backed up to <target>.bak
before writing.
"""
import json
import os
import shutil
import sys


def _merge_unique(existing, defaults):
    """Return an order-preserving union with the user's entries first."""
    merged = []
    for item in list(existing) + list(defaults):
        if item not in merged:
            merged.append(item)
    return merged


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: merge_settings.py <ours.json> <target.json>\n")
        sys.exit(2)
    ours_path, target_path = sys.argv[1], sys.argv[2]

    with open(ours_path, encoding="utf-8") as fh:
        ours = json.load(fh)
    if not isinstance(ours, dict):
        sys.stderr.write("ERROR: defaults in %s must be a JSON object.\n" % ours_path)
        sys.exit(2)
    ours = {k: v for k, v in ours.items() if not k.startswith("_")}

    target = {}
    if os.path.isfile(target_path):
        try:
            with open(target_path, encoding="utf-8") as fh:
                target = json.load(fh) or {}
        except Exception as exc:
            sys.stderr.write(
                "ERROR: could not parse %s (%s); left unchanged.\n"
                % (target_path, exc)
            )
            sys.exit(2)

    if not isinstance(target, dict):
        sys.stderr.write(
            "ERROR: existing settings in %s must be a JSON object; left unchanged.\n"
            % target_path
        )
        sys.exit(2)
    if os.path.isfile(target_path):
        shutil.copy2(target_path, target_path + ".bak")

    added = [k for k in ours if k not in target]
    preserved = [k for k in ours if k in target and k != "permissions"]
    permission_additions = {"allow": 0, "deny": 0}
    for key, val in ours.items():
        if key == "permissions" and isinstance(val, dict) and isinstance(target.get(key), dict):
            # Existing permission sub-keys win too. Only allow/deny receive special union
            # semantics, and malformed existing values are preserved rather than silently
            # replaced by installer defaults.
            tperm = target["permissions"]
            for sub, sval in val.items():
                if sub not in tperm:
                    tperm[sub] = sval
                elif sub in ("allow", "deny") and isinstance(sval, list):
                    existing = tperm[sub]
                    if isinstance(existing, list):
                        user_unique = _merge_unique(existing, [])
                        merged = _merge_unique(user_unique, sval)
                        permission_additions[sub] = len(merged) - len(user_unique)
                        tperm[sub] = merged
                    else:
                        sys.stderr.write(
                            "WARN: preserving non-list permissions.%s in %s; defaults not merged.\n"
                            % (sub, target_path)
                        )
        elif key not in target:
            target[key] = val
        else:
            # Existing top-level values are personal configuration and always win.
            continue

    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as fh:
        json.dump(target, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    sys.stdout.write(
        "merged settings: added defaults=%s; preserved existing=%s; "
        "permissions +allow=%d +deny=%d; preserved %d unrelated keys\n"
        % (",".join(added) or "-", ",".join(preserved) or "-",
           permission_additions["allow"], permission_additions["deny"],
           len([k for k in target if k not in ours]))
    )


if __name__ == "__main__":
    main()
