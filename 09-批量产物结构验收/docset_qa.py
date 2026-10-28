# -*- coding: utf-8 -*-
"""docset_qa.py —— 声明式批量产物结构验收

同一套规则要检查几十个目录时用这个：目录叫「单元」，每个单元里文件名固定，
检查项全部写在 spec.json 里，脚本里不出现项目路径。

用法：
    python docset_qa.py --spec spec.json
    python docset_qa.py --spec spec.json --unit 2013      # 只查名字含 2013 的单元
    python docset_qa.py --selftest                        # 自检脚本本身

退出码：有任一单元不通过返回 1。
"""
from __future__ import print_function

import argparse
import fnmatch
import glob
import io
import json
import os
import re
import shutil
import sys
import tempfile


def read_text(path, encoding):
    with io.open(path, encoding=encoding) as fh:
        return fh.read()


def scope_texts(texts, scope):
    if not scope or scope == '*':
        return list(texts.values())
    return [t for n, t in texts.items() if fnmatch.fnmatch(n, scope)]


def check_unit(unit_dir, spec):
    issues = []
    stats = {}
    enc = spec.get('encoding', 'utf-8')
    min_bytes = spec.get('min_file_bytes', 0)

    texts = {}
    for name in spec.get('files', []):
        path = os.path.join(unit_dir, name)
        if not os.path.exists(path):
            issues.append(u'缺文件 %s' % name)
            continue
        size = os.path.getsize(path)
        if size < min_bytes:
            issues.append(u'%s 过小(%d < %d)' % (name, size, min_bytes))
        try:
            texts[name] = read_text(path, enc)
        except UnicodeDecodeError:
            issues.append(u'%s 不是 %s 编码' % (name, enc))
    if issues:
        return issues, stats

    for name, t in texts.items():
        for field in spec.get('header_fields', []):
            if field not in t:
                issues.append(u'%s 缺字段 %s' % (name, field))
        for sec in spec.get('sections', []):
            if sec not in t:
                issues.append(u'%s 缺分节 %s' % (name, sec))
        for sec in spec.get('blank_line_before', []):
            if sec in t and ('\n\n' + sec) not in t:
                issues.append(u'%s %s 前无空行' % (name, sec))
        for pat in spec.get('forbidden', []):
            if re.search(pat, t):
                issues.append(u'%s 命中禁用模式 %s' % (name, pat))
        for phrase in spec.get('duplicate_phrases', []):
            if t.count(phrase) > 1:
                issues.append(u'%s 重复出现 %s' % (name, phrase))

    for rule in spec.get('counts', []):
        pat = rule['pattern']
        n = sum(len(re.findall(pat, t)) for t in scope_texts(texts, rule.get('scope')))
        key = rule.get('name') or '%s:%s' % (rule.get('scope', '*'), pat)
        stats[key] = n
        if 'exact' in rule and n != rule['exact']:
            issues.append(u'%s = %d，应为 %d' % (key, n, rule['exact']))
        if 'at_least' in rule and n < rule['at_least']:
            issues.append(u'%s = %d，至少 %d' % (key, n, rule['at_least']))
        if 'at_most' in rule and n > rule['at_most']:
            issues.append(u'%s = %d，至多 %d' % (key, n, rule['at_most']))

    for rule in spec.get('paired', []):
        a, b = rule['a'], rule['b']
        na = nb = 0
        for t in scope_texts(texts, rule.get('scope')):
            na += len(re.findall(a, t))
            nb += len(re.findall(b, t))
        key = rule.get('name') or '%s 配对' % rule.get('scope', '*')
        stats[key] = '%d/%d' % (na, nb)
        if na != nb:
            issues.append(u'%s 不配对 (%d/%d)' % (key, na, nb))
        if na < rule.get('min', 1):
            issues.append(u'%s 数量过少 (%d)' % (key, na))

    return issues, stats


def run(spec, only=None):
    root = spec['root']
    units = sorted(d for d in glob.glob(os.path.join(root, spec.get('unit_glob', '*/')))
                   if os.path.isdir(d))
    if only:
        units = [d for d in units if only in os.path.basename(os.path.normpath(d))]
    if not units:
        print(u'没有匹配到任何单元：%s' % root)
        return 1
    bad = 0
    for d in units:
        issues, stats = check_unit(d, spec)
        name = os.path.basename(os.path.normpath(d))
        print(u'%-4s %-24s %s' % ('OK' if not issues else 'FAIL', name,
                                  ' '.join('%s=%s' % kv for kv in stats.items())))
        for i in issues:
            print(u'       - %s' % i)
        bad += bool(issues)
    print(u'\n%d/%d 个单元通过' % (len(units) - bad, len(units)))
    return 1 if bad else 0


def selftest():
    tmp = tempfile.mkdtemp(prefix='docset_qa_')
    try:
        good = os.path.join(tmp, 'good_unit')
        bad = os.path.join(tmp, 'bad_unit')
        os.makedirs(good)
        os.makedirs(bad)
        body = (u'=== A ===\n\ntext\n\n=== B ===\n\n1.\n参考答案：A\n'
                u'EN: x\nCN: y\n')
        for d in (good, bad):
            io.open(os.path.join(d, 'a.txt'), 'w', encoding='utf-8', newline='\n').write(body)
        io.open(os.path.join(bad, 'a.txt'), 'a', encoding='utf-8', newline='\n').write(u'**bold**\n')

        spec = {
            'root': tmp,
            'unit_glob': '*/',
            'files': ['a.txt'],
            'header_fields': [],
            'sections': ['=== A ===', '=== B ==='],
            'blank_line_before': ['=== B ==='],
            'forbidden': [r'\*\*'],
            'counts': [{'scope': 'a.txt', 'pattern': u'(?m)^参考答案：', 'exact': 1}],
            'paired': [{'scope': 'a.txt', 'a': r'(?m)^EN: ', 'b': r'(?m)^CN: ', 'min': 1}],
        }
        g_issues, g_stats = check_unit(good, spec)
        b_issues, _ = check_unit(bad, spec)
        ok = not g_issues and any(u'禁用模式' in i for i in b_issues)
        print(u'selftest: %s' % ('PASS' if ok else 'FAIL'))
        if not ok:
            print(u'  good issues: %s' % g_issues)
            print(u'  bad  issues: %s' % b_issues)
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    ap = argparse.ArgumentParser(description=u'声明式批量产物结构验收')
    ap.add_argument('--spec', help=u'spec.json 路径')
    ap.add_argument('--unit', help=u'只检查名字包含该子串的单元')
    ap.add_argument('--selftest', action='store_true', help=u'自检脚本')
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.spec:
        ap.error(u'需要 --spec 或 --selftest')
    with io.open(args.spec, encoding='utf-8') as fh:
        spec = json.load(fh)
    # 相对 root 按 spec 文件所在目录解析，spec 与产物一起拷走即可用
    if not os.path.isabs(spec['root']):
        spec_dir = os.path.dirname(os.path.abspath(args.spec))
        spec['root'] = os.path.normpath(os.path.join(spec_dir, spec['root']))
    return run(spec, args.unit)


if __name__ == '__main__':
    sys.exit(main())
