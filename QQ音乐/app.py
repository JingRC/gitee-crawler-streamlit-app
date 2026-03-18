from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
import sqlite3
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from db import fetch_comments, fetch_songs, init_db, upsert_comments, upsert_song
from qq_music_client import QQMusicClient


st.set_page_config(page_title="QQ音乐爬取与分析", page_icon="🎵", layout="wide")


def get_client() -> QQMusicClient:
    return QQMusicClient()


def _songs_to_df(rows) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(x) for x in rows])


def _comments_to_df(rows) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(x) for x in rows])


def _display_song_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("当前没有歌曲数据。")
        return

    cols = [
        "song_name",
        "singer_names",
        "album",
        "language",
        "genre",
        "company",
        "publish_time",
        "comment_count",
        "crawled_at",
    ]
    show_cols = [c for c in cols if c in df.columns]

    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)


def _display_comment_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("当前没有评论数据。")
        return

    cols = [
        "song_mid",
        "user_name",
        "likes",
        "comment_time",
        "location",
        "content",
        "crawled_at",
    ]
    show_cols = [c for c in cols if c in df.columns]
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)


def _save_song_and_comments(payload: Dict, db_path: str) -> Dict[str, int]:
    song = dict(payload)
    comments = song.pop("comments", [])
    song.pop("comment_stats", None)
    upsert_song(song, db_path=db_path)
    saved_comments = upsert_comments(song.get("song_mid", ""), comments, db_path=db_path)
    return {"songs": 1, "comments": saved_comments}


def _to_excel_bytes(songs_df: pd.DataFrame, comments_df: pd.DataFrame) -> bytes:
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        songs_df.to_excel(writer, index=False, sheet_name="songs")
        comments_df.to_excel(writer, index=False, sheet_name="comments")
    bio.seek(0)
    return bio.read()


