# 04 · 下载加速与镜像

**适用**：从 GitHub 拉公开仓库里的文件（raw、release 附件），国内直连经常几十 KB/s 甚至超时。

**不适用**：私有仓库（jsDelivr / ghfast 只代理公开内容）；需要登录态的 API。

---

## 1. 症状对照

| 现象 | 判断 |
|---|---|
| `raw.githubusercontent.com` 长时间无响应，或只有几 KB/s | 直连被限，换镜像 |
| 下载“成功”但 PDF 打不开、`PdfStreamError: Stream has ended unexpectedly` | 下到了截断文件，必须校验体积/hash |
| 中文文件名 404 | URL 没做百分号编码 |
| 刚推到仓库，镜像里还是旧文件 | jsDelivr 有缓存，换 `@commit-sha` 或等几分钟 |

## 2. 镜像优先级（实测）

| 顺序 | 形态 | 说明 |
|---|---|---|
| 1 | `https://cdn.jsdelivr.net/gh/<owner>/<repo>@<branch>/<path>` | 最快；路径直接接在 `@branch/` 后 |
| 2 | `https://ghfast.top/https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>` | 前缀式代理，原 URL 原样拼在后面 |
| 3 | `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>` | 兜底 |

`<branch>` 写分支名（`main`/`master`）或 commit sha。**写错分支不会报“分支不存在”，只会 404**，先确认默认分支。

## 3. 中文/空格路径必须编码

```python
from urllib.parse import quote
url = '.../真题/2010年考研英语一真题.pdf'
quote(url, safe=":/?#[]@!$&'()*+,;=%")   # 保留 : / % 等，只转义中文与空格
```

`safe` 里保留 `%`，避免把已经编码过的 `%E7%9C%9F` 二次编码成 `%25E7...`。

## 4. 直接可用：fetch_cache.py

```bash
python fetch_cache.py \
  --url "https://raw.githubusercontent.com/<owner>/<repo>/main/<编码后的路径>" \
  --dest "<CACHE>/某个文件.pdf" \
  --jsdelivr --prefix https://ghfast.top --min-bytes 100000 \
  --retries 3 --timeout 60
```

行为：

- `--dest` 已存在且体积 ≥ `--min-bytes`、sha256 匹配 → 直接 `cached`，不联网。
- 依次尝试 jsDelivr → 各 `--prefix` → 原 URL；每个来源失败会打印原因。
- 先写 `<dest>.part`，校验通过才 `os.replace` 成正式文件——中断不会留下“看起来存在”的半截文件。
- 支持 `--sha256`；不符则删除并失败。
- `--selftest` 用本地 `file://` 跑通缓存命中、体积不足、hash 不符三种路径，不依赖网络。

## 5. 校验三件套

1. **体积**：和仓库页面/`Content-Length` 对得上；明显偏小就是截断。
2. **sha256**：能从发布方拿到就一定要比。
3. **能打开**：PDF 用 `pdftotext` 抽一页；zip 用 `unzip -t`。格式解析器是最诚实的校验器。

## 6. 坑

- **DNS 会间歇性失败**：本次整理中 `cdn.jsdelivr.net` 时好时坏（`getaddrinfo failed`、连接超时），同一分钟 `curl` 又能通。脚本要带 `--retries`，别把“一次失败”当成“镜像不可用”。
- **301 要跟随**：用 `curl` 手工验证时加 `-L`，否则只拿到 301 跳转页（约 200 字节），看起来像“下载成功”。
- **镜像只代理公开仓库**；私有库会 404，不是路径写错。
- **大文件**：jsDelivr 对单文件有大小限制，超大 release 附件走 ghfast 或官方 release 直链。
- **别用镜像做登录态请求**：不带 Cookie/Token，也不要把带 token 的 URL 交给第三方代理。

## 7. 自检

```bash
python fetch_cache.py --selftest    # 必须 PASS
```

网络可用时再跑一次真实小文件下载（例如仓库里的 README），确认镜像链路；网络异常时不要据此判断脚本坏了。
