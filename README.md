# 美国每日热榜 · 中英对照摘要站

每天北京时间 07:00 自动抓取美国为主、多国对照的主流信息源，用 Kimi API 批量翻译成中文，
生成移动端友好的静态网页，托管在 GitHub Pages（全免费）。

**页面为顶部标签栏切换结构**：头条 | 政治 | 军事 | 科技 | 财经 | 娱乐 | 体育 | 厄尔尼诺专板 | X 美国热搜 | 特朗普动态 | 历史归档，
点击按钮即切换板块，无需刷新页面（支持 #hash 直达）。

## 内容板块

| 标签 | 内容与数据源 | 是否需要密钥 |
|---|---|---|
| 头条 | Google News 美国版 20 条 + 各媒体 general 类报道 | 否 |
| 政治 / 军事 / 科技 / 财经 | 9 家媒体按国别分组（Kimi 翻译时打标）+ Google News 专题版块源保底（每板块 5 条以上） | 否 |
| 娱乐 | Google News ENTERTAINMENT 官方版块（电影/剧集/音乐/颁奖） | 否 |
| 体育 | Google News SPORTS 官方版块 | 否 |
| 厄尔尼诺专板 | NOAA CPC 周度 Niño 3.4 指数 + 4 个子板块：机构预测与解读 / 全球天灾动态 / 农业与粮食 / 南半球动态（Google News 主题检索） | 否 |
| X 美国热搜 | trends24.in → getdaytrends.com 回退 | 否 |
| 特朗普动态 | trumpstruth.org 存档站 → r.jina.ai → Truth Social API → RSSHub 回退 | 否 |

**专题版块源（fetchers/topics.py）**：科技/财经/娱乐/体育用 Google News 官方版块 RSS，
政治/军事用主题检索 RSS，各配一个备用源；每条带原始媒体名，确保各分类板块每天不少于 5 条。

**多国媒体（每家每天取最新 6 条）**：美国 NYT / CNN / NPR，俄罗斯 TASS / The Moscow Times，
中国 Global Times，法国 France 24 / RFI，英国 BBC。每条新闻带国家色块徽章，美国内容排前，便于各国对照。

YouTube 美国热榜、Google 美国热搜、Reddit 热帖已停用（代码保留，在 `main.py` 的 `FETCHERS` 中加回即可恢复）。
**目前仅 Kimi 翻译接口需要密钥，所有数据源均为免费公开渠道，无需任何额外 API。**

任一源抓取失败只影响对应板块（显示"本次更新失败"），页面照常生成。
历史每期自动归档到 `site/archive/YYYY-MM-DD.html`（每天一期，按北京时间日期命名）。

页首报头右侧为 **Niño 3.4 指数卡片**（NOAA CPC 周度 OISST 数据，每周更新）：
大号数字为海温距平 SSTA，按数值分级着色（暖橙红=厄尔尼诺、冷蓝=拉尼娜、灰=中性），
强度分级：|SSTA| 0.5~0.9 弱、1.0~1.4 中等、1.5~1.9 强、≥2.0 超强；点击卡片跳转
NOAA 官方 ENSO 监测页。数据周滞后或抓取失败时卡片显示"指数数据暂缺"。

## 1. 申请密钥

### Kimi API Key（翻译用，需少量充值）

1. 打开 <https://platform.moonshot.cn>，注册/登录
2. 充值开通（本项目每日消耗约 5~10 万 token（多国媒体+专题版块版），月成本约 25~60 元；
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

GitHub Actions（`.github/workflows/update.yml`）每天 UTC 23:00
（= 北京时间次日 07:00）自动运行，也可以用
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

不想依赖 GitHub Actions 时，可用系统任务计划每天本地运行一次：

1. 开始菜单搜索"任务计划程序" → 右侧"创建任务"
2. 常规：名称 `us-daily-brief`；安全选项选"不管用户是否登录都要运行"（或仅登录时）
3. 触发器：新建 1 个，每天 `07:00`
4. 操作：新建 → 程序填 `C:\Windows\System32\cmd.exe`，
   参数填 `/c "D:\个人记录\杂文\kimi'\us-daily-brief\run_local.bat"`
5. 条件选项卡：取消"只有在计算机使用交流电源时才启动"的勾选（笔记本）

运行日志追加在项目目录的 `run_log.txt`。

## 常见问题

- **某板块显示"本次更新失败"**：多为网络或目标站反爬。Truth Social 有
  trumpstruth.org → r.jina.ai → 官方 API → RSSHub 多级回退，X 热搜有
  trends24.in → getdaytrends.com 回退；GitHub Actions（美国机房）成功率远高于国内家庭网络。
- **翻译失败**：检查 `MOONSHOT_API_KEY` 是否有效、余额是否充足（欠费时 API 返回 429）；
  翻译按每批最多 10 条分批调用，单批失败只影响该批条目，
  在页面上标注"翻译失败"，不影响其他条目。
- **本地跑 news/enso 超时**：国内网络对 Google 的连通性问题，
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
