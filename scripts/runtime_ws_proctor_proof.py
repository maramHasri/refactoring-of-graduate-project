"""
One-shot runtime proof for proctoring WebSocket path.
Run while `python run.py` is up. Restores attempt/session afterward.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
from datetime import datetime, timezone

from simple_websocket import Client

from app_factory import create_app
from models import TestAttempt
from models.proctoring import ProctoringEvent, ProctoringSession, ProctoringViolation
from repositories.workspace_repository import MembershipRepository
from repositories.user_repository import UserRepository
from service.session_service import SessionService
from utils.db import db
from utils.enums import ProctoringSessionStatus, TestAttemptStatus


BASE = "127.0.0.1:5000"
# Reuse latest known proctored attempt (will flip to IN_PROGRESS temporarily)
ATTEMPT_ID = 27
TEST_ID = 38
WORKSPACE_ID = 21


def mint_token(user_id: int) -> str:
    access, _refresh, _session = SessionService().create_user_session(user_id=user_id)
    db.session.commit()
    return access


def ws_url(path: str, token: str, workspace_id: int) -> str:
    q = urllib.parse.urlencode({"token": token, "workspace_id": workspace_id})
    return f"ws://{BASE}{path}?{q}"


def main() -> None:
    app = create_app()
    report: dict = {"checks": {}}

    with app.app_context():
        attempt = db.session.get(TestAttempt, ATTEMPT_ID)
        assert attempt is not None, "attempt missing"
        session = (
            db.session.query(ProctoringSession)
            .filter_by(test_attempt_id=ATTEMPT_ID)
            .one_or_none()
        )
        assert session is not None, "proctoring session missing"

        prev_attempt_status = attempt.status
        prev_session_status = session.status
        prev_tab = session.tab_switch_count or 0
        prev_score = session.violation_score or 0
        prev_event_ids = {
            r[0]
            for r in db.session.query(ProctoringEvent.id)
            .filter_by(session_id=session.id)
            .all()
        }
        prev_violation_ids = {
            r[0]
            for r in db.session.query(ProctoringViolation.id)
            .filter_by(session_id=session.id)
            .all()
        }

        # Prepare ACTIVE in-progress state for the proof
        attempt.status = TestAttemptStatus.IN_PROGRESS.value
        attempt.submitted_at = None
        session.status = ProctoringSessionStatus.ACTIVE.value
        session.ended_at = None
        db.session.commit()

        student = UserRepository().get_by_id(attempt.user_id)
        student_token = mint_token(student.id)

        # Teacher = test creator membership user in same workspace
        teacher_m = MembershipRepository().get_by_id(
            attempt.test.created_by_membership_id
        )
        teacher_token = mint_token(teacher_m.user_id)

        teacher_msgs: list[dict] = []
        teacher_ready = threading.Event()
        teacher_done = threading.Event()

        def teacher_loop():
            url = ws_url(
                f"/ws/proctoring/tests/{TEST_ID}/monitor",
                teacher_token,
                WORKSPACE_ID,
            )
            try:
                ws = Client.connect(url)
                teacher_ready.set()
                while not teacher_done.is_set():
                    try:
                        raw = ws.receive(timeout=0.5)
                    except Exception:
                        continue
                    if raw is None:
                        break
                    teacher_msgs.append(json.loads(raw))
                ws.close()
            except Exception as exc:
                report["teacher_connect_error"] = str(exc)
                teacher_ready.set()

        t = threading.Thread(target=teacher_loop, daemon=True)
        t.start()
        if not teacher_ready.wait(10):
            raise RuntimeError("teacher WS failed to become ready")

        student_url = ws_url(
            f"/ws/proctoring/tests/{TEST_ID}/attempts/{ATTEMPT_ID}",
            student_token,
            WORKSPACE_ID,
        )

        # Plain HTTP GET to the same path (no Upgrade) — expect non-101 behavior documented
        import urllib.request

        http_status = None
        try:
            req = urllib.request.Request(
                f"http://{BASE}/ws/proctoring/tests/{TEST_ID}/attempts/{ATTEMPT_ID}"
                f"?token={urllib.parse.quote(student_token)}&workspace_id={WORKSPACE_ID}",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                http_status = resp.status
        except Exception as exc:
            http_status = f"error:{exc}"

        report["checks"]["plain_http_get_status"] = http_status

        ws = Client.connect(student_url)
        first = ws.receive(timeout=10)
        first_msg = json.loads(first)
        report["checks"]["session_started_from_server"] = first_msg.get("type")
        report["session_started_payload_keys"] = list(
            (first_msg.get("payload") or {}).keys()
        )

        # Send tab_switch like BrowserMonitor
        body = json.dumps(
            {
                "type": "tab_switch",
                "payload": {"reason": "runtime_proof", "hidden": True},
            }
        )
        ws.send(body)
        reply = ws.receive(timeout=10)
        reply_msg = json.loads(reply)
        report["checks"]["student_reply_type"] = reply_msg.get("type")
        report["student_reply"] = reply_msg

        time.sleep(1.0)
        teacher_done.set()
        t.join(timeout=3)
        ws.close()

        # DB assertions
        db.session.expire_all()
        session = (
            db.session.query(ProctoringSession)
            .filter_by(test_attempt_id=ATTEMPT_ID)
            .one()
        )
        new_events = (
            db.session.query(ProctoringEvent)
            .filter(
                ProctoringEvent.session_id == session.id,
                ~ProctoringEvent.id.in_(prev_event_ids)
                if prev_event_ids
                else True,
            )
            .order_by(ProctoringEvent.id.asc())
            .all()
        )
        new_violations = (
            db.session.query(ProctoringViolation)
            .filter(
                ProctoringViolation.session_id == session.id,
                ~ProctoringViolation.id.in_(prev_violation_ids)
                if prev_violation_ids
                else True,
            )
            .all()
        )

        report["checks"]["new_events"] = [
            {"id": e.id, "event_type": e.event_type, "source": e.source}
            for e in new_events
        ]
        report["checks"]["tab_switch_websocket"] = any(
            e.event_type == "TAB_SWITCH" and e.source == "WEBSOCKET" for e in new_events
        )
        report["checks"]["violation_created"] = len(new_violations) > 0
        report["checks"]["new_violations"] = [
            {"id": v.id, "type": v.violation_type, "severity": v.severity}
            for v in new_violations
        ]
        report["checks"]["tab_switch_count_delta"] = (
            (session.tab_switch_count or 0) - prev_tab
        )
        report["checks"]["violation_score_delta"] = (
            (session.violation_score or 0) - prev_score
        )

        teacher_types = [m.get("type") for m in teacher_msgs]
        report["checks"]["teacher_message_types"] = teacher_types
        report["checks"]["teacher_got_student_row_updated"] = (
            "student_row_updated" in teacher_types
        )
        report["checks"]["teacher_got_violation_created"] = (
            "violation_created" in teacher_types
        )

        # Restore prior statuses so we don't leave production data dirty
        attempt = db.session.get(TestAttempt, ATTEMPT_ID)
        session = (
            db.session.query(ProctoringSession)
            .filter_by(test_attempt_id=ATTEMPT_ID)
            .one()
        )
        attempt.status = prev_attempt_status
        if prev_attempt_status != TestAttemptStatus.IN_PROGRESS.value:
            attempt.submitted_at = attempt.submitted_at or datetime.now(timezone.utc)
        session.status = prev_session_status
        if prev_session_status != ProctoringSessionStatus.ACTIVE.value:
            session.ended_at = session.ended_at or datetime.now(timezone.utc)
        db.session.commit()
        report["restored"] = {
            "attempt_status": prev_attempt_status,
            "session_status": prev_session_status,
        }

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
