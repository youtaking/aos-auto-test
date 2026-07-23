#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查 tests/suites/ 下的测试代码是否有变化，与上次评审时的快照对比"""
import hashlib
import json
import sys
from pathlib import Path

SUITES_DIR = Path("tests/suites")
SNAPSHOT_FILE = Path("docs/.review_snapshot.json")

def compute_hashes():
    """计算所有测试文件的 MD5"""
    hashes = {}
    for f in sorted(SUITES_DIR.glob("test_*.py")):
        content = f.read_text(encoding="utf-8")
        hashes[f.name] = hashlib.md5(content.encode("utf-8")).hexdigest()
    return hashes

def load_snapshot():
    if SNAPSHOT_FILE.exists():
        return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    return None

def save_snapshot(hashes):
    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_FILE.write_text(json.dumps(hashes, indent=2, ensure_ascii=False), encoding="utf-8")

def main():
    current = compute_hashes()
    old = load_snapshot()

    if old is None:
        save_snapshot(current)
        print("FIRST_RUN")
        return

    changed = []
    added = []
    deleted = []

    for name, h in current.items():
        if name not in old:
            added.append(name)
        elif old[name] != h:
            changed.append(name)

    for name in old:
        if name not in current:
            deleted.append(name)

    if changed or added or deleted:
        save_snapshot(current)
        parts = []
        if added:
            parts.append(f"新增: {', '.join(added)}")
        if changed:
            parts.append(f"修改: {', '.join(changed)}")
        if deleted:
            parts.append(f"删除: {', '.join(deleted)}")
        print("CHANGED|" + " | ".join(parts))
    else:
        print("NO_CHANGE")

if __name__ == "__main__":
    main()
