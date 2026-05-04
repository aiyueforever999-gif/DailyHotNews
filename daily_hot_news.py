#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日热榜日报生成器
调用 36 氪、百度、抖音三个热榜接口，生成静态 HTML 日报页面及 JSON 数据。
"""

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime


# ============================================================
# 配置
# ============================================================
API_36KR = "https://api.iyuns.com/api/hot36kr"
API_BAIDU = "https://api.iyuns.com/api/baiduhot"
API_DOUYIN = "https://api.iyuns.com/api/douyinhot"

OUTPUT_HTML_DIR = "html"
OUTPUT_DATA_DIR = "data"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Server酱推送配置（免费版每天限额通常够用）
# 1. 访问 https://sct.ftqq.com/ 用 GitHub 账号登录
# 2. 获取 SendKey，填入下方或设置环境变量 SERVERCHAN_SENDKEY
SERVERCHAN_SENDKEY = os.environ.get("SERVERCHAN_SENDKEY", "SCT339556TpyiiJVS5IuBEXSoeFvMLkoaq")
SERVERCHAN_API = "https://sctapi.ftqq.com/{sendkey}.send"

# 企业微信机器人推送配置
# 1. 在企业微信群聊中，点击右上角「群设置」→「添加群机器人」→「新建机器人」
# 2. 复制 Webhook Key，填入下方或设置环境变量 WECHAT_WEBHOOK_KEY
WECHAT_WEBHOOK_KEY = os.environ.get("WECHAT_WEBHOOK_KEY", "01e35f3c-f51d-4e5b-b0d1-9853964b41d5")
WECHAT_WEBHOOK_API = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"

# GitHub Pages 地址前缀（用于生成可点击的日报链接）
# 格式: https://<用户名>.github.io/<仓库名>/html/
# 在 GitHub Actions 中会自动从 GITHUB_REPOSITORY 环境变量推断
_GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "")
if _GITHUB_REPO:
    _OWNER, _REPO = _GITHUB_REPO.split("/", 1)
    _AUTO_PAGES_URL = f"https://{_OWNER}.github.io/{_REPO}/html/"
else:
    _AUTO_PAGES_URL = ""

# 优先使用显式配置的环境变量，若为空则使用自动推断的地址
_GITHUB_PAGES_URL_ENV = os.environ.get("GITHUB_PAGES_URL", "")
if _GITHUB_PAGES_URL_ENV:
    GITHUB_PAGES_URL = _GITHUB_PAGES_URL_ENV
else:
    GITHUB_PAGES_URL = _AUTO_PAGES_URL


# ============================================================
# 网络请求
# ============================================================
def fetch_json(url: str) -> dict:
    """GET 请求并返回 JSON 数据"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
        return json.loads(data.decode("utf-8"))


# ============================================================
# 数据清洗与统一
# ============================================================
def normalize_36kr(raw_data: list) -> list:
    """清洗 36 氪热榜数据"""
    result = []
    for idx, item in enumerate(raw_data, start=1):
        tm = item.get("templateMaterial", {})
        item_id = item.get("itemId")

        hot_value = tm.get("statFormat", "").strip()
        if not hot_value:
            hot_value = f"{tm.get('statRead', 0)} 阅读"

        image = tm.get("widgetImage", "").strip()
        url = f"https://36kr.com/p/{item_id}" if item_id else ""

        result.append({
            "source": "36氪",
            "rank": idx,
            "title": tm.get("widgetTitle", "").strip(),
            "hot_value": hot_value,
            "url": url,
            "image": image,
            "summary": f"作者：{tm.get('authorName', '未知')}" if tm.get("authorName") else "",
        })
    return result


def normalize_baidu(raw_data: list) -> list:
    """清洗百度热搜数据"""
    result = []
    for item in raw_data:
        image = item.get("img", "").strip()
        if "de6163834f53ca92c1273fff98ac9078" in image:
            image = ""

        result.append({
            "source": "百度",
            "rank": item.get("index"),
            "title": item.get("title", "").strip(),
            "hot_value": item.get("hot", "").strip(),
            "url": item.get("url", "").strip(),
            "image": image,
            "summary": item.get("desc", "").strip(),
        })
    return result


