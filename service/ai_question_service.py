"""
AI-backed exam question generation.

Providers (AI_QUESTION_PROVIDER):
  - gemini       — Google Gemini (GEMINI_API_KEY)
  - qwen         — Alibaba DashScope (DASHSCOPE_API_KEY) or HuggingFace Qwen (HF_TOKEN)
  - huggingface  — HuggingFace Inference router (HF_TOKEN + HF_QWEN_MODEL)
  - placeholder  — local draft questions (no external API)
  - auto         — first available: gemini → qwen (dashscope) → huggingface → placeholder
"""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any

from flask import current_app

from service.exceptions import ValidationError

logger = logging.getLogger(__name__)

PLACEHOLDER_MODEL = "placeholder-local-draft"


class AIQuestionService:
    def generate_questions(self, *, request_body: dict) -> tuple[list[dict], str]:
        """Return (question_payloads, model_name)."""
        provider = self._resolve_provider()
        if provider is None:
            return self._generate_placeholder(request_body), PLACEHOLDER_MODEL

        kind, label, kwargs = provider
        try:
            if kind == "gemini":
                questions = self._generate_via_gemini(
                    request_body=request_body, **kwargs
                )
                return questions, label
            if kind == "openai_chat":
                questions = self._generate_via_openai_chat(
                    request_body=request_body, **kwargs
                )
                return questions, label
            raise ValidationError(f"Unsupported AI provider: {kind}")
        except ValidationError as exc:
            if self._should_fallback_to_placeholder(exc):
                logger.warning(
                    "AI provider %s failed (%s); using placeholder fallback",
                    label,
                    exc,
                )
                return self._generate_placeholder(request_body), PLACEHOLDER_MODEL
            raise
        except Exception as exc:
            logger.exception("AI question generation failed (%s)", label)
            if self._should_fallback_to_placeholder(exc):
                return self._generate_placeholder(request_body), PLACEHOLDER_MODEL
            raise ValidationError(f"AI question generation failed: {exc}") from exc

    def _resolve_provider(self) -> tuple[str, str, dict] | None:
        cfg = current_app.config
        mode = (cfg.get("AI_QUESTION_PROVIDER") or "auto").strip().lower()

        gemini_key = (cfg.get("GEMINI_API_KEY") or "").strip()
        gemini_model = cfg.get("GEMINI_MODEL", "gemini-2.5-flash")
        dashscope_key = (cfg.get("DASHSCOPE_API_KEY") or "").strip()
        qwen_model = cfg.get("QWEN_MODEL", "qwen-turbo")
        hf_token = (cfg.get("HF_TOKEN") or "").strip()
        hf_model = cfg.get("HF_QWEN_MODEL", "Qwen/Qwen2.5-7B-Instruct")

        if mode in ("placeholder", "off", "none"):
            return None

        if mode == "gemini":
            if not gemini_key:
                raise ValidationError("GEMINI_API_KEY is required when AI_QUESTION_PROVIDER=gemini")
            return (
                "gemini",
                gemini_model,
                {"api_key": gemini_key, "model": gemini_model},
            )

        if mode == "qwen":
            if dashscope_key:
                return (
                    "openai_chat",
                    f"qwen:{qwen_model}",
                    {
                        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                        "api_key": dashscope_key,
                        "model": qwen_model,
                        "provider_label": "Qwen DashScope",
                    },
                )
            if hf_token:
                return (
                    "openai_chat",
                    hf_model,
                    {
                        "base_url": "https://router.huggingface.co/v1",
                        "api_key": hf_token,
                        "model": hf_model,
                        "provider_label": "Qwen via HuggingFace",
                    },
                )
            raise ValidationError(
                "Qwen provider requires DASHSCOPE_API_KEY or HF_TOKEN in environment"
            )

        if mode == "huggingface":
            if not hf_token:
                raise ValidationError("HF_TOKEN is required when AI_QUESTION_PROVIDER=huggingface")
            return (
                "openai_chat",
                hf_model,
                {
                    "base_url": "https://router.huggingface.co/v1",
                    "api_key": hf_token,
                    "model": hf_model,
                    "provider_label": "HuggingFace",
                },
            )

        # auto
        if gemini_key:
            return (
                "gemini",
                gemini_model,
                {"api_key": gemini_key, "model": gemini_model},
            )
        if dashscope_key:
            return (
                "openai_chat",
                f"qwen:{qwen_model}",
                {
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "api_key": dashscope_key,
                    "model": qwen_model,
                    "provider_label": "Qwen DashScope",
                },
            )
        if hf_token:
            return (
                "openai_chat",
                hf_model,
                {
                    "base_url": "https://router.huggingface.co/v1",
                    "api_key": hf_token,
                    "model": hf_model,
                    "provider_label": "Qwen via HuggingFace",
                },
            )
        return None

    def _should_fallback_to_placeholder(self, exc: BaseException) -> bool:
        if not current_app.config.get("AI_FALLBACK_TO_PLACEHOLDER"):
            return False
        message = str(exc)
        return any(
            token in message
            for token in (
                "401",
                "403",
                "429",
                "404",
                "RESOURCE_EXHAUSTED",
                "NOT_FOUND",
                "quota",
                "Invalid username or password",
                "Insufficient permissions",
            )
        )

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
        raw = self._http_post_json(url, payload, headers={"Content-Type": "application/json"})
        text = self._extract_gemini_text(raw)
        return self._normalize_questions_from_json(text, request_body)

    def _generate_via_openai_chat(
        self,
        *,
        request_body: dict,
        base_url: str,
        api_key: str,
        model: str,
        provider_label: str,
    ) -> list[dict]:
        prompt = self.build_prompt(request_body)
        url = f"{base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        }
        raw = self._http_post_json(
            url,
            payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            text = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValidationError(f"Unexpected {provider_label} response format") from exc
        if not isinstance(text, str) or not text.strip():
            raise ValidationError(f"{provider_label} returned empty content")
        return self._normalize_questions_from_json(text, request_body)

    def _http_post_json(
        self, url: str, payload: dict, *, headers: dict[str, str]
    ) -> dict:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            label = "API"
            if "generativelanguage.googleapis.com" in url:
                label = "Gemini API"
            elif "huggingface.co" in url:
                label = "HuggingFace Inference"
                if exc.code in (401, 403):
                    detail = (
                        f"{detail} — Check HF_TOKEN: use a fine-grained token with "
                        '"Make calls to Inference Providers" permission and remaining credits. '
                        "Or set AI_QUESTION_PROVIDER=placeholder in .env for local testing."
                    )
            raise ValidationError(f"{label} error ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise ValidationError(f"Could not reach AI API: {exc.reason}") from exc

    def _normalize_questions_from_json(
        self, text: str, request_body: dict
    ) -> list[dict]:
        parsed = self._parse_json_payload(text)
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

    @staticmethod
    def _parse_json_payload(text: str) -> dict:
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", stripped)
            if not match:
                raise ValidationError("AI response was not valid JSON") from None
            return json.loads(match.group(0))

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
