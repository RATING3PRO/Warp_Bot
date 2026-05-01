from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Any

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519


WARP_REGISTER_URL = "https://api.cloudflareclient.com/v0a4005/reg"
WARP_ENDPOINT_HOST = "engage.cloudflareclient.com"
WARP_ENDPOINT_PORT = 2408


class WarpRegistrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class WarpConfigResult:
    config: str
    filename: str
    device_id: str


@dataclass(frozen=True)
class WireGuardKeyPair:
    private_key: str
    public_key: str


def generate_wireguard_keypair() -> WireGuardKeyPair:
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    return WireGuardKeyPair(
        private_key=base64.b64encode(private_bytes).decode("ascii"),
        public_key=base64.b64encode(public_bytes).decode("ascii"),
    )


def _registration_payload(public_key: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    install_id = secrets.token_hex(11)

    return {
        "key": public_key,
        "install_id": install_id,
        "fcm_token": f"{install_id}:APA91b{secrets.token_urlsafe(134)}",
        "tos": now,
        "type": "Android",
        "model": "PC",
        "locale": "zh_CN",
    }


async def register_warp_device(public_key: str, timeout: float = 20) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "CF-Client-Version": "a-6.11-2223",
        "Content-Type": "application/json",
        "User-Agent": "okhttp/3.12.1",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(WARP_REGISTER_URL, headers=headers, json=_registration_payload(public_key))
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300] if exc.response is not None else str(exc)
            raise WarpRegistrationError(f"Cloudflare 返回 HTTP {exc.response.status_code}: {detail}") from exc
        except httpx.HTTPError as exc:
            detail = str(exc) or exc.__class__.__name__
            raise WarpRegistrationError(f"无法连接 Cloudflare WARP API: {detail}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise WarpRegistrationError("Cloudflare 返回了非 JSON 响应") from exc

    return data


def _normalize_address(address: str) -> str:
    parsed = ip_address(address)
    prefix = 32 if parsed.version == 4 else 128
    return f"{parsed}/{prefix}"


def _get_nested(data: dict[str, Any], *path: str) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise WarpRegistrationError(f"Cloudflare 响应缺少字段: {'.'.join(path)}")
        current = current[key]
    return current


def render_wireguard_config(private_key: str, registration: dict[str, Any]) -> str:
    interface = _get_nested(registration, "config", "interface")
    peers = _get_nested(registration, "config", "peers")
    if not isinstance(peers, list) or not peers:
        raise WarpRegistrationError("Cloudflare 响应缺少 peer 配置")

    peer = peers[0]
    if not isinstance(peer, dict):
        raise WarpRegistrationError("Cloudflare peer 配置格式异常")

    addresses = interface.get("addresses")
    if not isinstance(addresses, dict):
        raise WarpRegistrationError("Cloudflare interface addresses 格式异常")

    try:
        address_v4 = _normalize_address(addresses["v4"])
        address_v6 = _normalize_address(addresses["v6"])
        peer_public_key = str(peer["public_key"])
    except KeyError as exc:
        raise WarpRegistrationError(f"Cloudflare 响应缺少字段: {exc.args[0]}") from exc
    except ValueError as exc:
        raise WarpRegistrationError(f"Cloudflare 返回了无效 IP 地址: {exc}") from exc

    endpoint = peer.get("endpoint", {}).get("host", WARP_ENDPOINT_HOST)
    if ":" not in str(endpoint).rsplit("]", 1)[-1]:
        endpoint = f"{endpoint}:{WARP_ENDPOINT_PORT}"

    return "\n".join(
        [
            "[Interface]",
            f"PrivateKey = {private_key}",
            f"Address = {address_v4}, {address_v6}",
            "DNS = 1.1.1.1, 1.0.0.1, 2606:4700:4700::1111, 2606:4700:4700::1001",
            "MTU = 1280",
            "",
            "[Peer]",
            f"PublicKey = {peer_public_key}",
            "AllowedIPs = 0.0.0.0/0, ::/0",
            f"Endpoint = {endpoint}",
            "PersistentKeepalive = 25",
            "",
        ]
    )


async def generate_warp_config(timeout: float = 20) -> WarpConfigResult:
    keypair = generate_wireguard_keypair()
    registration = await register_warp_device(keypair.public_key, timeout=timeout)
    config = render_wireguard_config(keypair.private_key, registration)

    device_id = str(registration.get("id", "unknown"))
    filename_device_id = "".join(ch for ch in device_id if ch.isalnum() or ch in {"-", "_"}) or "warp"
    return WarpConfigResult(
        config=config,
        filename=f"warp_{filename_device_id}.conf",
        device_id=device_id,
    )
