"""예약 알림: CloudWatch Logs 구독 필터(RESERVATION_CREATED) → Slack #mc-reservations."""
import base64
import gzip
import json
import os
import urllib.request

import boto3

_secret_cache = {}


def _webhook_url():
    sid = os.environ["SLACK_WEBHOOK_SECRET_ID"]
    if sid not in _secret_cache:
        sm = boto3.client("secretsmanager")
        _secret_cache[sid] = sm.get_secret_value(SecretId=sid)["SecretString"].strip()
    return _secret_cache[sid]


def _parse(line):
    # 예: RESERVATION_CREATED id=123 vet=김수의 time=2026-09-20T10:00 owner=홍*동 pet=초코
    fields = {}
    for tok in line.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            fields[k] = v
    return fields


def handler(event, _context):
    payload = json.loads(gzip.decompress(base64.b64decode(event["awslogs"]["data"])))
    base = os.environ.get("APP_BASE_URL", "")
    for e in payload.get("logEvents", []):
        f = _parse(e["message"])
        owner_id = f.get("owner_id", "")
        link = f"{base}/owners/{owner_id}" if owner_id else base
        text = (
            f":calendar: *새 예약* — 수의사 *{f.get('vet', '-')}* · {f.get('time', '-')} · "
            f"반려동물 {f.get('pet', '-')} (보호자 {f.get('owner', '-')})\n"
            f"<{link}|예약 확인 (로그인 필요)>"
        )
        body = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(_webhook_url(), data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5).read()
    return {"ok": True}
