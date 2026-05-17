"""错误分析器（智能中文提示）"""
import re


class ErrorAnalyzer:
    """错误分析器"""

    ERROR_PATTERNS = {
        "404": {
            "message": "包不存在或版本号有误",
            "suggestion": "请检查包名和版本号是否正确，或尝试搜索最新版本",
        },
        "Timeout": {
            "message": "网络连接超时",
            "suggestion": "请检查镜像源配置或稍后重试",
        },
        "SSL": {
            "message": "安全连接失败",
            "suggestion": "请检查网络环境，或尝试更换镜像源",
        },
        "RateLimit": {
            "message": "GitHub API 请求频率超限",
            "suggestion": "请稍后重试，或在服务器配置 GITHUB_TOKEN 提升限制",
        },
        "NoWinWheel": {
            "message": "该包没有 Windows 版本",
            "suggestion": "该包可能仅支持 Linux/macOS，或仅提供源码需要自行编译",
        },
        "HashMismatch": {
            "message": "文件校验失败，可能下载不完整",
            "suggestion": "请重新下载该包",
        },
        "Conflict": {
            "message": "依赖版本冲突",
            "suggestion": "建议使用最新版本或指定兼容版本",
        },
        "DiskFull": {
            "message": "服务器磁盘空间不足",
            "suggestion": "请联系管理员清理仓库空间",
        },
        "GitHubSrcErr": {
            "message": "GitHub 来源的包依赖树可能不完整",
            "suggestion": "建议切换为官方源以获得更完整的依赖树",
        },
        "RuntimeNotFound": {
            "message": "运行时安装包未预置",
            "suggestion": "请联系管理员预下载对应版本的运行时安装包",
        },
        "NoBinaryOrSource": {
            "message": "无法找到该包的下载链接",
            "suggestion": "该包可能已从源中移除，请尝试其他版本或来源",
        },
        "HTTP 403": {
            "message": "访问被拒绝",
            "suggestion": "GitHub API 可能触发了频率限制，请稍后重试或配置 GITHUB_TOKEN",
        },
        "HTTP 500": {
            "message": "服务器内部错误",
            "suggestion": "包源服务器暂时出现问题，请稍后重试",
        },
    }

    @staticmethod
    def analyze(error_msg: str) -> dict:
        """分析错误，返回中文提示和建议"""
        if not error_msg:
            return {
                "friendly_error": "",
                "suggestion": "",
            }

        for pattern, info in ErrorAnalyzer.ERROR_PATTERNS.items():
            if pattern.lower() in error_msg.lower():
                return {
                    "friendly_error": info["message"],
                    "suggestion": info["suggestion"],
                }

        # 通用错误处理
        if "Connection" in error_msg or "connect" in error_msg:
            return {
                "friendly_error": "网络连接失败",
                "suggestion": "请检查服务器网络连接和镜像源配置",
            }

        if "certificate" in error_msg.lower() or "verify" in error_msg.lower():
            return {
                "friendly_error": "SSL 证书验证失败",
                "suggestion": "请检查服务器时间是否正确，或尝试使用 HTTP 镜像源",
            }

        if "no space" in error_msg.lower() or "disk" in error_msg.lower():
            return {
                "friendly_error": "磁盘空间不足",
                "suggestion": "请联系管理员清理仓库空间",
            }

        if "not found" in error_msg.lower() or "no such" in error_msg.lower():
            return {
                "friendly_error": "资源未找到",
                "suggestion": "请检查包名和版本号是否正确",
            }

        # 默认
        return {
            "friendly_error": f"下载失败：{error_msg[:100]}",
            "suggestion": "请检查网络连接、包名和版本后重试，如问题持续请联系管理员",
        }
