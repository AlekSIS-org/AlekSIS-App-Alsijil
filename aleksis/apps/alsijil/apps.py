from aleksis.core.util.apps import AppConfig


class AlsijilConfig(AppConfig):
    name = "aleksis.apps.alsijil"
    verbose_name = "AlekSIS — Alsijil (Class register)"

    urls = {
        "Repository": "https://edugit.org/AlekSIS/official/AlekSIS-App-Alsijil/",
    }
    licence = "EUPL-1.2+"
    copyright_info = (
        ([2019, 2020], "Tom Teichler", "tom.teichler@teckids.org"),
        ([2019], "Dominik George", "dominik.george@teckids.org"),
        ([2019], "mirabilos", "thorsten.glaser@teckids.org"),
        ([2020], "Julian Leucker", "leuckeju@katharineum.de"),
        ([2020], "Jonathan Weth", "wethjo@katharineum.de"),
        ([2020], "Hangzhi Yu", "yuha@katharineum.de"),
    )
