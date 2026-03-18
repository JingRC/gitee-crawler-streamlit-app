import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Iterable, Dict, Any, List


DB_PATH = "qq_music_data.db"


def get_conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    with closing(get_conn(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_mid TEXT NOT NULL UNIQUE,
                song_id INTEGER,
                song_name TEXT,
                singer_names TEXT,
                album TEXT,
                language TEXT,
                genre TEXT,
                company TEXT,
                publish_time TEXT,
                intro TEXT,
                lyric TEXT,
                comment_count INTEGER,
                crawled_at TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_mid TEXT NOT NULL,
                comment_id TEXT,
                user_name TEXT,
                content TEXT,
                likes INTEGER,
                comment_time TEXT,
                location TEXT,
                crawled_at TEXT,
                UNIQUE(song_mid, comment_id)
            )
            """
        )

        conn.commit()


def upsert_song(song: Dict[str, Any], db_path: str = DB_PATH) -> None:
    song = dict(song)
    song.setdefault("crawled_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    with closing(get_conn(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO songs (
                song_mid, song_id, song_name, singer_names, album,
                language, genre, company, publish_time, intro, lyric,
                comment_count, crawled_at
            )
            VALUES (
                :song_mid, :song_id, :song_name, :singer_names, :album,
                :language, :genre, :company, :publish_time, :intro, :lyric,
                :comment_count, :crawled_at
            )
            ON CONFLICT(song_mid) DO UPDATE SET
                song_id=excluded.song_id,
                song_name=excluded.song_name,
                singer_names=excluded.singer_names,
                album=excluded.album,
                language=excluded.language,
                genre=excluded.genre,
                company=excluded.company,
                publish_time=excluded.publish_time,
                intro=excluded.intro,
                lyric=excluded.lyric,
                comment_count=excluded.comment_count,
                crawled_at=excluded.crawled_at
            """,
            song,
        )
        conn.commit()


def upsert_comments(song_mid: str, comments: Iterable[Dict[str, Any]], db_path: str = DB_PATH) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for c in comments:
        rows.append(
            {
                "song_mid": song_mid,
                "comment_id": str(c.get("comment_id", "")),
                "user_name": c.get("user_name", ""),
                "content": c.get("content", ""),
                "likes": int(c.get("likes", 0) or 0),
                "comment_time": c.get("comment_time", ""),
                "location": c.get("location", ""),
                "crawled_at": now,
            }
        )

    if not rows:
        return 0

    with closing(get_conn(db_path)) as conn:
        conn.executemany(
            """
            INSERT INTO comments (
                song_mid, comment_id, user_name, content,
                likes, comment_time, location, crawled_at
            )
            VALUES (
                :song_mid, :comment_id, :user_name, :content,
                :likes, :comment_time, :location, :crawled_at
            )
            ON CONFLICT(song_mid, comment_id) DO UPDATE SET
                user_name=excluded.user_name,
                content=excluded.content,
                likes=excluded.likes,
                comment_time=excluded.comment_time,
                location=excluded.location,
                crawled_at=excluded.crawled_at
            """,
            rows,
        )
        conn.commit()

    return len(rows)


def fetch_songs(limit: int = 200, db_path: str = DB_PATH) -> List[sqlite3.Row]:
    with closing(get_conn(db_path)) as conn:
        cur = conn.execute(
            """
            SELECT * FROM songs
            ORDER BY datetime(crawled_at) DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()


def fetch_comments(limit: int = 500, db_path: str = DB_PATH) -> List[sqlite3.Row]:
    with closing(get_conn(db_path)) as conn:
        cur = conn.execute(
            """
            SELECT * FROM comments
            ORDER BY datetime(crawled_at) DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()
