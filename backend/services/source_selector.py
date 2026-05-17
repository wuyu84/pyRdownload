"""源选择引擎（多来源优选 + 来源标签管理）"""
from backend.config import SOURCES


class SourceSelector:
    """源选择引擎"""

    @staticmethod
    def get_available_sources(lang: str) -> list[str]:
        """获取某语言的可用来源"""
        return SOURCES.get(lang, ["pypi"])

    @staticmethod
    def get_preferred_source(lang: str) -> str:
        """获取首选源"""
        sources = SOURCES.get(lang, [])
        if lang == "python":
            return "pypi"
        elif lang == "r":
            return "cran"
        return sources[0] if sources else "pypi"

    @staticmethod
    def get_source_label(source: str) -> str:
        """获取来源标签"""
        labels = {
            "pypi": "PyPI官方",
            "cran": "CRAN官方",
            "bioconductor": "Bioconductor",
            "github": "GitHub Releases",
        }
        return labels.get(source, source)

    @staticmethod
    def get_source_warning(source: str) -> str:
        """获取来源警告"""
        warnings = {
            "github": "非官方源，依赖树可能不完整",
            "bioconductor": "",
            "pypi": "",
            "cran": "",
        }
        return warnings.get(source, "")

    @staticmethod
    def search_all_sources(
        query: str, lang: str, sources: list[str] | None = None
    ) -> list[dict]:
        """多来源搜索"""
        from backend.services.python_resolver import PythonResolver
        from backend.services.r_resolver import RResolver
        from backend.services.github_resolver import GitHubResolver

        if sources is None:
            sources = SourceSelector.get_available_sources(lang)

        results = []

        for source in sources:
            if source == "pypi":
                pkg_list = PythonResolver.search_pypi(query)
                for pkg in pkg_list:
                    pkg["label"] = SourceSelector.get_source_label("pypi")
                results.extend(pkg_list)
            elif source == "cran":
                pkg_list = RResolver.search_cran(query)
                for pkg in pkg_list:
                    pkg["label"] = SourceSelector.get_source_label("cran")
                results.extend(pkg_list)
            elif source == "bioconductor":
                pkg_list = RResolver.search_bioconductor(query)
                for pkg in pkg_list:
                    pkg["label"] = SourceSelector.get_source_label("bioconductor")
                results.extend(pkg_list)
            elif source == "github":
                gh_results = GitHubResolver.search_releases(query, lang)
                for pkg in gh_results:
                    pkg["label"] = SourceSelector.get_source_label("github")
                results.extend(gh_results)

        return results