def normalize_douyin(raw_data: list) -> list:
    """清洗抖音热榜数据"""
    result = []
    for item in raw_data:
        word = item.get("word", "").strip()
        hot_value = item.get("hot_value")
        if isinstance(hot_value, int):
            hot_value_str = f"{hot_value:,}"
        else:
            hot_value_str = str(hot_value)

        cover = item.get("word_cover", {})
        image = ""
        if isinstance(cover, dict):
            url_list = cover.get("url_list", [])
            if url_list:
                image = url_list[0]

        url = f"https://www.douyin.com/search/{urllib.parse.quote(word)}" if word else ""

        result.append({
            "source": "抖音",
            "rank": item.get("position"),
            "title": word,
            "hot_value": hot_value_str,
            "url": url,
            "image": image,
            "summary": "",
        })
    return result


def fetch_and_normalize() -> dict:
    """获取三个来源数据并统一格式"""
    print("[1/3] 正在获取 36 氪热榜...")
    kr_data = fetch_json(API_36KR).get("data", [])
    kr_clean = normalize_36kr(kr_data)
    print(f"      OK 获取 {len(kr_clean)} 条")

    print("[2/3] 正在获取百度热搜...")
    baidu_data = fetch_json(API_BAIDU).get("data", [])
    baidu_clean = normalize_baidu(baidu_data)
    print(f"      OK 获取 {len(baidu_clean)} 条")

    print("[3/3] 正在获取抖音热榜...")
    douyin_data = fetch_json(API_DOUYIN).get("data", [])
    douyin_clean = normalize_douyin(douyin_data)
    print(f"      OK 获取 {len(douyin_clean)} 条")

    return {
        "36氪": kr_clean,
        "百度": baidu_clean,
        "抖音": douyin_clean,
    }


# ============================================================
# 企业微信机器人推送
# ============================================================
def push_wechat(title: str, data: dict, html_url: str = "") -> bool:
    """通过企业微信机器人推送热榜摘要"""
    if not WECHAT_WEBHOOK_KEY:
        print("[推送] WECHAT_WEBHOOK_KEY 未配置，跳过企业微信推送")
        return False

    lines = [f"📰 **{title}**\n"]

    for name in ["36氪", "百度", "抖音"]:
        items = data.get(name, [])
        if not items:
            continue
        lines.append(f"**🔹 {name} 热榜 Top 10**")
        for item in items[:10]:
            rank = item.get("rank", "-")
            title_text = item.get("title", "")
            hot = item.get("hot_value", "")
            url = item.get("url", "")
            if url:
                lines.append(f"{rank}. [{title_text}]({url}) {hot}")
            else:
                lines.append(f"{rank}. {title_text} {hot}")
        lines.append("")

    if html_url:
        lines.append(f"> 📎 [查看完整日报]({html_url})")

    content = "\n".join(lines)

    # 企业微信 markdown 消息长度限制约 4096，做截断保护
    if len(content) > 4000:
        content = content[:4000] + "\n\n...（内容过长，请查看完整日报）"

    payload = json.dumps({
        "msgtype": "markdown",
        "markdown": {"content": content},
    }).encode("utf-8")

    url = WECHAT_WEBHOOK_API.format(key=WECHAT_WEBHOOK_KEY)
    headers = {"Content-Type": "application/json"}

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("errcode") == 0:
                print("[推送] 企业微信 推送成功")
                return True
            else:
                print(f"[推送] 企业微信 推送失败: {result}")
                return False
    except Exception as e:
        print(f"[推送] 企业微信 异常: {e}")
        return False


