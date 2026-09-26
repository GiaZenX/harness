"""The user's idea of 2026-09-26: comments placed directly on a design preview with the '#' key. Thin FR in the inbox.
Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "FR"]

BODY = {
    "title": "Kommentare direkt in der Design-Vorschau: Taste '#' oeffnet am Mauszeiger ein Kommentarfeld, der "
             "Kommentar haengt an der Stelle und landet als Eingabe beim Designer",
    "request_text": "User 2026-09-26: 'Bei den Design-Vorschauen waere es cool, wenn man Kommentare hinzufuegen "
                    "koennte. Also z. B. einfach mit der Taste \"#\", dann erscheint auf dem Mauszeiger ein "
                    "Kommentarfeld und man kann einen Kommentar an die Stelle schreiben ... das waere Gold wert.' "
                    "LEAD'S READING (not yet a design): the designer stages a self-contained HTML draft "
                    "(staging/<task>/DSN-nnnn.html, product-designer SKILL 'VISIBLE preview'; frozen on approval as "
                    "design/revisions/DSN-nnnn.rNN.html; kit_design_render.py renders it). The draft itself must stay "
                    "clean (it becomes the visual contract), so the comment layer is NOT written into it: a kit-owned "
                    "review viewer (e.g. scripts/kit_design_review.py <task>) serves the draft locally and INJECTS an "
                    "overlay -- '#' outside a text field opens a box at the cursor; each comment is anchored to the "
                    "element under the cursor (CSS path + offset + data-view + viewport), shown as a numbered pin, "
                    "and saved to a record the designer must answer in the next iteration (open/done per comment, "
                    "the SIGHT loop reads it; nothing freezes with an open comment). Open questions for the design "
                    "round: where the record lives given gate_write_scope (kernel capture vs staging), whether the "
                    "same overlay works on the BUILT app (kit_browser_checks), Codex parity, and the keyboard layout "
                    "('#' is a direct key on German keyboards, Shift+3 on US).",
    "source": "user message 2026-09-26 ~08:10 (Desktop session); team-kits/dev-team/skills/product-designer/SKILL.md; "
              "team-kits/dev-team/templates/repo/scripts/kit_design_render.py",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr[-1500:])
sys.exit(result.returncode)
