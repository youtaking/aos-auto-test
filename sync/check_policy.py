# -*- coding: utf-8 -*-
"""校验 AI 改动是否落在 sync/policy.yml 的白名单内。

用法：
  python -X utf8 sync/check_policy.py --repo /repo --json-out /artifacts/changes.json
"""
import argparse
import fnmatch
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY_PATH = os.path.join(ROOT, 'sync', 'policy.yml')


def load_policy(path):
    try:
        import yaml
    except ImportError:
        sys.exit('缺少 PyYAML，请先 pip install pyyaml')
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def norm(pattern):
    """目录形式的白名单补成 **，让 fnmatch 覆盖其下所有文件。"""
    return pattern + '**' if pattern.endswith('/') else pattern


def match_any(path, patterns):
    return any(fnmatch.fnmatch(path, norm(p)) for p in patterns or [])


def changed_files(repo):
    out = subprocess.run(['git', '-C', repo, 'status', '--porcelain', '-z'],
                         check=True, capture_output=True, encoding='utf-8')
    entries = out.stdout.split('\0')
    files = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status, path = entry[:2], entry[3:]
        if status.startswith('R') or status.startswith('C'):
            # 重命名/复制：下一条是原路径，改动以新路径为准
            index += 1
        files.append(path)
    return files


def classify(path):
    result = {'unit': [], 'python': []}
    if path.startswith('unit_tests/') and path.endswith('.test.ts'):
        result['unit'].append(path)
    if path.endswith('.py'):
        result['python'].append(path)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--policy', default=POLICY_PATH)
    parser.add_argument('--json-out')
    args = parser.parse_args()

    policy = load_policy(args.policy)
    ignore = policy.get('ignore_paths') or []
    allowed = policy.get('allowed_write_paths') or []
    forbidden = policy.get('forbidden_paths') or []
    limit = (policy.get('ai') or {}).get('max_files_changed', 40)

    files = [f for f in changed_files(args.repo) if not match_any(f, ignore)]
    violations = []
    for path in files:
        if match_any(path, forbidden):
            violations.append(f'{path}: 命中禁区')
        elif not match_any(path, allowed):
            violations.append(f'{path}: 不在允许写入的白名单内')
    if len(files) > limit:
        violations.append(f'改动 {len(files)} 个文件，超过上限 {limit}')

    buckets = {'unit': [], 'python': []}
    for path in files:
        for kind, items in classify(path).items():
            buckets[kind].extend(items)
    result = {'files': files, **buckets, 'violations': violations}

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        with open(args.json_out, 'w', encoding='utf-8') as fh:
            fh.write(text)

    print(f'[policy] 改动 {len(files)} 个文件，上限 {limit}')
    for path in files:
        print(f'   {path}')
    if violations:
        print('[policy] ❌ 违规：')
        for item in violations:
            print(f'   - {item}')
        sys.exit(1)
    print('[policy] ✅ 全部改动在白名单内')


if __name__ == '__main__':
    main()
