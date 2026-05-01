from __future__ import annotations

import pytest

from warp import WarpRegistrationError, render_wireguard_config


def test_render_wireguard_config() -> None:
    registration = {
        "config": {
            "interface": {
                "addresses": {
                    "v4": "172.16.0.2",
                    "v6": "2606:4700:110:8abc:1111:2222:3333:4444",
                }
            },
            "peers": [
                {
                    "public_key": "peer-public-key",
                    "endpoint": {"host": "engage.cloudflareclient.com:2408"},
                }
            ],
        }
    }

    config = render_wireguard_config("private-key", registration)

    assert "PrivateKey = private-key" in config
    assert "Address = 172.16.0.2/32, 2606:4700:110:8abc:1111:2222:3333:4444/128" in config
    assert "PublicKey = peer-public-key" in config
    assert "Endpoint = engage.cloudflareclient.com:2408" in config


def test_render_wireguard_config_requires_peer() -> None:
    registration = {
        "config": {
            "interface": {"addresses": {"v4": "172.16.0.2", "v6": "2606:4700:110::1"}},
            "peers": [],
        }
    }

    with pytest.raises(WarpRegistrationError):
        render_wireguard_config("private-key", registration)
