#!/usr/bin/env python3
"""Classify a JUnit XML into PASS / KNOWN-ISSUE / FAIL / INCONCLUSIVE.

Usage: classify_junit.py <junit.xml> <known-issues.txt>
Exit:  0 = all real tests passed (known-issue failures tolerated)
       1 = real failures (image or genuine SDK regressions)
       2 = inconclusive (nothing ran, or every test skipped)
"""
import sys, os, re, glob, xml.etree.ElementTree as ET

xml_path, known_path = sys.argv[1], sys.argv[2]
known = []
if os.path.exists(known_path):
    known = [re.compile(l.strip()) for l in open(known_path)
             if l.strip() and not l.lstrip().startswith("#")]

files = glob.glob(xml_path) or [xml_path]
total = skipped = 0
failed = []
for f in files:
    if not os.path.exists(f):
        continue
    for tc in ET.parse(f).getroot().iter("testcase"):
        total += 1
        name = f"{tc.get('classname','')}.{tc.get('name','')}"
        if any(c.tag == "skipped" for c in tc):
            skipped += 1
        elif any(c.tag in ("failure", "error") for c in tc):
            failed.append(name)

ran = total - skipped
real = [n for n in failed if not any(k.search(n) for k in known)]
knownf = [n for n in failed if any(k.search(n) for k in known)]

print(f"tests={total} ran={ran} skipped={skipped} "
      f"failed={len(failed)} real-fail={len(real)} known-issue={len(knownf)}")
for n in real:   print(f"  FAIL         {n}")
for n in knownf: print(f"  KNOWN-ISSUE  {n}")

if ran == 0:
    print("INCONCLUSIVE: no tests executed (server unreachable or all skipped)")
    sys.exit(2)
sys.exit(1 if real else 0)
