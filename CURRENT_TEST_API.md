# توثيق APIs الامتحانات — السلوك الحالي للباكيند

> **آخر تحديث:** يعكس هذا الملف الكود الفعلي في المشروع (`router/test_routes.py`, `router/attempt_routes.py`, `router/proctoring_routes.py`).
>
> **Base URL:** جميع المسارات تحت `/tests` ما لم يُذكر خلاف ذلك.
>
> **Swagger:** `/apidocs/`

---

## جدول المحتويات

1. [المصادقة والصلاحيات](#1-المصادقة-والصلاحيات)
2. [دورة حياة الاختبار](#2-دورة-حياة-الاختبار)
3. [مفهوم Snapshot للأسئلة](#3-مفهوم-snapshot-للأسئلة)
4. [الكائنات المشتركة في الاستجابة](#4-الكائنات-المشتركة-في-الاستجابة)
5. [APIs المعلّم — من الإنشاء إلى النشر](#5-apis-المعلّم--من-الإنشاء-إلى-النشر)
6. [APIs الطالب — المحاولات](#6-apis-الطالب--المحاولات)
7. [APIs المراقبة Proctoring](#7-apis-المراقبة-proctoring)
8. [أنواع الأسئلة والإجابات](#8-أنواع-الأسئلة-والإجابات)
9. [سيناريو عمل كامل](#9-سيناريو-عمل-كامل)
10. [قيود وسلوك غير مُنفَّذ بعد](#10-قيود-وسلوك-غير-منفّذ-بعد)

---

## 1. المصادقة والصلاحيات

### Headers المطلوبة

| Header | مطلوب؟ | الغرض |
|--------|--------|--------|
| `Authorization: Bearer <JWT>` | نعم | هوية المستخدم |
| `X-Workspace-Id: <id>` | نعم (لجميع `/tests/*`) | تحديد مساحة العمل (المؤسسة/المعلّم المستقل) |
| `Content-Type: application/json` | لطلبات JSON | — |

### من يملك ماذا؟

| الدور | إنشاء/تعديل اختبار | إضافة أسئلة | نشر/إغلاق | عرض محاولات الطلاب | بدء محاولة |
|-------|-------------------|-------------|-----------|-------------------|------------|
| منشئ الاختبار | ✅ | ✅ (DRAFT) | ✅ | ✅ | — |
| Admin المساحة | ✅ | ✅ | ✅ | ✅ | — |
| معلّم المادة | ✅ | ✅ | ✅ | ✅ | — |
| طالب مسجّل في المادة | — | — | — | — | ✅ |
| Admin (كطالب تجريبي) | — | — | — | — | ✅* |

\* Admin يرى الاختبارات المنشورة في `GET /tests/available` لكن بدء المحاولة يتطلب صلاحية الطالب على المادة.

---

## 2. دورة حياة الاختبار

```
DRAFT ──► SCHEDULED ──► PUBLISHED ──► CLOSED ──► ARCHIVED
  │            │              │
  │            │              └── publish-now (مباشرة من DRAFT أو SCHEDULED)
  │            └── schedule-publication (publish_at في المستقبل)
  └── التعديل والأسئلة مسموحان هنا فقط
```

| الحالة | المعنى | متى تُعيَّن |
|--------|--------|-------------|
| `DRAFT` | مسودة — قابلة للتعديل | عند `POST /tests` |
| `SCHEDULED` | مجدول للنشر | `POST .../schedule-publication` |
| `PUBLISHED` | منشور — الطلاب يمكنهم البدء | `POST .../publish-now` أو المهمة الخلفية عند حلول `scheduled_publish_at` |
| `CLOSED` | مغلق — لا محاولات جديدة | `POST .../close` |
| `ARCHIVED` | مؤرشف | `POST .../archive` |

### قواعد زمنية للطالب (عند بدء المحاولة)

- الاختبار يجب أن يكون `PUBLISHED`.
- إذا وُجد `starts_at`: لا يبدأ الطالب قبل هذا الوقت.
- إذا وُجد `entry_window_minutes` مع `starts_at`: يُغلق باب الدخول بعد `starts_at + entry_window_minutes`.
- إذا وُجد `duration_minutes`: تُحسب `expires_at` للمحاولة = وقت البدء + المدة.

### النشر التلقائي للمجدول

مهمة خلفية (`jobs/scheduled_test_publisher.py`) تفحص كل **~5 ثوانٍ** (قابلة للتعديل عبر `SCHEDULED_TEST_PUBLISH_INTERVAL_SECONDS`) الاختبارات `SCHEDULED` التي مرّ `scheduled_publish_at` وتنشرها تلقائياً.

**التوقيت:** كل أوقات الجدولة والنشر تستخدم **`APP_TIMEZONE`** من `.env` (افتراضي `Asia/Damascus`). أرسل وقتًا محليًا بدون `Z`، مثل `"2026-06-29T08:00:00"`.

يمكن تشغيلها يدوياً: `flask publish-due-tests`

---

## 3. مفهوم Snapshot للأسئلة

عند إضافة سؤال للاختبار يُنشأ صف في `test_questions` يحتوي **نسخة ثابتة** من السؤال:

- نص السؤال، الخيارات، الدرجة، النوع، الموضوع… تُخزَّن في أعمدة `snapshot_*`.
- تعديل السؤال الأصلي في بنك الأسئلة **لا يغيّر** الاختبار المنشور.
- الطالب يجيب على `test_question_id` (اللقطة) وليس `question_id` من البنك.

**مصادر الأسئلة (`source_type`):**

| القيمة | المصدر |
|--------|--------|
| `MANUAL` | إدخال يدوي |
| `QUESTION_BANK` | من بنك أسئلة |
| `RANDOM_FROM_BANK` | اختيار عشوائي |
| `AI` | توليد بالذكاء الاصطناعي |
| `IMPORT` | استيراد CSV |

---

## 4. الكائنات المشتركة في الاستجابة

### 4.1 كائن `test` (من `serialize_test`)

يظهر في معظم استجابات المعلّم.

```json
{
  "test_id": 5,
  "name": "امتحان الفصل الأول",
  "slug": "امتحان-الفصل-الاول",
  "description": "وصف اختياري",
  "grading_mode": "AUTO",
  "subject_id": 1,
  "subject_name": "رياضيات",
  "status": "DRAFT",
  "total_score": 100,
  "passing_score": 50,
  "auto_distribute_scores": false,
  "scoring_config": null,
  "settings_config": { "proctoring": { "enabled": true } },
  "availability_time_mode": "SCHEDULED",
  "starts_at": "2026-06-20T09:00:00+00:00",
  "duration_minutes": 60,
  "entry_window_minutes": 30,
  "created_by_membership_id": 12,
  "published_at": null,
  "scheduled_publish_at": null,
  "closed_at": null,
  "archived_at": null,
  "created_at": "2026-06-17T10:00:00+00:00",
  "updated_at": "2026-06-17T11:00:00+00:00"
}
```

| الحقل | الغرض |
|-------|--------|
| `test_id` | المعرف الفريد |
| `name` | اسم الاختبار |
| `slug` | معرّف URL فريد على مستوى المنصة (يُولَّد تلقائياً من الاسم عند الإنشاء) |
| `description` | وصف للمعلّم/الطالب |
| `grading_mode` | نص حر (مثل `AUTO`) — **غير مُطبَّق بقوة** في التصحيح حالياً |
| `subject_id` / `subject_name` | المادة المرتبطة |
| `status` | `DRAFT` \| `SCHEDULED` \| `PUBLISHED` \| `CLOSED` \| `ARCHIVED` |
| `total_score` | الدرجة الكلية المتوقعة |
| `passing_score` | درجة النجاح (يجب ≤ `total_score`) |
| `auto_distribute_scores` | يُعيَّن عند الإنشاء فقط — **لا يُحدَّث عبر PATCH** |
| `scoring_config` | JSON اختياري — **يُخزَّن فقط**، لا يؤثر على التصحيح حالياً |
| `settings_config` | JSON — الجزء المفعّل: `proctoring.enabled` |
| `availability_time_mode` | `SCHEDULED` \| `FLEXIBLE` |
| `starts_at` | وقت فتح الامتحان (توقيت محلي `APP_TIMEZONE`) |
| `duration_minutes` | مدة المحاولة بالدقائق |
| `entry_window_minutes` | دقائق السماح بالدخول بعد `starts_at` |
| `published_at` | وقت النشر الفعلي |
| `scheduled_publish_at` | وقت النشر المجدول |
| `closed_at` / `archived_at` | طوابع الإغلاق والأرشفة |

### 4.2 كائن `question` (لقطة اختبار — `serialize_test_question`)

```json
{
  "id": 42,
  "test_id": 5,
  "question_id": 101,
  "source_type": "QUESTION_BANK",
  "source_bank_id": 3,
  "points": 5,
  "status": "ACTIVE",
  "snapshot_question_text": "ما ناتج 2+2؟",
  "snapshot_explanation": "الجمع البسيط",
  "snapshot_type_code": "MCQ",
  "snapshot_topic_id": 2,
  "snapshot_topic_name": "الجبر",
  "snapshot_difficulty": "EASY",
  "snapshot_points": 5,
  "snapshot_choices": [
    { "id": 1, "body": "3", "is_correct": false, "order_index": 0 },
    { "id": 2, "body": "4", "is_correct": true, "order_index": 1 }
  ],
  "created_at": "...",
  "updated_at": "..."
}
```

| الحقل | الغرض |
|-------|--------|
| `id` | `test_question_id` — يُستخدم في الإجابات والتعديل |
| `question_id` | مرجع السؤال الأصلي في البنك (قد يكون `null` لليدوي/AI/عشوائي) |
| `source_type` | مصدر اللقطة (انظر الجدول أعلاه) |
| `source_bank_id` | بنك المصدر إن وُجد |
| `points` | درجة السؤال في هذا الاختبار |
| `snapshot_*` | النسخة الثابتة المعروضة للطالب |

---

## 5. APIs المعلّم — من الإنشاء إلى النشر

### 5.1 `POST /tests` — إنشاء اختبار (الخطوة 1)

**الحالة الناتجة:** `DRAFT`

**Request (الحد الأدنى — الحقول الافتراضية تُطبَّق تلقائياً):**

```json
{
  "name": "امتحان منتصف الفصل",
  "subject_id": 1
}
```

**Request (كامل مع تجاوز الافتراضيات):**

```json
{
  "name": "امتحان منتصف الفصل",
  "description": "يشمل الفصول 1-3",
  "subject_id": 1,
  "duration_minutes": 90,
  "total_score": 100,
  "passing_score": 50,
  "auto_distribute_scores": false
}
```

| الحقل | مطلوب؟ | الافتراضي | الغرض |
|-------|--------|-----------|--------|
| `name` | نعم | — | اسم الاختبار (1–255 حرف) |
| `subject_id` | نعم | — | المادة — يجب أن يكون المعلّم مصرحاً عليها |
| `description` | لا | `null` | وصف |
| `duration_minutes` | لا | **`30`** | مدة المحاولة بالدقائق (≥ 1) |
| `total_score` | لا | **`100`** | الدرجة الكلية (≥ 0) |
| `passing_score` | لا | **`50`** | درجة النجاح (≥ 0) |
| `auto_distribute_scores` | لا | `false` | توزيع تلقائي للدرجات (غير مُطبَّق بالكامل بعد) |

**Response `201`:**

```json
{
  "message": "Test created successfully",
  "test": {
    "test_id": 8,
    "name": "Midterm Exam",
    "description": "Covers chapters 1-5",
    "subject_id": 24,
    "subject_name": "Cyber Security",
    "duration_minutes": 30,
    "total_score": 100,
    "passing_score": 50,
    "auto_distribute_scores": true,
    "status": "DRAFT",
    "slug": "midterm-exam",
    "created_at": "2026-06-17T10:00:00+00:00"
  }
}
```

> لا يُرجع حقول الإعدادات المتقدمة غير المُعيَّنة بعد الإنشاء (`scoring_config`, `settings_config`, `published_at`, …). استخدم `GET /tests/{test_id}` للتفاصيل الكاملة.

---

### 5.2 `GET /tests/my` — قائمة اختباراتي

**Request:** بدون body.

**Response `200`:**

```json
{
  "tests": [ { "...": "كائن test" } ],
  "count": 3
}
```

يعيد الاختبارات التي أنشأها المستخدم الحالي (`created_by_membership_id`).

---

### 5.3 `GET /tests/{test_id}` — تفاصيل الاختبار + الأسئلة

**Response `200`:** كائن `test` مباشرة في الجذر **مع** مفتاح `questions`:

```json
{
  "test_id": 5,
  "name": "...",
  "status": "DRAFT",
  "...": "...",
  "questions": [ { "...": "كائن question لقطة" } ]
}
```

---

### 5.4 `PATCH /tests/{test_id}` — تحديث الإعدادات

**شرط:** `status` = `DRAFT` فقط.

**Request (جزئي — أرسل ما تريد تغييره):**

```json
{
  "name": "امتحان محدّث",
  "description": "وصف جديد",
  "grading_mode": "AUTO",
  "total_score": 100,
  "passing_score": 60,
  "duration_minutes": 75,
  "availability_time_mode": "SCHEDULED",
  "starts_at": "2026-06-20T09:00:00Z",
  "entry_window_minutes": 30,
  "scoring_config": {},
  "settings_config": {
    "proctoring": { "enabled": true }
  }
}
```

| الحقل | الغرض |
|-------|--------|
| `scoring_config` | JSON اختياري — تخزين فقط حالياً |
| `settings_config` | JSON — `proctoring.enabled: true` يفعّل المراقبة عند بدء المحاولة |

> **تنبيه:** إرسال `scoring_config` أو `settings_config` **يستبدل** القيمة بالكامل (ليس دمجاً).

**Response `200`:**

```json
{
  "message": "Test updated",
  "test": {
    "test_id": 8,
    "name": "امتحان محدّث",
    "slug": "امتحان-محدث",
    "status": "DRAFT",
    "settings_config": { "proctoring": { "enabled": true } },
    "scheduled_publish_at": null,
    "updated_at": "..."
  }
}
```

> لا يُرجع `published_at` ولا `closed_at` ولا `archived_at` — تلك الحقول تظهر فقط بعد النشر/الإغلاق/الأرشفة عبر `GET /tests/{test_id}`.

---

### 5.5 إضافة الأسئلة (كلها تتطلب `DRAFT`)

#### `POST /tests/{test_id}/questions` — من بنك (بـ question_ids مباشرة)

```json
{
  "question_ids": [10, 11, 12],
  "source_type": "QUESTION_BANK"
}
```

| الحقل | الغرض |
|-------|--------|
| `question_ids` | معرفات أسئلة من workspace الحالي |
| `source_type` | `AI` \| `QUESTION_BANK` \| `RANDOM_FROM_BANK` \| `MANUAL` \| `IMPORT` — افتراضي `QUESTION_BANK` |

**Response `201`:**

```json
{
  "message": "Questions added to test",
  "questions": [ "...لقطات..." ],
  "count": 3
}
```

---

#### `POST /tests/{test_id}/questions/from-bank` — اختيار من بنك محدد

```json
{
  "bank_id": 3,
  "question_ids": [10, 11]
}
```

| الحقل | الغرض |
|-------|--------|
| `bank_id` | بنك الأسئلة (يدعم بنوك COMMUNITY عبر workspaces) |
| `question_ids` | أسئلة داخل ذلك البنك — يجب أن تطابق `subject_id` الاختبار |

---

#### `POST /tests/{test_id}/questions/manual` — أسئلة يدوية

```json
{
  "questions": [
    {
      "type_code": "MCQ",
      "body": "ما عاصمة فرنسا؟",
      "explanation": "باريس",
      "points": 2,
      "difficulty": "EASY",
      "topic_id": 1,
      "choices": [
        { "body": "باريس", "is_correct": true, "order_index": 0 },
        { "body": "لندن", "is_correct": false, "order_index": 1 }
      ]
    },
    {
      "type_code": "TRUE_FALSE",
      "body": "الشمس نجم",
      "points": 1,
      "choices": [
        { "body": "True", "is_correct": true, "order_index": 0 },
        { "body": "False", "is_correct": false, "order_index": 1 }
      ]
    },
    {
      "type_code": "ESSAY",
      "body": "اشرح مفهوم التشفير",
      "points": 10
    }
  ]
}
```

| حقل السؤال | الغرض |
|------------|--------|
| `type_code` | `MCQ` \| `TRUE_FALSE` \| `MULTI_SELECT` \| `ESSAY` |
| `body` | نص السؤال |
| `explanation` | تفسير الإجابة (اختياري) |
| `points` | الدرجة (افتراضي 1) |
| `difficulty` | `EASY` \| `MEDIUM` \| `HARD` |
| `topic_id` | موضوع ضمن المادة (اختياري) |
| `choices` | مطلوب لـ MCQ/TRUE_FALSE/MULTI_SELECT — **ممنوع** لـ ESSAY |

**حقول الخيار:**

| الحقل | الغرض |
|-------|--------|
| `body` | نص الخيار |
| `is_correct` | هل صحيح؟ |
| `order_index` | ترتيب العرض |

---

#### `GET /templates/exam-questions-csv` — تحميل قالب CSV

**Headers:** `Authorization`, `X-Workspace-Id`

يعيد ملف `exam_questions_template.csv` جاهزاً للتحرير في Excel. يحتوي على أمثلة لأنواع MCQ و TRUE_FALSE و MULTI_SELECT و ESSAY.

---

#### `POST /tests/{test_id}/questions/import-csv` — استيراد CSV

**Content-Type:** `multipart/form-data`

| الحقل | الغرض |
|-------|--------|
| `csv_file` | ملف CSV بترميز UTF-8 |

**أعمدة القالب (بدون JSON داخل الخلايا):**

| العمود | مطلوب؟ | الغرض |
|--------|--------|--------|
| `Question Type` | نعم | MCQ, TRUE_FALSE, MULTI_SELECT, ESSAY |
| `Question` | نعم | نص السؤال |
| `Explanation` | لا | شرح الإجابة |
| `Difficulty` | لا | EASY, MEDIUM, HARD |
| `Points` | لا | رقم أكبر من 0 (افتراضي 1 إذا تُرك فارغاً) |
| `Topic ID` | لا | معرف موضوع ضمن مادة الاختبار |
| `Choice A` … `Choice F` | حسب النوع | نص الخيارات (اترك فارغاً لـ ESSAY) |
| `Correct Answers` | حسب النوع | حروف A–F بدون فواصل، مثال: `B` أو `ABD` |

**قواعد الإجابات الصحيحة:**

| النوع | القاعدة |
|-------|---------|
| MCQ | حرف واحد فقط |
| TRUE_FALSE | حرف واحد: A أو B فقط (Choice C–F يجب أن تبقى فارغة) |
| MULTI_SELECT | حرف واحد أو أكثر |
| ESSAY | يترك `Correct Answers` فارغاً |

**استجابة ناجحة (201):**

```json
{
  "message": "CSV questions imported",
  "count": 13,
  "questions": [ ... ],
  "failed_count": 2,
  "failed_rows": [
    { "row": 6, "error": "Row 6: MCQ questions must have exactly one correct answer" },
    { "row": 12, "error": "Row 12: correct answer \"E\" references an empty choice" }
  ]
}
```

`failed_rows` و `failed_count` يظهران فقط عند وجود صفوف فاشلة (استيراد جزئي). الصفوف الصالحة تُنشأ؛ الفاشلة تُتخطى.

**التوافق مع الصيغة القديمة:** ما زال مقبولاً ملف بأعمدة `type_code`, `body`, `choices` (JSON في الخلية).

---

#### `POST /tests/{test_id}/questions/random-from-banks` — Exam Blueprint Generator

يُنشئ أسئلة الاختبار عشوائياً وفق **مخطط (blueprint)** لكل بنك: عدد الأسئلة، نسب المواضيع، وتوزيع الصعوبة داخل كل موضوع.

```json
{
  "banks": [
    {
      "bank_id": 3,
      "question_count": 20,
      "topics": [
        {
          "topic_id": 11,
          "percentage": 30,
          "difficulty_distribution": {
            "easy": 20,
            "medium": 50,
            "hard": 30
          }
        },
        {
          "topic_id": 12,
          "percentage": 50,
          "difficulty_distribution": {
            "easy": 10,
            "medium": 40,
            "hard": 50
          }
        },
        {
          "topic_id": 13,
          "percentage": 20,
          "difficulty_distribution": {
            "easy": 40,
            "medium": 30,
            "hard": 30
          }
        }
      ]
    },
    {
      "bank_id": 5,
      "question_count": 10,
      "topics": [
        {
          "topic_id": 11,
          "percentage": 100,
          "difficulty_distribution": {
            "easy": 33,
            "medium": 34,
            "hard": 33
          }
        }
      ]
    }
  ]
}
```

**قواعد التحقق:**

| القاعدة | الرسالة عند الخطأ |
|---------|-------------------|
| لكل بنك: مجموع `percentage` للمواضيع = **100** | Topic percentages must total 100% |
| لكل موضوع: `easy + medium + hard` = **100** | Difficulty percentages must total 100% inside Topic X |
| الموضوع موجود وله أسئلة في البنك | Bank X does not contain Topic Y |
| توفر أسئلة كافية لكل خانة | Requested N HARD questions but only M exist |

**Response `201`:**

```json
{
  "message": "Blueprint generated successfully",
  "count": 30,
  "summary": [
    { "bank_id": 3, "requested": 20, "inserted": 20 },
    { "bank_id": 5, "requested": 10, "inserted": 10 }
  ],
  "questions": [ "...لقطات snapshot..." ]
}
```

| حقل | الغرض |
|-----|--------|
| `banks` | قائمة مخططات البنوك |
| `bank_id` | معرف بنك الأسئلة (نفس مادة الاختبار) |
| `question_count` | إجمالي الأسئلة من هذا البنك |
| `topics` | توزيع المواضيع داخل البنك |
| `topic_id` | معرف الموضوع |
| `percentage` | نسبة الموضوع من `question_count` (مجموعها 100) |
| `difficulty_distribution` | نسب EASY/MEDIUM/HARD داخل الموضوع (مجموعها 100) |

---

#### `POST /tests/{test_id}/questions/ai-generate` — توليد AI

```json
{
  "count": 5,
  "type_code": "MCQ",
  "difficulty": "MEDIUM",
  "topics": ["التشفير", "الشبكات"],
  "learning_objectives": ["فهم AES"],
  "additional_instructions": "أسئلة بالعربية"
}
```

| الحقل | مطلوب؟ | الغرض |
|-------|--------|--------|
| `count` | نعم | 1–50 |
| `type_code` | لا | افتراضي `MCQ` |
| `difficulty` | لا | `EASY` \| `MEDIUM` \| `HARD` |
| `topics` | لا | مواضيع للتوجيه |
| `learning_objectives` | لا | أهداف تعليمية |
| `additional_instructions` | لا | تعليمات إضافية للنموذج |

**Response `201`:**

```json
{
  "message": "AI questions added",
  "questions": [ "..." ],
  "count": 5,
  "ai_model": "qwen-...",
  "subject_name": "أمن سيبراني"
}
```

> الأسئلة تُحفظ **فوراً** كـ snapshots — لا خطوة تأكيد منفصلة.

---

### 5.6 تعديل / حذف لقطة سؤال

#### `PATCH /tests/{test_id}/questions/{test_question_id}`

**شرط:** `DRAFT` + لا توجد محاولات طلاب على الاختبار.

**Request (جزئي):**

```json
{
  "type_code": "MCQ",
  "body": "نص محدّث",
  "explanation": "تفسير",
  "points": 3,
  "difficulty": "HARD",
  "topic_id": 2,
  "choices": [
    { "body": "خيار أ", "is_correct": true, "order_index": 0 },
    { "body": "خيار ب", "is_correct": false, "order_index": 1 }
  ]
}
```

**Response `200`:**

```json
{
  "message": "Test question updated",
  "question": { "...": "كائن لقطة" }
}
```

---

#### `DELETE /tests/{test_id}/questions/{test_question_id}`

**شرط:** نفس شروط PATCH.

**Response `200`:**

```json
{
  "message": "Test question removed"
}
```

---

### 5.7 تعيين الطلاب (Exam Whitelist)

> من الآن فصاعداً، النشر لا يعني إتاحة الامتحان لكل طلاب المادة تلقائياً.  
> يجب تعيين قائمة طلاب مسموح لهم قبل الدخول.

#### `POST /tests/{test_id}/assign-students`

```json
{
  "student_membership_ids": [15, 22, 35, 40]
}
```

**السلوك:**
- يتحقق من صلاحية المعلّم/المالك على الاختبار
- يحذف التكرار من القائمة
- يتحقق أن كل Membership:
  - داخل نفس Workspace
  - `role=STUDENT` و `status=ACTIVE`
  - مسجل في نفس مادة الاختبار (`subject_memberships`)
- يحفظهم في whitelist

**Response `201`:**

```json
{
  "message": "Students assigned successfully",
  "count": 4
}
```

#### `GET /tests/{test_id}/assigned-students`

يرجع الطلاب المعيّنين على الاختبار مع حالة دعوة البريد (`invite_status`).

#### `DELETE /tests/{test_id}/assigned-students/{membership_id}`

يحذف الطالب من whitelist لهذا الاختبار.

---

### 5.8 النشر والجدولة والإغلاق

#### `POST /tests/{test_id}/publish-now` — نشر فوري

**Request:** بدون body.

**السلوك:**
- يعيّن `status` = `PUBLISHED`
- يعيّن `published_at` = الآن
- يمسح `scheduled_publish_at`
- يطلق إرسال دعوات البريد للطلاب الموجودين في whitelist (مرة واحدة لكل طالب)

**Response `200`:**

```json
{
  "message": "Test published",
  "test": { "...": "status: PUBLISHED" }
}
```

---

#### `POST /tests/{test_id}/schedule-publication` — جدولة النشر

```json
{
  "publish_at": "2026-06-25T08:00:00"
}
```

| الحقل | الغرض |
|-------|--------|
| `publish_at` | وقت النشر المحلي — **يجب أن يكون في المستقبل** (بدون `Z` أو offset) |

**إعداد `.env`:**

```env
APP_TIMEZONE=Asia/Damascus
SCHEDULED_TEST_PUBLISH_INTERVAL_SECONDS=5
```

**السلوك:**
- `status` = `SCHEDULED`
- `scheduled_publish_at` = `publish_at`
- بدون إنشاء محاولات طلاب
- عند نشره لاحقاً من الـ background worker يتم إرسال دعوات البريد تلقائياً

**Response `200`:**

```json
{
  "message": "Test scheduled",
  "test": { "...": "status: SCHEDULED" }
}
```

---

#### `POST /tests/{test_id}/close` — إغلاق الاختبار

**Response `200`:**

```json
{
  "message": "Test closed",
  "test": { "...": "status: CLOSED, closed_at: ..." }
}
```

---

#### `POST /tests/{test_id}/archive` — أرشفة

**Response `200`:**

```json
{
  "message": "Test archived",
  "test": { "...": "status: ARCHIVED" }
}
```

---

## 6. APIs الطالب — المحاولات

### 6.1 `GET /tests/available` — الاختبارات المتاحة

**Response `200`:**

```json
{
  "tests": [
    {
      "test_id": 5,
      "name": "امتحان منتصف الفصل",
      "slug": "...",
      "description": "...",
      "subject_id": 1,
      "status": "PUBLISHED",
      "duration_minutes": 60,
      "total_score": 100,
      "passing_score": 50,
      "starts_at": "2026-06-20T09:00:00+00:00",
      "published_at": "2026-06-19T12:00:00+00:00"
    }
  ],
  "count": 1
}
```

يعيد فقط اختبارات `PUBLISHED` التي:
- الطالب مسجل بمادتها
- والطالب موجود في whitelist الخاصة بالاختبار

---

### 6.2 `POST /tests/{test_id}/attempts` — بدء أو استئناف محاولة

**Request:** بدون body.

**Response `201` (محاولة جديدة):**

```json
{
  "message": "Attempt started",
  "resumed": false,
  "attempt": { "...": "كائن attempt" }
}
```

**Response `200` (استئناف):**

```json
{
  "message": "Attempt resumed",
  "resumed": true,
  "attempt": { "...": "كائن attempt" }
}
```

**أخطاء شائعة:**
- `409` — أكمل الطالب الاختبار مسبقاً (محاولة واحدة فقط)
- `403` — الطالب غير معيّن في whitelist أو نافذة الدخول أُغلقت (للمحاولة الأولى)
- `400` — الاختبار غير منشور / لم يبدأ بعد

**مهم جداً (منطق الزمن العالمي):**
- وقت النهاية لا يُحسب من `attempt_start + duration`
- بل دائماً من:
  - `global_end = starts_at + duration_minutes`
- لذلك كل الطلاب ينتهون في نفس الوقت.

**الاستئناف:**
- نافذة الدخول (`entry_window`) تُفحص فقط عند إنشاء أول محاولة.
- إذا أنشأ الطالب محاولة قبل إغلاق النافذة، يمكنه الاستئناف لاحقاً حتى `global_end`.

---

### 6.3 `GET /tests/{test_id}/attempts/current` — المحاولة الجارية

**Response `200`:**

```json
{
  "attempt": { "...": "كائن attempt مع أسئلة وإجابات" }
}
```

---

### 6.4 `GET /tests/{test_id}/attempts/{attempt_id}` — تفاصيل محاولة

**Response `200`:**

```json
{
  "attempt": { "...": "كائن attempt" }
}
```

يعرض للطالب بدون `is_correct` في الخيارات.

---

### 6.5 `GET /tests/{test_id}/attempts` — قائمة المحاولات (معلّم)

**Response `200`:**

```json
{
  "attempts": [ { "...": "كائن attempt بدون تفاصيل إجابات كاملة" } ],
  "count": 15
}
```

---

### 6.6 حفظ الإجابات

#### `PUT /tests/{test_id}/attempts/{attempt_id}/answers` — حفظ دفعة

```json
{
  "answers": [
    {
      "test_question_id": 42,
      "selected_choice_indices": [1]
    },
    {
      "test_question_id": 43,
      "selected_choice_indices": [0, 2]
    },
    {
      "test_question_id": 44,
      "answer_text": "إجابة مقالية..."
    }
  ]
}
```

| الحقل | الغرض |
|-------|--------|
| `test_question_id` | معرف لقطة السؤال |
| `selected_choice_indices` | فهارس الخيارات (0-based) — لـ MCQ/TRUE_FALSE/MULTI_SELECT |
| `answer_text` | نص — لـ ESSAY |

**Response `200`:**

```json
{
  "message": "Answers saved",
  "answers": [ { "...": "كائن answer" } ],
  "count": 3
}
```

---

#### `PATCH /tests/{test_id}/attempts/{attempt_id}/answers/{test_question_id}` — إجابة واحدة

```json
{
  "selected_choice_indices": [0]
}
```

أو:

```json
{
  "answer_text": "نص محدّث"
}
```

**Response `200`:**

```json
{
  "message": "Answer updated",
  "answer": { "...": "كائن answer" }
}
```

---

### 6.7 إنهاء المحاولة

#### `POST /tests/{test_id}/attempts/{attempt_id}/submit` — تسليم الطالب

**Response `200`:**

```json
{
  "message": "Attempt submitted",
  "attempt": {
    "id": 7,
    "status": "GRADED",
    "raw_score": 85,
    "final_score": 85,
    "submission_source": "STUDENT",
    "...": "..."
  }
}
```

**التصحيح التلقائي:**
- `MCQ`, `TRUE_FALSE`: خيار واحد صحيح
- `MULTI_SELECT`: يجب تطابق كامل مع الخيارات الصحيحة
- `ESSAY`: `status` يبقى `SUBMITTED` — `is_correct` = `null` (لا تصحيح يدوي بعد)

---

#### `POST /tests/{test_id}/attempts/{attempt_id}/force-submit` — إجبار التسليم (معلّم)

نفس استجابة `submit` مع `submission_source: "FORCE"`.

---

#### `POST /tests/{test_id}/attempts/{attempt_id}/timeout` — انتهاء الوقت

`submission_source: "TIMEOUT"`. يُستدعى يدوياً أو يُطبَّق تلقائياً عند قراءة المحاولة بعد `expires_at`.

---

### 6.8 كائن `attempt` (ملخص الحقول)

```json
{
  "id": 7,
  "test_id": 5,
  "student_membership_id": 20,
  "user_id": 8,
  "status": "IN_PROGRESS",
  "started_at": "...",
  "submitted_at": null,
  "expires_at": "...",
  "last_activity_at": "...",
  "submission_source": null,
  "raw_score": null,
  "final_score": null,
  "questions": [
    {
      "test_question_id": 42,
      "snapshot_question_text": "...",
      "snapshot_type_code": "MCQ",
      "choices": [
        { "index": 0, "body": "خيار أ", "order_index": 0 }
      ],
      "answer": { "...": "إن وُجدت" }
    }
  ],
  "answers": [ { "...": "كائن answer" } ]
}
```

| حقل المحاولة | الغرض |
|--------------|--------|
| `status` | `IN_PROGRESS` \| `SUBMITTED` \| `GRADED` |
| `expires_at` | نهاية الوقت المسموح |
| `submission_source` | `STUDENT` \| `TIMEOUT` \| `FORCE` |
| `raw_score` / `final_score` | الدرجة بعد التصحيح |

| حقل الإجابة | الغرض |
|-------------|--------|
| `selected_choice_indices` | الفهارس المختارة |
| `answer_text` | نص المقال |
| `is_correct` | نتيجة التصحيح (`null` للمقالي) |
| `earned_score` | الدرجة المكتسبة |

---

## 7. APIs المراقبة Proctoring

**التفعيل:** `PATCH /tests/{id}` → `settings_config.proctoring.enabled: true`

عند بدء المحاولة تُنشأ جلسة مراقبة تلقائياً إن كانت مفعّلة.

### 7.1 `GET /tests/{test_id}/proctoring/sessions` — جلسات نشطة (مراقب/معلّم)

**Response `200`:**

```json
{
  "sessions": [
    {
      "id": 1,
      "test_attempt_id": 7,
      "workspace_id": 1,
      "status": "ACTIVE",
      "started_at": "...",
      "ended_at": null,
      "violation_score": 15,
      "tab_switch_count": 2,
      "settings_snapshot": { "enabled": true },
      "violation_count": 1,
      "event_count": 12
    }
  ],
  "count": 1
}
```

---

### 7.2 `POST /tests/{test_id}/attempts/{attempt_id}/proctoring/session` — بدء جلسة (طالب)

```json
{
  "device_metadata": { "os": "Windows 11" },
  "browser_metadata": { "name": "Chrome", "version": "120" }
}
```

**Response `201`:**

```json
{
  "message": "Proctoring session active",
  "session": { "...": "كائن session" }
}
```

---

### 7.3 `GET .../proctoring/session` — حالة الجلسة

**Response `200`:**

```json
{
  "session": { "...": "كائن session مع counts" }
}
```

---

### 7.4 `POST .../proctoring/events` — إرسال حدث (REST)

```json
{
  "event_type": "TAB_SWITCH",
  "payload": { "detail": "switched to another tab" },
  "occurred_at": "2026-06-20T10:15:00Z"
}
```

| الحقل | الغرض |
|-------|--------|
| `event_type` | مثل `TAB_SWITCH`, `FACE_LOST`, `MULTIPLE_FACES`, `COPY_PASTE`, … |
| `payload` | بيانات إضافية |
| `occurred_at` | وقت الحدث (اختياري) |

**Response `201`:**

```json
{
  "message": "Event recorded",
  "event": { "id": 5, "event_type": "TAB_SWITCH", "..." : "..." },
  "violation": { "...": "إن وُجدت مخالفة" },
  "warning": null,
  "evidence": { "...": "للمخالفات المتوسطة/العالية" }
}
```

**WebSocket بديل:**

```
ws://host/ws/proctoring/tests/{test_id}/attempts/{attempt_id}?token=<JWT>&workspace_id=<id>
```

---

### 7.5 `GET .../proctoring/violations` — قائمة المخالفات

**Response `200`:**

```json
{
  "violations": [
    {
      "id": 3,
      "violation_type": "TAB_SWITCH",
      "severity": "MEDIUM",
      "score_contribution": 12,
      "description": "Multiple tab/window switches (2)",
      "status": "OPEN",
      "created_at": "..."
    }
  ],
  "count": 1
}
```

---

### 7.6 `GET .../violations/{violation_id}` — تفاصيل مخالفة

**Response `200`:** كائن مخالفة كامل.

---

### 7.7 `GET .../violations/{violation_id}/evidence` — حزمة الأدلة

**Response `200`:**

```json
{
  "id": 1,
  "violation_id": 3,
  "timeline_before": "...",
  "timeline_after": "...",
  "screenshots": [],
  "video_clip_ref": null,
  "device_metadata": {},
  "browser_metadata": {},
  "event_logs": []
}
```

---

### 7.8 `POST .../violations/{violation_id}/review` — مراجعة (مراقب)

```json
{
  "status": "CONFIRMED",
  "review_notes": "مخالفة واضحة"
}
```

| `status` | الغرض |
|----------|--------|
| `REVIEWED` | تمت المراجعة |
| `DISMISSED` | مرفوضة |
| `CONFIRMED` | مؤكدة |

---

### 7.9 `GET .../proctoring/audit-logs` — سجل التدقيق

**Response `200`:**

```json
{
  "audit_logs": [ { "id": 1, "action": "EVENT_INGESTED", "..." : "..." } ],
  "count": 10
}
```

---

## 8. أنواع الأسئلة والإجابات

| `type_code` | خيارات (`choices`) | طريقة الإجابة | تصحيح تلقائي |
|-------------|-------------------|---------------|--------------|
| `MCQ` | ≥ 2، إجابة صحيحة واحدة | `selected_choice_indices: [i]` | ✅ |
| `TRUE_FALSE` | خياران بالضبط | `selected_choice_indices: [0 أو 1]` | ✅ |
| `MULTI_SELECT` | ≥ 2، ≥ 1 صحيح | `selected_choice_indices: [i, j, ...]` | ✅ (تطابق كامل) |
| `ESSAY` | بدون خيارات | `answer_text` | ❌ (يبقى SUBMITTED) |

**قواعد التحقق:**
- MCQ/TRUE_FALSE/MULTI_SELECT: لا تقبل `answer_text` فقط — تحتاج `selected_choice_indices`
- ESSAY: لا تقبل `selected_choice_indices`

---

## 9. سيناريو عمل كامل

```
المعلّم:
  1. POST /tests                          → إنشاء (DRAFT)
  2. PATCH /tests/5                       → إعدادات الوقت + proctoring
  3. POST /tests/5/questions/manual       → إضافة أسئلة
  4. PATCH /tests/5/questions/42          → تعديل سؤال (اختياري)
  5. POST /tests/5/publish-now            → نشر
     — أو —
     POST /tests/5/schedule-publication    → جدولة ثم انتظار النشر التلقائي

الطالب:
  6. GET /tests/available
  7. POST /tests/5/attempts               → بدء (يُنشئ proctoring إن مفعّل)
  8. PUT /tests/5/attempts/7/answers      → حفظ أثناء الحل
  9. POST /tests/5/attempts/7/submit      → تسليم + تصحيح تلقائي

المعلّم (متابعة):
  10. GET /tests/5/attempts
  11. GET /tests/5/proctoring/sessions
  12. POST /tests/5/close                 → إغلاق عند الانتهاء
```

---

## 10. قيود وسلوك غير مُنفَّذ بعد

| الموضوع | الوضع الحالي |
|---------|--------------|
| `scoring_config` | يُخزَّن فقط — لا يغيّر التصحيح |
| `grading_mode` | حقل نصي — غير مُطبَّق في المحرك |
| `auto_distribute_scores` | لا يُحدَّث بعد الإنشاء |
| تصحيح ESSAY يدوياً | غير موجود — لا API للمعلّم |
| `max_attempts` / إعادة المحاولة | محاولة واحدة مكتملة فقط |
| خلط الأسئلة / التنقل | غير مُطبَّق من `settings_config` |
| عتبات proctoring | ثابتة في الكود (`proctoring_violation_engine.py`) |
| مهمة timeout خلفية | Timeout يُطبَّق عند قراءة المحاولة (lazy) |

---

## ملحق — رموز الأخطاء الشائعة

| HTTP | المعنى |
|------|--------|
| `400` | تحقق من البيانات (ValidationError) |
| `401` | JWT غير صالح |
| `403` | صلاحيات غير كافية |
| `404` | اختبار/سؤال/محاولة غير موجود |
| `409` | تعارض (مثلاً محاولة مكتملة مسبقاً) |

---

*للاطلاع على حالة المشروع العامة: [PROJECT_STATUS_REPORT.md](./PROJECT_STATUS_REPORT.md)*
