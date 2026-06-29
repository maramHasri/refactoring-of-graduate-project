# توثيق وتنفيذ API توليد أسئلة الذكاء الاصطناعي

## المسار

- **Endpoint:** `POST /tests/{test_id}/questions/ai-generate`
- **الهدف:** توليد أسئلة بواسطة AI وإضافتها مباشرة إلى الاختبار كسجلات `TestQuestion` من نوع `AI`.

---

## النتيجة المختصرة: هل الميزة مطبقة فعليا؟

**نعم، الميزة مطبقة فعليا في الباكيند.**

الدليل من الكود:

1. يوجد Route فعلي للمسار داخل `router/test_routes.py`.
2. يوجد Schema للتحقق من المدخلات داخل `schemas/test_schema.py`.
3. يوجد Service method ينفذ منطق التوليد والحفظ داخل `service/test_service.py`.
4. يوجد AI provider integration (Gemini / Qwen / HuggingFace / Placeholder) داخل `service/ai_question_service.py`.
5. يوجد إرجاع استجابة `201` تشمل `questions` و `count` و `ai_model`.

---

## كيف يعمل الطلب داخليا (Flow)

1. **الراوتر** يستقبل الطلب:
   - `POST /tests/{test_id}/questions/ai-generate`
   - يحتاج عضوية Workspace عبر `@require_workspace_membership`.

2. **التحقق من Body** عبر `AIGenerateQuestionsSchema`:
   - `count`: مطلوب، بين 1 و 50
   - `type_code`: افتراضي `MCQ`
   - `difficulty`: اختياري (`EASY|MEDIUM|HARD`)
   - `topics`: قائمة نصوص اختيارية
   - `learning_objectives`: قائمة نصوص اختيارية
   - `additional_instructions`: نص اختياري

3. **التحقق من صلاحية الاختبار**:
   - يجب أن يكون الاختبار موجودا داخل نفس الـ workspace.
   - يجب أن يكون في حالة `DRAFT` (لا يسمح بالتعديل في الحالات الأخرى).
   - يجب أن يكون للاختبار مادة (`subject`) لأن التوليد يعتمد عليها.

4. **بناء طلب AI**:
   - يتم تجهيز `subject_name` و `exam_name` وباقي مدخلاتك.
   - يتم إنشاء prompt منظم يطلب JSON محدد الشكل.

5. **اختيار مزود AI**:
   - حسب `AI_QUESTION_PROVIDER`:
     - `gemini`
     - `qwen`
     - `huggingface`
     - `placeholder`
     - `auto` (ترتيب تلقائي)

6. **تطبيع المخرجات**:
   - النظام يتأكد أن الرد JSON صالح ويحتوي `questions`.
   - يتأكد من العدد المطلوب (`count`).
   - يحولها إلى payload داخلي موحد.

7. **الحفظ في قاعدة البيانات**:
   - كل سؤال يتحول إلى `TestQuestion` snapshot من نوع `AI`.
   - يتم `commit` ثم إرجاع النتيجة.

---

## شكل الطلب (Request) الواقعي

```json
{
  "count": 5,
  "type_code": "MCQ",
  "difficulty": "MEDIUM",
  "topics": ["Network Security", "Cryptography"],
  "learning_objectives": ["Understand AES", "Differentiate symmetric vs asymmetric encryption"],
  "additional_instructions": "Write clear exam-ready questions in Arabic."
}
```

---

## شكل الاستجابة المتوقعة (201)

```json
{
  "message": "AI questions added",
  "questions": [
    {
      "id": 123,
      "test_id": 14,
      "question_id": null,
      "source_type": "AI",
      "source_bank_id": null,
      "points": 1.0,
      "status": "ACTIVE",
      "snapshot_question_text": "...",
      "snapshot_explanation": "...",
      "snapshot_type_code": "MCQ",
      "snapshot_topic_id": null,
      "snapshot_topic_name": null,
      "snapshot_difficulty": "MEDIUM",
      "snapshot_points": 1.0,
      "snapshot_choices": [
        { "body": "Option A", "is_correct": true, "order_index": 0 },
        { "body": "Option B", "is_correct": false, "order_index": 1 }
      ],
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "count": 5,
  "ai_model": "qwen:...",
  "subject_name": "Cyber Security"
}
```

---

## Headers المطلوبة

- `Authorization: Bearer <JWT>`
- `X-Workspace-Id: <workspace_id>`
- `Content-Type: application/json`

---

## إعدادات البيئة المرتبطة بالميزة

من `config/settings.py` الميزة تعتمد على:

- `AI_QUESTION_PROVIDER` (`auto|gemini|qwen|huggingface|placeholder`)
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `DASHSCOPE_API_KEY` (Qwen عبر DashScope)
- `HF_TOKEN` و `HF_QWEN_MODEL` (Qwen/HF)
- `AI_FALLBACK_TO_PLACEHOLDER`

---

## سلوك مهم يجب معرفته

1. **Fallback موجود**:
   - إذا فشل مزود AI (بحسب نوع الخطأ والإعدادات)، يمكن الرجوع تلقائيا إلى `placeholder-local-draft`.

2. **الأسئلة تحفظ كسنابشوت**:
   - لا ترتبط بـ `question_id` من بنك أسئلة.
   - لذلك `question_id = null` و `source_bank_id = null`.

3. **النوع مهم**:
   - صحة `choices` تتحقق حسب `type_code` لاحقا ضمن فحص أنواع الأسئلة.

4. **التعديل مسموح فقط في DRAFT**:
   - أي محاولة إضافة AI في اختبار منشور/مغلق سترجع خطأ تحقق.

---

## كيف تتأكد عمليا أنها تعمل عندك الآن؟

1. تأكد من وجود اختبار بحالة `DRAFT` في نفس الـ workspace.
2. نفذ الطلب على المسار.
3. إذا رجعت `201` وفيها:
   - `count > 0`
   - `source_type = "AI"` داخل العناصر
   - `ai_model` موجود
   فهذا يعني الميزة تعمل فعليا End-to-End.
4. للتحقق الإضافي:
   - نفذ `GET /tests/{test_id}` وتأكد أن الأسئلة المضافة ظهرت ضمن `questions`.

---

## أسباب فشل شائعة

- `Test not found in this workspace` -> الـ `X-Workspace-Id` لا يطابق الاختبار.
- `Questions can only be modified while test is DRAFT` -> حالة الاختبار ليست `DRAFT`.
- أخطاء مفاتيح AI/صلاحيات المزود -> مشكلة إعداد مفاتيح/مزود.
- `Question type 'X' is not configured. Run flask seed.` -> أنواع الأسئلة غير مزروعة في قاعدة البيانات.

---

## خلاصة تنفيذية

ميزة `POST /tests/{test_id}/questions/ai-generate` **موجودة ومربوطة بالكامل** (Route + Validation + Service + Provider + DB persist + Response).
أي أنك **طبقتها فعليا** على مستوى الباكيند، وليست مجرد توثيق أو stub.
