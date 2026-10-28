# 06 · Windows 脚本避坑

**适用**：在 Windows 上用 Git Bash + Python 做批处理。**不适用**：纯 PowerShell 或 WSL 环境（部分条目仍成立，但路径写法不同）。

---

## 1. 症状对照

| 现象 | 原因 | 去哪节 |
|---|---|---|
| 中文全变 `���` 或 `锟斤拷` | 控制台 GBK，脚本按 UTF-8 输出 | §2 |
| `UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'` | `print` 遇到 GBK 编不出的字符 | §2 |
| bash 里 `cd E:\foo` 无效 | Git Bash 用 `/e/foo` | §3 |
| heredoc 报 `SyntaxError: unterminated string literal` | 引号/反斜杠被 bash 先吃掉了 | §4 |
| 命令太长，末尾被截断 | Windows 命令行长度限制 | §5 |
| 写出的文件在 Linux 下多出 `^M` | 默认 CRLF | §2 |
| 不知道某个文件是谁写的 | 没看 mtime | §6 |

## 2. 编码与换行（最高频）

**Python 输出**：入口处强制 UTF-8，别指望控制台。

```python
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
```

**临时运行**：`PYTHONIOENCODING=utf-8 python x.py`（只对本次进程有效）。

**写文件**：显式编码 + 显式 LF，两个都要写：

```python
io.open(path, 'w', encoding='utf-8', newline='\n')
```

`newline='\n'` 关掉 Windows 的 `\r\n` 转换。读文件用 `io.open(path, encoding='utf-8')`，不要用 `open()` 的默认编码（随系统区域变）。

**读子进程输出**：`subprocess` 默认按 locale 解码，中文会炸。加 `encoding='utf-8', errors='replace'`。

**判断有没有 BOM**：`t.startswith('\ufeff')`；要 BOM 才用 `utf-8-sig`。

## 3. Git Bash 的路径

- 盘符：`E:\a\b` → `/e/a/b`；命令里混用也行，但 `cd "E:\a"` 会失败。
- 带空格：一律双引号，`cd "/e/Program Files"`。
- 空设备：`/dev/null`，不是 `NUL`。
- 列进程：`ps -W`（Git Bash 自带，`-W` 才会显示 Windows 进程）。
- 当前目录会被工具重置：每条命令用绝对路径，别依赖上一条的 `cd`。

## 4. 引号与 heredoc

**要字面量就加单引号**：

```bash
python - <<'EOF'
print(r'E:\raw\text')
EOF
```

`<<'EOF'` 里的内容 bash 不做变量展开、不处理反斜杠；`<<EOF`（不带引号）会把 `$`、反引号、`\` 全解释一遍，Python 字符串里带反斜杠时极易炸。

**别在 shell 里塞长 Python**：`python -c "..."` 嵌套引号超过两层就开始出错，而且报错行号对不上。**改成两步**：用编辑器/`Write` 落一个 `.py`，再 `python x.py`。这次项目里所有能稳定复现的脚本都是这么来的。

**单行里出现 `\` 结尾**：`python -c "print('a\'')"` 这类写法在 bash + Windows 参数解析下会被二次转义。用双引号包外层、Python 内层用单引号，或直接换脚本文件。

## 5. 命令长度

Windows 单条命令行约 8191 字符。批量任务别拼 `python -c`，也别在一条 `find ... -exec` 里塞长表达式——写成脚本，传参数。

## 6. 时间戳：判断“谁写了什么”

```bash
find <DIR> -type f -newermt "2026-10-26 12:14"     # 某时刻之后被改过的文件
ls -lt <DIR> | head                                # 最近修改的在前
stat -c '%y %n' <FILE>                             # 精确到秒
```

派活/接手时这条比看日志可靠：**磁盘上的 mtime 不会撒谎**。

## 7. 删除与覆盖

- `rm -rf` 在 Git Bash 里不进回收站，且对中文路径同样生效。删除前先 `ls` 确认，优先“移到 `_scratch/`”而不是直接删。
- 覆盖生成物前先看 `git status`（若是仓库）；不是仓库就先把旧目录改名为 `xxx.bak_<日期>`。
- `mv` 跨盘（E: → C:）是复制+删除，大目录会慢，且中断会留下半份。

## 8. 中文文件名

- Git Bash 的 `ls`/`find` 能正常处理，但某些工具（老版 `curl -O`、部分压缩软件）会按 GBK 解析。
- 下载/生成时**自己指定输出文件名**（Python 里 `open(dest)`），不要让工具从 URL 推断。
- 文件名里避免 `:`、`?`、`*`、`"`、`<`、`>`、`|`，Windows 直接拒绝。

## 9. 一句话清单

1. 所有 Python 入口先 `reconfigure(utf-8)`。
2. 所有写文件 `encoding='utf-8', newline='\n'`。
3. 所有 shell 命令用绝对路径，heredoc 用 `<<'EOF'`。
4. 超过三行的 Python 一律落成 `.py` 再跑。
5. 判断产物归属看 mtime，不看日志。
