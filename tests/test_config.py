from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import assume
from hypothesis import strategies as st

from lora_forge.config import GENERIC_CLASS_WORDS, ProjectConfig


def make_config(**overrides):
    data = {
        "project_name": "demo",
        "trigger_token": "dawivre",
        "class_token": "woman",
        "source_folder": "/tmp/images",
    }
    data.update(overrides)
    return ProjectConfig(**data)


def test_caption_prefix():
    config = make_config(trigger_token="abc123", class_token="person")
    assert config.caption_prefix == "abc123 person,"


def test_config_round_trip_json():
    config = make_config()
    parsed = ProjectConfig.model_validate_json(config.to_json_text())
    assert parsed == config


@pytest.mark.parametrize("bad_trigger", ["", "two words", "bad/token", "woman", "photo"])
def test_bad_trigger_tokens_are_rejected(bad_trigger):
    with pytest.raises(ValueError):
        make_config(trigger_token=bad_trigger)


def test_trigger_and_class_must_differ():
    with pytest.raises(ValueError):
        make_config(trigger_token="dawivre", class_token="dawivre")


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=3, max_size=12))
def test_valid_trigger_tokens_round_trip(token):
    assume(token not in GENERIC_CLASS_WORDS)
    config = make_config(trigger_token=token)
    parsed = ProjectConfig.model_validate_json(config.to_json_text())
    assert parsed.trigger_token == token
