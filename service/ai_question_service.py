"""
AI-backed exam question generation.

Uses Google Gemini when GEMINI_API_KEY is configured; otherwise returns
deterministic placeholder content (same validation pipeline).
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from flask import current_app

from service.exceptions import ValidationError

logger = logging.getLogger(__name__)

PLACEHOLDER_MODEL = "placeholder-local-draft"


class AIQuestionService:
    def generate_questions(self, *, request_body: dict) -> tuple[list[dict], str]:
        """
        Return (question_payloads, model_name).
        Each payload matches the manual-question create shape.
        """
        api_key = (current_app.config.get("GEMINI_API_KEY") or "").strip()
        model = current_app.config.get("GEMINI_MODEL", "gemini-2.0-flash")

        if api_key:
            try:
                return self._generate_via_gemini(
                    request_body=request_body,
                    api_key=api_key,
                    model=model,
                ), model
            except ValidationError:
                raise
            except Exception as exc:
                logger.exception("Gemini question generation failed")
                raise ValidationError(f"AI question generation failed: {exc}") from exc

        return self._generate_placeholder(request_body), PLACEHOLDER_MODEL

    def build_request_body(
        self,
        *,
        subject_name: str,
        exam_name: str,
        count: int,
        type_code: str,
        difficulty: str | None,
        topics: list[str],
        learning_objectives: list[str],
        additional_instructions: str | None,
    ) -> dict[str, Any]:
        return {
            "subject_name": subject_name,
            "exam_name": exam_name,
            "count": count,
            "type_code": type_code,
            "difficulty": difficulty,
            "topics": topics,
            "learning_objectives": learning_objectives,
            "additional_instructions": additional_instructions,
        }

    def build_prompt(self, request_body: dict) -> str:
        topics = request_body.get("topics") or []
        objectives = request_body.get("learning_objectives") or []
        return (
            "You are an exam question writer for edu_forms.\n\n"
            f"Generate exactly {request_body['count']} assessment questions.\n\n"
            f"Subject: {request_body['subject_name']}\n"
            f"Exam title: {request_body['exam_name']}\n"
            f"Question type: {request_body['type_code']}\n"
            f"Difficulty: {request_body.get('difficulty') or 'MIXED'}\n"
            f"Topics: {', '.join(topics) if topics else 'general topics for this subject'}\n"
            f"Learning objectives: {', '.join(objectives) if objectives else 'core concepts'}\n"
            f"Additional instructions: {request_body.get('additional_instructions') or 'none'}\n\n"
            "Return ONLY valid JSON with this shape:\n"
            "{\n"
            '  "questions": [\n'
            "    {\n"
            '      "body": "question text",\n'
            '      "explanation": "brief explanation or null",\n'
            '      "difficulty": "EASY|MEDIUM|HARD or null",\n'
            '      "choices": [\n'
            '        {"body": "choice text", "is_correct": true, "order_index": 0}\n'
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            f"- Every question must be clearly tied to the subject \"{request_body['subject_name']}\".\n"
            "- For MCQ include 4 choices with exactly one correct answer.\n"
            "- For MULTI_SELECT include 4 choices with one or more correct answers.\n"
            "- For TRUE_FALSE include True and False with one correct answer.\n"
            "- For ESSAY use an empty choices array.\n"
        )

    def _generate_via_gemini(
        self, *, request_body: dict, api_key: str, model: str
    ) -> list[dict]:
        prompt = self.build_prompt(request_body)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.7,
            },
        }
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ValidationError(f"Gemini API error ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise ValidationError(f"Could not reach Gemini API: {exc.reason}") from exc

        text = self._extract_gemini_text(raw)
        parsed = json.loads(text)
        questions = parsed.get("questions")
        if not isinstance(questions, list) or not questions:
            raise ValidationError("AI response did not include a questions array")

        expected = int(request_body["count"])
        if len(questions) < expected:
            raise ValidationError(
                f"AI returned {len(questions)} question(s), expected {expected}"
            )

        type_code = request_body["type_code"]
        default_difficulty = request_body.get("difficulty")
        normalized: list[dict] = []
        for idx, item in enumerate(questions[:expected]):
            if not isinstance(item, dict):
                raise ValidationError(f"AI question #{idx + 1} is not an object")
            body = (item.get("body") or "").strip()
            if not body:
                raise ValidationError(f"AI question #{idx + 1} is missing body text")
            choices = item.get("choices")
            if choices is None:
                choices = []
            normalized.append(
                {
                    "type_code": type_code,
                    "body": body,
                    "explanation": item.get("explanation"),
                    "points": 1,
                    "difficulty": item.get("difficulty") or default_difficulty,
                    "choices": choices,
                }
            )
        return normalized

    def _extract_gemini_text(self, raw: dict) -> str:
        try:
            parts = raw["candidates"][0]["content"]["parts"]
            return "".join(part.get("text", "") for part in parts).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ValidationError("Unexpected Gemini response format") from exc

    def _generate_placeholder(self, request_body: dict) -> list[dict]:
        count = int(request_body["count"])
        type_code = request_body["type_code"]
        subject_name = request_body["subject_name"]
        topics = request_body.get("topics") or []
        objectives = request_body.get("learning_objectives") or []
        difficulty = request_body.get("difficulty")
        instructions = request_body.get("additional_instructions")

        default_choices = self._default_choices_for_type(type_code)
        payloads: list[dict] = []
        for idx in range(count):
            topic_label = (
                topics[idx % len(topics)]
                if topics
                else f"topic in {subject_name}"
            )
            objective_label = (
                objectives[idx % len(objectives)] if objectives else "core concept"
            )
            payloads.append(
                {
                    "type_code": type_code,
                    "body": (
                        f"[{subject_name}] {topic_label}: {objective_label} "
                        f"(draft #{idx + 1})"
                    ),
                    "explanation": instructions,
                    "points": 1,
                    "difficulty": difficulty,
                    "choices": default_choices,
                }
            )
        return payloads

    @staticmethod
    def _default_choices_for_type(type_code: str) -> list[dict]:
        normalized = (type_code or "").strip().upper()
        if normalized == "TRUE_FALSE":
            return [
                {"body": "True", "is_correct": True, "order_index": 0},
                {"body": "False", "is_correct": False, "order_index": 1},
            ]
        if normalized in ("MCQ", "MULTI_SELECT"):
            return [
                {"body": "Option A", "is_correct": True, "order_index": 0},
                {"body": "Option B", "is_correct": False, "order_index": 1},
            ]
        return []
