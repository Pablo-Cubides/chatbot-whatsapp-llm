"""
Monitoring API Router — Audit logs & Alert management.
Extracted from admin_panel.py.
"""

import logging
import os
import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.routers.deps import (
    alert_manager,
    audit_manager,
    get_current_user,
    log_security_event,
    require_admin,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["monitoring"])

_security_alert_cooldown: dict[str, datetime] = {}
_security_alert_silenced_until: dict[str, datetime] = {}


def _get_security_silence_limit_for_role(role: str) -> int:
    role_name = (role or "").strip().lower()
    if role_name == "admin":
        return max(1, int(os.environ.get("SECURITY_MAX_SILENCE_MINUTES_ADMIN", "240")))
    return 0


def _cleanup_security_alert_runtime_state(now: datetime | None = None) -> None:
    current = now or datetime.now(timezone.utc)
    for key, value in list(_security_alert_cooldown.items()):
        if value > current + timedelta(days=7):
            _security_alert_cooldown.pop(key, None)
    for key, value in list(_security_alert_silenced_until.items()):
        if value <= current:
            _security_alert_silenced_until.pop(key, None)


def reset_security_response_runtime_state() -> None:
    """Reset in-memory state for security alert automation (tests/runtime)."""
    _security_alert_cooldown.clear()
    _security_alert_silenced_until.clear()


def _list_active_security_silences(now: datetime | None = None) -> list[dict[str, Any]]:
    current = now or datetime.now(timezone.utc)
    _cleanup_security_alert_runtime_state(current)
    items: list[dict[str, Any]] = []
    for fingerprint, silenced_until in _security_alert_silenced_until.items():
        remaining = int((silenced_until - current).total_seconds())
        if remaining <= 0:
            continue
        items.append(
            {
                "fingerprint": fingerprint,
                "silenced_until": silenced_until.isoformat(),
                "remaining_seconds": remaining,
            }
        )
    items.sort(key=lambda item: item["silenced_until"])
    return items


