# -*- coding: utf-8 -*-
"""生成用于验证 spec.example.json 的示例产物目录。

全是占位文本，不含任何真实试题，只保证结构（文件/字段/分节/计数/配对）达标。
    python make_fixture.py            # 生成到 ./kaoyan_english/
    python make_fixture.py --out DIR
"""
from __future__ import print_function

import argparse
import io
import os
import sys

UNIT = u'2099_示例_英语一'
BAR = u'=' * 60
SEP = u'─' * 40

HEADER = u'{bar}\n【年份】2099\n【科目】英语一（示例数据）\n【题型】{kind}\n' \
         u'【文章主题】结构校验占位文本\n【大致词数】1200\n' \
         u'【来源】无\n【来源说明】测试夹具，非真实试题，仅用于验证 docset_qa.py\n{bar}\n'

FILLER_EN = u'Placeholder sentence %d: this line exists only to make the fixture ' \
            u'long enough for the byte-size check.'
FILLER_CN = u'占位句 %d：这一行只为让夹具达到体积阈值，不表达任何内容。'


def header(kind):
    return HEADER.format(bar=BAR, kind=kind)


def paragraphs(n, first_no=1):
    out = []
    for i in range(first_no, first_no + n):
        out.append(u'%s\n%s\n' % (FILLER_EN % i, FILLER_CN % i))
    return u''.join(out)


def cloze():
    body = [header(u'完形填空'), u'=== 原文 ===\n', paragraphs(10)]
    body.append(u'\n=== 题目与答案 ===\n')
    for i in range(1, 21):
        body.append(u'%d. 占位题干 %d，请选择。\n选项释义：A 占位；B 占位；C 占位；D 占位\n'
                    u'参考答案：A\n考查类型：示例\n\n' % (i, i))
    body.append(u'=== 逐段翻译 ===\n')
    for i in range(1, 11):
        body.append(u'【第%d段】\nEN: %s\nCN: %s\n\n' % (i, FILLER_EN % i, FILLER_CN % i))
    return u''.join(body)


def reading(n_q, seed):
    body = [header(u'阅读理解'), u'=== 原文 ===\n', paragraphs(5, seed)]
    body.append(u'\n=== 题目与答案 ===\n')
    for i in range(1, n_q + 1):
        body.append(u'%d. 占位题干 %d。\n参考答案：B\n考查类型：细节题\n\n' % (i, seed * 10 + i))
    body.append(u'=== 逐段翻译 ===\n')
    for i in range(1, 6):
        body.append(u'【第%d段】\nEN: %s\nCN: %s\n\n'
                    % (i, FILLER_EN % (seed + i), FILLER_CN % (seed + i)))
    return u''.join(body)


def plain(kind, seed):
    body = [header(kind), u'=== 原文 ===\n', paragraphs(6, seed)]
    body.append(u'\n=== 题目与答案 ===\n')
    if kind == u'翻译':
        body.append(u'参考答案：见参考译文（本夹具无题目）。\n考查类型：翻译\n\n')
    else:
        for i in range(1, 6):
            body.append(u'%d. 占位题干 %d。\n参考答案：C\n考查类型：示例\n\n' % (i, seed + i))
    body.append(u'=== 逐段翻译 ===\n')
    for i in range(1, 7):
        body.append(u'【第%d段】\nEN: %s\nCN: %s\n\n'
                    % (i, FILLER_EN % (seed + i), FILLER_CN % (seed + i)))
    return u''.join(body)


def pad(text, min_bytes=3200):
    n = len(text.encode('utf-8'))
    k = 1
    while n < min_bytes:
        extra = u'\n占位补充 %d：fixture padding line, ignore me.\n' % k
        text += extra
        n += len(extra.encode('utf-8'))
        k += 1
    return text


def build(out_dir):
    unit_dir = os.path.join(out_dir, UNIT)
    if not os.path.isdir(unit_dir):
        os.makedirs(unit_dir)

    parts = [
        (u'01_完形.txt', cloze()),
        (u'02_阅读_Passage1.txt', reading(5, 101)),
        (u'03_阅读_Passage2.txt', reading(5, 201)),
        (u'04_阅读_Passage3.txt', reading(5, 301)),
        (u'05_阅读_Passage4.txt', reading(5, 401)),
        (u'06_新题型.txt', plain(u'新题型', 501)),
        (u'07_翻译.txt', plain(u'翻译', 601)),
    ]

    written = {}
    for name, text in parts:
        text = pad(text)
        written[name] = text
        with io.open(os.path.join(unit_dir, name), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)

    # 00_整套：按段拼接，前后各加一条分隔线，保证计数规则（>=8）成立
    chunks = [SEP + u'\n']
    for name, _ in parts:
        chunks.append(written[name])
        chunks.append(SEP + u'\n')
    whole = u'\n'.join(chunks)
    with io.open(os.path.join(unit_dir, u'00_整套.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(whole)

    total = sum(os.path.getsize(os.path.join(unit_dir, n)) for n in os.listdir(unit_dir))
    print(u'生成 %s：8 个文件，共 %d 字节' % (unit_dir, total))


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=u'生成 docset_qa 示例夹具')
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  'kaoyan_english'))
    args = ap.parse_args()
    build(args.out)


if __name__ == '__main__':
    main()