# ============================================================
# 微信推送（Server酱）
# ============================================================
def push_serverchan(title: str, data: dict) -> bool:
    """通过 Server酱 将热榜摘要推送到微信"""
    if not SERVERCHAN_SENDKEY:
        print("[推送] SERVERCHAN_SENDKEY 未配置，跳过推送")
        return False

    lines = [f"📰 <b>{title}</b>", ""]

    for name in ["36氪", "百度", "抖音"]:
        items = data.get(name, [])
        if not items:
            continue
        lines.append(f"🔹 <b>{name}</b> 热榜 Top 10")
        for item in items[:10]:
            rank = item.get("rank", "-")
            title_text = item.get("title", "")
            hot = item.get("hot_value", "")
            lines.append(f"  {rank}. {title_text} {hot}")
        lines.append("")

    desp = "\n".join(lines)

    url = SERVERCHAN_API.format(sendkey=SERVERCHAN_SENDKEY)
    payload = urllib.parse.urlencode({
        "title": title,
        "desp": desp,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("code") == 0 or result.get("data", {}).get("error") == "SUCCESS":
                print("[推送] Server酱 推送成功")
                return True
            else:
                print(f"[推送] Server酱 推送失败: {result}")
                return False
    except Exception as e:
        print(f"[推送] Server酱 异常: {e}")
        return False


# ============================================================
# HTML 模板生成
# ============================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <style>
        :root {
            --bg: #f5f7fa;
            --card-bg: #ffffff;
            --text-main: #1a1a1a;
            --text-sub: #666666;
            --text-light: #999999;
            --border: #e8ecf1;
            --accent-36kr: #4285f4;
            --accent-baidu: #2932e1;
            --accent-douyin: #000000;
            --shadow: 0 2px 8px rgba(0,0,0,0.06);
            --shadow-hover: 0 6px 20px rgba(0,0,0,0.1);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            line-height: 1.6;
            padding-bottom: 40px;
        }

        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            padding: 40px 20px;
            text-align: center;
        }

        .header h1 {
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
            letter-spacing: 1px;
        }

        .header .date {
            font-size: 15px;
            opacity: 0.85;
            margin-bottom: 12px;
        }

        .header .meta {
            font-size: 13px;
            opacity: 0.6;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
            padding: 0 16px;
        }

        /* Tab 导航 */
        .tabs {
            display: flex;
            gap: 8px;
            margin-top: 24px;
            padding: 4px;
            background: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
        }

        .tab-btn {
            flex: 1;
            padding: 12px 16px;
            border: none;
            background: transparent;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            color: var(--text-sub);
            cursor: pointer;
            transition: all 0.2s ease;
            position: relative;
        }

        .tab-btn:hover {
            color: var(--text-main);
            background: var(--bg);
        }

        .tab-btn.active {
            color: #fff;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }

        .tab-btn .tab-count {
            font-size: 12px;
            font-weight: 400;
            opacity: 0.8;
            margin-left: 4px;
        }

        /* Tab 内容 */
        .tab-content {
            display: none;
            margin-top: 20px;
            animation: fadeIn 0.3s ease;
        }

        .tab-content.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .section-header {
            display: flex;
            align-items: center;
            margin-bottom: 16px;
            padding: 0 4px;
        }

        .section-icon {
            width: 6px;
            height: 22px;
            border-radius: 3px;
            margin-right: 10px;
            flex-shrink: 0;
        }

        .section-title {
            font-size: 20px;
            font-weight: 700;
        }

        .section-36kr .section-icon { background: var(--accent-36kr); }
        .section-baidu .section-icon { background: var(--accent-baidu); }
        .section-douyin .section-icon { background: var(--accent-douyin); }

        .cards {
            display: grid;
            grid-template-columns: 1fr;
            gap: 12px;
        }

        @media (min-width: 640px) {
            .cards {
                grid-template-columns: 1fr 1fr;
            }
        }

        .card {
            background: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
            overflow: hidden;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            display: flex;
            flex-direction: column;
        }

        .card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-hover);
        }

        .card-image {
            width: 100%;
            height: 160px;
            object-fit: cover;
            display: block;
            background: #f0f0f0;
        }

        .card-image[src=""] {
            display: none;
        }

        .card-body {
            padding: 14px 16px;
            flex: 1;
            display: flex;
            flex-direction: column;
        }

        .card-top {
            display: flex;
            align-items: flex-start;
            gap: 8px;
            margin-bottom: 8px;
        }

        .card-rank {
            width: 24px;
            height: 24px;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 700;
            color: #fff;
            flex-shrink: 0;
            margin-top: 2px;
        }

        .rank-1 { background: linear-gradient(135deg, #ff6b6b, #ee5a5a); }
        .rank-2 { background: linear-gradient(135deg, #ffa502, #ff7f00); }
        .rank-3 { background: linear-gradient(135deg, #2ed573, #1dd1a1); }
        .rank-other { background: #d1d8e0; color: #57606f; }

        .card-title {
            font-size: 15px;
            font-weight: 600;
            line-height: 1.5;
            color: var(--text-main);
            flex: 1;
        }

        .card-title a {
            color: inherit;
            text-decoration: none;
        }

        .card-title a:hover {
            color: var(--accent-36kr);
        }

        .card-summary {
            font-size: 13px;
            color: var(--text-sub);
            margin-top: 6px;
            line-height: 1.5;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .card-summary:empty {
            display: none;
        }

        .card-footer {
            margin-top: auto;
            padding-top: 10px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 12px;
            color: var(--text-light);
        }

        .card-hot {
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        .card-hot::before {
            content: "🔥";
            font-size: 11px;
        }

        .page-footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            font-size: 12px;
            color: var(--text-light);
        }
    </style>
</head>
<body>
    <header class="header">
        <h1>每日热榜日报</h1>
        <div class="date">{{date_str}}</div>
        <div class="meta">数据来源：36 氪 · 百度热搜 · 抖音热榜</div>
    </header>

    <main class="container">
        <div class="tabs">
            {{tab_buttons}}
        </div>
        {{tab_contents}}
    </main>

    <footer class="page-footer">
        <p>本页面由脚本自动生成，仅供阅读参考 · {{date_str}}</p>
    </footer>

    <script>
        function switchTab(id) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            document.getElementById('btn-' + id).classList.add('active');
            document.getElementById('tab-' + id).classList.add('active');
        }
    </script>
</body>
</html>
"""

TAB_BTN_TEMPLATE = """<button class="tab-btn {{active_class}}" id="btn-{{tab_id}}" onclick="switchTab('{{tab_id}}')">{{tab_name}}<span class="tab-count">{{count}}条</span></button>"""

TAB_CONTENT_TEMPLATE = """<div class="tab-content {{active_class}}" id="tab-{{tab_id}}">
    <div class="section section-{{section_class}}">
        <div class="section-header">
            <div class="section-icon"></div>
            <h2 class="section-title">{{section_name}}</h2>
        </div>
        <div class="cards">
            {{cards}}
        </div>
    </div>
</div>"""

CARD_TEMPLATE = """
                <article class="card">
                    {{image_html}}
                    <div class="card-body">
                        <div class="card-top">
                            <span class="card-rank {{rank_class}}">{{rank}}</span>
                            <h3 class="card-title">
                                <a href="{{url}}" target="_blank" rel="noopener">{{title}}</a>
                            </h3>
                        </div>
                        {{summary_html}}
                        <div class="card-footer">
                            <span class="card-hot">{{hot_value}}</span>
                            <span>{{source}}</span>
                        </div>
                    </div>
                </article>
"""


def escape_html(text: str) -> str:
    """简单的 HTML 转义"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_card(item: dict) -> str:
    """生成单条卡片 HTML"""
    rank = item["rank"]
    if rank == 1:
        rank_class = "rank-1"
    elif rank == 2:
        rank_class = "rank-2"
    elif rank == 3:
        rank_class = "rank-3"
    else:
        rank_class = "rank-other"

    image = item.get("image", "")
    if image:
        image_html = f'<img class="card-image" src="{image}" alt="" loading="lazy">'
    else:
        image_html = ""

    summary = item.get("summary", "")
    if summary:
        summary_html = f'<p class="card-summary">{escape_html(summary)}</p>'
    else:
        summary_html = ""

    return CARD_TEMPLATE.replace("{{image_html}}", image_html) \
                        .replace("{{rank_class}}", rank_class) \
                        .replace("{{rank}}", str(rank)) \
                        .replace("{{url}}", escape_html(item.get("url", "#"))) \
                        .replace("{{title}}", escape_html(item["title"])) \
                        .replace("{{summary_html}}", summary_html) \
                        .replace("{{hot_value}}", escape_html(item.get("hot_value", ""))) \
                        .replace("{{source}}", item["source"])


CLASS_MAP = {
    "36氪": "36kr",
    "百度": "baidu",
    "抖音": "douyin",
}


def build_section(name: str, items: list, tab_id: str, is_active: bool) -> str:
    """生成单个 Tab 内容面板"""
    cards_html = "\n".join(build_card(item) for item in items)
    return TAB_CONTENT_TEMPLATE.replace("{{section_class}}", CLASS_MAP.get(name, "other")) \
                               .replace("{{section_name}}", name) \
                               .replace("{{cards}}", cards_html) \
                               .replace("{{tab_id}}", tab_id) \
                               .replace("{{active_class}}", "active" if is_active else "")


def generate_html(data: dict, date_str: str) -> str:
    """生成完整 HTML 页面"""
    tab_buttons = ""
    tab_contents = ""
    first = True
    tab_index = 0
    for name in ["36氪", "百度", "抖音"]:
        if name in data and data[name]:
            tab_id = f"tab{tab_index}"
            tab_buttons += TAB_BTN_TEMPLATE.replace("{{tab_id}}", tab_id) \
                                           .replace("{{tab_name}}", name) \
                                           .replace("{{count}}", str(len(data[name]))) \
                                           .replace("{{active_class}}", "active" if first else "")
            tab_contents += build_section(name, data[name], tab_id, first)
            first = False
            tab_index += 1

    title = f"{date_str} 每日热榜日报"
    return HTML_TEMPLATE.replace("{{title}}", title) \
                        .replace("{{date_str}}", date_str) \
                        .replace("{{tab_buttons}}", tab_buttons) \
                        .replace("{{tab_contents}}", tab_contents)


# ============================================================
# 主流程
# ============================================================
def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"===== 每日热榜日报生成器 [{today}] =====\n")

    # 1. 获取并清洗数据
    data = fetch_and_normalize()

    # 2. 保存 JSON
    os.makedirs(OUTPUT_DATA_DIR, exist_ok=True)
    json_path = os.path.join(OUTPUT_DATA_DIR, f"{today}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n[JSON] 数据已保存 -> {json_path}")

    # 3. 生成 HTML
    os.makedirs(OUTPUT_HTML_DIR, exist_ok=True)
    html_content = generate_html(data, today)
    html_path = os.path.join(OUTPUT_HTML_DIR, f"{today}-热榜日报.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[HTML] 页面已生成 -> {html_path}")

    # 4. 构建 GitHub Pages 日报链接
    html_url = ""
    if GITHUB_PAGES_URL:
        html_url = f"{GITHUB_PAGES_URL}{today}-%E7%83%AD%E6%A6%9C%E6%97%A5%E6%8A%A5.html"

    # 5. 推送到微信（Server酱）
    push_serverchan(f"{today} 每日热榜日报", data)

    # 6. 推送到企业微信
    push_wechat(f"{today} 每日热榜日报", data, html_url)

    # 7. 统计
    total = sum(len(v) for v in data.values())
    print(f"\n===== 完成 =====")
    print(f"共计 {total} 条热榜内容（36氪 {len(data['36氪'])} / 百度 {len(data['百度'])} / 抖音 {len(data['抖音'])}）")
    print(f"本地双击即可打开 HTML 文件查看日报")


if __name__ == "__main__":
    main()
