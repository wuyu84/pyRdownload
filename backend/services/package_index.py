"""包索引引擎（比对 + 复用 + SHA256校验）"""
import hashlib
from pathlib import Path
from typing import Optional
from loguru import logger
from backend.database import db
from backend.config import PYTHON_DIR, R_DIR, REPOSITORY_DIR


class PackageIndex:
    """包索引引擎"""

    @staticmethod
    def compute_sha256(filepath: str) -> str:
        """计算文件 SHA256"""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def add_package(
        name: str,
        version: str,
        lang: str,
        platform: str,
        filename: str,
        filepath: str,
        source: str = "pypi",
        source_url: str = "",
        python_ver: str = "",
        file_size: int = 0,
        sha256: str = "",
    ) -> bool:
        """添加包到索引"""
        try:
            if not sha256 and Path(filepath).exists():
                sha256 = PackageIndex.compute_sha256(filepath)
            if not file_size and Path(filepath).exists():
                file_size = Path(filepath).stat().st_size

            db.execute(
                """
                INSERT OR IGNORE INTO package_index
                    (name, version, lang, platform, python_ver, source, source_url,
                     filename, filepath, file_size, sha256)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, version, lang, platform, python_ver, source, source_url,
                 filename, filepath, file_size, sha256),
            )
            return True
        except Exception as e:
            logger.error("添加包索引失败: {} {} {}", name, version, e)
            return False

    @staticmethod
    def find_package(
        name: str,
        version: str,
        lang: str,
        platform: str = "",
        python_ver: str = "",
        source: str = "",
    ) -> dict | None:
        """查找包是否在仓库中"""
        conditions = ["name = ?", "version = ?", "lang = ?"]
        params = [name, version, lang]

        if platform:
            conditions.append("platform = ?")
            params.append(platform)
        if python_ver:
            conditions.append("python_ver = ?")
            params.append(python_ver)
        if source:
            conditions.append("source = ?")
            params.append(source)

        sql = f"SELECT * FROM package_index WHERE {' AND '.join(conditions)}"
        return db.fetchone(sql, params)

    @staticmethod
    def batch_check(
        packages: list[dict],
    ) -> dict[str, dict]:
        """批量比对，返回 {pkg_key: {exists: bool, record: dict}}"""
        result = {}
        for pkg in packages:
            key = f"{pkg['name']}-{pkg.get('version', '')}"
            record = PackageIndex.find_package(
                name=pkg["name"],
                version=pkg.get("version", ""),
                lang=pkg.get("lang", "python"),
                source=pkg.get("source", ""),
                python_ver=pkg.get("python_ver", ""),
            )
            if record and Path(record["filepath"]).exists():
                # 验证 SHA256
                if record["sha256"]:
                    current_sha = PackageIndex.compute_sha256(record["filepath"])
                    if current_sha == record["sha256"]:
                        result[key] = {"exists": True, "record": record}
                    else:
                        result[key] = {"exists": False, "record": None, "reason": "hash_mismatch"}
                else:
                    result[key] = {"exists": True, "record": record}
            else:
                result[key] = {"exists": False, "record": None}
        return result

    @staticmethod
    def get_runtime_info(lang: str, version: str) -> dict | None:
        """获取运行时信息"""
        return db.fetchone(
            "SELECT * FROM runtime_index WHERE lang = ? AND version = ?",
            (lang, version),
        )

    @staticmethod
    def get_all_runtimes() -> list[dict]:
        """获取所有运行时"""
        return db.fetchall("SELECT * FROM runtime_index ORDER BY lang, version")

    @staticmethod
    def get_stats() -> dict:
        """获取仓库统计"""
        py_count = db.fetchone(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(file_size), 0) as size FROM package_index WHERE lang = 'python'"
        )
        r_count = db.fetchone(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(file_size), 0) as size FROM package_index WHERE lang = 'r'"
        )
        runtime_count = db.fetchone("SELECT COUNT(*) as cnt FROM runtime_index")
        active_tasks = db.fetchone(
            "SELECT COUNT(*) as cnt FROM tasks WHERE status IN ('pending', 'downloading', 'packaging')"
        )

        return {
            "python_pkgs": py_count["cnt"] if py_count else 0,
            "python_size": py_count["size"] if py_count else 0,
            "r_pkgs": r_count["cnt"] if r_count else 0,
            "r_size": r_count["size"] if r_count else 0,
            "runtimes_count": runtime_count["cnt"] if runtime_count else 0,
            "active_tasks": active_tasks["cnt"] if active_tasks else 0,
            "total_size": (py_count["size"] if py_count else 0) + (r_count["size"] if r_count else 0),
        }

    @staticmethod
    def detect_platform(filename: str) -> str:
        """检测平台"""
        if filename.endswith("win_amd64.whl"):
            return "win_amd64"
        elif filename.endswith("win32.whl"):
            return "win32"
        elif filename.endswith("any.whl") or filename.endswith("none-any.whl"):
            return "none_any"
        elif filename.endswith(".zip"):
            return "win_binary"
        elif filename.endswith(".tar.gz"):
            return "source"
        return "unknown"

    @staticmethod
    def verify_file_integrity(filepath: str, expected_sha256: str) -> bool:
        """验证文件完整性"""
        try:
            if not Path(filepath).exists():
                return False
            current_sha = PackageIndex.compute_sha256(filepath)
            return current_sha == expected_sha256
        except Exception as e:
            logger.error("文件完整性校验失败: {} {}", filepath, e)
            return False
