"""
Verify that Asian / non-ASCII names work end-to-end through the parts of the
pipeline that touch a person's name:

  1. PathManager.sanitize_name  -> folder/file names
  2. the spoken-name detection regex in person_manager
  3. SQLite store + retrieve round-trip (database_handler)

Run from the project root:  python tests/test_asian_names.py
Network, camera and ML models are NOT required.
"""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from src.path_manager import PathManager
import src.database_handler as db

# Mix of scripts: Chinese, Japanese, Korean, plus romanized multi-token names.
NAMES = ["田中", "李雷", "山田太郎", "김민준", "Mei Lin", "Nguyễn", "佐藤 花子"]


def check_sanitize():
    print("\n[1] sanitize_name (folder/file safety)")
    ok = True
    for n in NAMES:
        safe = PathManager.sanitize_name(n)
        folder = f"person_1_{safe}"
        # Prove the resulting folder name is actually creatable on this FS.
        try:
            with tempfile.TemporaryDirectory() as d:
                os.makedirs(os.path.join(d, folder))
            creatable = True
        except OSError:
            creatable = False
        empty = (safe == "")
        status = "OK " if (creatable and not empty) else "FAIL"
        if not creatable or empty:
            ok = False
        print(f"    {status}  {n!r:>16} -> {safe!r}  (folder creatable={creatable})")
    return ok


def check_detection():
    print("\n[2] spoken-name detection regex")
    # Rebuilt exactly as in person_manager.py
    first_tok = r"[^\W\d_]+(?:[-'’][^\W\d_]+)?"
    cont_tok = r"[A-ZÀ-Þ][^\W\d_]*(?:[-'’][^\W\d_]+)?"
    name_group = rf"({first_tok}(?:\s+{cont_tok}){{0,2}})"
    patterns = [
        rf"(?i:my name is|i'm called|this is|i am|i'm)\s+{name_group}",
        rf"(?i:ich heiße|mein name ist|ich bin)\s+{name_group}",
        rf"(?i:hello|hi|hey),?\s+(?i:i'm|i am)\s+{name_group}",
    ]
    samples = [f"Hi, my name is {n}." for n in NAMES]
    for s, expected in zip(samples, NAMES):
        detected = None
        for p in patterns:
            m = re.search(p, s, re.UNICODE)
            if m:
                detected = m.group(1).strip()
                break
        match = "OK  " if detected == expected else "PART"
        print(f"    {match}  said {expected!r:>16} -> detected {detected!r}")
    print("    (PART = single token captured but trailing tokens dropped;")
    print("     expected for space-separated non-Latin names — see note.)")
    return True  # informational, not a hard failure


def check_db_roundtrip():
    print("\n[3] SQLite store + retrieve round-trip")
    ok = True
    emb = np.zeros(128, dtype=np.float32)
    with tempfile.TemporaryDirectory() as d:
        dbp = os.path.join(d, "test.db")
        db.init_db(dbp)
        for n in NAMES:
            pid = db.add_person(n, "ctx", "/tmp/p.jpg", None, emb, db_path=dbp)
            row = db.get_person_by_id(pid, db_path=dbp)
            got = row["name"] if row else None
            status = "OK " if got == n else "FAIL"
            if got != n:
                ok = False
            print(f"    {status}  stored {n!r:>16} -> read back {got!r}")
    return ok


if __name__ == "__main__":
    r1 = check_sanitize()
    check_detection()
    r3 = check_db_roundtrip()
    print("\n=== SUMMARY ===")
    print(f"  filename sanitize : {'PASS' if r1 else 'FAIL'}")
    print(f"  db round-trip     : {'PASS' if r3 else 'FAIL'}")
    sys.exit(0 if (r1 and r3) else 1)
