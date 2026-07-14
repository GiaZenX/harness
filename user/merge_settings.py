#!/usr/bin/env python3
"""
merge_settings.py <ours.json> <target.json>

Top-level-merges the agents-and-skills global keys (<ours.json>) into the user's
<target.json>, preserving every other key the user already has. Keys starting with
'_' (comments) are skipped. The previous target is backed up to <target>.bak before
writing. Used by the installer so personal settings (model, theme, permissions, …)
survive the install.
"""
import sys
import os
import json
import shutil


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: merge_settings.py <ours.json> <target.json>\n")
        sys.exit(2)
    ours_path, target_path = sys.argv[1], sys.argv[2]

    with open(ours_path, encoding="utf-8") as fh:
        ours = json.load(fh)
    ours = {k: v for k, v in ours.items() if not k.startswith("_")}

    target = {}
    if os.path.isfile(target_path):
        try:
            with open(target_path, encoding="utf-8") as fh:
                target = json.load(fh) or {}
        except Exception as exc:
            sys.stderr.write("WARN: could not parse %s (%s); writing fresh.\n" % (target_path, exc))
            target = {}
        shutil.copy2(target_path, target_path + ".bak")

    added = [k for k in ours if k not in target]
    overwritten = [k for k in ours if k in target and k != "permissions"]
    for key, val in ours.items():
        if key == "permissions" and isinstance(val, dict) and isinstance(target.get("permissions"), dict):
            # Deep-merge permissions: UNION allow/deny (dedup, order-preserving). Any OTHER
            # permission sub-key we ship DOES overwrite the user's value — which is exactly why
            # the shipped defaults deliberately contain none (an audit caught this file claiming
            # "defaultMode untouched" while the code below overwrote it; never ship a global
            # defaultMode — removing the user's veto everywhere is not an installer's call).
            tperm = target["permissions"]
            for sub, sval in val.items():
                if sub in ("allow", "deny") and isinstance(sval, list):
                    existing = tperm.get(sub) if isinstance(tperm.get(sub), list) else []
                    merged = list(existing)
                    for item in sval:
                        if item not in merged:
                            merged.append(item)
                    tperm[sub] = merged
                else:
                    tperm[sub] = sval
        else:
            target[key] = val

    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as fh:
        json.dump(target, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    sys.stdout.write(
        "merged settings: +%s  ~%s  (preserved %d other keys)\n"
        % (",".join(added) or "-", ",".join(overwritten) or "-",
           len([k for k in target if k not in ours]))
    )


if __name__ == "__main__":
    main()
