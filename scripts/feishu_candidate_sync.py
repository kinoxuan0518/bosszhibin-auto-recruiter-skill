#!/usr/bin/env python3
"""Generic Feishu Bitable sync script for bosszhibin-auto-recruiter.

This script reads one or more session output JSON files and upserts data into
three Feishu Bitable tables:
- candidate_master
- interaction_log
- job_funnel_daily

Required env vars:
- FEISHU_APP_ID
- FEISHU_APP_SECRET
- FEISHU_BITABLE_APP_TOKEN
- FEISHU_TABLE_CANDIDATE_MASTER
- FEISHU_TABLE_INTERACTION_LOG
- FEISHU_TABLE_JOB_FUNNEL_DAILY

Optional env vars:
- FEISHU_BASE_URL (default: https://open.feishu.cn/open-apis)
- BOSSZHIBIN_CACHE_DIR (used when no input path is provided)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
RETRYABLE_FEISHU_CODES = {
    99991663,  # common rate limit
    99991400,  # transient backend error (varies)
}


@dataclass
class Config:
    app_id: str
    app_secret: str
    app_token: str
    table_candidate: str
    table_interaction: str
    table_funnel: str
    base_url: str

    @staticmethod
    def from_env() -> "Config":
        required = {
            "FEISHU_APP_ID": os.getenv("FEISHU_APP_ID", "").strip(),
            "FEISHU_APP_SECRET": os.getenv("FEISHU_APP_SECRET", "").strip(),
            "FEISHU_BITABLE_APP_TOKEN": os.getenv("FEISHU_BITABLE_APP_TOKEN", "").strip(),
            "FEISHU_TABLE_CANDIDATE_MASTER": os.getenv("FEISHU_TABLE_CANDIDATE_MASTER", "").strip(),
            "FEISHU_TABLE_INTERACTION_LOG": os.getenv("FEISHU_TABLE_INTERACTION_LOG", "").strip(),
            "FEISHU_TABLE_JOB_FUNNEL_DAILY": os.getenv("FEISHU_TABLE_JOB_FUNNEL_DAILY", "").strip(),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError("Missing required env vars: " + ", ".join(missing))

        return Config(
            app_id=required["FEISHU_APP_ID"],
            app_secret=required["FEISHU_APP_SECRET"],
            app_token=required["FEISHU_BITABLE_APP_TOKEN"],
            table_candidate=required["FEISHU_TABLE_CANDIDATE_MASTER"],
            table_interaction=required["FEISHU_TABLE_INTERACTION_LOG"],
            table_funnel=required["FEISHU_TABLE_JOB_FUNNEL_DAILY"],
            base_url=os.getenv("FEISHU_BASE_URL", "https://open.feishu.cn/open-apis").rstrip("/"),
        )


def _json_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Tuple[int, Dict[str, Any]]:
    data = None
    req_headers: Dict[str, str] = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            return status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        parsed: Dict[str, Any]
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"code": -1, "msg": body}
        return exc.code, parsed


def _is_retryable(status: int, body: Dict[str, Any]) -> bool:
    if status in RETRYABLE_HTTP_STATUS:
        return True
    code = body.get("code")
    if isinstance(code, int) and code in RETRYABLE_FEISHU_CODES:
        return True
    msg = str(body.get("msg", "")).lower()
    if "too many" in msg or "rate" in msg and "limit" in msg:
        return True
    return False


class FeishuBitableClient:
    def __init__(self, config: Config, timeout: int = 30, max_retries: int = 3) -> None:
        self.cfg = config
        self.timeout = timeout
        self.max_retries = max_retries
        self._tenant_token: Optional[str] = None
        self._tenant_expire_at: float = 0
        self._field_name_cache: Dict[str, set[str]] = {}

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        auth: bool = True,
    ) -> Dict[str, Any]:
        query = ""
        if params:
            query = "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self.cfg.base_url}{path}{query}"

        headers: Dict[str, str] = {}
        if auth:
            headers["Authorization"] = f"Bearer {self.tenant_access_token()}"

        last_body: Dict[str, Any] = {}
        for attempt in range(self.max_retries + 1):
            status, body = _json_request(method, url, headers=headers, payload=payload, timeout=self.timeout)
            last_body = body
            code = body.get("code", -1)
            if status < 400 and code == 0:
                return body

            if attempt < self.max_retries and _is_retryable(status, body):
                time.sleep(2 ** attempt)
                continue

            raise RuntimeError(
                f"Feishu API failed: {method} {path} status={status} code={code} msg={body.get('msg')}"
            )

        raise RuntimeError(f"Feishu API failed unexpectedly: {method} {path} {last_body}")

    def tenant_access_token(self) -> str:
        now = time.time()
        if self._tenant_token and now < self._tenant_expire_at - 60:
            return self._tenant_token

        body = self._request(
            "POST",
            "/auth/v3/tenant_access_token/internal",
            auth=False,
            payload={"app_id": self.cfg.app_id, "app_secret": self.cfg.app_secret},
        )
        token = body["tenant_access_token"]
        expire = int(body.get("expire", 7200))
        self._tenant_token = token
        self._tenant_expire_at = now + expire
        return token

    def list_table_field_names(self, table_id: str) -> set[str]:
        if table_id in self._field_name_cache:
            return self._field_name_cache[table_id]

        names: set[str] = set()
        page_token: Optional[str] = None
        while True:
            body = self._request(
                "GET",
                f"/bitable/v1/apps/{self.cfg.app_token}/tables/{table_id}/fields",
                params={"page_size": 500, "page_token": page_token},
            )
            data = body.get("data", {})
            for item in data.get("items", []):
                name = str(item.get("field_name", "")).strip()
                if name:
                    names.add(name)
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")

        self._field_name_cache[table_id] = names
        return names

    def list_records(self, table_id: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        while True:
            body = self._request(
                "GET",
                f"/bitable/v1/apps/{self.cfg.app_token}/tables/{table_id}/records",
                params={"page_size": 500, "page_token": page_token},
            )
            data = body.get("data", {})
            items.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
        return items

    def create_record(self, table_id: str, fields: Dict[str, Any]) -> str:
        body = self._request(
            "POST",
            f"/bitable/v1/apps/{self.cfg.app_token}/tables/{table_id}/records",
            payload={"fields": fields},
        )
        return body.get("data", {}).get("record", {}).get("record_id", "")

    def update_record(self, table_id: str, record_id: str, fields: Dict[str, Any]) -> None:
        self._request(
            "PUT",
            f"/bitable/v1/apps/{self.cfg.app_token}/tables/{table_id}/records/{record_id}",
            payload={"fields": fields},
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync session output JSON to Feishu Bitable tables.")
    parser.add_argument("inputs", nargs="*", help="Input session JSON files.")
    parser.add_argument("--dry-run", action="store_true", help="Build payload but do not call Feishu APIs.")
    parser.add_argument("--output", help="Write summary JSON to this file.")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds. Default 30.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on any failed upsert.")
    return parser.parse_args()


def pick_default_input() -> Optional[Path]:
    cache_dir = Path(os.getenv("BOSSZHIBIN_CACHE_DIR", "~/.codex/bosszhibin_cache")).expanduser()
    if not cache_dir.exists():
        return None
    candidates = sorted(cache_dir.glob("session_output*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_sessions(raw: Any, source_path: Path) -> List[Dict[str, Any]]:
    if isinstance(raw, dict) and isinstance(raw.get("candidates"), list):
        return [raw]
    if isinstance(raw, dict) and isinstance(raw.get("sessions"), list):
        return [s for s in raw["sessions"] if isinstance(s, dict)]
    if isinstance(raw, list):
        return [s for s in raw if isinstance(s, dict) and isinstance(s.get("candidates"), list)]
    raise ValueError(f"Unsupported JSON format: {source_path}")


def parse_datetime_to_ms(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None

    local_tz = datetime.now().astimezone().tzinfo
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None and local_tz is not None:
                dt = dt.replace(tzinfo=local_tz)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue

    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None and local_tz is not None:
            dt = dt.replace(tzinfo=local_tz)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None


def normalize_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def slug_job_id(job_name: str) -> str:
    digest = hashlib.sha1(job_name.encode("utf-8")).hexdigest()[:12]
    return f"job_{digest}"


def bool_from_candidate_ai_hit(candidate: Dict[str, Any]) -> Optional[bool]:
    if "ai_skill_hit" in candidate:
        value = candidate.get("ai_skill_hit")
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"true", "1", "yes", "y", "pass"}:
                return True
            if text in {"false", "0", "no", "n", "fail"}:
                return False
    skills = candidate.get("skills")
    if isinstance(skills, list) and skills:
        return True
    return None


def build_candidate_fingerprint(candidate: Dict[str, Any], job_name: str) -> str:
    explicit = str(candidate.get("candidate_fingerprint", "")).strip()
    if explicit:
        return explicit

    platform_id = str(candidate.get("platform_id", "")).strip()
    name = str(candidate.get("name", "")).strip()
    school = str(candidate.get("education_school", "")).strip()
    company = str(candidate.get("current_company", "")).strip()

    base = "|".join([platform_id or name or "unknown", school or "na", company or "na", job_name or "na"])
    return base


def build_trigger_summary(candidate: Dict[str, Any]) -> Dict[str, str]:
    summary = {
        "trigger_school": "pass",
        "trigger_ai_skill": "pass",
        "trigger_company": "pass",
        "trigger_experience": "pass",
    }

    reason = str(candidate.get("skip_reason", "")).strip()
    if "学校" in reason:
        summary["trigger_school"] = "fail"
    if "公司" in reason:
        summary["trigger_company"] = "fail"
    if "分数" in reason:
        summary["trigger_ai_skill"] = "fail"
    if "经验" in reason:
        summary["trigger_experience"] = "fail"

    exp = normalize_number(candidate.get("experience_years"))
    if exp is not None and not (1 <= exp <= 5):
        summary["trigger_experience"] = "fail"

    ai_hit = bool_from_candidate_ai_hit(candidate)
    if ai_hit is False:
        summary["trigger_ai_skill"] = "fail"

    return summary


def build_rule_label(candidate: Dict[str, Any], trigger_summary: Dict[str, str]) -> str:
    if str(candidate.get("action", "")) == "跳过":
        reason = str(candidate.get("skip_reason", "")).strip()
        return f"rejected_{reason}" if reason else "rejected"

    exp = normalize_number(candidate.get("experience_years"))
    if exp is not None and 1 <= exp <= 5:
        return "experienced_1_5y"

    if all(v == "pass" for v in trigger_summary.values()):
        return "qualified_general"
    return "qualified_relaxed"


def build_interaction_fingerprint(candidate_fp: str, action_time: int, action_type: str, job_name: str) -> str:
    raw = f"{candidate_fp}|{action_time}|{action_type}|{job_name}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def filter_fields_for_table(fields: Dict[str, Any], supported_fields: set[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in fields.items():
        if supported_fields and k not in supported_fields:
            continue
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        out[k] = v
    return out


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def compute_funnel(session: Dict[str, Any], job_id: str) -> Dict[str, Any]:
    candidates = session.get("candidates", [])
    total = len(candidates)
    skipped = sum(1 for c in candidates if str(c.get("action", "")).strip() == "跳过")
    contacted = max(total - skipped, 0)
    pass_rate = round((contacted / total), 4) if total else 0.0

    session_date = str(session.get("session_date", "")).strip()
    date_ms = parse_datetime_to_ms(session_date)

    fields: Dict[str, Any] = {
        "date": date_ms,
        "job_id": job_id,
        "job_name": str(session.get("job_name", "")).strip(),
        "tab_name": str(session.get("tab_name", "main")).strip() or "main",
        "seen_count": total,
        "contacted_count": contacted,
        "skipped_count": skipped,
        "pass_rate": pass_rate,
        "daily_quota_hit": bool(session.get("daily_quota_hit", False)),
        "rate_limit_hits": safe_int(session.get("rate_limit_hits", 0)),
        "parse_quality_anomaly": bool(session.get("parse_quality_anomaly", False)),
    }

    # For idempotency when table has this field.
    composite = f"{session_date or 'unknown'}|{job_id}|{fields['tab_name']}"
    fields["funnel_fingerprint"] = composite
    return fields


def build_records(sessions: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    candidate_records: List[Dict[str, Any]] = []
    interaction_records: List[Dict[str, Any]] = []
    funnel_records: List[Dict[str, Any]] = []

    for session in sessions:
        job_name = str(session.get("job_name", "")).strip()
        if not job_name:
            continue
        job_id = str(session.get("job_id", "")).strip() or slug_job_id(job_name)
        session_date = str(session.get("session_date", "")).strip() or datetime.now().strftime("%Y-%m-%d")

        funnel_records.append(compute_funnel(session, job_id))

        for cand in session.get("candidates", []):
            name = str(cand.get("name", "")).strip()
            if not name:
                continue

            action_time_ms = parse_datetime_to_ms(str(cand.get("action_time", "")).strip())
            if action_time_ms is None:
                action_time_ms = parse_datetime_to_ms(session_date)
            if action_time_ms is None:
                action_time_ms = int(time.time() * 1000)

            candidate_fp = build_candidate_fingerprint(cand, job_name)
            trigger = build_trigger_summary(cand)
            rule_label = build_rule_label(cand, trigger)
            action_type = str(cand.get("action", "")).strip() or "unknown"

            company_background = str(cand.get("current_company", "")).strip()
            if cand.get("current_title"):
                company_background = (
                    f"{company_background} / {cand.get('current_title')}" if company_background else str(cand.get("current_title"))
                )

            candidate_fields: Dict[str, Any] = {
                "candidate_fingerprint": candidate_fp,
                "name": name,
                "job_id": job_id,
                "job_name": job_name,
                "school": str(cand.get("education_school", "")).strip(),
                "degree": str(cand.get("education_degree", "")).strip(),
                "experience_years": normalize_number(cand.get("experience_years")),
                "company_background": company_background,
                "ai_skill_hit": bool_from_candidate_ai_hit(cand),
                "rule_label": rule_label,
                "last_action_time": action_time_ms,
                "status": str(cand.get("status", cand.get("outcome", ""))).strip(),
                "platform": str(cand.get("platform", session.get("platform", "BOSS直聘"))).strip(),
                "platform_id": str(cand.get("platform_id", "")).strip(),
                "match_score": normalize_number(cand.get("match_score")),
            }
            candidate_records.append(candidate_fields)

            interaction_fp = build_interaction_fingerprint(candidate_fp, action_time_ms, action_type, job_name)
            summary_parts = [
                f"action={action_type}",
                f"status={cand.get('status', '')}",
                f"outcome={cand.get('outcome', '')}",
            ]
            skip_reason = str(cand.get("skip_reason", "")).strip()
            if skip_reason:
                summary_parts.append(f"skip_reason={skip_reason}")

            interaction_fields: Dict[str, Any] = {
                "interaction_fingerprint": interaction_fp,
                "candidate_fingerprint": candidate_fp,
                "action_time": action_time_ms,
                "action_type": action_type,
                "trigger_school": trigger["trigger_school"],
                "trigger_ai_skill": trigger["trigger_ai_skill"],
                "trigger_company": trigger["trigger_company"],
                "trigger_experience": trigger["trigger_experience"],
                "summary": " | ".join(summary_parts),
                "job_name": job_name,
                "outcome": str(cand.get("outcome", "")).strip(),
                "match_score": normalize_number(cand.get("match_score")),
            }
            interaction_records.append(interaction_fields)

    return candidate_records, interaction_records, funnel_records


def build_key_index(records: List[Dict[str, Any]], key_field: str) -> Dict[str, str]:
    idx: Dict[str, str] = {}
    for item in records:
        fields = item.get("fields", {})
        key = fields.get(key_field)
        if key is None:
            continue
        key_text = str(key).strip()
        if not key_text:
            continue
        idx[key_text] = str(item.get("record_id", ""))
    return idx


def build_funnel_index(records: List[Dict[str, Any]]) -> Dict[str, str]:
    idx: Dict[str, str] = {}
    for item in records:
        fields = item.get("fields", {})
        explicit = str(fields.get("funnel_fingerprint", "")).strip()
        if explicit:
            idx[explicit] = str(item.get("record_id", ""))
            continue

        date_val = str(fields.get("date", "")).strip()
        job_id = str(fields.get("job_id", "")).strip()
        tab_name = str(fields.get("tab_name", "main")).strip() or "main"
        if date_val and job_id:
            idx[f"{date_val}|{job_id}|{tab_name}"] = str(item.get("record_id", ""))
    return idx


def main() -> int:
    args = parse_args()

    input_paths: List[Path] = [Path(p).expanduser() for p in args.inputs]
    if not input_paths:
        default_input = pick_default_input()
        if not default_input:
            print("No input provided and no default session_output*.json found.", file=sys.stderr)
            return 2
        input_paths = [default_input]

    sessions: List[Dict[str, Any]] = []
    load_errors: List[str] = []
    for path in input_paths:
        try:
            raw = load_json(path)
            sessions.extend(normalize_sessions(raw, path))
        except Exception as exc:  # noqa: BLE001
            load_errors.append(f"{path}: {exc}")

    if not sessions:
        print("No valid sessions parsed.", file=sys.stderr)
        if load_errors:
            for err in load_errors:
                print(f"- {err}", file=sys.stderr)
        return 2

    candidate_records, interaction_records, funnel_records = build_records(sessions)

    summary: Dict[str, Any] = {
        "success": True,
        "run_id": f"sync_{int(time.time())}",
        "files": [str(p) for p in input_paths],
        "sessions": len(sessions),
        "prepared": {
            "candidate_master": len(candidate_records),
            "interaction_log": len(interaction_records),
            "job_funnel_daily": len(funnel_records),
        },
        "upserts": {
            "candidate_master": {"created": 0, "updated": 0},
            "interaction_log": {"created": 0, "updated": 0},
            "job_funnel_daily": {"created": 0, "updated": 0},
        },
        "failures": 0,
        "errors": list(load_errors),
    }

    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if args.output:
            Path(args.output).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0

    try:
        cfg = Config.from_env()
        client = FeishuBitableClient(cfg, timeout=args.timeout)

        candidate_fields_supported = client.list_table_field_names(cfg.table_candidate)
        interaction_fields_supported = client.list_table_field_names(cfg.table_interaction)
        funnel_fields_supported = client.list_table_field_names(cfg.table_funnel)

        candidate_existing = build_key_index(client.list_records(cfg.table_candidate), "candidate_fingerprint")
        interaction_existing = build_key_index(client.list_records(cfg.table_interaction), "interaction_fingerprint")
        funnel_existing = build_funnel_index(client.list_records(cfg.table_funnel))

        for fields in candidate_records:
            key = str(fields.get("candidate_fingerprint", "")).strip()
            if not key:
                continue
            payload = filter_fields_for_table(fields, candidate_fields_supported)
            if not payload:
                continue
            try:
                if key in candidate_existing:
                    client.update_record(cfg.table_candidate, candidate_existing[key], payload)
                    summary["upserts"]["candidate_master"]["updated"] += 1
                else:
                    record_id = client.create_record(cfg.table_candidate, payload)
                    candidate_existing[key] = record_id
                    summary["upserts"]["candidate_master"]["created"] += 1
            except Exception as exc:  # noqa: BLE001
                summary["failures"] += 1
                summary["errors"].append(f"candidate_master[{key}]: {exc}")

        for fields in interaction_records:
            key = str(fields.get("interaction_fingerprint", "")).strip()
            if not key:
                continue
            payload = filter_fields_for_table(fields, interaction_fields_supported)
            if not payload:
                continue
            try:
                if key in interaction_existing:
                    client.update_record(cfg.table_interaction, interaction_existing[key], payload)
                    summary["upserts"]["interaction_log"]["updated"] += 1
                else:
                    record_id = client.create_record(cfg.table_interaction, payload)
                    interaction_existing[key] = record_id
                    summary["upserts"]["interaction_log"]["created"] += 1
            except Exception as exc:  # noqa: BLE001
                summary["failures"] += 1
                summary["errors"].append(f"interaction_log[{key}]: {exc}")

        for fields in funnel_records:
            key = str(fields.get("funnel_fingerprint", "")).strip()
            if not key:
                continue
            payload = filter_fields_for_table(fields, funnel_fields_supported)
            if not payload:
                continue

            # Fallback key: use date|job_id|tab_name if funnel_fingerprint not in table.
            effective_key = key
            if key not in funnel_existing and "funnel_fingerprint" not in funnel_fields_supported:
                date_val = str(fields.get("date", "")).strip()
                job_id = str(fields.get("job_id", "")).strip()
                tab_name = str(fields.get("tab_name", "main")).strip() or "main"
                effective_key = f"{date_val}|{job_id}|{tab_name}"

            try:
                if effective_key in funnel_existing:
                    client.update_record(cfg.table_funnel, funnel_existing[effective_key], payload)
                    summary["upserts"]["job_funnel_daily"]["updated"] += 1
                else:
                    record_id = client.create_record(cfg.table_funnel, payload)
                    funnel_existing[effective_key] = record_id
                    summary["upserts"]["job_funnel_daily"]["created"] += 1
            except Exception as exc:  # noqa: BLE001
                summary["failures"] += 1
                summary["errors"].append(f"job_funnel_daily[{effective_key}]: {exc}")

        if summary["failures"] > 0:
            summary["success"] = False

    except Exception as exc:  # noqa: BLE001
        summary["success"] = False
        summary["failures"] += 1
        summary["errors"].append(str(exc))

    result_text = json.dumps(summary, ensure_ascii=False, indent=2)
    print(result_text)

    if args.output:
        Path(args.output).expanduser().write_text(result_text, encoding="utf-8")

    if args.strict and not summary["success"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
