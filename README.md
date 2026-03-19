# Gitee Search Crawler & Analytics Dashboard

一个面向教学与课程实验的 Gitee 搜索数据采集与分析项目。项目以 Python 为核心，提供命令行爬虫与 Streamlit 可视化控制台，支持从关键词抓取到分析报告导出的完整流程。

## 项目目标

- 构建可复现的关键词分页抓取流程
- 提供可交互的数据分析界面
- 输出结构化数据和可提交报告
- 兼容本地运行与云端部署（Streamlit Community Cloud）

## 主要功能

- 分页抓取：按 `from + size` 偏移量进行稳定翻页
- 安全抓取：随机 User-Agent、随机延时、指数退避重试
- 数据清洗：统一字段映射、去重汇总、单 CSV 输出
- 交互筛选：语言筛选、最小 Star 筛选、关键词包含筛选
- 可视化分析：
	- 语言占比
	- 简介关键词词云
	- Star Top10 排行
	- 近 30 天活跃趋势
	- 语言 x Star 交叉分析（平均值/中位数）
- 报告导出：一键导出 HTML 报告与 PNG 看板

## 技术栈

- Python 3.11
- requests
- pandas
- streamlit
- matplotlib
- wordcloud
- jieba

## 项目结构

```text
.
├─ crawler_ui.py                  # Streamlit 可视化界面
├─ forum.py                       # 爬虫主流程（命令行）
├─ proxy_checker.py               # 代理可用性检测脚本
├─ start_ui.bat                   # Windows 一键启动脚本
├─ requirements.txt               # 依赖清单
├─ runtime.txt                    # Streamlit Cloud Python 版本声明
├─ .python-version                # Python 版本提示
└─ assets/fonts/                  # 云端中文字体（词云/图表防乱码）
```

## 数据字段

输出 CSV 列包含：

- `project_name`
- `author`
- `description`
- `star`
- `fork`
- `updated_at`
- `project_url`
- `language`
- `owner`
- `repo`

## 快速开始

### 1. 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 2. 启动 UI

```bash
python -m streamlit run crawler_ui.py
```

### 3. 命令行抓取（可选）

```bash
python forum.py --keyword 爬虫 --start 1 --end 10 --size 20 --force
```

## Streamlit Community Cloud 部署

1. 将代码推送到 GitHub `main` 分支
2. 打开 https://share.streamlit.io
3. 点击 `New app`
4. 选择仓库和分支：`main`
5. Main file path 填写：`crawler_ui.py`
6. 点击 `Deploy`

部署后将生成公开访问地址（`*.streamlit.app`）。

## 常见问题

### 1. 云端依赖安装失败（Pillow/zlib）

原因通常是 Python 版本过高导致部分依赖无预编译轮子。

建议：

- 使用 `runtime.txt` 与 `.python-version` 固定 Python 3.11
- 在 Streamlit Cloud 后台执行 `Clear cache` + `Reboot`

### 2. 词云或图表中文乱码

项目已内置中文字体到 `assets/fonts`，并在代码中优先加载。

若仍乱码：

- 确认最新提交已部署
- 在云端执行 `Clear cache` + `Reboot`

## 合规与安全

- 仅采集公开可访问数据
- 禁止将 Cookie、Token、账号密钥提交到仓库
- 请遵守目标网站使用规则与相关法律法规

## 许可证

用于课程实验与学习研究。若用于公开发布，建议补充正式 License 文件。
