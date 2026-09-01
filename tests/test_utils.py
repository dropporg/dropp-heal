import json
import logging

from pydantic import BaseModel

from api.utils.jsonify import MESSAGE_CODES, NOT_FOUND, NOT_IMPLEMENTED, OK, Jsonify
from api.utils.logging import JSONFormatter
from api.utils.network import is_allowed_target, is_private_address


class Sample(BaseModel):
    id: int


def body(response: Jsonify) -> dict:
    return json.loads(response.body)


def test_envelope_wraps_a_model():
    payload = body(Jsonify(result=Sample(id=1)))
    assert payload["result"] == {"id": 1}
    assert payload["status"] == {"code": OK, "message": "OK"}
    assert payload["_metadata"] == ""


def test_envelope_wraps_a_list_and_carries_metadata():
    payload = body(Jsonify(result=[Sample(id=1), Sample(id=2)], metadata="page 1"))
    assert len(payload["result"]) == 2
    assert payload["_metadata"] == "page 1"


def test_application_code_maps_to_http_status():
    assert Jsonify(code=NOT_FOUND).status_code == 404
    assert Jsonify(code=NOT_IMPLEMENTED).status_code == 501


def test_http_status_can_be_overridden():
    response = Jsonify(code=NOT_FOUND, http_status=200)
    assert response.status_code == 200
    assert body(response)["status"]["code"] == NOT_FOUND


def test_every_code_has_a_message():
    assert all(
        isinstance(message, str) and message for message in MESSAGE_CODES.values()
    )


def test_private_and_metadata_addresses_are_detected():
    assert is_private_address("127.0.0.1")
    assert is_private_address("10.1.2.3")
    assert is_private_address("169.254.169.254")
    assert not is_private_address("8.8.8.8")


def test_localhost_is_blocked_unless_explicitly_allowed():
    allowed, reason = is_allowed_target("localhost", allow_private=False)
    assert allowed is False and reason
    assert is_allowed_target("localhost", allow_private=True)[0] is True


def test_json_formatter_keeps_context_and_redacts_secrets():
    record = logging.LogRecord(
        "heal", logging.INFO, __file__, 1, "check complete", (), None
    )
    record.fqdn = "arvancloud.ir"
    record.password = "hunter2"
    payload = json.loads(JSONFormatter().format(record))
    assert payload["fqdn"] == "arvancloud.ir"
    assert payload["password"] == "***"
    assert payload["message"] == "check complete"


def test_cors_origins_accept_a_comma_separated_list(monkeypatch):
    """ConfigMaps hold plain strings, so the env value must not need JSON."""
    from api.config.settings import Settings

    monkeypatch.setenv("HEAL_API_CORS_ORIGINS", "http://a.test, http://b.test")
    assert Settings().cors_origins == ["http://a.test", "http://b.test"]


def test_cors_is_disabled_by_default(monkeypatch):
    from api.config.settings import Settings

    monkeypatch.delenv("HEAL_API_CORS_ORIGINS", raising=False)
    assert Settings(_env_file=None).cors_origins == []
