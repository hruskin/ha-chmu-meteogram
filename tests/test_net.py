"""Testy limitu na velikost stahovaných dat."""
import pytest

from chmu_meteogram.net import MAX_DOWNLOAD_BYTES, ResponseTooLarge, read_limited


class _FakeContent:
    def __init__(self, chunks):
        self._chunks = chunks

    async def iter_chunked(self, _size):
        for chunk in self._chunks:
            yield chunk


class _FakeResponse:
    """Napodobuje jen to, co read_limited potřebuje."""

    url = "https://example.test/data"

    def __init__(self, chunks, declared=None):
        self.content = _FakeContent(chunks)
        self.content_length = declared


@pytest.mark.asyncio
async def test_reads_whole_body_across_chunks():
    resp = _FakeResponse([b"abc", b"def", b"gh"])
    assert await read_limited(resp) == b"abcdefgh"


@pytest.mark.asyncio
async def test_rejects_body_over_limit():
    resp = _FakeResponse([b"x" * 60, b"x" * 60])
    with pytest.raises(ResponseTooLarge):
        await read_limited(resp, max_bytes=100)


@pytest.mark.asyncio
async def test_rejects_early_on_declared_length():
    """Když server rovnou hlásí obří délku, nečteme vůbec."""
    resp = _FakeResponse([b"x"], declared=10_000_000)
    with pytest.raises(ResponseTooLarge):
        await read_limited(resp, max_bytes=1000)


@pytest.mark.asyncio
async def test_lying_declared_length_still_caught():
    """Deklarace může lhát — rozhoduje skutečně přečtený objem."""
    resp = _FakeResponse([b"x" * 500] * 10, declared=10)
    with pytest.raises(ResponseTooLarge):
        await read_limited(resp, max_bytes=1000)


@pytest.mark.asyncio
async def test_limit_allows_real_payloads():
    """Největší reálný soubor (alerts.json ~110 kB) musí projít."""
    resp = _FakeResponse([b"y" * 65536] * 3)
    assert len(await read_limited(resp)) == 3 * 65536
    assert MAX_DOWNLOAD_BYTES >= 1024 * 1024
