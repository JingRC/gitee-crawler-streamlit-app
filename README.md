# Gitee 关键词爬取与可视化平台

这是一个基于 Python + Streamlit 的 Gitee 搜索爬取与分析项目，支持：

- 关键词分页抓取
- 单 CSV 汇总输出
- 交互筛选（语言/Star/关键词）
- 可视化分析（语言占比、词云、Top10、趋势、交叉分析）
- 报告导出（HTML/PNG）

## 本地运行

```bash
python -m pip install -r requirements.txt
python -m streamlit run crawler_ui.py
```

## 部署到 Streamlit Community Cloud

1. 将本项目推送到 GitHub 仓库（`main` 分支）。
2. 打开 https://share.streamlit.io/ 并使用 GitHub 登录。
3. 点击 `New app`。
4. 选择你的仓库和分支：`main`。
5. Main file path 填：`crawler_ui.py`。
6. 点击 `Deploy`。

部署完成后会得到一个公开地址（`*.streamlit.app`），别人可直接访问使用。

## 说明

- 抓取逻辑：`forum.py`
- 可视化 UI：`crawler_ui.py`
- 启动脚本：`start_ui.bat`

请勿在仓库中提交 Cookie、Token 等敏感信息。
