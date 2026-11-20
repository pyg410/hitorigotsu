from pathlib import Path

import pytest

from hitorigotsu.cache import Cache
from hitorigotsu.downloader import download


def test_failed_download_never_published(tmp_path, monkeypatch):
    import yt_dlp

    import hitorigotsu.downloader as module

    monkeypatch.setattr(module, "require_ffmpeg", lambda: None)

    class FailedDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def extract_info(self, *_args, **_kwargs):
            Path(self.options["outtmpl"].replace("%(ext)s", "part")).write_bytes(b"partial")
            raise yt_dlp.utils.DownloadError("network unavailable")

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FailedDL)
    cache = Cache(tmp_path)
    with pytest.raises(ValueError, match="download failed"):
        download("https://youtu.be/BaW_jenozKc", cache)
    assert cache.get("BaW_jenozKc") is None
    assert list(tmp_path.iterdir()) == []


def test_publish_and_offline_reuse(tmp_path, monkeypatch):
    import yt_dlp

    import hitorigotsu.cache as cache_module
    import hitorigotsu.decoder as decoder
    import hitorigotsu.downloader as module
    from hitorigotsu.source import resolve_source

    monkeypatch.setattr(module, "require_ffmpeg", lambda: None)
    monkeypatch.setattr(decoder, "probe", lambda _: None)
    monkeypatch.setattr(cache_module, "user_cache_path", lambda _: tmp_path)

    class SuccessfulDL:
        def __init__(self, options):
            assert options["format"] == "bv[height<=480]+ba/b[height<=480]"
            assert options["noplaylist"]
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def extract_info(self, *_args, **_kwargs):
            Path(self.options["outtmpl"].replace("%(ext)s", "mkv")).write_bytes(b"merged")
            return {"title": "generated test"}

    monkeypatch.setattr(yt_dlp, "YoutubeDL", SuccessfulDL)
    url = "https://youtu.be/BaW_jenozKc"
    path = download(url, Cache(tmp_path))
    assert path.read_bytes() == b"merged"

    def no_network(*_args, **_kwargs):
        raise AssertionError("cache hit must not contact network")

    monkeypatch.setattr(module, "download", no_network)
    assert resolve_source(url, offline=True) == path
    path.write_bytes(b"broken")
    with pytest.raises(ValueError, match="No valid cached"):
        resolve_source(url, offline=True)
