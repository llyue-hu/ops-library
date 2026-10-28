# -*- coding: utf-8 -*-
"""fetch_cache.py —— 带镜像回退、完整性校验、原子落盘的下载缓存

设计目标：同样的 URL 第二次跑直接命中缓存；镜像挂了自动换；下到一半中断
不会留下一个“看起来存在”的半截文件。

用法：
    python fetch_cache.py --url <URL> --dest <FILE> [--jsdelivr] [--prefix https://ghfast.top/]...
    python fetch_cache.py --url ... --dest ... --min-bytes 100000 --sha256 <hex>
    python fetch_cache.py --selftest

退出码：成功 0；全部来源失败 1。
"""
from __future__ import print_function

import argparse
import hashlib
import io
import os
import shutil
import sys
import tempfile
import time
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

SAFE = ":/?#[]@!$&'()*+,;=%"


def encode_url(url):
    """只编码非 ASCII 与空格，保留已有的 %XX，避免二次编码。"""
    return quote(url, safe=SAFE)


def jsdelivr_url(raw_url):
    """raw.githubusercontent.com/u/r/branch/path -> cdn.jsdelivr.net/gh/u/r@branch/path"""
    p = urlsplit(raw_url)
    if p.netloc != 'raw.githubusercontent.com':
        return None
    parts = p.path.lstrip('/').split('/')
    if len(parts) < 4:
        return None
    owner, repo, branch = parts[0], parts[1], parts[2]
    rest = '/'.join(parts[3:])
    return 'https://cdn.jsdelivr.net/gh/%s/%s@%s/%s' % (owner, repo, branch, rest)


def sha256_of(path):
    h = hashlib.sha256()
    with io.open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def is_complete(path, min_bytes, sha256):
    if not os.path.exists(path):
        return False
    size = os.path.getsize(path)
    if min_bytes and size < min_bytes:
        return False
    if sha256 and sha256_of(path) != sha256.lower():
        return False
    return True


def try_download(url, part, timeout):
    req = Request(encode_url(url), headers={'User-Agent': 'fetch-cache/1.0'})
    with urlopen(req, timeout=timeout) as resp:
        expected = resp.headers.get('Content-Length')
        with io.open(part, 'wb') as fh:
            shutil.copyfileobj(resp, fh)
    got = os.path.getsize(part)
    if expected and expected.isdigit() and int(expected) != got:
        raise IOError('大小不符：期望 %s，实际 %d' % (expected, got))
    return got


def fetch(url, dest, prefixes=(), use_jsdelivr=False, min_bytes=0, sha256=None,
          force=False, timeout=60, retries=1):
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    if not force and is_complete(dest, min_bytes, sha256):
        print('cached  %s (%d bytes)' % (dest, os.path.getsize(dest)))
        return True

    candidates = []
    if use_jsdelivr:
        j = jsdelivr_url(url)
        if j:
            candidates.append(j)
    for p in prefixes:
        candidates.append(p.rstrip('/') + '/' + url)
    candidates.append(url)

    part = dest + '.part'
    for attempt in range(1, retries + 1):
        for cand in candidates:
            try:
                print('fetch   %s' % cand, file=sys.stderr)
                size = try_download(cand, part, timeout)
                if min_bytes and size < min_bytes:
                    raise IOError('体积过小：%d < %d，疑似被截断' % (size, min_bytes))
                if sha256 and sha256_of(part) != sha256.lower():
                    raise IOError('sha256 不符')
                os.replace(part, dest)
                print('ok      %s (%d bytes)' % (dest, size))
                return True
            except Exception as exc:  # noqa: BLE001 - 需要逐个来源尝试
                print('fail    %s -> %s' % (cand, exc), file=sys.stderr)
                if os.path.exists(part):
                    os.remove(part)
        if attempt < retries:
            time.sleep(1.5 * attempt)
    return False


def selftest():
    tmp = tempfile.mkdtemp(prefix='fetch_cache_')
    try:
        src = os.path.join(tmp, 'src.bin')
        io.open(src, 'wb').write(b'x' * 2048)
        url = 'file:///' + src.replace('\\', '/')
        dest = os.path.join(tmp, 'out', 'dst.bin')

        assert fetch(url, dest, min_bytes=1024), '首次下载应成功'
        assert os.path.getsize(dest) == 2048
        assert not os.path.exists(dest + '.part'), '不应残留 .part'
        assert fetch(url, dest, min_bytes=1024), '缓存命中应成功'

        bad_sha = '0' * 64
        ok = fetch(url, os.path.join(tmp, 'bad.bin'), sha256=bad_sha)
        assert not ok, 'sha256 不符必须失败'
        assert not os.path.exists(os.path.join(tmp, 'bad.bin'))

        mini = os.path.join(tmp, 'mini.bin')
        io.open(mini, 'wb').write(b'y' * 10)
        ok = fetch('file:///' + mini.replace('\\', '/'), os.path.join(tmp, 'mini_out.bin'),
                   min_bytes=100)
        assert not ok, '小于 min_bytes 必须失败'
        print('selftest: PASS')
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='带镜像回退的下载缓存')
    ap.add_argument('--url', help='原始 URL（通常是 raw.githubusercontent.com）')
    ap.add_argument('--dest', help='本地保存路径')
    ap.add_argument('--jsdelivr', action='store_true', help='优先尝试 jsDelivr 镜像')
    ap.add_argument('--prefix', action='append', default=[], help='镜像前缀，可重复')
    ap.add_argument('--min-bytes', type=int, default=0, help='小于该体积视为失败')
    ap.add_argument('--sha256', help='期望的 sha256')
    ap.add_argument('--force', action='store_true', help='忽略已有缓存')
    ap.add_argument('--timeout', type=int, default=60)
    ap.add_argument('--retries', type=int, default=1)
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not (args.url and args.dest):
        ap.error('需要 --url 和 --dest')
    ok = fetch(args.url, args.dest, args.prefix, args.jsdelivr, args.min_bytes,
               args.sha256, args.force, args.timeout, args.retries)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
