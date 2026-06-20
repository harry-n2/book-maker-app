"""ジョブ状態の永続化レイヤ（$0・有料課金なし）。

バックエンド:
  - 既定: SQLite（ローカルファイル・標準ライブラリのみ・登録不要・$0）
  - DATABASE_URL がある場合: PostgreSQL（Vercel本番の Neon 無料枠等。要 psycopg）

設計:
  - JOB_STATE を本モジュールの PersistentJobState に差し替えるだけで app.py はほぼ無改修。
  - 1ジョブ = 1行（state を JSON 文字列で保存）。プロセス再起動・サーバーレス再実行をまたいで状態が残る。
  - ★ APIキーは永続化しない（cfg.api_key を保存前に除去）。鍵は実行中プロセスのメモリにのみ保持。
    → 再起動後も status/ダウンロードは可能。生成の再開には鍵の再投入が必要（BYOKの安全側仕様）。

注意（既知の制約）:
  - サーバーレスではバックグラウンドスレッドが関数終了で破棄されるため、「状態の永続化」はできても
    「裏で生成を進め続ける」ことは別途ステップ実行化(R1後半)が必要。本モジュールはその土台。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from collections.abc import Iterator, MutableMapping
from pathlib import Path
from typing import Any

import _resource

_LOCK = threading.RLock()
# 実行中プロセスのみで鍵を保持（DB/ディスクには書かない）
_KEY_CACHE: dict[str, str] = {}


def _db_path() -> Path:
    override = os.environ.get("BOOKMAKER_DB_PATH")
    if override:
        return Path(override)
    return _resource.writable_root() / "bookmaker_state.db"


# ---------------------------------------------------------------------------
# バックエンド
# ---------------------------------------------------------------------------
class _SqliteBackend:
    def __init__(self, path: Path) -> None:
        self.path = str(path)
        with self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS jobs ("
                "job_id TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at REAL NOT NULL)"
            )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=30, check_same_thread=False)

    def load(self, job_id: str) -> dict | None:
        with _LOCK, self._conn() as c:
            row = c.execute("SELECT state FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, job_id: str, state: dict) -> None:
        payload = json.dumps(state, ensure_ascii=False, default=str)
        with _LOCK, self._conn() as c:
            c.execute(
                "INSERT INTO jobs(job_id, state, updated_at) VALUES(?,?,?) "
                "ON CONFLICT(job_id) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at",
                (job_id, payload, time.time()),
            )

    def delete(self, job_id: str) -> None:
        with _LOCK, self._conn() as c:
            c.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))

    def ids(self) -> list[str]:
        with _LOCK, self._conn() as c:
            return [r[0] for r in c.execute("SELECT job_id FROM jobs").fetchall()]


class _PostgresBackend:
    """Vercel本番の無料Postgres(Neon等)用。DATABASE_URL があるときのみ使用。

    ドライバは psycopg(v3) を遅延import。未インストール時は明示エラー（SQLiteに影響しない）。
    """

    def __init__(self, dsn: str) -> None:
        try:
            import psycopg  # type: ignore
        except ImportError as exc:  # noqa: BLE001
            raise RuntimeError(
                "DATABASE_URL が設定されていますが psycopg が未インストールです。"
                "requirements に psycopg[binary] を追加してください（無料Postgres利用時のみ）。"
            ) from exc
        self._psycopg = psycopg
        self.dsn = dsn
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS jobs ("
                    "job_id TEXT PRIMARY KEY, state JSONB NOT NULL, updated_at DOUBLE PRECISION NOT NULL)"
                )
            c.commit()

    def _conn(self):
        return self._psycopg.connect(self.dsn)

    def load(self, job_id: str) -> dict | None:
        with self._conn() as c, c.cursor() as cur:
            cur.execute("SELECT state FROM jobs WHERE job_id=%s", (job_id,))
            row = cur.fetchone()
        if not row:
            return None
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])

    def save(self, job_id: str, state: dict) -> None:
        payload = json.dumps(state, ensure_ascii=False, default=str)
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO jobs(job_id, state, updated_at) VALUES(%s, %s::jsonb, %s) "
                    "ON CONFLICT(job_id) DO UPDATE SET state=EXCLUDED.state, updated_at=EXCLUDED.updated_at",
                    (job_id, payload, time.time()),
                )
            c.commit()

    def delete(self, job_id: str) -> None:
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute("DELETE FROM jobs WHERE job_id=%s", (job_id,))
            c.commit()

    def ids(self) -> list[str]:
        with self._conn() as c, c.cursor() as cur:
            cur.execute("SELECT job_id FROM jobs")
            return [r[0] for r in cur.fetchall()]


def _make_backend():
    dsn = os.environ.get("DATABASE_URL")
    if dsn:
        return _PostgresBackend(dsn)
    return _SqliteBackend(_db_path())


# ---------------------------------------------------------------------------
# 鍵の取り扱い（DBに保存しない）
# ---------------------------------------------------------------------------
def _strip_secrets(state: dict, job_id: str) -> dict:
    """保存用にAPIキーを除去し、実行中メモリにだけ退避する。"""
    safe = dict(state)
    cfg = safe.get("cfg")
    if isinstance(cfg, dict) and cfg.get("api_key"):
        _KEY_CACHE[job_id] = cfg["api_key"]
        cfg = dict(cfg)
        cfg["api_key"] = ""
        safe["cfg"] = cfg
    return safe


def _reinject_secrets(state: dict, job_id: str) -> dict:
    key = _KEY_CACHE.get(job_id)
    if key and isinstance(state.get("cfg"), dict):
        state["cfg"]["api_key"] = key
    return state


# ---------------------------------------------------------------------------
# JOB_STATE 互換のマッピング
# ---------------------------------------------------------------------------
class _JobDict(dict):
    """get/[] で返す状態dict。.update()/[]=で全体を永続化する（書き戻し透過）。"""

    def __init__(self, owner: "PersistentJobState", job_id: str, data: dict) -> None:
        super().__init__(data)
        object.__setattr__(self, "_owner", owner)
        object.__setattr__(self, "_job_id", job_id)

    def _persist(self) -> None:
        self._owner._backend.save(self._job_id, _strip_secrets(dict(self), self._job_id))

    def __setitem__(self, k: Any, v: Any) -> None:
        super().__setitem__(k, v)
        self._persist()

    def update(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        super().update(*args, **kwargs)
        self._persist()


class PersistentJobState(MutableMapping):
    """app.py の `JOB_STATE: dict` をそのまま置き換える永続マッピング。"""

    def __init__(self) -> None:
        self._backend = _make_backend()

    def __getitem__(self, job_id: str) -> _JobDict:
        data = self._backend.load(job_id)
        if data is None:
            raise KeyError(job_id)
        return _JobDict(self, job_id, _reinject_secrets(data, job_id))

    def get(self, job_id: str, default: Any = None) -> Any:
        data = self._backend.load(job_id)
        if data is None:
            return default
        return _JobDict(self, job_id, _reinject_secrets(data, job_id))

    def __setitem__(self, job_id: str, value: dict) -> None:
        self._backend.save(job_id, _strip_secrets(dict(value), job_id))

    def __delitem__(self, job_id: str) -> None:
        self._backend.delete(job_id)
        _KEY_CACHE.pop(job_id, None)

    def __contains__(self, job_id: object) -> bool:
        return isinstance(job_id, str) and self._backend.load(job_id) is not None

    def __iter__(self) -> Iterator[str]:
        return iter(self._backend.ids())

    def __len__(self) -> int:
        return len(self._backend.ids())
