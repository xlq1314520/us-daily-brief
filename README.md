# 美国每日热榜 · 中英对照摘要站

每天北京时间 07:50 / 19:50 自动抓取 5 个美国热门信息源，用 Kimi API 批量翻译成中文，
生成移动端友好的静态网页，托管在 GitHub Pages（全免费）。

## 内容板块

| 板块 | 数据源 | 是否需要密钥 |
|---|---|---|
| YouTube 美国热榜 | YouTube Data API v3（mostPopular, US） | ✅ `YOUTUBE_API_KEY` |
| 美国新闻头条 | Google News RSS（美国版） | 否 |
| Google 美国热搜 | trends.google.com 官方每日热搜 RSS（geo=US） | 否 |
| Reddit 热帖 | r/news + r/worldnews 当日 top | 否 |
| X 美国热搜 | trends24.in → getdaytrends.com 回退 | 否 |
| 特朗普动态 | trumpstruth.org 存档站 → r.jina.ai → Truth Social API → RSSHub 回退 | 否 |

任一源抓取失败只影响对应板块（显示"本次更新失败"），页面照常生成。
历史每期自动归档到 `site/archive/YYYY-MM-DD-{am,pm}.html`（按北京时间分上午/下午版）。

## 1. 申请密钥

### Kimi API Key（翻译用，需少量充值）

1. 打开 <https://platform.moonshot.cn>，注册/登录
2. 充值开通（本项目每日消耗约 1~3 万 token，月成本约 5~20 元；
   已翻译过的内容有本地缓存，重复内容不重复扣费）
3. 在"API Key 管理"创建 key，复制备用
4. 用量可在控制台查看；不想翻译时也可用 `--no-translate` 跑纯英文版

### YouTube Data API Key（免费）

1. 打开 <https://console.cloud.google.com>，用 Google 账号登录
2. 新建一个项目（任意名称）
3. 进入"API 和服务 → 库"，搜索 **YouTube Data API v3**，点击启用
4. 进入"凭据 → 创建凭据 → API 密钥"，复制备用
5. 免费额度：每天 10,000 quota，本项目每次调用只消耗几个单位，绰绰有余

> 不配 YouTube key 也能运行，只是 YouTube 板块显示"本次更新失败"。

## 2. 创建 GitHub 仓库并配置

1. 在 <https://github.com/new> 创建一个**公开**仓库（如 `us-daily-brief`），不要初始化 README
2. 本地推送代码：
   ```bash
   cd us-daily-brief
   git remote add origin https://github.com/<你的用户名>/us-daily-brief.git
   git branch -M main
   git push -u origin main
   ```
3. 仓库 → **Settings → Secrets and variables → Actions → New repository secret**，
   添加两个 secret：
   - `MOONSHOT_API_KEY`
   - `YOUTUBE_API_KEY`

## 3. 启用 GitHub Pages

仓库 → **Settings → Pages**：
- Source 选 **Deploy from a branch**
- Branch 选 `gh-pages` / `(root)`，保存

GitHub Actions（`.github/workflows/update.yml`）每天 UTC 23:50 和 11:50
（= 北京时间次日 07:50 / 当天 19:50）自动运行，也可以用
Actions 页面右上角的 **Run workflow** 按钮手动触发。
首次运行成功后，Pages 地址即为 `https://<你的用户名>.github.io/us-daily-brief/`。

## 4. 本地运行（备用 / 调试）

要求 Python 3.10+（Windows 可 `winget install Python.Python.3.12`）：

```bash
pip install -r requirements.txt
python main.py --no-translate   # 不调翻译，先跑通流程
python main.py                  # 需要环境变量 MOONSHOT_API_KEY
```

生成的页面在 `site/index.html`，浏览器直接打开即可查看。

### Windows 任务计划（本地定时备用）

不想依赖 GitHub Actions 时，可用系统任务计划每天本地运行两次：

1. 开始菜单搜索"任务计划程序" → 右侧"创建任务"
2. 常规：名称 `us-daily-brief`；安全选项选"不管用户是否登录都要运行"（或仅登录时）
3. 触发器：新建 ×2 个，分别是每天 `07:50` 和 `19:50`
4. 操作：新建 → 程序填 `C:\Windows\System32\cmd.exe`，
   参数填 `/c "D:\个人记录\杂文\kimi'\us-daily-brief\run_local.bat"`
5. 条件选项卡：取消"只有在计算机使用交流电源时才启动"的勾选（笔记本）

运行日志追加在项目目录的 `run_log.txt`。

## 常见问题

- **某板块显示"本次更新失败"**：多为网络或目标站反爬。Reddit 有
  www → old.reddit.com → r.jina.ai 三级回退，Truth Social 有
  官方 API → RSSHub 实例 → r.jina.ai 三级回退，X 热搜有
  trends24.in → getdaytrends.com 回退；GitHub Actions（美国机房）成功率远高于国内家庭网络。
- **翻译失败**：检查 `MOONSHOT_API_KEY` 是否有效、余额是否充足；
  翻译按每批最多 10 条分批调用，单批失败只影响该批条目，
  在页面上标注"翻译失败"，不影响其他条目。
- **本地跑 news/reddit 超时**：国内网络对 Google/Reddit 的连通性问题，
  不是代码问题，云端运行不受影响。

## 项目结构

```
us-daily-brief/
├── main.py                 # 入口：抓取 → 翻译 → 生成 HTML
├── fetchers/               # 5 个数据源，各自独立容错
├── translator.py           # Kimi 批量翻译（缓存 + 重试 + 降级）
├── build_site.py           # jinja2 渲染 index.html + 归档页
├── templates/page.html     # 页面模板
├── site/                   # 生成的网页（部署目录）
├── data/                   # 原始 JSON + 翻译缓存（可提交）
└── .github/workflows/update.yml
```
