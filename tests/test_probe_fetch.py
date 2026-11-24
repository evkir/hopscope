import httpx
import pytest

from hopscope.probe.card import CardError
from hopscope.probe.fetch import MAX_CARD_BYTES, FetchError, fetch_card
from hopscope.targets import TargetRefused

URL = "http://127.0.0.1:7020/.well-known/agent-card.json"
CARD = {"name": "Orchestrator", "url": "http://127.0.0.1:7020/", "skills": []}


def mock(handler):
    return httpx.MockTransport(handler)


def test_fetches_local_card():
    card = fetch_card(URL, transport=mock(lambda r: httpx.Response(200, json=CARD)))
    assert card.name == "Orchestrator"


def test_remote_target_refused_before_any_request():
    def boom(request):
        raise AssertionError("no request may be sent")

    with pytest.raises(TargetRefused):
        fetch_card("https://agent.example.com/.well-known/agent-card.json", transport=mock(boom))


def test_redirect_is_refused_not_followed():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(301, headers={"location": "https://evil.example/card.json"})

    with pytest.raises(FetchError, match="redirect"):
        fetch_card(URL, transport=mock(handler))
    assert seen == [URL]


def test_card_advertising_remote_url_is_refused():
    poisoned = {**CARD, "supportedInterfaces": [{"url": "https://ops.evil.example/a2a"}]}
    with pytest.raises(TargetRefused):
        fetch_card(URL, transport=mock(lambda r: httpx.Response(200, json=poisoned)))


def test_allow_remote_accepts_remote_advertised_url():
    remote = {**CARD, "url": "https://agent.example.com/"}
    card = fetch_card(URL, allow_remote=True, transport=mock(lambda r: httpx.Response(200, json=remote)))
    assert card.urls == ("https://agent.example.com/",)


def test_non_200_and_oversize_and_non_json():
    with pytest.raises(FetchError, match="404"):
        fetch_card(URL, transport=mock(lambda r: httpx.Response(404)))
    with pytest.raises(FetchError, match="exceeds"):
        fetch_card(URL, transport=mock(lambda r: httpx.Response(200, content=b" " * (MAX_CARD_BYTES + 1))))
    with pytest.raises(CardError, match="JSON"):
        fetch_card(URL, transport=mock(lambda r: httpx.Response(200, content=b"<html>")))
