"""Offline, generic v2/v3 comparison. Uses no key, network or song identities.

Run from the project root: python -m tools.compare_genre_profiles
The optional frozen v2 baseline is produced before an engine edit and lives in
artifacts/color_v2_profiles.json. Without it, prints only the current results.
"""
import json
from html import escape
from pathlib import Path

from app.services.mood_engine import analyze_tags


def main():
    root = Path(__file__).resolve().parents[1]
    profiles = json.loads((root / "tests/fixtures/genre_profiles.json").read_text(encoding="utf-8"))
    baseline_path = root / "artifacts/color_v2_profiles.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.exists() else {}
    outputs = {}
    for name, case in profiles.items():
        after = analyze_tags(case["tags"], source=case["source"])
        before = baseline.get(name, {}).get("before")
        outputs[name] = case | {"before": before, "after": after}
        old = " / ".join(c["hex"] for c in before["palette"][:3]) if before else "baseline unavailable"
        new = " / ".join(c["hex"] for c in after["palette"][:3])
        print(f"{name}: {old} -> {new}")
        print("  families: " + ", ".join(f"{f['family']}={f['share']:.1f}%" for f in after["genre_families"]))
        print("  roles: " + ", ".join(f"{role}={after['palette_anchors'][role]['family']} ({after['palette_anchors'][role]['source']})" for role in ("Primary", "Secondary", "Accent")))
    destination = root / "artifacts/color_v3_profiles.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
    cards = []
    for name, case in outputs.items():
        rows = []
        for label, key in (("v2", "before"), ("v3", "after")):
            if not case[key]:
                continue
            swatches = "".join(
                f'<div class="swatch" style="background:{c["hex"]};color:{c["text"]}"><span>{escape(c["label"])}</span><strong>{c["hex"]}</strong></div>'
                for c in case[key]["palette"]
            )
            rows.append(f'<p>{label}</p><div class="row">{swatches}</div>')
        shares = ", ".join(f'{f["label"]} {f["share"]:.1f}%' for f in case["after"]["genre_families"])
        cards.append(f'<section><h2>{escape(name)}</h2><small>{escape(shares or "Neutral — no evidence")}</small>{"".join(rows)}</section>')
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TONESCAPE v2 / v3 fixture comparison</title><style>
*{box-sizing:border-box}body{background:#131510;color:#eeefdf;font:14px/1.6 Arial,sans-serif;margin:0 auto;padding:32px 20px;max-width:1050px}
h1{font-size:30px;font-weight:500}h2{font-size:19px;margin-bottom:4px}small,p{color:#b8bfac}section{padding:24px 0;border-top:1px solid #3b4230;margin-top:30px}
.row{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4px}.swatch{padding:14px 10px;min-height:110px;display:flex;flex-direction:column;justify-content:space-between}.swatch span{font-size:11px}.swatch strong{font:13px monospace}
@media(max-width:500px){.swatch{padding:10px 4px;min-height:90px}.swatch strong{font-size:9px}.swatch span{font-size:9px}}
</style><h1>TONESCAPE — v2 / v3</h1><p>Offline synthetic fixtures. Each supplied tag has count=100. Not captured live Last.fm or deployed output.</p>'''
    (root / "artifacts/color_engine_v3_comparison.html").write_text(html + "".join(cards) + "</html>", encoding="utf-8")


if __name__ == "__main__":
    main()
