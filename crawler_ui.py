from __future__ import annotations

import os
import re
import io
import subprocess
import sys
from collections import Counter
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

try:
  import jieba
except ImportError:
  jieba = None

try:
  from wordcloud import WordCloud
except ImportError:
  WordCloud = None

try:
  from PIL import ImageFont
except ImportError:
  ImageFont = None


BASE_DIR = Path(__file__).resolve().parent
CRAWLER_FILE = BASE_DIR / "forum.py"
OUTPUT_DIR = BASE_DIR / "爬取内容"

st.set_page_config(
    page_title="Gitee 爬虫控制台",
    page_icon="🕷",
    layout="wide",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=ZCOOL+XiaoWei&family=Noto+Sans+SC:wght@400;500;700&display=swap');

:root {
  --bg-ink: #f4fbff;
  --bg-sea: #eaf7ff;
  --bg-glow: #b6ffe2;
  --card: rgba(255,255,255,0.96);
  --line: rgba(7,45,60,0.16);
  --accent: #ff6f3c;
  --accent-2: #0f9d80;
  --text-main: #082033;
  --text-sub: #2a5267;
  --text-strong: #041723;
}

html, body, [class*="css"] {
  font-family: 'Noto Sans SC', sans-serif;
  color: var(--text-main);
}

.stApp {
  background:
    radial-gradient(820px 480px at -8% -15%, #9ed8ff88, transparent 56%),
    radial-gradient(780px 460px at 108% 0%, #9affd186, transparent 56%),
    radial-gradient(720px 420px at 55% 108%, #ffe6be7a, transparent 58%),
    linear-gradient(145deg, var(--bg-ink), var(--bg-sea));
}

[data-testid="stAppViewContainer"] {
  background: transparent;
}

.hero {
  border: 1px solid rgba(8, 54, 72, 0.18);
  border-radius: 26px;
  padding: 24px 26px;
  background:
    linear-gradient(110deg, rgba(255,255,255,0.92), rgba(255,255,255,0.68)),
    radial-gradient(120% 120% at 100% 0%, rgba(153,255,215,0.24), transparent 60%);
  backdrop-filter: blur(10px);
  margin-bottom: 16px;
  box-shadow: 0 18px 36px rgba(8, 42, 58, 0.16);
}

.hero h1 {
  font-family: 'ZCOOL XiaoWei', serif;
  font-size: 2.25rem;
  margin: 0;
  color: #062236;
  letter-spacing: 0.2px;
}

.hero p {
  margin: 9px 0 0 0;
  color: #24556a;
  font-weight: 500;
  font-size: 1.02rem;
}

.block {
  border-radius: 20px;
  background: var(--card);
  border: 1px solid var(--line);
  padding: 16px;
  box-shadow: 0 10px 26px rgba(8, 45, 62, 0.14);
  color: var(--text-main);
}

.block h1, .block h2, .block h3, .block h4, .block p, .block li, .block label {
  color: var(--text-main) !important;
}

.block h3 {
  font-weight: 800 !important;
  color: var(--text-strong) !important;
}

.block h3::before {
  content: "";
  display: inline-block;
  width: 6px;
  height: 20px;
  margin-right: 9px;
  border-radius: 99px;
  vertical-align: -3px;
  background: linear-gradient(180deg, #ff6f3c, #ffa552);
}

.chip-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.chip {
  border-radius: 999px;
  padding: 7px 11px;
  font-size: 12px;
  font-weight: 700;
  color: #0b3446;
  background: linear-gradient(180deg, #f0fff5, #ddfff0);
  border: 1px solid rgba(15,157,128,0.34);
}

.metric-card {
  border-radius: 14px;
  padding: 10px 12px;
  background: linear-gradient(180deg, #ffffff, #f2fffb);
  border: 1px solid rgba(15,157,128,0.25);
}

.small-note {
  font-size: 0.92rem;
  color: #315f73;
}

.stats-wrap {
  display: grid;
  grid-template-columns: repeat(3, minmax(120px, 1fr));
  gap: 14px;
  margin: 12px 0 16px;
}

.stat-card {
  border-radius: 18px;
  border: 1px solid rgba(11,59,76,0.18);
  padding: 14px 14px 12px;
  background:
    linear-gradient(180deg, #ffffff, #ecfff8),
    radial-gradient(120% 120% at 100% 0%, rgba(147,255,214,0.18), transparent 60%);
  box-shadow: 0 10px 22px rgba(8, 45, 62, 0.11);
  transition: transform .2s ease, box-shadow .2s ease;
}

.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 14px 30px rgba(7, 30, 44, 0.2);
}

.stat-title {
  font-size: 0.82rem;
  color: #2f6179;
  margin-bottom: 6px;
  font-weight: 600;
}

.stat-value {
  font-size: 1.8rem;
  line-height: 1;
  font-weight: 800;
  color: #0a2c42;
}

.stat-foot {
  margin-top: 8px;
  font-size: 0.78rem;
  color: #2d6b71;
}

.viz-card {
  border-radius: 16px;
  padding: 14px 14px 12px;
  margin-bottom: 12px;
  border: 1px solid rgba(57, 185, 140, 0.28);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.98), rgba(239,255,250,0.93)),
    radial-gradient(130% 130% at 100% 0%, rgba(126, 248, 208, 0.18), transparent 62%);
  box-shadow:
    0 8px 22px rgba(8, 45, 62, 0.11),
    inset 0 0 0 1px rgba(144, 255, 222, 0.25);
}

.viz-title {
  margin: 0 0 8px 0;
  font-size: 1.06rem;
  font-weight: 800;
  color: #0a2b3f;
  letter-spacing: 0.1px;
}

.viz-note {
  margin: -2px 0 10px 0;
  font-size: 0.88rem;
  color: #2f6076;
}

.guide-card {
  border-radius: 14px;
  padding: 12px;
  margin-top: 10px;
  border: 1px dashed rgba(11, 100, 133, 0.32);
  background: linear-gradient(180deg, rgba(245,252,255,0.9), rgba(237,255,248,0.95));
}

.guide-card p {
  margin: 0;
  font-size: 0.9rem;
  color: #27536a !important;
  line-height: 1.6;
}

div.stButton > button {
  border-radius: 14px;
  border: none;
  background: linear-gradient(90deg, var(--accent), #ff9b54);
  color: white;
  padding: 0.6rem 1.2rem;
  font-weight: 700;
  box-shadow: 0 8px 18px rgba(255, 111, 60, 0.35);
}

div.stButton > button:hover {
  filter: brightness(1.06);
  transform: translateY(-1px);
}

div.stDownloadButton > button {
  border-radius: 12px;
  background: linear-gradient(90deg, var(--accent-2), #16b89c);
  color: #fff;
  border: none;
  font-weight: 700;
}

.stCodeBlock code, .stCodeBlock pre {
  color: #e8fff6 !important;
}

[data-testid="stCode"] {
  border-radius: 14px;
  border: 1px solid rgba(147,255,220,0.25);
  box-shadow: inset 0 0 0 1px rgba(0,0,0,0.2);
}

[data-testid="stSidebar"] * {
  color: #08263a !important;
}

label,
.stTextInput label,
.stSelectbox label,
.stSlider label,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
  color: #0a2c43 !important;
  font-weight: 700 !important;
}

[data-testid="stTextInput"] input,
[data-baseweb="select"] * {
  color: #072538 !important;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
label,
.stTextInput label,
.stSelectbox label,
.stSlider label {
  color: #072132 !important;
  font-weight: 600 !important;
}

[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] div,
[data-baseweb="select"] div,
[data-testid="stSlider"] {
  color: #041a28 !important;
}

[data-testid="stDataFrame"] {
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid rgba(10, 54, 68, 0.2);
}

[data-testid="stSidebar"] {
  background: linear-gradient(170deg, rgba(255,255,255,0.95), rgba(229,255,247,0.98));
  border-right: 1px solid rgba(15,157,128,0.25);
}

#MainMenu,
header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stStatusWidget"],
[data-testid="stDecoration"] {
  display: none !important;
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
  <h1>Gitee 关键词爬取控制台</h1>
  <p>输入关键词，最多抓取 <b>10 页</b>，自动采用安全节奏（随机 UA、退避重试、随机延时），并汇总到单一表格。</p>
  <div class="chip-row">
    <span class="chip">上限 10 页</span>
    <span class="chip">自动防反爬</span>
    <span class="chip">预览 + 导出</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("输出设置")
    output_dir_input = st.text_input("保存目录", value=str(OUTPUT_DIR), help="支持绝对路径；若填相对路径，将以当前项目目录为基准。")
    st.caption("示例：D:/file/python网络爬虫/实验二/爬取内容")

    raw_output = Path(output_dir_input.strip()) if output_dir_input.strip() else OUTPUT_DIR
    selected_output_dir = raw_output if raw_output.is_absolute() else (BASE_DIR / raw_output)
    st.text(f"实际目录: {selected_output_dir}")

left, right = st.columns([1.15, 1], gap="large")

with left:
    st.markdown('<div class="block">', unsafe_allow_html=True)
    st.subheader("抓取参数")

    keyword = st.text_input("关键词", value="爬虫", placeholder="例如：爬虫、机器学习、微服务")
    pages = st.slider("抓取页数（上限 10）", min_value=1, max_value=10, value=5, step=1)

    level = st.selectbox(
        "安全节奏",
        options=["均衡（推荐）", "稳健（更慢）", "极速（更快，风险更高）"],
        index=0,
    )

    if level == "稳健（更慢）":
        delay_min, delay_max = 1.2, 2.8
    elif level == "极速（更快，风险更高）":
        delay_min, delay_max = 0.2, 0.6
    else:
        delay_min, delay_max = 0.6, 1.4

    run_now = st.button("开始爬取", use_container_width=True)

    st.markdown(
        f'<p class="small-note">当前节奏：{delay_min:.1f}s ~ {delay_max:.1f}s / 请求；结果会覆盖同关键词旧表。</p>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="block">', unsafe_allow_html=True)
    st.subheader("说明")
    st.markdown(
        """
1. 数据来源：so.gitee.com 分页搜索接口，按页抓取并自动去重。
2. 抓取策略：随机 UA + 指数退避 + 随机延时，降低被限流概率。
3. 输出模式：单一 CSV 汇总，便于后续统计分析和复现实验。
4. 可视化解读：语言占比看技术栈分布，词云看主题聚焦，Top10 看头部项目热度。
5. 使用建议：先用 3~5 页快速试跑，确认关键词有效后再提升页数。
6. 质量提醒：简介字段可能为空，词云与关键词统计会自动过滤无效文本。
"""
    )
    st.markdown(
        """
<div class="guide-card">
  <p>
  分析思路建议：先看 <b>语言占比</b> 确定技术方向，再看 <b>Top20 关键词</b> 判断内容主题，最后结合 <b>Star Top10</b> 与仓库链接做样本深挖。
  </p>
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


log_box = st.empty()
preview_box = st.empty()


CN_FONT_CANDIDATES = [
  BASE_DIR / "assets" / "fonts" / "NotoSansCJKsc-Regular.otf",
  BASE_DIR / "assets" / "fonts" / "NotoSansSC-Regular.ttf",
  Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
  Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
  Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
  Path("C:/Windows/Fonts/msyh.ttc"),
  Path("C:/Windows/Fonts/simhei.ttf"),
  Path("C:/Windows/Fonts/simsun.ttc"),
  Path("C:/Windows/Fonts/msyhbd.ttc"),
]

WORD_STOPWORDS = {
  "项目", "一个", "可以", "这个", "用于", "使用", "支持", "功能", "开发", "进行", "实现", "以及", "相关",
  "并且", "帮助", "更多", "提供", "代码", "仓库", "基于", "工具", "系统", "框架", "版本", "服务", "平台",
  "the", "and", "for", "with", "from", "this", "that", "are", "was", "you", "your", "have", "has", "not",
}


def find_chinese_font() -> str | None:
  for font_path in CN_FONT_CANDIDATES:
    if not font_path.exists() or font_path.stat().st_size < 100000:
      continue
    try:
      if ImageFont is not None:
        ImageFont.truetype(str(font_path), 16)
      return str(font_path)
    except OSError:
      continue
  return None


def configure_matplotlib_font() -> None:
  font_path = find_chinese_font()
  if font_path:
    try:
      fm.fontManager.addfont(font_path)
      font_name = fm.FontProperties(fname=font_path).get_name()
      plt.rcParams["font.family"] = font_name
      plt.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
    except Exception:
      plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
  else:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
  plt.rcParams["axes.unicode_minus"] = False


configure_matplotlib_font()


def make_star_numeric(star_series: pd.Series) -> pd.Series:
  cleaned = (
    star_series.astype(str)
    .str.strip()
    .str.replace(",", "", regex=False)
    .str.replace(r"[^0-9.]", "", regex=True)
  )
  return pd.to_numeric(cleaned, errors="coerce").fillna(0)


def build_word_frequencies(texts: pd.Series) -> Counter:
  combined = " ".join(texts.dropna().astype(str).tolist()).strip()
  if not combined:
    return Counter()

  if jieba is not None:
    tokens = [
      w.strip().lower()
      for w in jieba.cut(combined, cut_all=False)
      if w and len(w.strip()) >= 2
    ]
  else:
    tokens = [
      w.strip().lower()
      for w in re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z][a-zA-Z0-9_+-]{1,}", combined)
    ]

  filtered = [w for w in tokens if w not in WORD_STOPWORDS and not w.isdigit()]
  return Counter(filtered)


def compute_recent_trend(df: pd.DataFrame, days: int = 30) -> tuple[pd.DataFrame, str]:
  end_date = pd.Timestamp.now().normalize()
  date_index = pd.date_range(end=end_date, periods=days, freq="D")

  if "updated_at" not in df.columns:
    return pd.DataFrame({"date": date_index, "count": [0] * len(date_index)}), "数据不足"

  dt_series = pd.to_datetime(df["updated_at"], errors="coerce", utc=True)
  if dt_series.notna().any():
    dt_series = dt_series.dt.tz_convert(None)
  dt_series = dt_series.dt.normalize()

  valid_dates = dt_series.dropna()
  if valid_dates.empty:
    return pd.DataFrame({"date": date_index, "count": [0] * len(date_index)}), "数据不足"

  daily_counts = valid_dates.value_counts().sort_index()
  trend = pd.Series(0, index=date_index, dtype="int64")
  trend.update(daily_counts)

  trend_df = trend.reset_index()
  trend_df.columns = ["date", "count"]

  first_week = trend_df["count"].head(7).mean()
  last_week = trend_df["count"].tail(7).mean()
  if last_week - first_week > 0.5:
    direction = "上升"
  elif first_week - last_week > 0.5:
    direction = "下降"
  else:
    direction = "平稳"

  return trend_df, direction


def build_language_star_table(df: pd.DataFrame) -> pd.DataFrame:
  if "language" not in df.columns or "star_num" not in df.columns:
    return pd.DataFrame()

  lang_series = df["language"].fillna("").astype(str).str.strip()
  base = df.copy()
  base["language_clean"] = lang_series.replace("", "未知")

  table = base.groupby("language_clean", as_index=False).agg(
    平均Star=("star_num", "mean"),
    中位数Star=("star_num", "median"),
    项目数=("star_num", "count"),
  )
  table = table.rename(columns={"language_clean": "语言"})
  table["平均Star"] = table["平均Star"].round(2)
  table["中位数Star"] = table["中位数Star"].round(2)
  table = table.sort_values(["项目数", "平均Star"], ascending=[False, False])
  return table


def build_png_report(
  trend_df: pd.DataFrame,
  lang_star_table: pd.DataFrame,
  ranked: pd.DataFrame,
  lang_counts: pd.Series,
  filter_text: str,
) -> bytes:
  fig, axes = plt.subplots(2, 2, figsize=(14, 9), dpi=140)
  fig.suptitle(f"Gitee 分析报告快照\n{filter_text}", fontsize=14, fontweight="bold")

  ax1, ax2 = axes[0, 0], axes[0, 1]
  ax3, ax4 = axes[1, 0], axes[1, 1]

  if not trend_df.empty:
    ax1.plot(trend_df["date"], trend_df["count"], color="#0f9d80", marker="o", linewidth=2)
    ax1.set_title("近30天活跃趋势")
    ax1.set_ylabel("项目数")
    ax1.grid(alpha=0.25, linestyle="--")
    ax1.tick_params(axis="x", rotation=20)
  else:
    ax1.text(0.5, 0.5, "无趋势数据", ha="center", va="center")
    ax1.set_axis_off()

  if not lang_star_table.empty:
    top_lang = lang_star_table.head(8)
    x = range(len(top_lang))
    ax2.bar([i - 0.2 for i in x], top_lang["平均Star"], width=0.4, label="平均Star", color="#4aa3ff")
    ax2.bar([i + 0.2 for i in x], top_lang["中位数Star"], width=0.4, label="中位数Star", color="#39b98c")
    ax2.set_title("语言 x Star 交叉分析")
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(top_lang["语言"], rotation=20)
    ax2.legend()
    ax2.grid(axis="y", alpha=0.25, linestyle="--")
  else:
    ax2.text(0.5, 0.5, "无语言Star数据", ha="center", va="center")
    ax2.set_axis_off()

  if not ranked.empty:
    y = ranked["project_name"].astype(str).tolist()[::-1]
    v = ranked["star_num"].tolist()[::-1]
    ax3.barh(y, v, color="#39b98c")
    ax3.set_title("Star Top 10")
    ax3.set_xlabel("Star")
    ax3.grid(axis="x", alpha=0.25, linestyle="--")
  else:
    ax3.text(0.5, 0.5, "无Top10数据", ha="center", va="center")
    ax3.set_axis_off()

  if not lang_counts.empty:
    pie_counts = lang_counts.head(8)
    ax4.pie(
      pie_counts.values,
      labels=pie_counts.index,
      autopct="%1.1f%%",
      startangle=120,
      textprops={"fontsize": 8},
    )
    ax4.set_title("语言占比")
  else:
    ax4.text(0.5, 0.5, "无语言占比数据", ha="center", va="center")
    ax4.set_axis_off()

  fig.tight_layout(rect=[0, 0, 1, 0.95])
  buf = io.BytesIO()
  fig.savefig(buf, format="png", bbox_inches="tight")
  plt.close(fig)
  return buf.getvalue()


def build_html_report(
  summary_dict: dict,
  trend_df: pd.DataFrame,
  lang_star_table: pd.DataFrame,
  top_words: pd.DataFrame,
  ranked_links: pd.DataFrame,
  filter_text: str,
) -> bytes:
  summary_html = "".join([f"<li><b>{k}:</b> {v}</li>" for k, v in summary_dict.items()])
  trend_html = trend_df.tail(30).to_html(index=False, border=0)
  lang_star_html = lang_star_table.to_html(index=False, border=0) if not lang_star_table.empty else "<p>无数据</p>"
  words_html = top_words.to_html(index=False, border=0) if not top_words.empty else "<p>无数据</p>"
  links_html = ranked_links.to_html(index=False, border=0) if not ranked_links.empty else "<p>无数据</p>"

  html = f"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Gitee 分析报告</title>
  <style>
    body {{ font-family: 'Microsoft YaHei', sans-serif; background: #f4fbff; color: #082033; padding: 20px; }}
    h1, h2 {{ color: #0a2b3f; }}
    .card {{ background: #fff; border: 1px solid #d8edf3; border-radius: 12px; padding: 14px; margin-bottom: 14px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border: 1px solid #d9edf2; padding: 8px; text-align: left; }}
    th {{ background: #effbff; }}
    .note {{ color: #2f6076; font-size: 13px; }}
  </style>
</head>
<body>
  <h1>Gitee 可视化分析报告</h1>
  <p class="note">筛选条件：{filter_text}</p>
  <div class="card">
    <h2>统计摘要</h2>
    <ul>{summary_html}</ul>
  </div>
  <div class="card">
    <h2>近30天活跃趋势</h2>
    {trend_html}
  </div>
  <div class="card">
    <h2>语言 x Star 交叉分析</h2>
    {lang_star_html}
  </div>
  <div class="card">
    <h2>Top20 关键词</h2>
    {words_html}
  </div>
  <div class="card">
    <h2>Star Top10 项目链接</h2>
    {links_html}
  </div>
</body>
</html>
"""
  return html.encode("utf-8")


def render_analytics(df: pd.DataFrame) -> None:
  st.markdown('<div class="block">', unsafe_allow_html=True)
  st.subheader("可视化分析")

  data = df.copy()
  if "star" in data.columns:
    data["star_num"] = make_star_numeric(data["star"])
  else:
    data["star_num"] = 0

  if "language" in data.columns:
    data["language_clean"] = data["language"].fillna("").astype(str).str.strip().replace("", "未知")
  else:
    data["language_clean"] = "未知"

  st.markdown('<div class="viz-card">', unsafe_allow_html=True)
  st.markdown('<p class="viz-title">交互筛选</p>', unsafe_allow_html=True)
  st.markdown('<p class="viz-note">按语言、最小 Star、关键词包含进行联动筛选，所有图表会同步更新。</p>', unsafe_allow_html=True)

  f1, f2, f3 = st.columns([1.1, 1, 1.2], gap="medium")
  lang_options = sorted(data["language_clean"].dropna().unique().tolist())
  with f1:
    selected_langs = st.multiselect("语言筛选", options=lang_options, default=lang_options)
  max_star = int(data["star_num"].max()) if not data.empty else 0
  with f2:
    min_star = st.slider("最小 Star", min_value=0, max_value=max_star if max_star > 0 else 1, value=0)
  with f3:
    kw_filter = st.text_input("关键词包含筛选", value="", placeholder="匹配项目名/简介/作者")

  filtered = data.copy()
  if selected_langs:
    filtered = filtered[filtered["language_clean"].isin(selected_langs)]
  filtered = filtered[filtered["star_num"] >= min_star]
  if kw_filter.strip():
    needle = kw_filter.strip().lower()
    name_s = filtered.get("project_name", pd.Series("", index=filtered.index)).astype(str).str.lower()
    desc_s = filtered.get("description", pd.Series("", index=filtered.index)).astype(str).str.lower()
    author_s = filtered.get("author", pd.Series("", index=filtered.index)).astype(str).str.lower()
    filtered = filtered[name_s.str.contains(needle, na=False) | desc_s.str.contains(needle, na=False) | author_s.str.contains(needle, na=False)]

  st.caption(f"筛选后记录数：{len(filtered)} / {len(data)}")
  st.markdown("</div>", unsafe_allow_html=True)

  if filtered.empty:
    st.warning("当前筛选条件下没有数据，请放宽筛选条件。")
    st.markdown("</div>", unsafe_allow_html=True)
    return

  freq = Counter()
  if "description" in filtered.columns:
    freq = build_word_frequencies(filtered["description"])

  ranked = pd.DataFrame()
  if "project_name" in filtered.columns:
    ranked = filtered.sort_values("star_num", ascending=False).head(10)

  lang_counts = filtered["language_clean"].value_counts().head(12)
  trend_df, trend_direction = compute_recent_trend(filtered, days=30)
  lang_star_table = build_language_star_table(filtered)

  ranked = pd.DataFrame()
  if "project_name" in filtered.columns:
    ranked = filtered.sort_values("star_num", ascending=False).head(10)

  row1_left, row1_right = st.columns([1, 1], gap="large")

  with row1_left:
    st.markdown('<div class="viz-card">', unsafe_allow_html=True)
    st.markdown('<p class="viz-title">Top 20 关键词</p>', unsafe_allow_html=True)
    st.markdown('<p class="viz-note">高频词可以快速反映项目简介中的核心能力与场景。</p>', unsafe_allow_html=True)
    if "description" not in filtered.columns:
      st.info("结果中未找到 description 列。")
    elif not freq:
      st.info("简介文本太少或无有效关键词，无法统计 Top 关键词。")
    else:
      top_words = pd.DataFrame(freq.most_common(20), columns=["关键词", "频次"])
      top_words.insert(0, "序号", range(1, len(top_words) + 1))
      st.caption("关键词频次（序号从 1 开始）")
      st.dataframe(top_words, use_container_width=True, height=360, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

  with row1_right:
    st.markdown('<div class="viz-card">', unsafe_allow_html=True)
    st.markdown('<p class="viz-title">语言占比</p>', unsafe_allow_html=True)
    st.markdown('<p class="viz-note">用于观察技术栈结构，识别关键词下最活跃的语言生态。</p>', unsafe_allow_html=True)
    if "language_clean" in filtered.columns:
      if lang_counts.empty:
        st.info("暂无可用于统计语言的数据。")
      else:
        fig, ax = plt.subplots(figsize=(6.6, 4.9), dpi=110)
        colors = plt.cm.Set3(range(len(lang_counts)))
        ax.pie(
          lang_counts.values,
          labels=lang_counts.index,
          autopct="%1.1f%%",
          startangle=120,
          pctdistance=0.8,
          textprops={"fontsize": 10},
          colors=colors,
        )
        ax.axis("equal")
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
      st.info("结果中未找到 language 列。")
    st.markdown("</div>", unsafe_allow_html=True)

  row2_left, row2_right = st.columns([1.25, 1], gap="large")

  with row2_left:
    st.markdown('<div class="viz-card">', unsafe_allow_html=True)
    st.markdown('<p class="viz-title">Star Top 10 排行</p>', unsafe_allow_html=True)
    st.markdown('<p class="viz-note">横向对比头部项目热度，便于快速锁定高价值仓库。</p>', unsafe_allow_html=True)
    if "star" not in filtered.columns or ranked.empty:
      st.info("暂无可用于排行的 Star 数据。")
    else:
      y_labels = [
        f"{name}"[:30] + ("..." if len(f"{name}") > 30 else "")
        for name in ranked["project_name"].astype(str).tolist()
      ]
      fig, ax = plt.subplots(figsize=(8.2, 4.8), dpi=110)
      bars = ax.barh(y_labels[::-1], ranked["star_num"].tolist()[::-1], color="#39b98c")
      ax.set_xlabel("Star")
      ax.set_ylabel("项目")
      ax.grid(axis="x", linestyle="--", alpha=0.25)
      for bar in bars:
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height() / 2, f" {int(width)}", va="center", fontsize=9)
      st.pyplot(fig, use_container_width=True)
      plt.close(fig)
    st.markdown("</div>", unsafe_allow_html=True)

  with row2_right:
    st.markdown('<div class="viz-card">', unsafe_allow_html=True)
    st.markdown('<p class="viz-title">Top 10 项目链接</p>', unsafe_allow_html=True)
    st.markdown('<p class="viz-note">点击项目名可直接跳转仓库，进行代码质量与活跃度深读。</p>', unsafe_allow_html=True)
    if ranked.empty or "project_url" not in ranked.columns:
      st.info("暂无可展示的项目链接。")
    else:
      ranked_links = ranked[["project_name", "project_url", "star_num"]].copy()
      ranked_links = ranked_links[ranked_links["project_url"].astype(str).str.strip() != ""]
      ranked_links = ranked_links.reset_index(drop=True)
      if ranked_links.empty:
        st.info("Top 10 中没有有效项目链接。")
      else:
        st.caption("点击项目名可直接跳转到仓库")
        for idx, row in ranked_links.iterrows():
          project_name = str(row["project_name"]) if pd.notna(row["project_name"]) else "未命名项目"
          project_url = str(row["project_url"]).strip()
          star_num = int(row["star_num"])
          st.markdown(f"{idx + 1}. [{project_name}]({project_url})  ·  ⭐ {star_num}")
    st.markdown("</div>", unsafe_allow_html=True)

  row3_left, row3_right = st.columns([1.05, 1], gap="large")

  with row3_left:
    st.markdown('<div class="viz-card">', unsafe_allow_html=True)
    st.markdown('<p class="viz-title">近 30 天活跃趋势</p>', unsafe_allow_html=True)
    st.markdown('<p class="viz-note">按更新时间聚合每日项目量，用于判断热度变化趋势。</p>', unsafe_allow_html=True)
    if trend_df.empty:
      st.info("缺少更新时间数据，无法绘制趋势图。")
    else:
      fig, ax = plt.subplots(figsize=(8.2, 4.3), dpi=110)
      ax.plot(trend_df["date"], trend_df["count"], color="#0f9d80", marker="o", linewidth=2)
      ax.fill_between(trend_df["date"], trend_df["count"], color="#0f9d80", alpha=0.12)
      ax.set_ylabel("项目数")
      ax.set_xlabel("日期")
      ax.grid(alpha=0.25, linestyle="--")
      ax.tick_params(axis="x", rotation=22)
      st.pyplot(fig, use_container_width=True)
      plt.close(fig)
      st.caption(f"趋势判断：近 30 天整体呈 {trend_direction} 趋势")
    st.markdown("</div>", unsafe_allow_html=True)

  with row3_right:
    st.markdown('<div class="viz-card">', unsafe_allow_html=True)
    st.markdown('<p class="viz-title">语言 x Star 交叉分析</p>', unsafe_allow_html=True)
    st.markdown('<p class="viz-note">对比各语言平均 Star 与中位数 Star，兼顾规模与质量。</p>', unsafe_allow_html=True)
    if lang_star_table.empty:
      st.info("暂无可用于交叉分析的数据。")
    else:
      top_lang = lang_star_table.head(8)
      fig, ax = plt.subplots(figsize=(8.0, 4.3), dpi=110)
      x = range(len(top_lang))
      ax.bar([i - 0.2 for i in x], top_lang["平均Star"], width=0.4, label="平均Star", color="#4aa3ff")
      ax.bar([i + 0.2 for i in x], top_lang["中位数Star"], width=0.4, label="中位数Star", color="#39b98c")
      ax.set_xticks(list(x))
      ax.set_xticklabels(top_lang["语言"], rotation=20)
      ax.grid(axis="y", alpha=0.25, linestyle="--")
      ax.legend()
      st.pyplot(fig, use_container_width=True)
      plt.close(fig)
      st.dataframe(lang_star_table, use_container_width=True, height=230, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

  st.markdown('<div class="viz-card">', unsafe_allow_html=True)
  st.markdown('<p class="viz-title">简介关键词词云</p>', unsafe_allow_html=True)
  st.markdown('<p class="viz-note">词云用于直观看到主题强度，字号越大代表频次越高。</p>', unsafe_allow_html=True)
  if "description" not in filtered.columns:
    st.info("结果中未找到 description 列。")
  elif WordCloud is None:
    st.warning("未安装 wordcloud，暂无法绘制词云。请安装：pip install wordcloud")
  elif not freq:
    st.info("简介文本太少或无有效关键词，无法生成词云。")
  else:
    font_path = find_chinese_font()
    try:
      wc = WordCloud(
        width=1200,
        height=560,
        background_color="white",
        max_words=180,
        colormap="viridis",
        font_path=font_path,
        prefer_horizontal=0.9,
      ).generate_from_frequencies(freq)

      fig, ax = plt.subplots(figsize=(12, 5.5), dpi=120)
      ax.imshow(wc, interpolation="bilinear")
      ax.axis("off")
      st.pyplot(fig, use_container_width=True)
      plt.close(fig)
    except OSError:
      st.warning("词云字体加载失败，已跳过词云渲染。请在云端 Reboot 后重试。")
  st.markdown("</div>", unsafe_allow_html=True)

  st.markdown('<div class="viz-card">', unsafe_allow_html=True)
  st.markdown('<p class="viz-title">导出分析报告</p>', unsafe_allow_html=True)
  st.markdown('<p class="viz-note">一键导出当前筛选结果的统计摘要与图表快照，适合作业提交。</p>', unsafe_allow_html=True)

  top_words_df = pd.DataFrame(freq.most_common(20), columns=["关键词", "频次"])
  if not top_words_df.empty:
    top_words_df.insert(0, "序号", range(1, len(top_words_df) + 1))

  ranked_links = pd.DataFrame()
  if not ranked.empty and "project_url" in ranked.columns:
    ranked_links = ranked[["project_name", "project_url", "star_num"]].copy()
    ranked_links = ranked_links.rename(columns={"project_name": "项目名", "project_url": "链接", "star_num": "Star"})

  filter_text = f"语言={','.join(selected_langs) if selected_langs else '全部'}；最小Star={min_star}；关键词包含={kw_filter.strip() or '无'}"
  summary_dict = {
    "筛选后项目数": len(filtered),
    "作者数": int(filtered["author"].nunique()) if "author" in filtered.columns else 0,
    "语言种类": int(filtered["language_clean"].nunique()),
    "平均Star": round(float(filtered["star_num"].mean()), 2),
    "趋势判断": trend_direction,
  }

  html_bytes = build_html_report(
    summary_dict=summary_dict,
    trend_df=trend_df,
    lang_star_table=lang_star_table,
    top_words=top_words_df,
    ranked_links=ranked_links,
    filter_text=filter_text,
  )
  png_bytes = build_png_report(
    trend_df=trend_df,
    lang_star_table=lang_star_table,
    ranked=ranked,
    lang_counts=lang_counts,
    filter_text=filter_text,
  )

  exp_col1, exp_col2 = st.columns(2, gap="medium")
  with exp_col1:
    st.download_button(
      label="导出 HTML 报告",
      data=html_bytes,
      file_name="gitee_analysis_report.html",
      mime="text/html",
      use_container_width=True,
    )
  with exp_col2:
    st.download_button(
      label="导出 PNG 快照",
      data=png_bytes,
      file_name="gitee_analysis_dashboard.png",
      mime="image/png",
      use_container_width=True,
    )
  st.markdown("</div>", unsafe_allow_html=True)

  if "star" not in filtered.columns or "project_name" not in filtered.columns:
    st.info("结果中未找到 star 或 project_name 列。")

  st.markdown("</div>", unsafe_allow_html=True)


def decode_output(data: bytes) -> str:
  if not data:
    return ""
  for enc in ("utf-8", "gbk", "cp936"):
    try:
      return data.decode(enc)
    except UnicodeDecodeError:
      continue
  return data.decode("utf-8", errors="replace")


def render_result_panels(df: pd.DataFrame, csv_path: Path) -> None:
  total_count = int(len(df))
  author_count = int(df["author"].nunique()) if "author" in df.columns else 0
  lang_count = int(df["language"].nunique()) if "language" in df.columns else 0
  avg_star = 0
  if "star" in df.columns:
    star_vals = pd.to_numeric(df["star"], errors="coerce")
    if star_vals.notna().any():
      avg_star = int(star_vals.fillna(0).mean())

  st.markdown(
      f"""
<div class="stats-wrap">
  <div class="stat-card">
    <div class="stat-title">项目总数</div>
    <div class="stat-value">{total_count}</div>
    <div class="stat-foot">去重后可用记录</div>
  </div>
  <div class="stat-card">
    <div class="stat-title">作者数</div>
    <div class="stat-value">{author_count}</div>
    <div class="stat-foot">独立贡献主体</div>
  </div>
  <div class="stat-card">
    <div class="stat-title">语言种类</div>
    <div class="stat-value">{lang_count}</div>
    <div class="stat-foot">技术栈覆盖面</div>
  </div>
</div>
""",
      unsafe_allow_html=True,
  )

  st.caption(f"平均 Star：{avg_star}  |  保存路径：{csv_path}")

  render_analytics(df)

  preview_box.markdown('<div class="block">', unsafe_allow_html=True)
  st.subheader("数据预览")
  st.caption(f"文件位置：{csv_path}")
  st.dataframe(df, use_container_width=True, height=420)

  csv_bytes = csv_path.read_bytes()
  st.download_button(
      label="导出 CSV",
      data=csv_bytes,
      file_name=csv_path.name,
      mime="text/csv",
      use_container_width=True,
  )
  preview_box.markdown("</div>", unsafe_allow_html=True)

if "last_csv_path" not in st.session_state:
  st.session_state["last_csv_path"] = ""

clean_keyword = keyword.strip()
target_csv = selected_output_dir / f"gitee_so_{clean_keyword}_projects.csv" if clean_keyword else None

if run_now:
  if not clean_keyword:
    st.error("请输入关键词后再开始。")
  else:
    selected_output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
      sys.executable,
      "-X",
      "utf8",
      str(CRAWLER_FILE),
      "--keyword",
      clean_keyword,
      "--start",
      "1",
      "--end",
      str(pages),
      "--size",
      "20",
      "--query-id",
      "1048",
      "--widget-id",
      "wong1slagnlmzwvsu5ya",
      "--delay-min",
      str(delay_min),
      "--delay-max",
      str(delay_max),
      "--output",
      str(selected_output_dir),
      "--force",
    ]

    with st.spinner("正在安全抓取中，请稍候..."):
      child_env = os.environ.copy()
      child_env["PYTHONUTF8"] = "1"
      child_env["PYTHONIOENCODING"] = "utf-8"
      proc = subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=False,
        env=child_env,
      )

    stdout_text = decode_output(proc.stdout)
    stderr_text = decode_output(proc.stderr)
    all_logs = (stdout_text or "") + "\n" + (stderr_text or "")
    log_box.markdown('<div class="block">', unsafe_allow_html=True)
    if proc.returncode == 0:
      st.success("抓取完成")
    else:
      st.error(f"抓取失败（退出码 {proc.returncode}）")
    st.code(all_logs.strip() or "无日志输出", language="text")
    log_box.markdown("</div>", unsafe_allow_html=True)

    if target_csv and target_csv.exists():
      st.session_state["last_csv_path"] = str(target_csv)

display_csv_path: Path | None = None
if target_csv and target_csv.exists():
  display_csv_path = target_csv
elif st.session_state.get("last_csv_path"):
  previous_path = Path(st.session_state["last_csv_path"])
  if previous_path.exists():
    display_csv_path = previous_path

if display_csv_path and display_csv_path.exists():
  if target_csv and display_csv_path != target_csv:
    st.info(f"当前关键词暂无本地结果，已加载上次结果：{display_csv_path.name}")
  df = pd.read_csv(display_csv_path, encoding="utf-8-sig")
  render_result_panels(df, display_csv_path)
else:
  st.info("设置关键词和页数后，点击“开始爬取”；或先爬取一次后可直接在本地结果上交互筛选。")
