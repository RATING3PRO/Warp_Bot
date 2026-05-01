from __future__ import annotations

import json

import pytest

from warp import WarpRegistrationError, build_warp_config_bundle, render_wireguard_config, render_xray_config


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
            "client_id": "AQID",
        }
    }

    config = render_wireguard_config("private-key", registration)

    assert "PrivateKey = private-key" in config
    assert "Address = 172.16.0.2/32, 2606:4700:110:8abc:1111:2222:3333:4444/128" in config
    assert "PublicKey = peer-public-key" in config
    assert "Endpoint = engage.cloudflareclient.com:2408" in config


def test_render_xray_config() -> None:
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
                    "endpoint": {"host": "engage.cloudflareclient.com"},
                }
            ],
            "client_id": "AQID",
        }
    }

    config = json.loads(render_xray_config("private-key", registration))

    assert config["inbounds"][0]["protocol"] == "socks"
    assert config["inbounds"][0]["port"] == 10808
    assert config["inbounds"][1]["protocol"] == "http"
    assert config["inbounds"][1]["port"] == 10809
    assert config["outbounds"][0]["protocol"] == "wireguard"
    assert config["outbounds"][0]["settings"]["secretKey"] == "private-key"
    assert config["outbounds"][0]["settings"]["reserved"] == [1, 2, 3]
    assert config["outbounds"][0]["settings"]["address"] == [
        "172.16.0.2/32",
        "2606:4700:110:8abc:1111:2222:3333:4444/128",
    ]
    assert config["outbounds"][0]["settings"]["peers"][0]["endpoint"] == "engage.cloudflareclient.com:2408"


def test_build_warp_config_bundle_uses_same_registration() -> None:
    registration = {
        "id": "test-device",
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
                    "endpoint": {"host": "engage.cloudflareclient.com"},
                }
            ],
            "client_id": "AQID",
        },
    }

    bundle = build_warp_config_bundle("private-key", registration)
    xray_config = json.loads(bundle.xray.config)

    assert bundle.device_id == "test-device"
    assert bundle.wireguard.filename == "warp_test-device.conf"
    assert bundle.xray.filename == "warp_test-device.json"
    assert "PrivateKey = private-key" in bundle.wireguard.config
    assert xray_config["outbounds"][0]["settings"]["secretKey"] == "private-key"


def test_render_wireguard_config_requires_peer() -> None:
    registration = {
        "config": {
            "interface": {"addresses": {"v4": "172.16.0.2", "v6": "2606:4700:110::1"}},
            "peers": [],
        }
    }

    with pytest.raises(WarpRegistrationError):
        render_wireguard_config("private-key", registration)
