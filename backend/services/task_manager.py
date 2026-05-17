"""任务管理（含IP记录 + 来源记录）"""
import uuid
from datetime import datetime
from typing import Optional
from loguru import logger
from backend.database import db
from backend.services.error_analyzer import ErrorAnalyzer


class TaskManager:
    """任务管理器"""

    @staticmethod
    def create_task(
        lang: str,
        package_name: str,
        source: str,
        client_ip: str,
        package_version: Optional[str] = None,
        python_ver: Optional[str] = None,
        r_ver: Optional[str] = None,
    ) -> str:
        """创建任务"""
        task_id = f"T{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"

        db.execute(
            """
            INSERT INTO tasks (id, lang, source, package_name, package_version,
                               python_ver, r_ver, status, client_ip)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (task_id, lang, source, package_name, package_version,
             python_ver, r_ver, client_ip),
        )
        logger.info("创建任务: {} {} {} {}", task_id, package_name, source, lang)
        return task_id

    @staticmethod
    def update_task_status(task_id: str, status: str):
        """更新任务状态"""
        db.execute(
            "UPDATE tasks SET status = ? WHERE id = ?",
            (status, task_id),
        )

    @staticmethod
    def add_task_package(
        task_id: str,
        pkg_name: str,
        pkg_version: str,
        lang: str,
        source: str,
        status: str = "pending",
        is_cached: bool = False,
        error_msg: Optional[str] = None,
        file_path: Optional[str] = None,
    ):
        """添加任务包记录"""
        friendly_error = None
        if error_msg:
            analysis = ErrorAnalyzer.analyze(error_msg)
            friendly_error = analysis["friendly_error"]

        db.execute(
            """
            INSERT INTO task_packages
                (task_id, pkg_name, pkg_version, lang, source, status,
                 is_cached, error_msg, friendly_error, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, pkg_name, pkg_version, lang, source, status,
             is_cached, error_msg, friendly_error, file_path),
        )

    @staticmethod
    def update_task_package_status(
        task_id: str,
        pkg_name: str,
        status: str,
        error_msg: Optional[str] = None,
        file_path: Optional[str] = None,
    ):
        """更新任务包状态"""
        updates = ["status = ?"]
        params = [status]

        if error_msg:
            analysis = ErrorAnalyzer.analyze(error_msg)
            updates.append("error_msg = ?")
            params.append(error_msg)
            updates.append("friendly_error = ?")
            params.append(analysis["friendly_error"])
        if file_path:
            updates.append("file_path = ?")
            params.append(file_path)

        params.extend([task_id, pkg_name])
        db.execute(
            f"UPDATE task_packages SET {', '.join(updates)} WHERE task_id = ? AND pkg_name = ?",
            params,
        )

    @staticmethod
    def update_task_counts(task_id: str):
        """更新任务计数"""
        stats = db.fetchone(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_cached = 1 THEN 1 ELSE 0 END) as cached,
                SUM(CASE WHEN status = 'downloaded' AND is_cached = 0 THEN 1 ELSE 0 END) as downloaded,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM task_packages WHERE task_id = ?
            """,
            (task_id,),
        )
        if stats:
            db.execute(
                "UPDATE tasks SET total_pkgs=?, cached_pkgs=?, downloaded_pkgs=?, failed_pkgs=? WHERE id=?",
                (stats["total"], stats["cached"], stats["downloaded"], stats["failed"], task_id),
            )

    @staticmethod
    def get_task(task_id: str) -> dict | None:
        """获取任务信息"""
        task = db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if not task:
            return None

        packages = db.fetchall(
            "SELECT * FROM task_packages WHERE task_id = ? ORDER BY id",
            (task_id,),
        )
        task["packages"] = packages
        return task

    @staticmethod
    def get_task_list(
        lang: str = "",
        status: str = "",
        search: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取任务列表"""
        conditions = []
        params = []

        if lang:
            conditions.append("lang = ?")
            params.append(lang)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if search:
            conditions.append("(package_name LIKE ? OR id LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # 总数
        count_sql = f"SELECT COUNT(*) as total FROM tasks {where}"
        total = db.fetchone(count_sql, params)["total"]

        # 分页
        offset = (page - 1) * page_size
        sql = f"SELECT * FROM tasks {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        tasks = db.fetchall(sql, params + [page_size, offset])

        return {"tasks": tasks, "total": total}

    @staticmethod
    def search_tasks(
        query: str,
        lang: str = "",
        source: str = "",
    ) -> list[dict]:
        """搜索历史任务"""
        conditions = ["(package_name LIKE ? OR package_version LIKE ? OR id LIKE ?)"]
        params = [f"%{query}%", f"%{query}%", f"%{query}%"]

        if lang:
            conditions.append("lang = ?")
            params.append(lang)
        if source:
            conditions.append("source = ?")
            params.append(source)

        sql = f"SELECT * FROM tasks WHERE {' AND '.join(conditions)} ORDER BY created_at DESC LIMIT 20"
        return db.fetchall(sql, params)

    @staticmethod
    def delete_task(task_id: str):
        """删除任务记录"""
        db.execute("DELETE FROM task_packages WHERE task_id = ?", (task_id,))
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
