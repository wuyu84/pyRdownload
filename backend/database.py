"""SQLite 数据库管理"""
import sqlite3
import threading
from pathlib import Path
from loguru import logger
from backend.config import INDEX_DB_PATH, REPOSITORY_DIR


class DatabaseManager:
    """数据库管理器（线程安全）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._local = threading.local()
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(INDEX_DB_PATH))
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _init_database(self):
        """初始化数据库表结构"""
        # 确保目录存在
        REPOSITORY_DIR.mkdir(parents=True, exist_ok=True)
        (REPOSITORY_DIR / "python").mkdir(exist_ok=True)
        (REPOSITORY_DIR / "r").mkdir(exist_ok=True)
        (REPOSITORY_DIR / "runtimes").mkdir(exist_ok=True)
        (REPOSITORY_DIR / "exports").mkdir(exist_ok=True)

        conn = self._get_connection()
        cursor = conn.cursor()

        # 包文件索引表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS package_index (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                version     TEXT NOT NULL,
                lang        TEXT NOT NULL,
                platform    TEXT NOT NULL,
                python_ver  TEXT,
                source      TEXT NOT NULL DEFAULT 'pypi',
                source_url  TEXT,
                filename    TEXT NOT NULL,
                filepath    TEXT NOT NULL,
                file_size   INTEGER,
                sha256      TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, version, lang, platform, python_ver, source)
            )
        """)

        # 运行时索引表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runtime_index (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                lang        TEXT NOT NULL,
                version     TEXT NOT NULL,
                arch        TEXT NOT NULL DEFAULT 'amd64',
                filename    TEXT NOT NULL,
                filepath    TEXT NOT NULL,
                file_size   INTEGER,
                sha256      TEXT,
                download_url TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(lang, version, arch)
            )
        """)

        # 任务表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id              TEXT PRIMARY KEY,
                lang            TEXT NOT NULL,
                source          TEXT NOT NULL DEFAULT 'pypi',
                package_name    TEXT NOT NULL,
                package_version TEXT,
                python_ver      TEXT,
                r_ver           TEXT,
                status          TEXT NOT NULL,
                total_pkgs      INTEGER DEFAULT 0,
                cached_pkgs     INTEGER DEFAULT 0,
                downloaded_pkgs INTEGER DEFAULT 0,
                failed_pkgs     INTEGER DEFAULT 0,
                file_size       INTEGER DEFAULT 0,
                export_path     TEXT,
                client_ip       TEXT NOT NULL,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                finished_at     DATETIME
            )
        """)

        # 任务-包关联表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_packages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id         TEXT NOT NULL REFERENCES tasks(id),
                pkg_name        TEXT NOT NULL,
                pkg_version     TEXT NOT NULL,
                lang            TEXT NOT NULL,
                source          TEXT NOT NULL DEFAULT 'pypi',
                status          TEXT NOT NULL,
                is_cached       BOOLEAN DEFAULT 0,
                error_msg       TEXT,
                friendly_error  TEXT,
                file_path       TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)

        # 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pkg_name ON package_index(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pkg_name_ver ON package_index(name, version)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pkg_lang ON package_index(lang)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_pkg ON tasks(package_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_ip ON tasks(client_ip)")

        conn.commit()
        logger.info("数据库初始化完成: {}", INDEX_DB_PATH)

        # 兼容性升级：添加 api_cache 表（如不存在）
        self._upgrade_schema()

    def _upgrade_schema(self):
        """数据库 schema 兼容性升级"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_cache (
                cache_key    TEXT PRIMARY KEY,
                url          TEXT NOT NULL,
                response     TEXT NOT NULL,
                content_type TEXT DEFAULT 'json',
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at   DATETIME
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_cache_expires ON api_cache(expires_at)")
        conn.commit()

    def execute(self, sql: str, params=None) -> sqlite3.Cursor:
        """执行 SQL"""
        conn = self._get_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        conn.commit()
        return cursor

    def fetchone(self, sql: str, params=None) -> dict | None:
        """查询单条记录"""
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetchall(self, sql: str, params=None) -> list[dict]:
        """查询多条记录"""
        cursor = self.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def close(self):
        """关闭连接"""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# 全局单例
db = DatabaseManager()
