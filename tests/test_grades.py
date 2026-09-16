import json

import pytest


def test_load_config_reads_file(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "ns_login": "test",
        "ns_password": "pass",
        "ns_school": "School",
        "max_bot_token": "token123"
    }), encoding='utf-8')

    from grades import load_config
    result = load_config(str(config_path))

    assert result["ns_login"] == "test"
    assert result["max_bot_token"] == "token123"