def _save_tables_to_dir(
    songs_df: pd.DataFrame,
    comments_df: pd.DataFrame,
    save_dir: str,
    table_file_stem: str,
) -> Dict[str, str]:
    base = Path(save_dir)
    base.mkdir(parents=True, exist_ok=True)

    stem = (table_file_stem or "qq_music_export").strip()
    songs_csv = base / f"{stem}_songs.csv"
    comments_csv = base / f"{stem}_comments.csv"
    excel_path = base / f"{stem}.xlsx"

    songs_df.to_csv(songs_csv, index=False, encoding="utf-8-sig")
    comments_df.to_csv(comments_csv, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        songs_df.to_excel(writer, index=False, sheet_name="songs")
        comments_df.to_excel(writer, index=False, sheet_name="comments")

    return {
        "songs_csv": str(songs_csv),
        "comments_csv": str(comments_csv),
        "excel": str(excel_path),
    }


def _sanitize_filename(name: str) -> str:
    s = (name or "").strip()
    if not s:
        return "unknown"
    bad_chars = '<>:"/\\|?*\n\r\t'
    for ch in bad_chars:
        s = s.replace(ch, "_")
    return s[:120].strip(" .") or "unknown"


def _save_song_comments_file(payload: Dict[str, Any], comments_dir: str) -> str:
    comments = payload.get("comments", []) or []
    if not comments:
        return ""

    base = Path(comments_dir)
    base.mkdir(parents=True, exist_ok=True)

    song_name = _sanitize_filename(str(payload.get("song_name", "")))
    song_mid = _sanitize_filename(str(payload.get("song_mid", "")))
    file_name = f"{song_name}_{song_mid}.csv"
    file_path = base / file_name

    rows = []
    for c in comments:
        rows.append(
            {
                "song_mid": payload.get("song_mid", ""),
                "song_name": payload.get("song_name", ""),
                "singer_names": payload.get("singer_names", ""),
                "album": payload.get("album", ""),
                "comment_type": c.get("comment_type", ""),
                "comment_id": c.get("comment_id", ""),
                "user_name": c.get("user_name", ""),
                "likes": c.get("likes", 0),
                "comment_time": c.get("comment_time", ""),
                "location": c.get("location", ""),
                "content": c.get("content", ""),
            }
        )

    pd.DataFrame(rows).to_csv(file_path, index=False, encoding="utf-8-sig")
    return str(file_path)


def _auto_export_db_tables(db_path: str, save_dir: str, table_file_stem: str) -> Dict[str, str]:
    songs_df = _songs_to_df(fetch_songs(limit=200000, db_path=db_path))
    comments_df = _comments_to_df(fetch_comments(limit=500000, db_path=db_path))
    return _save_tables_to_dir(
        songs_df=songs_df,
        comments_df=comments_df,
        save_dir=save_dir,
        table_file_stem=table_file_stem,
    )


def _repair_db_mojibake(db_path: str) -> Dict[str, int]:
    fixer = QQMusicClient()
    songs_updated = 0
    comments_updated = 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        song_rows = conn.execute(
            """
            SELECT id, song_name, singer_names, album, language, genre, company, intro, lyric
            FROM songs
            """
        ).fetchall()
        for row in song_rows:
            updates = {}
            for key in ["song_name", "singer_names", "album", "language", "genre", "company", "intro", "lyric"]:
                raw = row[key] or ""
                fixed = fixer._repair_text(raw)
                if fixed != raw:
                    updates[key] = fixed
            if updates:
                set_clause = ", ".join(f"{k}=?" for k in updates.keys())
                vals = list(updates.values()) + [row["id"]]
                conn.execute(f"UPDATE songs SET {set_clause} WHERE id=?", vals)
                songs_updated += 1

        comment_rows = conn.execute(
            """
            SELECT id, user_name, content, location
            FROM comments
            """
        ).fetchall()
        for row in comment_rows:
            updates = {}
            for key in ["user_name", "content", "location"]:
                raw = row[key] or ""
                fixed = fixer._repair_text(raw)
                if fixed != raw:
                    updates[key] = fixed
            if updates:
                set_clause = ", ".join(f"{k}=?" for k in updates.keys())
                vals = list(updates.values()) + [row["id"]]
                conn.execute(f"UPDATE comments SET {set_clause} WHERE id=?", vals)
                comments_updated += 1

        conn.commit()
    finally:
        conn.close()

    return {
        "songs_updated": songs_updated,
        "comments_updated": comments_updated,
    }


def _crawl_songs_parallel(songs: List[Dict[str, Any]], crawl_cfg: Dict[str, Any]) -> Dict[str, int]:
    if not songs:
        return {"songs": 0, "comments": 0, "failed": 0}

    total_song_saved = 0
    total_comment_saved = 0
    failed = 0
    latest_comments = 0
    hot_comments = 0
    highlight_comments = 0
    deduped_comments = 0
    comment_files_saved = 0
    progress = st.progress(0)

    def worker(song_brief: Dict[str, Any]) -> Dict[str, Any]:
        song_mid = song_brief.get("song_mid", "")
        if not song_mid:
            raise ValueError("song_mid 为空")

        local_client = QQMusicClient(
            timeout=int(crawl_cfg["timeout"]),
            max_retries=int(crawl_cfg["max_retries"]),
            retry_backoff=float(crawl_cfg["retry_backoff"]),
            min_delay=float(crawl_cfg["min_delay"]),
            max_delay=float(crawl_cfg["max_delay"]),
        )
        payload = local_client.fetch_song_full_detail(
            song_mid=song_mid,
            fallback_song_id=int(song_brief.get("song_id") or 0),
            comment_pages=int(crawl_cfg["comment_batches"]),
            comment_page_size=int(crawl_cfg["comment_batch_size"]),
            include_latest_comments=bool(crawl_cfg["include_latest_comments"]),
            include_recent_hot_comments=bool(crawl_cfg["include_recent_hot_comments"]),
            include_highlight_comments=bool(crawl_cfg["include_highlight_comments"]),
            include_extra=bool(crawl_cfg["include_extra"]),
            include_lyric=bool(crawl_cfg["include_lyric"]),
            include_comments=bool(crawl_cfg["include_comments"]),
        )

        # 用检索列表结果补齐基础字段，避免部分接口字段缺失。
        payload["song_name"] = payload.get("song_name") or song_brief.get("song_name", "")
        payload["singer_names"] = payload.get("singer_names") or song_brief.get("singer_names", "")
        payload["album"] = payload.get("album") or song_brief.get("album", "")
        return payload

    with ThreadPoolExecutor(max_workers=int(crawl_cfg["max_workers"])) as pool:
        futures = [pool.submit(worker, s) for s in songs]
        done = 0
        for fut in as_completed(futures):
            done += 1
            try:
                payload = fut.result()
                cstats = payload.get("comment_stats", {}) or {}
                latest_comments += int(cstats.get("latest_count", 0) or 0)
                hot_comments += int(cstats.get("hot_count", 0) or 0)
                highlight_comments += int(cstats.get("highlight_count", 0) or 0)
                deduped_comments += int(cstats.get("deduped_count", 0) or 0)
                result = _save_song_and_comments(payload, db_path=str(crawl_cfg["db_path"]))
                total_song_saved += result["songs"]
                total_comment_saved += result["comments"]
                if bool(crawl_cfg.get("save_per_song_comments", True)):
                    fp = _save_song_comments_file(payload, comments_dir=str(crawl_cfg.get("comments_dir", "评论")))
                    if fp:
                        comment_files_saved += 1
            except Exception:
                failed += 1
            progress.progress(done / len(futures))

    return {
        "songs": total_song_saved,
        "comments": total_comment_saved,
        "failed": failed,
        "latest_comments": latest_comments,
        "hot_comments": hot_comments,
        "highlight_comments": highlight_comments,
        "deduped_comments": deduped_comments,
        "comment_files_saved": comment_files_saved,
    }


def _dedupe_songs(songs: List[Dict[str, Any]], mode: str) -> List[Dict[str, Any]]:
    if mode == "不去重":
        return songs

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for s in songs:
        if mode == "按歌曲MID去重":
            key = (s.get("song_mid") or "").strip()
        else:
            key = (
                (s.get("song_name") or "").strip().lower(),
                (s.get("singer_names") or "").strip().lower(),
            )

        if not key:
            deduped.append(s)
            continue
        if key in seen:
            continue
        seen.add(key)
        deduped.append(s)
    return deduped


def _enrich_singer_counts(client: QQMusicClient, singers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not singers:
        return singers

    enriched = [dict(s) for s in singers]
    missing_idx = [
        i
        for i, s in enumerate(enriched)
        if int(s.get("song_num", 0) or 0) <= 0 and (s.get("singer_mid") or "")
    ]
    if not missing_idx:
        return enriched

    # Parallelize count completion to avoid long wait on sequential network requests.
    with ThreadPoolExecutor(max_workers=min(4, len(missing_idx))) as pool:
        future_map = {
            pool.submit(client.fetch_singer_total_song, enriched[i]["singer_mid"], "listen"): i
            for i in missing_idx
        }
        for fut in as_completed(future_map):
            i = future_map[fut]
            try:
                total = int(fut.result() or 0)
                if total > 0:
                    enriched[i]["song_num"] = total
            except Exception:
                # Keep unknown when a single singer metadata request fails.
                pass

    return enriched


def _render_crawl_options(prefix: str) -> Dict[str, Any]:
    st.markdown("#### 抓取项设置")
    c1, c2, c3 = st.columns(3)
    with c1:
        include_extra = st.checkbox("抓取简介/语种/流派/公司/发行时间", value=True, key=f"{prefix}_include_extra")
    with c2:
        include_lyric = st.checkbox("抓取歌词", value=True, key=f"{prefix}_include_lyric")
    with c3:
        include_comments = st.checkbox("抓取评论", value=True, key=f"{prefix}_include_comments")

    comment_pages = 1
    comment_page_size = 20
    include_latest_comments = True
    include_recent_hot_comments = True
    include_highlight_comments = True
    if include_comments:
        st.markdown("最新评论可按滚动批次控制，热评和精彩评论可按复选框附加抓取。")
        c4, c5 = st.columns(2)
        with c4:
            include_recent_hot_comments = st.checkbox(
                "附加抓取近期热评",
                value=True,
                key=f"{prefix}_include_recent_hot_comments",
            )
        with c5:
            include_highlight_comments = st.checkbox(
                "附加抓取精彩评论",
                value=True,
                key=f"{prefix}_include_highlight_comments",
            )

        c6, c7 = st.columns(2)
        with c6:
            comment_pages = st.number_input(
                "加载批次",
                min_value=1,
                max_value=10,
                value=2,
                step=1,
                key=f"{prefix}_comment_pages",
            )
        with c7:
            comment_page_size = st.number_input(
                "每批条数",
                min_value=10,
                max_value=50,
                value=20,
                step=5,
                key=f"{prefix}_comment_page_size",
            )

        include_latest_comments = st.checkbox(
            "抓取最新评论（滚动加载）",
            value=True,
            key=f"{prefix}_include_latest_comments",
        )

        if not (include_latest_comments or include_recent_hot_comments or include_highlight_comments):
            st.warning("你已勾选“抓取评论”但未选择任何评论子类型，默认将仅抓取最新评论。")
            include_latest_comments = True

    with st.expander("可选高级设置（稳定性/速度）", expanded=False):
        a1, a2, a3 = st.columns(3)
        with a1:
            max_workers = st.number_input(
                "并发线程数",
                min_value=1,
                max_value=16,
                value=4,
                step=1,
                key=f"{prefix}_max_workers",
            )
        with a2:
            timeout = st.number_input(
                "请求超时(秒)",
                min_value=5,
                max_value=60,
                value=15,
                step=1,
                key=f"{prefix}_timeout",
            )
        with a3:
            max_retries = st.number_input(
                "最大重试次数",
                min_value=1,
                max_value=8,
                value=3,
                step=1,
                key=f"{prefix}_max_retries",
            )

        b1, b2 = st.columns(2)
        with b1:
            retry_backoff = st.number_input(
                "重试退避系数",
                min_value=0.5,
                max_value=5.0,
                value=1.2,
                step=0.1,
                key=f"{prefix}_retry_backoff",
            )
        with b2:
            min_delay = st.number_input(
                "随机延时最小值(秒)",
                min_value=0.0,
                max_value=3.0,
                value=0.2,
                step=0.1,
                key=f"{prefix}_min_delay",
            )

        max_delay = st.number_input(
            "随机延时最大值(秒)",
            min_value=0.0,
            max_value=5.0,
            value=0.8,
            step=0.1,
            key=f"{prefix}_max_delay",
        )

    if max_delay < min_delay:
        min_delay, max_delay = max_delay, min_delay

    return {
        "include_extra": include_extra,
        "include_lyric": include_lyric,
        "include_comments": include_comments,
        "include_latest_comments": include_latest_comments,
        "include_recent_hot_comments": include_recent_hot_comments,
        "include_highlight_comments": include_highlight_comments,
        "comment_batches": int(comment_pages),
        "comment_batch_size": int(comment_page_size),
        "max_workers": int(max_workers),
        "timeout": int(timeout),
        "max_retries": int(max_retries),
        "retry_backoff": float(retry_backoff),
        "min_delay": float(min_delay),
        "max_delay": float(max_delay),
    }


def singer_mode(client: QQMusicClient, db_path: str, save_dir: str, table_file_stem: str) -> None:
    st.subheader("按歌手检索并爬取")

    st.markdown("#### 1) 先检索歌手")
    singer_keyword = st.text_input("输入歌手名关键词", placeholder="例如：周杰伦")

    if st.button("1) 检索歌手", type="primary", key="btn_search_singer"):
        if not singer_keyword.strip():
            st.warning("请先输入歌手关键词。")
        else:
            with st.spinner("正在检索歌手..."):
                smartbox_payload = client.smartbox_search(singer_keyword.strip())
                singers = smartbox_payload.get("singers", [])
                preview_songs = smartbox_payload.get("songs", [])
            if singers:
                with st.spinner("正在补全候选歌手曲目数..."):
                    singers = _enrich_singer_counts(client, singers)
            st.session_state["singer_candidates"] = singers
            st.session_state["singer_preview_songs"] = preview_songs
            st.session_state["singer_song_candidates"] = []

    singers: List[Dict] = st.session_state.get("singer_candidates", [])
    preview_songs: List[Dict] = st.session_state.get("singer_preview_songs", [])

    if "singer_candidates" in st.session_state:
        if singers:
            st.success(f"已检索到 {len(singers)} 位歌手候选。")
        else:
            st.warning("未检索到歌手候选，请更换关键词（如更短的歌手名）。")

    if preview_songs:
        st.markdown("#### 检索预览：相关歌曲")
        preview_df = pd.DataFrame(preview_songs)
        show_cols = [c for c in ["song_name", "singer_names", "album", "song_mid"] if c in preview_df.columns]
        st.dataframe(preview_df[show_cols], use_container_width=True, hide_index=True)

    if singers:
        st.markdown("#### 2) 选择歌手并获取其歌曲列表")
        options = {
            f"{i + 1}. {x['singer_name']} (曲目数: {x.get('song_num', 0) if int(x.get('song_num', 0) or 0) > 0 else '未知'})": x
            for i, x in enumerate(singers)
        }
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            selected_key = st.selectbox("选择目标歌手", list(options.keys()))
        with c2:
            list_size = st.number_input("先拉取多少首供选择", min_value=10, max_value=1000, value=200, step=10)
        with c3:
            order = st.selectbox("列表排序", options=["按播放热度", "按发布时间"], index=0)

        if st.button("2) 获取该歌手歌曲列表", key="btn_fetch_singer_song_list"):
            selected = options[selected_key]
            singer_mid = selected["singer_mid"]
            with st.spinner("正在获取该歌手歌曲列表..."):
                singer_payload = client.fetch_singer_song_list(
                    singer_mid=singer_mid,
                    limit=int(list_size),
                    order=order,
                )
                songs = singer_payload.get("songs", [])
                total_song = int(singer_payload.get("total_song") or 0)
            st.session_state["singer_song_candidates"] = songs
            st.session_state["singer_total_song"] = total_song
            if total_song > 0:
                current_singers = st.session_state.get("singer_candidates", [])
                updated_singers = []
                for it in current_singers:
                    row = dict(it)
                    if row.get("singer_mid") == singer_mid:
                        row["song_num"] = total_song
                    updated_singers.append(row)
                st.session_state["singer_candidates"] = updated_singers
            if songs:
                if total_song > 0:
                    st.success(
                        f"该歌手总曲目约 {total_song} 首，本次请求 {int(list_size)} 首，实际拉取到 {len(songs)} 首。"
                    )
                else:
                    st.success(f"已获取到 {len(songs)} 首歌曲，可继续选择抓取。")
            else:
                st.warning("该歌手歌曲列表为空，请尝试切换排序或重新检索。")

    song_candidates: List[Dict[str, Any]] = st.session_state.get("singer_song_candidates", [])
    if song_candidates:
        st.markdown("#### 3) 选择要爬取的歌曲与字段")
        dedupe_mode = st.radio(
            "重复歌曲处理",
            options=["不去重", "按歌曲MID去重", "按歌名+歌手去重"],
            index=1,
            horizontal=True,
        )
        filtered_candidates = _dedupe_songs(song_candidates, dedupe_mode)

        if len(filtered_candidates) != len(song_candidates):
            st.info(f"去重后：{len(song_candidates)} -> {len(filtered_candidates)} 首。")

        songs_df = pd.DataFrame(filtered_candidates)
        if not songs_df.empty:
            st.dataframe(
                songs_df[["song_name", "singer_names", "album", "song_mid"]],
                use_container_width=True,
                hide_index=True,
            )

        pick_mode = st.radio("歌曲选择方式", options=["抓取前N首", "手动勾选歌曲"], index=0, horizontal=True)
        selected_songs: List[Dict[str, Any]] = []
        if pick_mode == "抓取前N首":
            top_n = st.number_input(
                "抓取前 N 首",
                min_value=1,
                max_value=len(filtered_candidates),
                value=min(20, len(filtered_candidates)),
                step=1,
            )
            selected_songs = filtered_candidates[: int(top_n)]
        else:
            labels = [
                f"{i + 1}. {x.get('song_name', '')} - {x.get('singer_names', '')} ({x.get('album', '')})"
                for i, x in enumerate(filtered_candidates)
            ]
            chosen = st.multiselect("手动选择歌曲", labels)
            selected_songs = [filtered_candidates[labels.index(x)] for x in chosen]

        crawl_cfg = _render_crawl_options(prefix="singer")
        crawl_cfg["db_path"] = db_path
        crawl_cfg["comments_dir"] = str(Path(save_dir) / "评论")
        crawl_cfg["save_per_song_comments"] = True

        if st.button("4) 开始爬取", type="primary", key="btn_crawl_singer_songs"):
            if not selected_songs:
                st.warning("请先选择至少 1 首歌。")
                return

            with st.spinner("正在并发抓取歌曲详情与评论..."):
                stats = _crawl_songs_parallel(
                    songs=selected_songs,
                    crawl_cfg=crawl_cfg,
                )

            st.success(
                f"完成：保存歌曲 {stats['songs']} 首，评论 {stats['comments']} 条，失败 {stats['failed']} 首。"
            )
            st.info(
                "评论来源统计："
                f"最新评论条数 {stats['latest_comments']}，"
                f"热评条数 {stats['hot_comments']}，"
                f"精彩评论条数 {stats['highlight_comments']}，"
                f"去重后最终条数 {stats['deduped_comments']}。"
            )
            st.info(f"每首歌评论文件已保存 {stats['comment_files_saved']} 个，目录：{Path(save_dir) / '评论'}")
            with st.spinner("正在自动导出总表到保存目录..."):
                paths = _auto_export_db_tables(db_path=db_path, save_dir=save_dir, table_file_stem=table_file_stem)
            st.success(
                "总表已自动保存："
                f"songs_csv={paths['songs_csv']}；"
                f"comments_csv={paths['comments_csv']}；"
                f"excel={paths['excel']}"
            )


def song_mode(client: QQMusicClient, db_path: str, save_dir: str, table_file_stem: str) -> None:
    st.subheader("按歌名检索并爬取")

    song_keyword = st.text_input("输入歌名关键词", placeholder="例如：晴天")

    if st.button("1) 检索歌曲", type="primary", key="btn_search_song"):
        if not song_keyword.strip():
            st.warning("请先输入歌名关键词。")
        else:
            with st.spinner("正在检索歌曲..."):
                songs = client.search_songs(song_keyword.strip(), page=1, size=30)
            st.session_state["song_candidates"] = songs

    songs: List[Dict] = st.session_state.get("song_candidates", [])
    if "song_candidates" in st.session_state:
        if songs:
            st.success(f"已检索到 {len(songs)} 首候选歌曲。")
        else:
            st.warning("未检索到歌曲，请尝试更换关键词。")

    if songs:
        songs_df = pd.DataFrame(songs)
        st.dataframe(
            songs_df[["song_name", "singer_names", "album", "song_mid"]],
            use_container_width=True,
            hide_index=True,
        )

        display = [
            f"{i + 1}. {x.get('song_name', '')} - {x.get('singer_names', '')} ({x.get('album', '')})"
            for i, x in enumerate(songs)
        ]
        selected_labels = st.multiselect("选择要抓取的歌曲", display)
        crawl_cfg = _render_crawl_options(prefix="song")
        crawl_cfg["db_path"] = db_path
        crawl_cfg["comments_dir"] = str(Path(save_dir) / "评论")
        crawl_cfg["save_per_song_comments"] = True

        if st.button("2) 抓取所选歌曲详情", key="btn_crawl_selected_songs"):
            picked = [songs[display.index(x)] for x in selected_labels]
            if not picked:
                st.warning("请至少选择 1 首歌。")
                return

            with st.spinner("正在并发抓取所选歌曲详情与评论..."):
                stats = _crawl_songs_parallel(
                    songs=picked,
                    crawl_cfg=crawl_cfg,
                )

            st.success(
                f"完成：保存歌曲 {stats['songs']} 首，评论 {stats['comments']} 条，失败 {stats['failed']} 首。"
            )
            st.info(
                "评论来源统计："
                f"最新评论条数 {stats['latest_comments']}，"
                f"热评条数 {stats['hot_comments']}，"
                f"精彩评论条数 {stats['highlight_comments']}，"
                f"去重后最终条数 {stats['deduped_comments']}。"
            )
            st.info(f"每首歌评论文件已保存 {stats['comment_files_saved']} 个，目录：{Path(save_dir) / '评论'}")
            with st.spinner("正在自动导出总表到保存目录..."):
                paths = _auto_export_db_tables(db_path=db_path, save_dir=save_dir, table_file_stem=table_file_stem)
            st.success(
                "总表已自动保存："
                f"songs_csv={paths['songs_csv']}；"
                f"comments_csv={paths['comments_csv']}；"
                f"excel={paths['excel']}"
            )


def data_view_mode(db_path: str, save_dir: str, table_file_stem: str) -> None:
    st.subheader("本地数据查看与导出")
    st.caption(f"当前读取数据库：{db_path}")

    cfix1, cfix2 = st.columns([1, 2])
    with cfix1:
        if st.button("尝试修复当前数据库乱码", key="btn_fix_mojibake"):
            with st.spinner("正在修复乱码..."):
                stats = _repair_db_mojibake(db_path)
            st.success(
                f"修复完成：songs 更新 {stats['songs_updated']} 行，comments 更新 {stats['comments_updated']} 行。"
            )
    with cfix2:
        st.caption("仅修复明显乱码文本，不会删除原有记录。")

    c1, c2 = st.columns(2)
    with c1:
        song_limit = st.number_input("歌曲显示条数", min_value=10, max_value=2000, value=200, step=10)
    with c2:
        comment_limit = st.number_input("评论显示条数", min_value=10, max_value=5000, value=500, step=10)

    c3, c4 = st.columns(2)
    with c3:
        min_likes = st.number_input("评论最少点赞数", min_value=0, max_value=1000000, value=0, step=1)
    with c4:
        like_order = st.selectbox("评论点赞排序", options=["点赞数降序", "点赞数升序"], index=0)

    songs_df = _songs_to_df(fetch_songs(int(song_limit), db_path=db_path))
    comments_df = _comments_to_df(fetch_comments(int(comment_limit), db_path=db_path))

    if not comments_df.empty and "likes" in comments_df.columns:
        comments_df["likes"] = pd.to_numeric(comments_df["likes"], errors="coerce").fillna(0).astype(int)
        comments_df = comments_df[comments_df["likes"] >= int(min_likes)]
        comments_df = comments_df.sort_values(
            by="likes",
            ascending=(like_order == "点赞数升序"),
        )

    tab1, tab2 = st.tabs(["歌曲主表 songs", "评论明细表 comments"])

    with tab1:
        _display_song_table(songs_df)
        if not songs_df.empty:
            st.download_button(
                label="下载 songs.csv",
                data=songs_df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"{table_file_stem}_songs.csv",
                mime="text/csv",
            )

    with tab2:
        _display_comment_table(comments_df)
        if not comments_df.empty:
            st.download_button(
                label="下载 comments.csv",
                data=comments_df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"{table_file_stem}_comments.csv",
                mime="text/csv",
            )

    if not songs_df.empty or not comments_df.empty:
        excel_bytes = _to_excel_bytes(songs_df=songs_df, comments_df=comments_df)
        st.download_button(
            label="一键导出 Excel（多 sheet）",
            data=excel_bytes,
            file_name=f"{table_file_stem}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        if st.button("保存当前表格到本地目录", key="btn_save_tables_to_dir"):
            paths = _save_tables_to_dir(
                songs_df=songs_df,
                comments_df=comments_df,
                save_dir=save_dir,
                table_file_stem=table_file_stem,
            )
            st.success(
                "保存完成："
                f"songs_csv={paths['songs_csv']}；"
                f"comments_csv={paths['comments_csv']}；"
                f"excel={paths['excel']}"
            )


def main() -> None:
    st.sidebar.subheader("保存设置")
    save_dir_input = st.sidebar.text_input("数据保存目录", value="data")
    db_filename = st.sidebar.text_input("数据库文件名", value="qq_music_data.db")
    table_file_stem = st.sidebar.text_input("表格文件名（不含扩展名）", value="qq_music_export")

    save_dir = Path(save_dir_input.strip() or "data")
    if not save_dir.is_absolute():
        save_dir = Path.cwd() / save_dir
    save_dir.mkdir(parents=True, exist_ok=True)

    db_path = str(save_dir / (db_filename.strip() or "qq_music_data.db"))
    table_file_stem = (table_file_stem.strip() or "qq_music_export").replace(".xlsx", "")
    init_db(db_path=db_path)

    client = get_client()

    st.title("QQ 音乐检索与爬取实验平台")
    st.caption("先检索，再选择歌曲与抓取项；支持分表存储、筛选排序和 Excel 导出。")
    st.caption(f"当前保存路径：{db_path}")

    mode = st.sidebar.radio(
        "功能菜单",
        options=["按歌手爬取", "按歌名爬取", "查看本地数据"],
        index=0,
    )

    if mode == "按歌手爬取":
        singer_mode(client, db_path=db_path, save_dir=str(save_dir), table_file_stem=table_file_stem)
    elif mode == "按歌名爬取":
        song_mode(client, db_path=db_path, save_dir=str(save_dir), table_file_stem=table_file_stem)
    else:
        data_view_mode(db_path=db_path, save_dir=str(save_dir), table_file_stem=table_file_stem)


if __name__ == "__main__":
    main()
