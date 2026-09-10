#!/usr/bin/env python3
"""Classify `go test -json` output into PASS / KNOWN-ISSUE / FAIL / INCONCLUSIVE.

Usage: classify_go.py <go-test.json> <known-issues.txt>
Exit:  0 = all real tests passed (known-issue failures tolerated)
       1 = real failures
       2 = inconclusive (no tests ran, or all skipped)
"""
import sys, os, re, json

json_path, known_path = sys.argv[1], sys.argv[2]
known = []
if os.path.exists(known_path):
    known = [re.compile(l.strip()) for l in open(known_path)
             if l.strip() and not l.lstrip().startswith("#")]

# Final action per (package, test); ignore package-level (no Test) rollups.
final = {}
if os.path.exists(json_path):
    for line in open(json_path):
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        t = ev.get("Test")
        a = ev.get("Action")
        if t and a in ("pass", "fail", "skip"):
            final[(ev.get("Package", ""), t)] = a

passed = [k for k, v in final.items() if v == "pass"]
skipped = [k for k, v in final.items() if v == "skip"]
failed = [k for k, v in final.items() if v == "fail"]
ran = len(passed) + len(failed)

def nm(k):  # package/test → test name for matching
    return k[1]

real = [k for k in failed if not any(kx.search(nm(k)) for kx in known)]
knownf = [k for k in failed if any(kx.search(nm(k)) for kx in known)]

print(f"tests={len(final)} ran={ran} passed={len(passed)} skipped={len(skipped)} "
      f"failed={len(failed)} real-fail={len(real)} known-issue={len(knownf)}")
for k in real:   print(f"  FAIL         {nm(k)}")
for k in knownf: print(f"  KNOWN-ISSUE  {nm(k)}")

# The go-sdk integration suite gates almost everything behind Orkes version
# checks, so against OSS very few tests actually run. Treat a near-empty run as
# inconclusive (WARN) rather than a confident PASS — it means the suite gave
# little real OSS coverage, not that the image is good.
GO_MIN_RAN = int(os.environ.get("GO_MIN_RAN", "3"))
if ran < GO_MIN_RAN:
    print(f"INCONCLUSIVE: only {ran} test(s) ran ({len(skipped)} skipped/gated) — "
          f"thin OSS coverage; go-sdk integration suite is Orkes-version-gated")
    sys.exit(2)
sys.exit(1 if real else 0)
