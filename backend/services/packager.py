"""打包 + 生成 .bat + 可选附带运行时"""
import json
import os
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger
from backend.config import EXPORT_DIR, REPOSITORY_DIR, RUNTIMES_DIR
from backend.database import db


class Packager:
    """打包管理器"""

    @staticmethod
    def generate_checksums(package_dir: Path) -> dict:
        """生成校验文件"""
        import hashlib

        checksums = {}
        for f in package_dir.iterdir():
            if f.is_file():
                sha256 = hashlib.sha256()
                with open(f, "rb") as fh:
                    for chunk in iter(lambda: fh.read(65536), b""):
                        sha256.update(chunk)
                checksums[f.name] = sha256.hexdigest()
        return checksums

    @staticmethod
    def generate_python_bat(package_names: list[str], runtime_name: str = "") -> str:
        """生成 install_python.bat"""
        pkg_list = " ".join(package_names)
        runtime_block = ""
        if runtime_name:
            runtime_block = f"""set RUNTIME_FILE={runtime_name}
if not exist \".\\\runtime\\%RUNTIME_FILE%\" (
    echo [INFO] Runtime installer not found, skip runtime installation
) else (
    echo [INFO] Runtime installer found: .\\\runtime\\%RUNTIME_FILE%
)
"""

        return f"""@echo off
chcp 65001 >nul
:: ============================================
:: Python Package Offline Installer - Auto-generated
:: Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
:: ============================================

:: 1. Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Python not found! Please install Python first.
    echo Runtime installer located in .\\\runtime\ folder
{runtime_block}    echo Then re-run this script.
    pause
    exit /b 1
)

:: 2. Check Python version compatibility
python -c "import sys; ver=sys.version_info; exit(0 if ver.major==3 and ver.minor>=8 else 1)"
if %errorlevel% neq 0 (
    echo [WARNING] Python version too old (need ^>= 3.8). Please upgrade.
    pause
    exit /b 1
)

:: 3. Verify package file integrity
echo Verifying package integrity...
python -c "import hashlib, json; f=open('./packages/checksums.json', encoding='utf-8-sig'); d=json.load(f); ok=True
for fn,sha in d.items(): h=hashlib.sha256(open(f'./packages/{fn}','rb').read()).hexdigest(); print(f'  {fn}: {"OK" if h==sha else "FAIL"}'); ok=ok and (h==sha)
exit(0 if ok else 1)"
if %errorlevel% neq 0 (
    echo [ERROR] Checksum verification failed! Some packages may be corrupted.
    echo Please re-download from the server.
    pause
    exit /b 1
)

:: 4. Offline install
echo Installing packages...
pip install --no-index --find-links=.\\\packages {pkg_list}
if %errorlevel% equ 0 (
    echo All packages installed successfully!
) else (
    echo Some packages failed to install. Please check the error messages.
)

:: 5. Verify installation
python -c "import {package_names[0] if package_names else ''}; print('Main package installed successfully!')" 2>nul || echo Verification skipped.
echo.
echo Installation complete! Press any key to exit...
pause
"""

    @staticmethod
    def _convert_r_zip_to_tar_gz(zip_path: Path) -> Path | None:
        """将 R Windows binary (.zip) 转换为 .tar.gz 格式（适配 RStudio）"""
        import tempfile
        import shutil

        try:
            # 在临时目录中解压 .zip
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(tmp_path)

                # 确定输出文件名（.zip → .tar.gz）
                tar_gz_name = zip_path.name.removesuffix(".zip") + ".tar.gz"
                tar_gz_path = zip_path.with_name(tar_gz_name)

                # 创建 .tar.gz
                with tarfile.open(tar_gz_path, "w:gz") as tar:
                    for item in tmp_path.iterdir():
                        if item.is_dir():
                            tar.add(item, arcname=item.name)

                # 删除原 .zip
                zip_path.unlink()
                logger.info("R 包已转换为 .tar.gz: {} → {}", zip_path.name, tar_gz_name)
                return tar_gz_path

        except Exception as e:
            logger.error("R 包 .zip→.tar.gz 转换失败: {} {}", zip_path, e)
            return None

    @staticmethod
    def generate_r_bat(package_files: list[str], has_rtools: bool = False) -> str:
        """生成 install_r.bat（所有包均为 .tar.gz 格式）"""
        pkg_install = " ".join(
            f'.\\packages\\{f}' for f in package_files
        )

        rtools_block = ""
        if has_rtools:
            rtools_block = """
:: 3. Install Rtools silently if bundled
if exist .\\\runtime\\\rtools*.exe (
    echo Installing Rtools silently...
    .\\\runtime\\\rtools*.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
    if %errorlevel% neq 0 (
        echo [WARNING] Rtools installation failed. Please install manually.
    ) else (
        echo Rtools installed successfully.
    )
)
"""

        return f"""@echo off
chcp 65001 >nul
:: ============================================
:: R Package Offline Installer - Auto-generated
:: Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
:: ============================================

:: 1. Check if R is installed
Rscript --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] R not found! Please install R first.
    echo Runtime installer located in .\\\runtime\ folder
    echo Run the installer manually, then re-run this script.
    pause
    exit /b 1
)

:: 2. Get R library path
for /f "tokens=*" %%i in ('Rscript -e "cat(.libPaths()[1])"') do set R_LIB=%%i
echo R library path: %R_LIB%{rtools_block}

:: 4. Install packages (all .tar.gz format, RStudio compatible)
echo Installing R packages...
R CMD INSTALL --library="%R_LIB%" {pkg_install}

:: 5. Verify installation
echo.
echo Verifying installation...
Rscript -e "cat('Installation verified!')"
if %errorlevel% equ 0 (
    echo All packages installed successfully!
) else (
    echo Some packages failed to install. Please check the error messages.
)
echo.
echo Installation complete! Press any key to exit...
pause
"""

    @staticmethod
    def _convert_r_packages_in_dir(packages_dir: Path, package_files: list[str]) -> list[str]:
        """将 packages_dir 中所有 R 的 .zip 包转换为 .tar.gz，并返回更新后的文件名列表"""
        updated_files = []
        for pf in package_files:
            if pf.endswith(".tar.gz"):
                # 源码包保持原样
                updated_files.append(pf)
            elif pf.endswith(".zip"):
                # binary 包需要转换
                zip_path = packages_dir / pf
                if zip_path.exists():
                    tar_gz_path = Packager._convert_r_zip_to_tar_gz(zip_path)
                    if tar_gz_path:
                        updated_files.append(tar_gz_path.name)
                    else:
                        # 转换失败，保持原样
                        updated_files.append(pf)
                else:
                    updated_files.append(pf)
            else:
                updated_files.append(pf)
        return updated_files

    @staticmethod
    def create_package(
        task_id: str,
        packages: list[dict],
        source: str,
        lang: str,
        include_runtime: bool = False,
        runtime_info: dict | None = None,
        python_ver: str = "",
        has_rtools: bool = False,
    ) -> tuple[bool, str]:
        """
        创建打包文件
        返回: (成功?, 文件路径)
        """
        export_dir = EXPORT_DIR / task_id
        packages_dir = export_dir / "packages"
        runtime_dir = export_dir / "runtime"

        export_dir.mkdir(parents=True, exist_ok=True)
        packages_dir.mkdir(exist_ok=True)
        if include_runtime:
            runtime_dir.mkdir(exist_ok=True)

        try:
            # 复制包文件
            package_names = []
            package_files = []
            for pkg in packages:
                file_path = pkg.get("file_path", "")
                if file_path and Path(file_path).exists():
                    dest = packages_dir / Path(file_path).name
                    # 硬链接或复制
                    try:
                        import shutil
                        if not dest.exists():
                            shutil.copy2(file_path, dest)
                    except Exception as e:
                        logger.warning("复制包文件失败: {} {}", file_path, e)
                    if lang == "python":
                        package_names.append(pkg["pkg_name"])
                    package_files.append(Path(file_path).name)

            # 复制运行时
            if include_runtime and runtime_info:
                rt_path = runtime_info.get("filepath", "")
                if rt_path and Path(rt_path).exists():
                    import shutil
                    shutil.copy2(rt_path, runtime_dir / Path(rt_path).name)

            # R 包：将 .zip binary 转换为 .tar.gz（适配 RStudio 本地安装）
            # 注意：必须在 checksums.json 生成之前执行
            if lang == "r":
                package_files = Packager._convert_r_packages_in_dir(packages_dir, package_files)

            # 生成 checksums.json（在文件转换完成后，确保校验和准确）
            checksums = Packager.generate_checksums(packages_dir)
            with open(packages_dir / "checksums.json", "w", encoding="utf-8-sig") as f:
                json.dump(checksums, f, ensure_ascii=False, indent=2)

            # 生成安装脚本
            if lang == "python":
                bat_content = Packager.generate_python_bat(
                    package_names,
                    runtime_info.get("filename", "") if runtime_info else "",
                )
                with open(export_dir / "install_python.bat", "w", encoding="utf-8-sig") as f:
                    f.write(bat_content)
            elif lang == "r":
                bat_content = Packager.generate_r_bat(package_files, has_rtools)
                with open(export_dir / "install_r.bat", "w", encoding="utf-8-sig") as f:
                    f.write(bat_content)

            # 打包为 zip
            zip_name = f"{task_id}_{lang}_{source}.zip"
            zip_path = str(EXPORT_DIR / zip_name)

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for item in export_dir.rglob("*"):
                    if item.is_file():
                        arcname = str(item.relative_to(export_dir))
                        zf.write(item, arcname)

            # 清理临时目录
            import shutil
            shutil.rmtree(export_dir, ignore_errors=True)

            logger.info("打包完成: {}", zip_path)

            # 更新任务记录
            zip_size = Path(zip_path).stat().st_size
            db.execute(
                "UPDATE tasks SET status = 'done', export_path = ?, file_size = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
                (zip_path, zip_size, task_id),
            )

            return True, zip_path

        except Exception as e:
            logger.error("打包失败: {} {}", task_id, e)
            db.execute(
                "UPDATE tasks SET status = 'failed' WHERE id = ?",
                (task_id,),
            )
            return False, str(e)
