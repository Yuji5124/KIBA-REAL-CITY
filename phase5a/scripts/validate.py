#!/usr/bin/env python3
"""Validate Phase 5A local data and confirm the protected v07 hashes."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "output/KIBA_REAL_CITY_v07.blend": "649388c21f230fe048c79ce67460dc0916a42aceed9de5cc0205b477e924da16",
    "output/KIBA_REAL_CITY_v07.glb": "4830f6f43a0cadcf8ac0388b5ff5fa519a9c72fe8bed9b596d87afc30991eebb",
    "output/geo_reference_v07.json": "ac0ad9987c51c5798c3abd99c805f86d22405dabbeeae5cc7e85709843b5b4dc",
}

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    data = json.loads((ROOT / "phase5a/processed/viewer_features.json").read_text(encoding="utf-8"))
    georef = json.loads((ROOT / "phase5a/metadata/georeference.json").read_text(encoding="utf-8"))
    hashes = {name: digest(ROOT / name) for name in EXPECTED}
    checks = {
        "v07_hashes_unchanged": {"status": "PASS" if hashes == EXPECTED else "FAIL", "actual": hashes},
        "crs_and_axes": {"status": "PASS" if data.get("crs") == "EPSG:6677" and data.get("threeAxes") == "X=east, Y=up, Z=-north" else "FAIL"},
        "unique_feature_ids": {"status": "PASS" if len([f["featureId"] for k in ("roads", "trees", "vegetation") for f in data[k]]) == len(set(f["featureId"] for k in ("roads", "trees", "vegetation") for f in data[k])) else "FAIL"},
        "terrain_vertical_datum_license": {"status": "BLOCKED", "reason": data["terrain"]["reason"]},
        "osm_full_terms_and_redistribution": {"status": "BLOCKED", "reason": data["source"]["licenseReview"]},
        "device_performance": {"status": "NOT_APPLICABLE", "reason": "No real browser or device FPS measurement was performed."},
    }
    checks["georeference_consistency"] = {"status": "PASS" if georef.get("crs") == data.get("crs") and georef.get("centerProjectedM") == data.get("centerProjectedM") and georef.get("v07Sha256") == hashes else "FAIL"}
    report = {"generatedAtUtc": datetime.now(timezone.utc).isoformat(), "counts": {key: len(data[key]) for key in ("roads", "trees", "vegetation")}, "checks": checks,
              "summary": "PASS_WITH_BLOCKERS" if all(v["status"] in ("PASS", "BLOCKED", "NOT_APPLICABLE") for v in checks.values()) and all(v["status"] != "FAIL" for v in checks.values()) else "FAIL"}
    report_dir = ROOT / "phase5a/reports"; report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = ["# Phase 5A validation", "", f"Generated: {report['generatedAtUtc']}", "", f"Status: **{report['summary']}**", "", f"Counts: roads {report['counts']['roads']}, individual trees {report['counts']['trees']}, vegetation {report['counts']['vegetation']}", "", "| Check | Status |", "|---|---|"]
    rows += [f"| {key} | {value['status']} |" for key, value in checks.items()]
    (report_dir / "validation.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["summary"] == "PASS_WITH_BLOCKERS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
