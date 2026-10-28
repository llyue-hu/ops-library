# 09 · 批量产物结构验收

**适用**：几十个同构目录，每个目录里文件集合固定（如“每年 8 个 TXT”）。人工翻一遍要半天，且第二遍会漏。

**不适用**：产物之间结构不同；或者只有一两个文件（直接读一遍更快）。

---

## 1. 30 秒上手

```bash
python docset_qa.py --selftest                 # 先确认脚本本身没坏
python docset_qa.py --spec spec.example.json   # 跑内置夹具，应输出 1/1 通过
python docset_qa.py --spec spec.json           # 全量
python docset_qa.py --spec spec.json --unit 2013   # 只查名字含 2013 的单元
```

输出：每个单元一行 `OK/FAIL` + 关键计数；失败项缩进列出。有失败时退出码为 1，可直接接 CI。

## 2. spec 怎么写

```json
{
  "root": "<OUT>",
  "unit_glob": "*_英语一/",
  "files": ["00_整套.txt", "01_完形.txt"],
  "min_file_bytes": 3000,
  "header_fields": ["【年份】"],
  "sections": ["=== 原文 ==="],
  "blank_line_before": ["=== 题目与答案 ==="],
  "forbidden": ["\\*\\*", "\\ufeff", "\\f"],
  "duplicate_phrases": ["中文说明：中文说明："],
  "counts": [{"name": "完形答案", "scope": "01_完形.txt", "pattern": "(?m)^参考答案：", "exact": 20}],
  "paired": [{"scope": "0[2-5]_*.txt", "a": "(?m)^EN: ", "b": "(?m)^CN: ", "min": 2}]
}
```

| 字段 | 作用 |
|---|---|
| `root` / `unit_glob` | 产物根目录；每个匹配到的子目录是一个“单元” |
| `files` | 单元内必须存在的文件名，缺一个就 FAIL |
| `min_file_bytes` | 防“空文件也算通过” |
| `header_fields` / `sections` | 必须出现的固定串 |
| `blank_line_before` | 该标记前必须有空行 |
| `forbidden` | 正则黑名单：残留的 Markdown、BOM、分页符等 |
| `duplicate_phrases` | 重复粘贴事故的指纹 |
| `counts` | 正则计数，支持 `exact` / `at_least` / `at_most`；`scope` 用文件名 glob，多文件会合并计数 |
| `paired` | 两个标记数量必须相等（如 EN/CN 配对） |

`spec.example.json` 开箱可跑：它指向内置夹具 `fixtures/kaoyan_english/2099_示例_英语一`（全占位文本，由 `fixtures/make_fixture.py` 生成，不代表任何真实试题）。正式使用时把 `root` 改成你的产物目录——相对路径按 spec 文件所在目录解析，写绝对路径也行。

## 3. 怎么从一次人工检查反推 spec

人工检查时你其实在反复看四件事，逐个翻译成字段：

1. “文件齐吗” → `files`
2. “东西在不在位置上” → `header_fields` / `sections` / `blank_line_before`
3. “数量对不对” → `counts`（题号数、答案数、分隔线数）
4. “有没有脏东西” → `forbidden` / `duplicate_phrases`

第 5 类“内容对不对”（答案是否正确、译文是否通顺）**不要写进 spec**，抽查 1–2 份人工读。

## 4. 坑

**a) 计数正则必须加锚点。** 页眉说明里写了一句“参考答案取自……”时，`参考答案：` 会把 20 题数成 21。用 `(?m)^参考答案：`，并且先跑一个已知正确的单元校准。

**b) 一个产物族一个 spec。** 英语一和英语二的版式细节不同（有的文件段间没有空行），硬塞进一个 spec 会得到一堆假 FAIL。要么 `unit_glob` 分开，要么把规则放宽到两族都成立。

**c) Windows 控制台是 GBK。** 脚本里做 `sys.stdout.reconfigure(encoding='utf-8')`，否则中文全是乱码，看着像脚本坏了。

**d) 结构过 ≠ 内容对。** 本脚本只保证“形状对”。答案字母错位、OCR 错词这类问题它看不见——那要靠多源比对和抽样阅读。

**e) 别把“排版好看”写进验收。** 全角字符列对齐这类事属于人工审美，用字符宽度算出来的 PASS/FAIL 只会制造噪音。

## 5. 维护

- 改了产物版式，先改 spec 再重跑；spec 与产物同版本提交。
- 改了 spec 规则后，跑一次 `fixtures/make_fixture.py` 再跑示例，确认夹具仍通过。
- 脚本升级后跑 `--selftest`；自检里有一条故意写坏的样例，必须能被抓出来。