def _build_security_recommendations(anomaly_report: dict[str, Any], active_silences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    anomalies = anomaly_report.get("anomalies", [])
    if not anomalies:
        return [
            {
                "id": "baseline-monitoring",
                "priority": "low",
                "title": "Keep baseline monitoring active",
                "action": "Continue periodic review of /api/audit/security-overview and rotation policy checks.",
            }
        ]

    recommendations: list[dict[str, Any]] = []
    anomaly_index = {str(item.get("event", "")): item for item in anomalies}

    if "SECURITY_LOGIN_FAILED" in anomaly_index:
        recommendations.append(
            {
                "id": "login-failed-spike",
                "priority": "high",
                "title": "Harden authentication pressure",
                "action": "Temporarily reduce auth rate limits and review recent failed-login source IPs.",
            }
        )

    if "SECURITY_LOGIN_LOCKOUT" in anomaly_index:
        recommendations.append(
            {
                "id": "lockout-spike",
                "priority": "high",
                "title": "Investigate brute-force pattern",
                "action": "Enable temporary network controls (WAF/IP block) and force credential reset for impacted users.",
            }
        )

    if "SECURITY_REFRESH_FAILED" in anomaly_index:
        recommendations.append(
            {
                "id": "refresh-failed-spike",
                "priority": "medium",
                "title": "Review token lifecycle health",
                "action": "Validate refresh cookie delivery settings (Secure/SameSite) and inspect token replay attempts.",
            }
        )

    if "SECURITY_WS_UNAUTHORIZED" in anomaly_index or "SECURITY_WS_INVALID_SCOPE" in anomaly_index:
        recommendations.append(
            {
                "id": "ws-anomaly-spike",
                "priority": "medium",
                "title": "Restrict realtime channel abuse",
                "action": "Audit ws-token issuance volume and consider shorter ws-token TTL during incident window.",
            }
        )

    if active_silences:
        recommendations.append(
            {
                "id": "active-silences-review",
                "priority": "medium",
                "title": "Review active anomaly silences",
                "action": "Confirm silences still valid and clear obsolete fingerprints to avoid missing renewed attacks.",
            }
        )

    return recommendations


def _build_security_playbooks(anomaly_report: dict[str, Any]) -> list[dict[str, Any]]:
    anomalies = anomaly_report.get("anomalies", [])
    anomaly_events = {str(item.get("event", "")) for item in anomalies}

    if not anomaly_events:
        return [
            {
                "id": "security-baseline-readiness",
                "severity": "low",
                "title": "Baseline security readiness",
                "triggers": [],
                "checklist": [
                    "Review daily security overview and confirm no unresolved anomalies.",
                    "Validate JWT/refresh rotation policy and key age checks remain compliant.",
                    "Keep silence entries minimal and time-bounded.",
                ],
            }
        ]

    playbooks: list[dict[str, Any]] = []

    if "SECURITY_LOGIN_FAILED" in anomaly_events or "SECURITY_LOGIN_LOCKOUT" in anomaly_events:
        playbooks.append(
            {
                "id": "credential-abuse-response",
                "severity": "high",
                "title": "Credential abuse / brute-force response",
                "triggers": ["SECURITY_LOGIN_FAILED", "SECURITY_LOGIN_LOCKOUT"],
                "checklist": [
                    "Lower auth request thresholds temporarily and monitor impact.",
                    "Identify top source IP ranges and apply temporary edge/WAF blocking.",
                    "Force password reset for accounts impacted by repeated lockouts.",
                ],
            }
        )

    if "SECURITY_REFRESH_FAILED" in anomaly_events:
        playbooks.append(
            {
                "id": "session-token-lifecycle-response",
                "severity": "medium",
                "title": "Session token lifecycle response",
                "triggers": ["SECURITY_REFRESH_FAILED"],
                "checklist": [
                    "Validate refresh cookie flags (Secure, HttpOnly, SameSite) in current environment.",
                    "Check for replay patterns and invalidate suspicious sessions.",
                    "Review recent frontend/session deployments for regressions.",
                ],
            }
        )

    if "SECURITY_WS_UNAUTHORIZED" in anomaly_events or "SECURITY_WS_INVALID_SCOPE" in anomaly_events:
        playbooks.append(
            {
                "id": "realtime-channel-abuse-response",
                "severity": "medium",
                "title": "Realtime channel abuse response",
                "triggers": ["SECURITY_WS_UNAUTHORIZED", "SECURITY_WS_INVALID_SCOPE"],
                "checklist": [
                    "Inspect ws-token issuance volume and suspicious client fingerprints.",
                    "Reduce ws token TTL for the incident window.",
                    "Throttle websocket handshake attempts at edge/network layer.",
                ],
            }
        )

    return playbooks


def _build_security_incident_snapshot(
    window_minutes: int,
    recent_events_limit: int,
    role: str,
) -> dict[str, Any]:
    anomaly_report = audit_manager.get_security_signal_report(window_minutes=window_minutes)
    active_silences = _list_active_security_silences()
    recommendations = _build_security_recommendations(anomaly_report, active_silences)
    playbooks = _build_security_playbooks(anomaly_report)

    recent_logs = audit_manager.get_logs(limit=max(recent_events_limit * 3, 50), offset=0)
    recent_security_events = [entry for entry in recent_logs if str(entry.get("action", "")).startswith("SECURITY_")][
        :recent_events_limit
    ]

    # Keep payload compact for handoff use.
    compact_events = [
        {
            "timestamp": entry.get("timestamp"),
            "action": entry.get("action"),
            "username": entry.get("username"),
            "success": entry.get("success"),
        }
        for entry in recent_security_events
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_minutes": window_minutes,
        "status": "healthy" if anomaly_report.get("healthy", True) else "incident",
        "anomaly_count": len(anomaly_report.get("anomalies", [])),
        "anomalies": anomaly_report.get("anomalies", []),
        "silences": {
            "count": len(active_silences),
            "items": active_silences,
            "max_silence_minutes": _get_security_silence_limit_for_role(role),
        },
        "recommended_actions": recommendations,
        "playbooks": playbooks,
        "recent_security_actions": compact_events,
    }


def _canonical_json(payload: dict[str, Any]) -> str:
    """Stable JSON representation for hashing/signing operations."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _snapshot_integrity_envelope(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Create integrity metadata (hash + optional HMAC signature) for snapshot export."""
    canonical = _canonical_json(snapshot)
    payload_bytes = canonical.encode("utf-8")
    content_sha256 = hashlib.sha256(payload_bytes).hexdigest()

    signing_key = os.environ.get("SECURITY_SNAPSHOT_SIGNING_KEY") or os.environ.get("JWT_SECRET") or ""
    key_bytes = signing_key.encode("utf-8") if signing_key else b""
    signature = hmac.new(key_bytes, payload_bytes, hashlib.sha256).hexdigest() if key_bytes else None

    return {
        "canonical_json": canonical,
        "content_sha256": content_sha256,
        "signature": signature,
        "signature_algorithm": "HMAC-SHA256" if signature else "NONE",
        "signed": signature is not None,
        "key_id": os.environ.get("SECURITY_SNAPSHOT_SIGNING_KEY_ID", "default" if signature else None),
    }


def _verify_snapshot_integrity(snapshot: dict[str, Any], integrity: dict[str, Any]) -> dict[str, Any]:
    """Verify hash/signature integrity envelope for externally received snapshots."""
    canonical = _canonical_json(snapshot)
    payload_bytes = canonical.encode("utf-8")

    received_hash = str(integrity.get("content_sha256") or "")
    computed_hash = hashlib.sha256(payload_bytes).hexdigest()
    hash_valid = bool(received_hash) and hmac.compare_digest(received_hash, computed_hash)

    received_signature = integrity.get("signature")
    received_algorithm = str(integrity.get("signature_algorithm") or "NONE").upper()
    signed_flag = bool(integrity.get("signed"))

    signing_key = os.environ.get("SECURITY_SNAPSHOT_SIGNING_KEY") or os.environ.get("JWT_SECRET") or ""
    key_bytes = signing_key.encode("utf-8") if signing_key else b""

    signature_valid = False
    if signed_flag and received_algorithm == "HMAC-SHA256" and isinstance(received_signature, str) and key_bytes:
        computed_signature = hmac.new(key_bytes, payload_bytes, hashlib.sha256).hexdigest()
        signature_valid = hmac.compare_digest(received_signature, computed_signature)
    elif not signed_flag:
        signature_valid = True

    overall_valid = hash_valid and signature_valid
    return {
        "valid": overall_valid,
        "hash_valid": hash_valid,
        "signature_valid": signature_valid,
        "computed_content_sha256": computed_hash,
        "received_content_sha256": received_hash or None,
        "signed": signed_flag,
        "signature_algorithm": received_algorithm,
    }


def _get_cursor_signing_key() -> bytes:
    key = (
        os.environ.get("SECURITY_EXPORT_CURSOR_SIGNING_KEY")
        or os.environ.get("SECURITY_SNAPSHOT_SIGNING_KEY")
        or os.environ.get("JWT_SECRET")
        or ""
    )
    return key.encode("utf-8") if key else b""


def _encode_cursor_token(cursor: dict[str, Any]) -> str:
    key_bytes = _get_cursor_signing_key()
    if not key_bytes:
        raise HTTPException(status_code=500, detail="No signing key available for cursor token")

    canonical = _canonical_json(cursor)
    signature = hmac.new(key_bytes, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    envelope = {
        "cursor": cursor,
        "sig": signature,
        "alg": "HMAC-SHA256",
    }
    raw = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _decode_cursor_token(cursor_token: str) -> dict[str, Any]:
    try:
        token = (cursor_token or "").strip()
        if not token:
            raise HTTPException(status_code=400, detail="cursor_token requerido")

        padded = token + ("=" * (-len(token) % 4))
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        envelope = json.loads(decoded)

        cursor = envelope.get("cursor")
        received_sig = str(envelope.get("sig") or "")
        if not isinstance(cursor, dict) or not received_sig:
            raise HTTPException(status_code=400, detail="cursor_token malformado")

        key_bytes = _get_cursor_signing_key()
        if not key_bytes:
            raise HTTPException(status_code=500, detail="No signing key available for cursor token")

        expected_sig = hmac.new(
            key_bytes,
            _canonical_json(cursor).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(received_sig, expected_sig):
            raise HTTPException(status_code=400, detail="cursor_token invalido")

        since_raw = str(cursor.get("since") or "")
        if not since_raw:
            raise HTTPException(status_code=400, detail="cursor_token sin campo since")

        parsed_since = datetime.fromisoformat(since_raw)
        if parsed_since.tzinfo is None:
            parsed_since = parsed_since.replace(tzinfo=timezone.utc)

        parsed_after_id = max(0, int(cursor.get("after_id") or 0))
        return {
            "since": parsed_since,
            "after_id": parsed_after_id,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="cursor_token malformado")


def _build_chain_of_custody_entries(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in logs:
        details = item.get("details") or {}
        entries.append(
            {
                "timestamp": item.get("timestamp"),
                "username": item.get("username"),
                "role": item.get("role"),
                "action": item.get("action"),
                "verification_valid": details.get("valid"),
                "hash_valid": details.get("hash_valid"),
                "signature_valid": details.get("signature_valid"),
                "computed_content_sha256": details.get("computed_content_sha256"),
                "received_content_sha256": details.get("received_content_sha256"),
                "signed": details.get("signed"),
                "signature_algorithm": details.get("signature_algorithm"),
                "signature_key_id": details.get("signature_key_id"),
            }
        )
    return entries


def _build_security_alert_fingerprint(anomalies: list[dict[str, Any]]) -> str:
    entries = sorted(f"{item.get('event', 'unknown')}:{item.get('threshold', 0)}" for item in anomalies)
    return "|".join(entries)


# ═══════════════════════ Audit ═══════════════════════


@router.get("/api/audit/logs", response_model=dict[str, Any])
async def get_audit_logs(
    username: Optional[str] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Obtener logs de auditoría (solo admin)"""
    try:
        logs = audit_manager.get_logs(
            username=username,
            action=action,
            resource=resource,
            limit=limit,
            offset=offset,
        )
        return {"logs": logs, "count": len(logs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/stats", response_model=dict[str, Any])
async def get_audit_stats(
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Obtener estadísticas de auditoría (solo admin)"""
    try:
        stats = audit_manager.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/security-anomalies", response_model=dict[str, Any])
async def get_security_anomalies(
    window_minutes: int = 15,
    login_failed_threshold: Optional[int] = None,
    login_lockout_threshold: Optional[int] = None,
    refresh_failed_threshold: Optional[int] = None,
    ws_unauthorized_threshold: Optional[int] = None,
    ws_invalid_scope_threshold: Optional[int] = None,
    auto_create_alert: bool = False,
    alert_cooldown_minutes: int = 30,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Reporte de anomalías basado en eventos SECURITY_* de auditoría."""
    try:
        custom_thresholds = {
            "SECURITY_LOGIN_FAILED": login_failed_threshold,
            "SECURITY_LOGIN_LOCKOUT": login_lockout_threshold,
            "SECURITY_REFRESH_FAILED": refresh_failed_threshold,
            "SECURITY_WS_UNAUTHORIZED": ws_unauthorized_threshold,
            "SECURITY_WS_INVALID_SCOPE": ws_invalid_scope_threshold,
        }
        thresholds = {key: value for key, value in custom_thresholds.items() if isinstance(value, int) and value > 0}
        report = audit_manager.get_security_signal_report(window_minutes=window_minutes, thresholds=thresholds)

        if auto_create_alert:
            anomalies = report.get("anomalies", [])
            if not anomalies:
                report["security_alert"] = {"created": False, "reason": "no_anomalies"}
                return report

            now = datetime.now(timezone.utc)
            _cleanup_security_alert_runtime_state(now)
            cooldown_minutes = max(1, min(alert_cooldown_minutes, 24 * 60))
            fingerprint = _build_security_alert_fingerprint(anomalies)
            silenced_until = _security_alert_silenced_until.get(fingerprint)

            if silenced_until and silenced_until > now:
                report["security_alert"] = {
                    "created": False,
                    "reason": "silenced",
                    "fingerprint": fingerprint,
                    "silenced_until": silenced_until.isoformat(),
                }
                return report

            last_created_at = _security_alert_cooldown.get(fingerprint)

            if last_created_at and (now - last_created_at).total_seconds() < (cooldown_minutes * 60):
                report["security_alert"] = {
                    "created": False,
                    "reason": "cooldown",
                    "fingerprint": fingerprint,
                }
                return report

            has_high = any(str(item.get("severity", "")).lower() == "high" for item in anomalies)
            alert_severity = "urgent" if has_high else "high"
            summary = ", ".join(f"{item.get('event')}={item.get('count')}" for item in anomalies)
            alert_id = alert_manager.create_alert(
                chat_id="security:platform",
                severity=alert_severity,
                message_text=f"Security anomalies detected: {summary}",
                metadata={
                    "source": "security_anomalies",
                    "fingerprint": fingerprint,
                    "anomalies": anomalies,
                    "window_minutes": report.get("window_minutes"),
                    "thresholds": report.get("thresholds"),
                    "generated_at": report.get("generated_at"),
                },
            )

            if alert_id:
                _security_alert_cooldown[fingerprint] = now
                log_security_event(
                    "security_alert_created",
                    username=current_user.get("sub") or current_user.get("username", "unknown"),
                    role=current_user.get("role", "unknown"),
                    success=True,
                    details={"alert_id": alert_id, "fingerprint": fingerprint, "anomalies": len(anomalies)},
                )
                report["security_alert"] = {
                    "created": True,
                    "alert_id": alert_id,
                    "fingerprint": fingerprint,
                    "severity": alert_severity,
                }
            else:
                report["security_alert"] = {"created": False, "reason": "create_failed", "fingerprint": fingerprint}

        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/alerts/{alert_id}/acknowledge-security", response_model=dict[str, Any])
async def acknowledge_security_alert(
    alert_id: str,
    silence_minutes: int = 0,
    reason: Optional[str] = None,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Confirmar alerta automática de seguridad y silenciar temporalmente su fingerprint."""
    try:
        alert = alert_manager.get_alert_by_id(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")

        metadata = alert.get("metadata") or {}
        if metadata.get("source") != "security_anomalies":
            raise HTTPException(status_code=400, detail="Solo se pueden confirmar alertas automáticas de seguridad")

        username = current_user.get("sub") or current_user.get("username", "unknown")
        role = str(current_user.get("role", "unknown"))
        max_silence_minutes = _get_security_silence_limit_for_role(role)
        if silence_minutes > 0 and silence_minutes > max_silence_minutes:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Silence duration exceeds role policy. "
                    f"Max allowed for role '{role}' is {max_silence_minutes} minutes."
                ),
            )

        acknowledged = alert_manager.acknowledge_security_alert(
            alert_id=alert_id,
            acknowledged_by=username,
            note=reason,
            silence_minutes=silence_minutes,
        )
        if not acknowledged:
            raise HTTPException(status_code=500, detail="No se pudo confirmar la alerta")

        updated_meta = acknowledged.get("metadata") or {}
        fingerprint = updated_meta.get("fingerprint")
        silenced_until = updated_meta.get("silenced_until")

        silenced = False
        if fingerprint and silenced_until:
            try:
                parsed_until = datetime.fromisoformat(str(silenced_until))
                if parsed_until.tzinfo is None:
                    parsed_until = parsed_until.replace(tzinfo=timezone.utc)
                _security_alert_silenced_until[fingerprint] = parsed_until
                silenced = True
            except ValueError:
                silenced = False

        log_security_event(
            "security_alert_acknowledged",
            username=username,
            role=role,
            success=True,
            details={
                "alert_id": alert_id,
                "fingerprint": fingerprint,
                "silence_minutes": max(0, silence_minutes),
                "silenced": silenced,
                "max_silence_minutes": max_silence_minutes,
            },
        )

        return {
            "success": True,
            "alert_id": alert_id,
            "acknowledged_by": username,
            "silenced": silenced,
            "silenced_until": silenced_until,
            "fingerprint": fingerprint,
            "max_silence_minutes": max_silence_minutes,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/security-silences", response_model=dict[str, Any])
async def get_security_silences(
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Listar silencios activos de anomalías de seguridad para operación SOC."""
    try:
        active = _list_active_security_silences()
        return {
            "count": len(active),
            "silences": active,
            "policy": {
                "max_silence_minutes": _get_security_silence_limit_for_role(str(current_user.get("role", "unknown"))),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/audit/security-silences/renew", response_model=dict[str, Any])
async def renew_security_silence(
    fingerprint: str,
    minutes: int = 30,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Renovar silencio activo por fingerprint para reducir ruido operacional."""
    try:
        normalized = (fingerprint or "").strip()
        if not normalized:
            raise HTTPException(status_code=400, detail="fingerprint requerido")

        _cleanup_security_alert_runtime_state()
        if normalized not in _security_alert_silenced_until:
            raise HTTPException(status_code=404, detail="Silencio no encontrado")

        role = str(current_user.get("role", "unknown"))
        max_silence_minutes = _get_security_silence_limit_for_role(role)
        if minutes > max_silence_minutes:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Silence duration exceeds role policy. "
                    f"Max allowed for role '{role}' is {max_silence_minutes} minutes."
                ),
            )

        safe_minutes = max(1, min(minutes, max_silence_minutes))
        now = datetime.now(timezone.utc)
        updated_until = now + timedelta(minutes=safe_minutes)
        _security_alert_silenced_until[normalized] = updated_until

        username = current_user.get("sub") or current_user.get("username", "unknown")
        log_security_event(
            "security_silence_renewed",
            username=username,
            role=role,
            success=True,
            details={"fingerprint": normalized, "minutes": safe_minutes, "max_silence_minutes": max_silence_minutes},
        )

        return {
            "success": True,
            "fingerprint": normalized,
            "silenced_until": updated_until.isoformat(),
            "minutes": safe_minutes,
            "max_silence_minutes": max_silence_minutes,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/audit/security-silences", response_model=dict[str, Any])
async def clear_security_silence(
    fingerprint: str,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Eliminar manualmente silencio activo para reactivar auto-respuesta."""
    try:
        normalized = (fingerprint or "").strip()
        if not normalized:
            raise HTTPException(status_code=400, detail="fingerprint requerido")

        _cleanup_security_alert_runtime_state()
        existed = _security_alert_silenced_until.pop(normalized, None)
        if existed is None:
            raise HTTPException(status_code=404, detail="Silencio no encontrado")

        username = current_user.get("sub") or current_user.get("username", "unknown")
        log_security_event(
            "security_silence_cleared",
            username=username,
            role=current_user.get("role", "unknown"),
            success=True,
            details={"fingerprint": normalized},
        )

        return {
            "success": True,
            "fingerprint": normalized,
            "cleared": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/security-overview", response_model=dict[str, Any])
async def get_security_overview(
    window_minutes: int = 60,
    events_limit: int = 25,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Resumen SOC consolidado: anomalías, silencios activos y eventos recientes."""
    try:
        normalized_window = max(1, min(window_minutes, 24 * 60))
        normalized_events_limit = max(1, min(events_limit, 200))

        anomaly_report = audit_manager.get_security_signal_report(window_minutes=normalized_window)
        active_silences = _list_active_security_silences()

        # Reuse existing audit reader and filter SECURITY_* events for compact SOC view.
        recent_logs = audit_manager.get_logs(limit=max(normalized_events_limit * 3, 50), offset=0)
        recent_security_events = [entry for entry in recent_logs if str(entry.get("action", "")).startswith("SECURITY_")][
            :normalized_events_limit
        ]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_minutes": normalized_window,
            "anomalies": {
                "healthy": anomaly_report.get("healthy", True),
                "items": anomaly_report.get("anomalies", []),
                "totals": anomaly_report.get("totals", {}),
                "thresholds": anomaly_report.get("thresholds", {}),
            },
            "silences": {
                "count": len(active_silences),
                "items": active_silences,
                "policy": {
                    "max_silence_minutes": _get_security_silence_limit_for_role(str(current_user.get("role", "unknown"))),
                },
            },
            "recent_security_actions": {
                "count": len(recent_security_events),
                "limit": normalized_events_limit,
                "items": recent_security_events,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/security-recommendations", response_model=dict[str, Any])
async def get_security_recommendations(
    window_minutes: int = 60,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Generate actionable mitigation recommendations from current anomaly signals."""
    try:
        normalized_window = max(1, min(window_minutes, 24 * 60))
        anomaly_report = audit_manager.get_security_signal_report(window_minutes=normalized_window)
        active_silences = _list_active_security_silences()
        recommendations = _build_security_recommendations(anomaly_report, active_silences)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_minutes": normalized_window,
            "healthy": anomaly_report.get("healthy", True),
            "anomaly_count": len(anomaly_report.get("anomalies", [])),
            "active_silences": len(active_silences),
            "recommendations": recommendations,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/security-playbooks", response_model=dict[str, Any])
async def get_security_playbooks(
    window_minutes: int = 60,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Provide severity-based operational playbooks from active security anomalies."""
    try:
        normalized_window = max(1, min(window_minutes, 24 * 60))
        anomaly_report = audit_manager.get_security_signal_report(window_minutes=normalized_window)
        playbooks = _build_security_playbooks(anomaly_report)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_minutes": normalized_window,
            "healthy": anomaly_report.get("healthy", True),
            "anomaly_count": len(anomaly_report.get("anomalies", [])),
            "playbooks": playbooks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/security-incident-snapshot", response_model=dict[str, Any])
async def get_security_incident_snapshot(
    window_minutes: int = 60,
    recent_events_limit: int = 20,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Export compact SOC handoff snapshot as JSON."""
    try:
        normalized_window = max(1, min(window_minutes, 24 * 60))
        normalized_recent_limit = max(1, min(recent_events_limit, 100))
        role = str(current_user.get("role", "unknown"))

        snapshot = _build_security_incident_snapshot(
            window_minutes=normalized_window,
            recent_events_limit=normalized_recent_limit,
            role=role,
        )
        return snapshot
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/security-incident-snapshot-signed", response_model=dict[str, Any])
async def get_security_incident_snapshot_signed(
    window_minutes: int = 60,
    recent_events_limit: int = 20,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Export incident snapshot with hash/signature envelope for handoff integrity."""
    try:
        normalized_window = max(1, min(window_minutes, 24 * 60))
        normalized_recent_limit = max(1, min(recent_events_limit, 100))
        role = str(current_user.get("role", "unknown"))

        snapshot = _build_security_incident_snapshot(
            window_minutes=normalized_window,
            recent_events_limit=normalized_recent_limit,
            role=role,
        )
        integrity = _snapshot_integrity_envelope(snapshot)
        return {
            "snapshot": snapshot,
            "integrity": integrity,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════ Alerts ═══════════════════════


@router.get("/api/alerts", response_model=dict[str, Any])
async def get_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    chat_id: Optional[str] = None,
    assigned_to: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Obtener alertas con filtros"""
    try:
        alerts = alert_manager.get_alerts(
            status=status,
            severity=severity,
            chat_id=chat_id,
            assigned_to=assigned_to,
            limit=limit,
            offset=offset,
        )
        return {"alerts": alerts, "count": len(alerts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/alerts/{alert_id}/assign", response_model=dict[str, Any])
async def assign_alert(
    alert_id: str,
    assigned_to: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Asignar una alerta a un operador"""
    try:
        success = alert_manager.assign_alert(alert_id, assigned_to)
        if not success:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")
        return {"success": True, "message": f"Alerta asignada a {assigned_to}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/alerts/{alert_id}/resolve", response_model=dict[str, Any])
async def resolve_alert(
    alert_id: str,
    notes: Optional[str] = None,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Resolver una alerta"""
    try:
        success = alert_manager.resolve_alert(alert_id, notes)
        if not success:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")
        return {"success": True, "message": "Alerta resuelta"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/alert-rules", response_model=dict[str, Any])
async def get_alert_rules(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Obtener todas las reglas de alerta"""
    try:
        rules = alert_manager.get_rules()
        return {"rules": rules, "count": len(rules)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AlertRuleCreate(BaseModel):
    name: str
    rule_type: str
    pattern: str
    severity: str
    actions: list[str]
    enabled: Optional[bool] = True
    schedule: Optional[dict] = None
    metadata: Optional[dict] = None


class SnapshotVerificationRequest(BaseModel):
    snapshot: dict[str, Any]
    integrity: dict[str, Any]


@router.post("/api/alert-rules", response_model=dict[str, Any])
async def create_alert_rule(
    rule: AlertRuleCreate,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Crear una regla de alerta (solo admin)"""
    try:
        rule_id = alert_manager.create_rule(
            name=rule.name,
            rule_type=rule.rule_type,
            pattern=rule.pattern,
            severity=rule.severity,
            actions=rule.actions,
            created_by=current_user.get("username", "unknown"),
            enabled=rule.enabled,
            schedule=rule.schedule,
            metadata=rule.metadata,
        )

        if not rule_id:
            raise HTTPException(status_code=500, detail="Error creando regla")

        return {"success": True, "rule_id": rule_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/audit/security-incident-snapshot-verify", response_model=dict[str, Any])
async def verify_security_incident_snapshot(
    payload: SnapshotVerificationRequest,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Verify integrity envelope of a received incident snapshot."""
    try:
        verification = _verify_snapshot_integrity(payload.snapshot, payload.integrity)
        username = current_user.get("sub") or current_user.get("username", "unknown")
        role = current_user.get("role", "unknown")
        log_security_event(
            "snapshot_verification_performed",
            username=username,
            role=role,
            success=bool(verification.get("valid")),
            details={
                "valid": bool(verification.get("valid")),
                "hash_valid": bool(verification.get("hash_valid")),
                "signature_valid": bool(verification.get("signature_valid")),
                "computed_content_sha256": verification.get("computed_content_sha256"),
                "received_content_sha256": verification.get("received_content_sha256"),
                "signed": bool(payload.integrity.get("signed")),
                "signature_algorithm": payload.integrity.get("signature_algorithm"),
                "signature_key_id": payload.integrity.get("key_id"),
            },
        )
        return {
            "verification": verification,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/security-chain-of-custody", response_model=dict[str, Any])
async def get_security_chain_of_custody(
    hours_back: int = 24,
    limit: int = 100,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Export chain-of-custody view for snapshot verification operations."""
    try:
        normalized_hours = max(1, min(hours_back, 24 * 30))
        normalized_limit = max(1, min(limit, 1000))
        start_date = datetime.now(timezone.utc) - timedelta(hours=normalized_hours)

        logs = audit_manager.get_logs(
            action="SECURITY_SNAPSHOT_VERIFICATION_PERFORMED",
            start_date=start_date,
            limit=normalized_limit,
            offset=0,
        )
        entries = _build_chain_of_custody_entries(logs)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "hours_back": normalized_hours,
            "count": len(entries),
            "entries": entries,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/security-retention-policy", response_model=dict[str, Any])
async def get_security_retention_policy(
    retention_days: int = 365,
    include_protected_actions: bool = False,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Preview retention policy impact for SECURITY_* forensic events."""
    try:
        preview = audit_manager.get_security_retention_preview(
            retention_days=retention_days,
            include_protected_actions=include_protected_actions,
        )
        return {
            "preview": preview,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/audit/security-retention-purge", response_model=dict[str, Any])
async def purge_security_retention(
    retention_days: int = 365,
    dry_run: bool = True,
    include_protected_actions: bool = False,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Execute (or preview) retention purge for old SECURITY_* audit records."""
    try:
        result = audit_manager.purge_security_logs(
            retention_days=retention_days,
            dry_run=dry_run,
            include_protected_actions=include_protected_actions,
        )

        username = current_user.get("sub") or current_user.get("username", "unknown")
        log_security_event(
            "security_retention_purge",
            username=username,
            role=current_user.get("role", "unknown"),
            success=True,
            details={
                "retention_days": retention_days,
                "dry_run": dry_run,
                "include_protected_actions": include_protected_actions,
                "deleted_count": result.get("deleted_count", 0),
                "candidate_count": result.get("count", 0),
            },
        )

        return {
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/security-events-export")
async def export_security_events_incremental(
    since: datetime,
    limit: int = 200,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Incremental export feed of SECURITY_* audit events for SIEM/SOC ingestion."""
    try:
        normalized_limit = max(1, min(limit, 2000))
        events = audit_manager.export_security_events_since(since=since, limit=normalized_limit)
        next_since = events[-1].get("timestamp") if events else since.isoformat()

        username = current_user.get("sub") or current_user.get("username", "unknown")
        audit_manager.log_action(
            username=username,
            action="AUDIT_SECURITY_EVENTS_EXPORTED",
            role=current_user.get("role", "unknown"),
            success=True,
            details={
                "since": since.isoformat(),
                "limit": normalized_limit,
                "count": len(events),
            },
        )

        return {
            "since": since.isoformat(),
            "limit": normalized_limit,
            "count": len(events),
            "has_more": len(events) >= normalized_limit,
            "next_since": next_since,
            "events": events,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/security-events-export-v2")
async def export_security_events_incremental_v2(
    since: Optional[datetime] = None,
    after_id: int = 0,
    cursor_token: Optional[str] = None,
    limit: int = 200,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Cursor-safe export feed with signed batch envelope for SOC/SIEM pipelines."""
    try:
        normalized_limit = max(1, min(limit, 2000))
        if cursor_token:
            parsed_cursor = _decode_cursor_token(cursor_token)
            effective_since = parsed_cursor["since"]
            normalized_after_id = parsed_cursor["after_id"]
        else:
            if since is None:
                raise HTTPException(status_code=400, detail="since o cursor_token requerido")
            effective_since = since
            normalized_after_id = max(0, int(after_id or 0))

        events = audit_manager.export_security_events_cursor(
            since=effective_since,
            after_id=normalized_after_id,
            limit=normalized_limit,
        )

        if events:
            last = events[-1]
            next_since = str(last.get("timestamp") or effective_since.isoformat())
            next_after_id = int(last.get("id") or normalized_after_id)
        else:
            next_since = effective_since.isoformat()
            next_after_id = normalized_after_id

        cursor = {
            "since": next_since,
            "after_id": next_after_id,
        }
        next_cursor_token = _encode_cursor_token(cursor)
        batch_payload = {
            "since": effective_since.isoformat(),
            "after_id": normalized_after_id,
            "limit": normalized_limit,
            "count": len(events),
            "cursor": cursor,
            "events": events,
        }
        integrity = _snapshot_integrity_envelope(batch_payload)

        username = current_user.get("sub") or current_user.get("username", "unknown")
        audit_manager.log_action(
            username=username,
            action="AUDIT_SECURITY_EVENTS_EXPORTED_V2",
            role=current_user.get("role", "unknown"),
            success=True,
            details={
                "since": effective_since.isoformat(),
                "after_id": normalized_after_id,
                "limit": normalized_limit,
                "count": len(events),
                "next_since": next_since,
                "next_after_id": next_after_id,
                "used_cursor_token": bool(cursor_token),
            },
        )

        return {
            **batch_payload,
            "has_more": len(events) >= normalized_limit,
            "integrity": integrity,
            "cursor_token": next_cursor_token,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/security-export-checkpoints")
async def list_security_export_checkpoints(
    limit: int = 100,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """List latest SECURITY export checkpoints per consumer."""
    try:
        items = audit_manager.list_security_export_checkpoints(limit=limit)
        return {
            "count": len(items),
            "items": items,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/audit/security-export-checkpoints/{consumer}")
async def get_security_export_checkpoint(
    consumer: str,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Get latest SECURITY export checkpoint for one consumer."""
    try:
        checkpoint = audit_manager.get_security_export_checkpoint(consumer)
        if not checkpoint:
            raise HTTPException(status_code=404, detail="Checkpoint no encontrado")
        return {
            "checkpoint": checkpoint,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/audit/security-export-checkpoints/{consumer}")
async def upsert_security_export_checkpoint(
    consumer: str,
    since: datetime,
    after_id: int = 0,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Upsert SECURITY export checkpoint for a consumer."""
    try:
        username = current_user.get("sub") or current_user.get("username", "unknown")
        role = current_user.get("role", "unknown")
        checkpoint = audit_manager.set_security_export_checkpoint(
            consumer=consumer,
            since=since,
            after_id=after_id,
            updated_by=username,
            role=role,
        )
        return {
            "checkpoint": checkpoint,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/audit/security-events-export-v2/consumer/{consumer}")
async def export_security_events_for_consumer(
    consumer: str,
    limit: int = 200,
    bootstrap_since: Optional[datetime] = None,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Consumer-aware incremental export that auto-resumes and updates checkpoint."""
    try:
        normalized_consumer = (consumer or "").strip().lower()
        if not normalized_consumer:
            raise HTTPException(status_code=400, detail="consumer requerido")

        normalized_limit = max(1, min(limit, 2000))
        checkpoint = audit_manager.get_security_export_checkpoint(normalized_consumer)

        if checkpoint:
            since_raw = str(checkpoint.get("since") or "")
            if not since_raw:
                raise HTTPException(status_code=500, detail="Checkpoint invalido")
            effective_since = datetime.fromisoformat(since_raw)
            if effective_since.tzinfo is None:
                effective_since = effective_since.replace(tzinfo=timezone.utc)
            effective_after_id = int(checkpoint.get("after_id") or 0)
        elif bootstrap_since is not None:
            effective_since = bootstrap_since
            effective_after_id = 0
        else:
            raise HTTPException(status_code=400, detail="No checkpoint found. Provide bootstrap_since first")

        events = audit_manager.export_security_events_cursor(
            since=effective_since,
            after_id=effective_after_id,
            limit=normalized_limit,
        )

        if events:
            last = events[-1]
            next_since = str(last.get("timestamp") or effective_since.isoformat())
            next_after_id = int(last.get("id") or effective_after_id)
        else:
            next_since = effective_since.isoformat()
            next_after_id = effective_after_id

        cursor = {
            "since": next_since,
            "after_id": next_after_id,
        }
        next_cursor_token = _encode_cursor_token(cursor)

        username = current_user.get("sub") or current_user.get("username", "unknown")
        updated_checkpoint = audit_manager.set_security_export_checkpoint(
            consumer=normalized_consumer,
            since=datetime.fromisoformat(next_since),
            after_id=next_after_id,
            updated_by=username,
            role=current_user.get("role", "unknown"),
        )

        batch_payload = {
            "consumer": normalized_consumer,
            "since": effective_since.isoformat(),
            "after_id": effective_after_id,
            "limit": normalized_limit,
            "count": len(events),
            "cursor": cursor,
            "events": events,
        }
        integrity = _snapshot_integrity_envelope(batch_payload)

        return {
            **batch_payload,
            "has_more": len(events) >= normalized_limit,
            "integrity": integrity,
            "cursor_token": next_cursor_token,
            "checkpoint": updated_checkpoint,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/alert-rules/{rule_id}")
async def update_alert_rule(
    rule_id: int,
    updates: dict[str, Any],
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Actualizar una regla de alerta (solo admin)"""
    try:
        success = alert_manager.update_rule(rule_id, **updates)
        if not success:
            raise HTTPException(status_code=404, detail="Regla no encontrada")
        return {"success": True, "message": "Regla actualizada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/alert-rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Eliminar una regla de alerta (solo admin)"""
    try:
        success = alert_manager.delete_rule(rule_id)
        if not success:
            raise HTTPException(status_code=404, detail="Regla no encontrada")
        return {"success": True, "message": "Regla eliminada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
