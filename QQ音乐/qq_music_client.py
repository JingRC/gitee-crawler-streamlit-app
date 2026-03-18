import json
import random
import re
import time
from datetime import datetime
from typing import Any, Dict, List

import requests


class QQMusicClient:
    def __init__(
        self,
        timeout: int = 15,
        max_retries: int = 3,
        retry_backoff: float = 1.2,
        min_delay: float = 0.2,
        max_delay: float = 0.8,
    ):
        self.timeout = timeout
        self.max_retries = max(1, int(max_retries))
        self.retry_backoff = max(0.0, float(retry_backoff))
        self.min_delay = max(0.0, float(min_delay))
        self.max_delay = max(self.min_delay, float(max_delay))
        self.session = requests.Session()
        self.session.headers.update(
            {
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "referer": "https://y.qq.com/",
                "origin": "https://y.qq.com",
            }
        )

    def _sleep_jitter(self, attempt: int) -> None:
        base = random.uniform(self.min_delay, self.max_delay)
        backoff = self.retry_backoff * max(0, attempt - 1)
        time.sleep(base + backoff)

    @staticmethod
    def _count_cjk(text: str) -> int:
        return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")

    @staticmethod
    def _looks_mojibake(text: str) -> bool:
        if not text:
            return False
        bad_tokens = ["锟斤拷", "Ã", "Â", "æ", "ç", "¤", "�", "浣", "鎴", "鐨"]
        return any(tok in text for tok in bad_tokens)

    def _repair_text(self, text: str) -> str:
        if not isinstance(text, str) or not text:
            return text

        source = text
        candidates = [source]
        transforms = [
            ("latin1", "utf-8"),
            ("latin1", "gb18030"),
            ("gb18030", "utf-8"),
            ("cp1252", "utf-8"),
        ]
        for enc_a, enc_b in transforms:
            try:
                candidates.append(source.encode(enc_a, errors="ignore").decode(enc_b, errors="ignore"))
            except Exception:
                continue

        def score(s: str) -> tuple[int, int]:
            # Prefer text with more Chinese chars and fewer mojibake hints.
            cjk = self._count_cjk(s)
            bad = 1 if self._looks_mojibake(s) else 0
            return (cjk, -bad)

        best = max(candidates, key=score)
        if score(best) > score(source):
            return best
        return source

    def _normalize_fields(self, item: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
        out = dict(item)
        for k in keys:
            if isinstance(out.get(k), str):
                out[k] = self._repair_text(out[k])
        return out

    @staticmethod
    def _decode_bytes(data: bytes) -> str:
        for enc in ("utf-8", "gb18030", "gbk"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    def _request_text(
        self,
        url: str,
        params: Dict[str, Any] | None = None,
        method: str = "GET",
        json_payload: Dict[str, Any] | None = None,
    ) -> str:
        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self._sleep_jitter(attempt)
                if method.upper() == "POST":
                    body = json.dumps(json_payload or {}, ensure_ascii=False).encode("utf-8")
                    resp = self.session.post(
                        url,
                        data=body,
                        timeout=self.timeout,
                        headers={"content-type": "application/json"},
                    )
                else:
                    resp = self.session.get(url, params=params or {}, timeout=self.timeout)
                resp.raise_for_status()
                return self._decode_bytes(resp.content)
            except requests.RequestException as exc:
                last_err = exc
                if attempt == self.max_retries:
                    break

        if last_err is not None:
            raise last_err
        raise RuntimeError("请求失败")

    def _safe_get_json(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        text = self._request_text(url, params).strip()

        # Handle jsonp fallback.
        if text.startswith("callback") or text.startswith("MusicJsonCallback"):
            m = re.search(r"^[^(]*\((.*)\)\s*;?$", text, re.S)
            if m:
                text = m.group(1)

        return json.loads(text)

    def _safe_post_musicu(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        text = self._request_text(
            url="https://u.y.qq.com/cgi-bin/musicu.fcg",
            method="POST",
            json_payload=payload,
        ).strip()
        return json.loads(text)

    def smartbox_search(self, keyword: str) -> Dict[str, List[Dict[str, Any]]]:
        url = "https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg"
        params = {
            "is_xml": "0",
            "format": "json",
            "inCharset": "utf8",
            "outCharset": "utf-8",
            "key": keyword,
        }
        data = self._safe_get_json(url, params)
        block = data.get("data", {})
        singer_items = block.get("singer", {}).get("itemlist", []) or []
        song_items = block.get("song", {}).get("itemlist", []) or []

        singers: List[Dict[str, Any]] = []
        for item in singer_items:
            singers.append(self._normalize_fields(
                {
                    "singer_mid": item.get("mid") or "",
                    "singer_id": item.get("id") or "",
                    "singer_name": item.get("name") or "",
                    "song_num": item.get("singer_num") or 0,
                },
                ["singer_name"],
            ))

        songs: List[Dict[str, Any]] = []
        for item in song_items:
            songs.append(self._normalize_fields(
                {
                    "song_mid": item.get("mid") or "",
                    "song_id": int(item.get("id") or 0),
                    "song_name": item.get("name") or "",
                    "singer_names": item.get("singer") or "",
                    "album": item.get("album") or "",
                },
                ["song_name", "singer_names", "album"],
            ))

        return {"singers": singers, "songs": songs}

    def search_singers(self, keyword: str, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
        payload = self.smartbox_search(keyword)
        singer_list = payload.get("singers", [])
        result = []
        start = max(0, (page - 1) * size)
        end = start + size
        for item in singer_list[start:end]:
            result.append(
                {
                    "singer_mid": item.get("singer_mid") or "",
                    "singer_id": item.get("singer_id") or "",
                    "singer_name": item.get("singer_name") or "",
                    "song_num": item.get("song_num") or 0,
                }
            )
        return result

    def search_songs(self, keyword: str, page: int = 1, size: int = 20) -> List[Dict[str, Any]]:
        payload = self.smartbox_search(keyword)
        song_list = payload.get("songs", [])
        result = []
        start = max(0, (page - 1) * size)
        end = start + size
        for item in song_list[start:end]:
            result.append(
                {
                    "song_mid": item.get("song_mid") or "",
                    "song_id": int(item.get("song_id") or 0),
                    "song_name": item.get("song_name") or "",
                    "singer_names": item.get("singer_names") or "",
                    "album": item.get("album") or "",
                }
            )
        return result

    def _fetch_singer_song_page(
        self,
        singer_mid: str,
        sin: int,
        num: int,
        order: str = "listen",
    ) -> Dict[str, Any]:
        sort_map = {
            "listen": 5,
            "time": 1,
        }
        sort_code = sort_map.get(order, 5)
        payload = {
            "comm": {"ct": 24, "cv": 0},
            "singer": {
                "module": "music.web_singer_info_svr",
                "method": "get_singer_detail_info",
                "param": {
                    "sort": sort_code,
                    "singermid": singer_mid,
                    "sin": int(sin),
                    "num": int(num),
                },
            },
        }
        data = self._safe_post_musicu(payload)
        singer_data = data.get("singer", {}).get("data", {})
        tracks = singer_data.get("songlist", []) or []

        result = []
        for music in tracks:
            singers = music.get("singer", []) or []
            singer_names = "/".join(x.get("name", "") for x in singers if x.get("name"))
            result.append(self._normalize_fields(
                {
                    "song_mid": music.get("mid") or "",
                    "song_id": int(music.get("id") or 0),
                    "song_name": music.get("name") or music.get("title") or "",
                    "singer_names": singer_names,
                    "album": (music.get("album") or {}).get("name", ""),
                },
                ["song_name", "singer_names", "album"],
            ))

        return {
            "songs": result,
            "total_song": int(singer_data.get("total_song") or 0),
            "singer_name": (singer_data.get("singer_info") or {}).get("name", ""),
        }

    def fetch_singer_song_list(self, singer_mid: str, limit: int = 20, order: str = "listen") -> Dict[str, Any]:
        # singer detail endpoint single-page often returns up to ~60 songs, so use pagination.
        target = max(1, int(limit))
        page_cap = 60
        sin = 0
        all_songs: List[Dict[str, Any]] = []
        total_song = 0
        singer_name = ""
        loop_guard = 0

        while len(all_songs) < target and loop_guard < 200:
            loop_guard += 1
            num = min(page_cap, target - len(all_songs))
            page = self._fetch_singer_song_page(
                singer_mid=singer_mid,
                sin=sin,
                num=num,
                order=order,
            )

            page_songs = page.get("songs", [])
            total_song = int(page.get("total_song") or total_song or 0)
            singer_name = page.get("singer_name") or singer_name

            if not page_songs:
                break

            all_songs.extend(page_songs)
            sin += len(page_songs)

            if total_song > 0 and sin >= total_song:
                break

        return {
            "songs": all_songs[:target],
            "total_song": total_song,
            "singer_name": singer_name,
            "requested": target,
            "fetched": len(all_songs[:target]),
        }

    def fetch_singer_total_song(self, singer_mid: str, order: str = "listen") -> int:
        alias_map = {
            "按播放热度": "listen",
            "按发布时间": "time",
        }
        api_order = alias_map.get(order, order)
        page = self._fetch_singer_song_page(
            singer_mid=singer_mid,
            sin=0,
            num=1,
            order=api_order,
        )
        return int(page.get("total_song") or 0)

    def fetch_singer_hot_songs(self, singer_mid: str, limit: int = 20, order: str = "listen") -> List[Dict[str, Any]]:
        alias_map = {
            "按播放热度": "listen",
            "按发布时间": "time",
        }
        api_order = alias_map.get(order, order)
        payload = self.fetch_singer_song_list(singer_mid=singer_mid, limit=limit, order=api_order)
        return payload.get("songs", [])

    def fetch_song_base_detail(self, song_mid: str) -> Dict[str, Any]:
        payload = {
            "comm": {"ct": 24, "cv": 0},
            "song_detail": {
                "module": "music.pf_song_detail_svr",
                "method": "get_song_detail_yqq",
                "param": {"song_mid": song_mid},
            },
        }
        data = self._safe_post_musicu(payload)
        info = data.get("song_detail", {}).get("data", {}).get("track_info", {})
        singers = info.get("singer", []) or []
        singer_names = "/".join(x.get("name", "") for x in singers if x.get("name"))

        base = {
            "song_mid": info.get("mid") or song_mid,
            "song_id": int(info.get("id") or 0),
            "song_name": info.get("name") or "",
            "singer_names": singer_names,
            "album": (info.get("album") or {}).get("name", ""),
            "publish_time": info.get("time_public") or "",
            "language": "",
            "genre": "",
            "company": "",
            "intro": "",
        }
        return self._normalize_fields(base, ["song_name", "singer_names", "album"])

    def fetch_song_page_extra(self, song_mid: str) -> Dict[str, str]:
        # 从歌曲详情页里提取额外字段，接口变化时允许为空
        url = f"https://y.qq.com/n/ryqq/songDetail/{song_mid}"
        html = self._request_text(url, {}).strip()

        extra = {
            "language": "",
            "genre": "",
            "company": "",
            "intro": "",
            "publish_time": "",
        }

        m = re.search(r"window\.__INITIAL_DATA__\s*=\s*(\{.*?\})\s*;\s*</script>", html, re.S)
        if not m:
            return extra

        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            return extra

        # 页面结构可能调整，使用多路径兜底
        detail_candidates = [
            data.get("detail"),
            data.get("songDetail"),
            data.get("songInfo"),
            data,
        ]

        for block in detail_candidates:
            if not isinstance(block, dict):
                continue
            basic = block.get("basic_info") or block.get("basicInfo") or block
            if isinstance(basic, dict):
                extra["language"] = extra["language"] or str(
                    basic.get("lan") or basic.get("language") or ""
                )
                extra["genre"] = extra["genre"] or str(
                    basic.get("genre") or basic.get("style") or ""
                )
                extra["company"] = extra["company"] or str(
                    basic.get("company") or basic.get("label") or ""
                )
                extra["publish_time"] = extra["publish_time"] or str(
                    basic.get("time_public") or basic.get("publish_time") or ""
                )

            desc = block.get("desc") or block.get("introduction") or ""
            if isinstance(desc, str) and desc.strip():
                extra["intro"] = extra["intro"] or desc.strip()

        return extra

    def fetch_lyric(self, song_mid: str) -> str:
        url = "https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg"
        params = {
            "songmid": song_mid,
            "g_tk": "5381",
            "loginUin": "0",
            "hostUin": "0",
            "format": "json",
            "inCharset": "utf8",
            "outCharset": "utf-8",
            "notice": "0",
            "platform": "yqq.json",
            "needNewCode": "0",
            "nobase64": "1",
        }
        data = self._safe_get_json(url, params)
        lyric = data.get("lyric", "")
        return lyric if isinstance(lyric, str) else ""

    def fetch_comments(
        self,
        song_id: int,
        page_size: int = 20,
        pages: int = 1,
        mode: str = "最新评论（滚动加载）",
    ) -> Dict[str, Any]:
        # comments endpoint 对参数敏感，失败时返回空结果
        url = "https://c.y.qq.com/base/fcgi-bin/fcg_global_comment_h5.fcg"
        all_comments: List[Dict[str, Any]] = []
        total = 0

        cmd_map = {
            "最新评论（滚动加载）": "8",
            "近期热评": "6",
            "精彩评论": "6",
        }
        cmd = cmd_map.get(mode, "8")

        # cmd=6 is a fixed hot list and does not scroll by page; request once.
        max_pages = 1 if cmd == "6" else max(1, pages)
        seen_comment_ids = set()

        for p in range(max_pages):
            params = {
                "g_tk": "5381",
                "loginUin": "0",
                "hostUin": "0",
                "format": "json",
                "inCharset": "utf8",
                "outCharset": "GB2312",
                "notice": "0",
                "platform": "yqq.json",
                "needNewCode": "0",
                "cid": "205360772",
                "reqtype": "2",
                "biztype": "1",
                "topid": str(song_id),
                "cmd": cmd,
                "needmusiccrit": "0",
                "pagenum": str(p),
                "pagesize": str(page_size),
                "domain": "qq.com",
            }

            try:
                data = self._safe_get_json(url, params)
            except Exception:
                break

            comment_block = data.get("comment") or {}
            if p == 0:
                total = int(comment_block.get("commenttotal", 0) or 0)

            items = comment_block.get("commentlist") or []
            if not items:
                break

            for it in items:
                content = (
                    it.get("rootcommentcontent")
                    or it.get("middlecommentcontent")
                    or it.get("subcommentcontent")
                    or ""
                )
                nick = it.get("nick") or (it.get("userinfo") or {}).get("nick") or ""
                likes = it.get("praisenum") or it.get("praisenumnew") or 0
                ts = it.get("time") or 0
                comment_time = ""
                if isinstance(ts, int) and ts > 0:
                    comment_time = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

                location = it.get("ip_location") or it.get("location") or ""

                all_comments.append(self._normalize_fields(
                    {
                        "comment_id": str(it.get("rootcommentid") or it.get("commentid") or ""),
                        "user_name": nick,
                        "content": content,
                        "likes": int(likes or 0),
                        "comment_time": comment_time,
                        "location": location,
                        "is_hot": int(bool(it.get("is_hot") or it.get("is_hot_cmt") or it.get("is_stick"))),
                        "comment_type": mode,
                    },
                    ["user_name", "content", "location"],
                ))

        # 去重并按模式处理
        uniq_comments: List[Dict[str, Any]] = []
        for c in all_comments:
            cid = (c.get("comment_id") or "").strip()
            if cid and cid in seen_comment_ids:
                continue
            if cid:
                seen_comment_ids.add(cid)
            uniq_comments.append(c)

        if mode == "精彩评论":
            # 精彩评论优先保留热评标记或高赞评论。
            uniq_comments = [
                c for c in uniq_comments if int(c.get("is_hot", 0) or 0) == 1 or int(c.get("likes", 0) or 0) >= 50
            ]
            uniq_comments.sort(key=lambda x: int(x.get("likes", 0) or 0), reverse=True)

        if mode == "近期热评":
            uniq_comments.sort(key=lambda x: int(x.get("likes", 0) or 0), reverse=True)

        return {"total": total, "comments": uniq_comments}

    def fetch_song_full_detail(
        self,
        song_mid: str,
        fallback_song_id: int = 0,
        comment_pages: int = 1,
        comment_page_size: int = 20,
        include_latest_comments: bool = True,
        include_recent_hot_comments: bool = False,
        include_highlight_comments: bool = False,
        include_extra: bool = True,
        include_lyric: bool = True,
        include_comments: bool = True,
    ) -> Dict[str, Any]:
        base = self.fetch_song_base_detail(song_mid)
        extra = self.fetch_song_page_extra(song_mid) if include_extra else {
            "language": "",
            "genre": "",
            "company": "",
            "intro": "",
            "publish_time": "",
        }
        lyric = self.fetch_lyric(song_mid) if include_lyric else ""

        song_id = int(base.get("song_id") or 0)
        if song_id <= 0:
            song_id = int(fallback_song_id or 0)
            if song_id > 0:
                base["song_id"] = song_id
        comments_payload = {"total": 0, "comments": []}
        comment_stats = {
            "latest_count": 0,
            "hot_count": 0,
            "highlight_count": 0,
            "deduped_count": 0,
        }
        if include_comments and song_id:
            all_comments: List[Dict[str, Any]] = []
            comment_total = 0

            if include_latest_comments:
                latest_payload = self.fetch_comments(
                    song_id=song_id,
                    page_size=comment_page_size,
                    pages=comment_pages,
                    mode="最新评论（滚动加载）",
                )
                latest_comments = latest_payload.get("comments", [])
                all_comments.extend(latest_comments)
                comment_stats["latest_count"] = len(latest_comments)
                comment_total = int(latest_payload.get("total") or 0)

            if include_recent_hot_comments:
                hot_payload = self.fetch_comments(
                    song_id=song_id,
                    page_size=max(comment_page_size, 30),
                    pages=1,
                    mode="近期热评",
                )
                hot_comments = hot_payload.get("comments", [])
                all_comments.extend(hot_comments)
                comment_stats["hot_count"] = len(hot_comments)
                if comment_total <= 0:
                    comment_total = int(hot_payload.get("total") or 0)

            if include_highlight_comments:
                highlight_payload = self.fetch_comments(
                    song_id=song_id,
                    page_size=max(comment_page_size, 30),
                    pages=1,
                    mode="精彩评论",
                )
                highlight_comments = highlight_payload.get("comments", [])
                all_comments.extend(highlight_comments)
                comment_stats["highlight_count"] = len(highlight_comments)
                if comment_total <= 0:
                    comment_total = int(highlight_payload.get("total") or 0)

            # Merge by comment_id to avoid duplicates across modes.
            seen_ids = set()
            merged_comments: List[Dict[str, Any]] = []
            for c in all_comments:
                cid = (c.get("comment_id") or "").strip()
                if cid and cid in seen_ids:
                    continue
                if cid:
                    seen_ids.add(cid)
                merged_comments.append(c)
            comment_stats["deduped_count"] = len(merged_comments)

            comments_payload = {"total": comment_total, "comments": merged_comments}

        # base 字段优先，缺失时由 extra 补齐
        payload = {
            **base,
            "language": base.get("language") or extra.get("language") or "",
            "genre": base.get("genre") or extra.get("genre") or "",
            "company": base.get("company") or extra.get("company") or "",
            "publish_time": base.get("publish_time") or extra.get("publish_time") or "",
            "intro": base.get("intro") or extra.get("intro") or "",
            "lyric": lyric,
            "comment_count": int(comments_payload.get("total", 0) or 0),
            "comments": comments_payload.get("comments", []),
            "comment_stats": comment_stats,
        }
        return payload
