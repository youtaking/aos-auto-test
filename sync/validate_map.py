# -*- coding: utf-8 -*-
"""校验 coverage-map，并计算某段 main 变更命中的测试用例。

用法：
  python -X utf8 sync/validate_map.py
  python -X utf8 sync/validate_map.py --impact BASE_SHA HEAD_SHA --repo D:/path/FenixAgent
  python -X utf8 sync/validate_map.py --impact BASE HEAD --repo /workspace --json-out /tmp/impact.json
"""
import argparse
import fnmatch
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP_PATH = os.path.join(ROOT, 'sync', 'coverage-map.yml')

KINDS = ('unit', 'api', 'e2e')


def load_map(path):
    try:
        import yaml
    except ImportError:
        sys.exit('缺少 PyYAML，请先 pip install pyyaml')
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def matches(path, patterns):
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns or [])


def target_path(target):
    return os.path.join(ROOT, target.replace('/', os.sep))


def check_targets(doc):
    errors = []
    seen_ids = set()
    for rule in doc.get('rules', []):
        rid = rule.get('id')
        if not rid:
            errors.append('规则缺少 id')
            continue
        if rid in seen_ids:
            errors.append(f'id 重复: {rid}')
        seen_ids.add(rid)
        if not rule.get('match'):
            errors.append(f'{rid}: match 为空')
        for kind in KINDS:
            for target in (rule.get('targets') or {}).get(kind) or []:
                p = target_path(target)
                exists = os.path.isdir(p) if target.endswith('/') else os.path.isfile(p)
                if not exists:
                    errors.append(f'{rid}: {kind} 目标不存在 → {target}')
    return errors


def check_coverage(doc):
    """提醒：仓库里有、但没有任何规则指向的用例文件（只告警，不失败）。"""
    refs = set()
    for rule in doc.get('rules', []):
        for kind in KINDS:
            for target in (rule.get('targets') or {}).get(kind) or []:
                p = target_path(target)
                if os.path.isdir(p):
                    for base, dirs, files in os.walk(p):
                        dirs[:] = [d for d in dirs if d not in ('node_modules', '__pycache__')]
                        for name in files:
                            refs.add(os.path.normpath(os.path.join(base, name)))
                else:
                    refs.add(os.path.normpath(p))
    missing = []
    for sub in ('tests/api_suites', 'tests/suites', 'unit_tests'):
        for base, dirs, files in os.walk(target_path(sub)):
            dirs[:] = [d for d in dirs if d not in ('node_modules', '__pycache__')]
            for name in files:
                if name == 'conftest.py' or name == '__init__.py':
                    continue
                if not (name.endswith('.py') or name.endswith('.test.ts')):
                    continue
                full = os.path.normpath(os.path.join(base, name))
                if full not in refs:
                    missing.append(os.path.relpath(full, ROOT).replace(os.sep, '/'))
    return sorted(missing)


def git_changed(repo, base, head):
    out = subprocess.run(
        ['git', '-C', repo, 'diff', '--name-only', base, head],
        check=True, capture_output=True, text=True, encoding='utf-8')
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def impact(doc, changed):
    ignored, unmapped = [], []
    hit = {}
    for path in changed:
        if matches(path, doc.get('ignore')):
            ignored.append(path)
            continue
        rules = [r for r in doc.get('rules', []) if matches(path, r.get('match'))]
        if not rules:
            unmapped.append(path)
            continue
        for rule in rules:
            entry = hit.setdefault(rule['id'], {
                'mode': rule.get('mode', 'auto'),
                'files': [],
                'unit': set(),
                'api': set(),
                'e2e': set(),
            })
            entry['files'].append(path)
            for kind in KINDS:
                entry[kind].update((rule.get('targets') or {}).get(kind) or [])
    result = {
        'changed': len(changed),
        'ignored': ignored,
        'unmapped': unmapped,
        'rules': {
            rid: {
                'mode': value['mode'],
                'files': sorted(value['files']),
                **{kind: sorted(value[kind]) for kind in KINDS},
            }
            for rid, value in sorted(hit.items())
        },
    }
    auto = {kind: set() for kind in KINDS}
    manual_rules = []
    for rid, value in result['rules'].items():
        if value['mode'] == 'manual':
            manual_rules.append(rid)
            continue
        for kind in KINDS:
            auto[kind].update(value[kind])
    result['auto'] = {kind: sorted(auto[kind]) for kind in KINDS}
    result['manual_rules'] = manual_rules
    result['empty'] = not (result['unmapped'] or result['rules'])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--impact', nargs=2, metavar=('BASE', 'HEAD'))
    parser.add_argument('--repo', default=None)
    parser.add_argument('--json-out')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()

    doc = load_map(MAP_PATH)
    errors = check_targets(doc)
    if errors:
        for err in errors:
            print(f'❌ {err}')
        sys.exit(1)
    if not args.quiet:
        print(f'✅ coverage-map 校验通过：{len(doc.get("rules", []))} 条规则')

    if args.impact:
        base, head = args.impact
        repo = args.repo or os.environ.get('FENIXAGENT_REPO')
        if not repo:
            sys.exit('--impact 需要 --repo 或 FENIXAGENT_REPO')
        changed = git_changed(repo, base, head)
        result = impact(doc, changed)
        text = json.dumps(result, ensure_ascii=False, indent=2)
        if args.json_out:
            with open(args.json_out, 'w', encoding='utf-8') as fh:
                fh.write(text)
        if not args.quiet:
            print(text)
        return

    missing = check_coverage(doc)
    if missing and not args.quiet:
        print(f'⚠️  {len(missing)} 个用例文件未被任何规则覆盖（仅提示）：')
        for item in missing:
            print(f'   - {item}')


if __name__ == '__main__':
    main()
