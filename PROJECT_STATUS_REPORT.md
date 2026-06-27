# تقرير حالة المشروع — edu_forms API

**تاريخ التحديث:** 2026-06-26  
**المستودع:** `refactoring_of_graduating_project`  
**التقارير التفصيلية للمراحل:** [PHASE_1_REPORT.md](./PHASE_1_REPORT.md) · [PHASE_2_REPORT.md](./PHASE_2_REPORT.md)

---

## 1. ملخص تنفيذي

منصة **edu_forms** هي API متعدد المستأجرين (multi-tenant) مبنية على **Flask 3 + PostgreSQL** لإدارة المؤسسات التعليمية، المواد، بنوك الأسئلة، الاختبارات الإلكترونية، محاولات الطلاب، والمراقبة (proctoring).

| المؤشر | القيمة |
|--------|--------|
| جداول قاعدة البيانات | 31 جدولاً |
| مسارات HTTP | ~97 |
| WebSocket | 1 (مراقبة الامتحان) |
| Blueprints | 13 |
| خدمات الأعمال (services) | 18 |
| سلسلة migrations (HEAD) | `h4c5d6e7f8a9` |
| أوامر CLI | `flask seed` · `flask publish-due-tests` |
| مهام خلفية | نشر الاختبارات المجدولة (كل 60 ثانية) |

**الحالة العامة:** البنية الأساسية، المصادقة، إدارة المساحات والمواد، بنوك الأسئلة، دورة حياة الاختبار الكاملة (إنشاء → نشر → محاولة → تصحيح تلقائي)، والمراقبة الإلكترونية — **منفّذة ومتصلة**. الفواتير والدفع، تصحيح المقالات يدوياً، ومجموعة اختبارات آلية — **غير منفّذة بعد**.

---

## 2. البنية المعمارية

```
HTTP / WebSocket
      ↓
router/          (Blueprints + decorators: JWT, X-Workspace-Id)
      ↓
service/         (قواعد الأعمال، RBAC، التحقق)
      ↓
repositories/    (استعلامات SQLAlchemy)
      ↓
models/          (31 جدول)
      ↓
PostgreSQL
```

**أنماط ثابتة في المشروع:**

- **Multi-tenancy:** كل طلب يحمل `X-Workspace-Id` مع JWT.
- **RBAC أكاديمي:** `utils/academic_rbac.py` — صلاحيات المعلم/الطالب/المالك على مستوى المادة والاختبار.
- **لقطات الأسئلة (snapshots):** عند إضافة سؤال للاختبار يُحفظ في `test_questions` — الطالب يجيب على اللقطة وليس على سجل السؤال الحي.
- **إعدادات مرنة:** `tests.settings_config` و `tests.scoring_config` كـ JSON نصي.
- **توثيق:** Swagger في `/apidocs/` عبر `swagger/template.yml`.

---

## 3. ما تم إنجازه — حسب المجال

### 3.1 البنية التحتية والصحة

| المكوّن | الحالة | الملاحظات |
|---------|--------|-----------|
| `app_factory.py` | ✅ | تهيئة DB، CORS، Swagger، WebSocket، CLI، المهمة الخلفية |
| `GET /health` | ✅ | فحص الخدمة |
| `GET /health/db` | ✅ | فحص الاتصال بقاعدة البيانات |
| `GET /api/enums` | ✅ | كل الـ enums المستخدمة في الواجهة |
| Seeds | ✅ | `flask seed` — خطط، أنواع أسئلة، أدوار |
| Alembic | ✅ | 15 revision، HEAD: proctoring |

---

### 3.2 المصادقة والمستخدمون (`/auth`)

| الميزة | الحالة |
|--------|--------|
| تسجيل مالك مساحة عمل (Solo / Institution) | ✅ |
| تسجيل الدخول / الخروج / تحديث JWT | ✅ |
| OTP بالبريد (تسجيل، تحقق، إعادة إرسال) | ✅ |
| إعادة تعيين كلمة المرور | ✅ |
| جلسات JWT مع JTI (`user_sessions`) | ✅ |
| موافقة المؤسسة (pending / approve / reject) | ✅ |
| تسجيل دخول Super Admin | ✅ |

**ملف مرجعي:** `docs/AUTH_API.md`

---

### 3.3 مساحات العمل والعضويات

| الميزة | API تقريبي | الحالة |
|--------|------------|--------|
| إنشاء وإدارة workspace | `/workspaces` | ✅ |
| أدوار العضوية: ADMIN, TEACHER, STUDENT | — | ✅ |
| دعوات الأعضاء (invite lifecycle) | `/invites` | ✅ |
| انضمام الطالب بكود | `/join-codes` | ✅ |
| ربط الطالب بالمواد | `/student-memberships` | ✅ |
| ملف المؤسسة (`workspace_profiles`) | — | ✅ |

---

### 3.4 المنهج الأكاديمي (`/subjects`)

| الميزة | الحالة |
|--------|--------|
| CRUD المواد (subjects) | ✅ |
| تعيين معلمين وطلاب للمادة | ✅ |
| **Topics** — CRUD تحت `/subjects/{id}/topics` | ✅ |
| إثراء `GET /subjects` بقائمة topics | ✅ |
| إزالة عمود `code` من subjects و topics | ✅ (migrations) |
| صلاحيات: الكتابة = owner/admin؛ القراءة = تعيين المادة أو admin | ✅ |

---

### 3.5 بنوك الأسئلة (`/question-banks`)

| الميزة | الحالة |
|--------|--------|
| بنوك شخصية / مساحة العمل / مجتمعية | ✅ |
| CRUD أسئلة موحّد حسب `type_code` | ✅ |
| أنواع مدعومة: MCQ, TRUE_FALSE, MULTI_SELECT, ESSAY | ✅ |
| التحقق في `utils/question_type_validation.py` | ✅ |
| ربط السؤال بـ `topic_id` | ✅ |
| أرشفة البنك (soft delete) | ✅ |

---

### 3.6 الاختبارات — إدارة المعلّم (`/tests` — tag: **Tests**)

#### دورة الحياة

```
DRAFT → SCHEDULED → PUBLISHED → CLOSED → ARCHIVED
         (جدولة)    (نشر فوري أو تلقائي)
```

| الميزة | API | الحالة |
|--------|-----|--------|
| إنشاء اختبار (خطوة UI الأولى) | `POST /tests` | ✅ |
| تعديل الإعدادات (DRAFT فقط) | `PATCH /tests/{id}` | ✅ |
| قائمة اختبارات المنشئ | `GET /tests/my` | ✅ |
| تفاصيل + أسئلة اللقطة | `GET /tests/{id}` | ✅ |
| إضافة أسئلة يدوياً | `POST .../questions/manual` | ✅ |
| إضافة من بنك الأسئلة | `POST .../questions` · `.../from-bank` | ✅ |
| أسئلة عشوائية من بنوك | `POST .../questions/random-from-banks` | ✅ |
| استيراد CSV | `POST .../questions/import-csv` | ✅ |
| توليد AI (Gemini أو placeholder) | `POST .../questions/ai-generate` | ✅ |
| نشر فوري | `POST .../publish-now` | ✅ |
| جدولة النشر | `POST .../schedule-publication` | ✅ |
| **نشر تلقائي عند الموعد** | مهمة خلفية + `flask publish-due-tests` | ✅ |
| إغلاق / أرشفة | `POST .../close` · `.../archive` | ✅ |

#### حقول الإعدادات على الاختبار

| الحقل | الغرض |
|-------|--------|
| `duration_minutes` | مدة المحاولة |
| `starts_at` + `entry_window_minutes` | نافذة دخول الطالب |
| `availability_time_mode` | SCHEDULED / FLEXIBLE |
| `settings_config` | JSON — مثال: `proctoring.enabled` |
| `scoring_config` | JSON — قواعد تصحيح إضافية |
| `scheduled_publish_at` | وقت النشر المجدول |
| `auto_distribute_scores` | توزيع الدرجات تلقائياً |

---

### 3.7 محاولات الطلاب — Phase 1 (`/tests` — tag: **Student Exams**)

**تقرير تفصيلي:** [PHASE_1_REPORT.md](./PHASE_1_REPORT.md)

| الميزة | API | الحالة |
|--------|-----|--------|
| الاختبارات المتاحة | `GET /tests/available` | ✅ |
| بدء / استئناف محاولة | `POST /tests/{id}/attempts` | ✅ |
| المحاولة الجارية | `GET .../attempts/current` | ✅ |
| تفاصيل المحاولة | `GET .../attempts/{attempt_id}` | ✅ |
| حفظ إجابات (دفعة) | `PUT .../answers` | ✅ |
| تحديث إجابة واحدة | `PATCH .../answers/{test_question_id}` | ✅ |
| تسليم | `POST .../submit` | ✅ |
| انتهاء الوقت | `POST .../timeout` (+ فحص تلقائي عند القراءة) | ✅ |
| قائمة محاولات (معلّم) | `GET .../attempts` | ✅ |
| إجبار التسليم (معلّم) | `POST .../force-submit` | ✅ |

**قرارات معمارية Phase 1:**

- `attempt_answers.test_question_id` → FK إلى لقطة الاختبار (وليس `questions`).
- الإجابات الاختيارية: `selected_choice_indices` (مصفوفة JSON).
- تصحيح تلقائي: MCQ, TRUE_FALSE, MULTI_SELECT.
- ESSAY يبقى `SUBMITTED` حتى التصحيح اليدوي (غير منفّذ).
- محاولة واحدة مكتملة لكل طالب لكل اختبار.
- إخفاء `is_correct` عن عرض الطالب.

**Migration:** `g3b4c5d6e7f8_attempt_runtime_refactor.py`

---

### 3.8 المراقبة Proctoring — Phase 2 (`/tests` — tag: **Proctoring** + **Student Exams**)

**تقرير تفصيلي:** [PHASE_2_REPORT.md](./PHASE_2_REPORT.md)

| المكوّن | الحالة |
|---------|--------|
| 5 جداول: sessions, events, violations, evidence, audit_logs | ✅ |
| محرك مخالفات قائم على قواعد | ✅ |
| تخزين أدلة محلي (`PROCTORING_STORAGE_DIR`) | ✅ |
| REST — 9 endpoints | ✅ |
| WebSocket — `ws://.../ws/proctoring/tests/{id}/attempts/{id}` | ✅ |
| تكامل تلقائي عند بدء/إنهاء المحاولة | ✅ |
| تفعيل عبر `settings_config.proctoring.enabled` | ✅ |

**Migration:** `h4c5d6e7f8a9_proctoring_domain.py`

**أنواع أحداث رئيسية:** TAB_SWITCH, FACE_LOST, MULTIPLE_FACES, FULLSCREEN_EXIT, COPY_PASTE, AUDIO_ANOMALY, ...

---

### 3.9 إدارة المنصة (`/admin`)

| الميزة | الحالة |
|--------|--------|
| قائمة مؤسسات بانتظار الموافقة | ✅ |
| موافقة / رفض مؤسسة | ✅ |

---

### 3.10 توثيق Swagger

| Tag | الجمهور | المحتوى |
|-----|---------|---------|
| Meta | عام | health, enums |
| Auth | عام | تسجيل، دخول، OTP |
| Super Admin | منصة | موافقة المؤسسات |
| Workspaces | مالك/admin | مساحات العمل |
| Subjects | معلّم/admin | مواد، topics، تعيينات |
| Question banks | معلّم | بنوك وأسئلة |
| **Tests** | معلّم/admin | إنشاء وإدارة الاختبارات |
| **Student Exams** | طالب | إجراء الامتحان والمحاولات |
| **Proctoring** | معلّم/مراقب | جلسات، مخالفات، مراجعة |
| Invites / Join codes | مختلط | انضمام الأعضاء |

**تحديث 2026-06-26:** فصل APIs الطالب في قسم **Student Exams** منفصل عن **Tests**.

---

## 4. المهام الخلفية (Background Jobs)

### ناشر الاختبارات المجدولة

**الملف:** `jobs/scheduled_test_publisher.py`

| الإعداد | الافتراضي | الوصف |
|---------|-----------|--------|
| `SCHEDULED_TEST_PUBLISH_ENABLED` | `true` | تفعيل/تعطيل |
| `SCHEDULED_TEST_PUBLISH_INTERVAL_SECONDS` | `60` | فترة الفحص |

**السلوك:**

1. عند تشغيل السيرفر تبدأ خيط daemon.
2. كل N ثانية: `TestService.publish_due_scheduled_tests()`.
3. اختبارات `SCHEDULED` حيث `scheduled_publish_at <= now` → `PUBLISHED` + `published_at`.
4. أمر يدوي: `flask publish-due-tests`.

**ملاحظة:** يُتخطى في وضع `TESTING` وفي عملية Werkzeug reloader الأب.

---

## 5. قاعدة البيانات

### سلسلة Migrations (HEAD → BASE)

```
h4c5d6e7f8a9  proctoring_domain
  ← g3b4c5d6e7f8  attempt_runtime_refactor
  ← f2a3b4c5d6e7  drop_topics_code
  ← e1f2a3b4c5d6  topic_description_and_timestamps
  ← d0e1f2a3b4c5  email_otp_verified_at
  ← c9d0e1f2a3b4  exam_creation_ui_fields
  ← b8c9d0e1f2a3  test_lifecycle_and_snapshot
  ← ... (auth, academic, questions, invites)
  ← fc65c4e81928  initial_schema
```

### جداول بدون API (مخطط فقط)

| المجال | الجداول | الحالة |
|--------|---------|--------|
| الفواتير | `plans`, `features`, `plan_features`, `workspace_subscriptions`, `subscriptions`, `payments` | ⚠️ نماذج + schemas فقط — **لا routes/services** |
| الإشعارات | `NotificationType` enum | ⚠️ **غير منفّذ** |

---

## 6. تسلسل العمل (Workflows)

### 6.1 المعلّم — من الصفر إلى النشر

```
1. POST /tests
2. PATCH /tests/{id}          ← إعدادات، proctoring، starts_at
3. POST /tests/{id}/questions/manual  (أو bank / csv / ai)
4. POST /tests/{id}/schedule-publication  أو  publish-now
5. GET /tests/{id}            ← متابعة الحالة
6. GET /tests/{id}/attempts   ← متابعة الطلاب
7. POST /tests/{id}/close
```

### 6.2 الطالب — إجراء الامتحان

```
1. GET /tests/available
2. POST /tests/{id}/attempts
3. PUT .../answers            ← أثناء الحل
4. POST .../submit            ← أو timeout تلقائي
```

### 6.3 حالات الاختبار والتوقيت

| الحالة | متى |
|--------|-----|
| `SCHEDULED` | بعد `schedule-publication` |
| `PUBLISHED` | بعد `publish-now` أو المهمة الخلفية |
| الطالب لا يبدأ | قبل `starts_at` أو بعد إغلاق `entry_window` |
| الطالب لا يرى الاختبار | قبل `PUBLISHED` في `GET /tests/available` |

---

## 7. الصلاحيات (RBAC) — ملخص

| الإجراء | من يملك الصلاحية |
|---------|------------------|
| إنشاء/تعديل اختبار | منشئ الاختبار، admin المساحة، معلّم المادة |
| نشر / إغلاق | نفس ما سبق |
| بدء محاولة | طالب مسجّل في المادة (أو admin للاختبار) |
| حفظ إجابات / تسليم | الطالب صاحب المحاولة فقط |
| قائمة المحاولات / force-submit | معلّم، admin، أو منشئ الاختبار |
| مراقبة proctoring | معلّم/مراقب؛ الطالب يرسل أحداثاً فقط |

**الدوال:** `can_manage_subjects`, `verify_subject_teacher_access`, `verify_subject_student_access`, `can_take_published_test`, `can_manage_test_attempts` في `utils/academic_rbac.py`.

---

## 8. التبعيات الرئيسية

```
Flask 3, Flask-SQLAlchemy, Flask-Migrate, Marshmallow
PostgreSQL (psycopg2), PyJWT, bcrypt
flasgger (Swagger), flask-cors
flask-sock, simple-websocket (proctoring)
python-dotenv, email-validator, PyYAML
```

---

## 9. ما لم يُنجز بعد (فجوات)

### أولوية عالية (تأثير على المنتج)

| الفجوة | التفاصيل |
|--------|----------|
| **تصحيح المقالات يدوياً** | ESSAY يبقى `SUBMITTED` — لا API لتصحيح المعلّم |
| **سياسة إعادة المحاولة** | محاولة واحدة فقط — لا `max_attempts` في `settings_config` |
| **إعدادات سلوك الامتحان** | التنقل بين الأسئلة، خلط الأسئلة — غير مطبّقة في backend |
| **مجموعة اختبارات آلية** | لا مجلد `tests/` |

### أولوية متوسطة

| الفجوة | التفاصيل |
|--------|----------|
| **مهمة انتهاء الوقت الخلفية** | Timeout يُطبَّق عند الطلب فقط (lazy) |
| **لوحة مراقبة حية للمعلّم** | WebSocket broadcast للمعلمين — غير منفّذ |
| **عتبات proctoring قابلة للتخصيص** | القواعد ثابتة في الكود |
| **تخزين سحابي للأدلة** | محلي فقط — لا S3 |
| **نظام الفواتير** | جداول موجودة — لا API |
| **الإشعارات** | enum فقط |

### أولوية منخفضة / تحسينات

| الفجوة | التفاصيل |
|--------|----------|
| `HF_TOKEN`, `SHAM_CASH_API_KEY` | معرّفة في config — غير مستخدمة |
| AI بدون مفتاح Gemini | placeholder ثابت |
| README قديم | يذكر أن models/schemas «pending» — يحتاج تحديث |
| Downgrade migrations | معظمها `NotImplementedError` |

---

## 10. هيكل الملفات الحالي

```
config/settings.py       إعدادات البيئة
app_factory.py           مصنع التطبيق
run.py                   نقطة الدخول

models/                  31 جدول (users → proctoring → billing schema)
repositories/            طبقة الوصول للبيانات
service/                 18 خدمة أعمال
schemas/                 تحقق Marshmallow
router/                  13 blueprints + proctoring_ws
jobs/                    ناشر الاختبارات المجدولة
migrations/versions/     15 revision
swagger/template.yml     توثيق OpenAPI
seeds/                   بيانات أولية
utils/                   db, enums, rbac, security, validation
docs/AUTH_API.md         توثيق المصادقة
PHASE_1_REPORT.md        تقرير محاولات الامتحان
PHASE_2_REPORT.md        تقرير المراقبة
PROJECT_STATUS_REPORT.md هذا الملف
```

---

## 11. التشغيل والاختبار السريع

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/create_database.py
set FLASK_APP=run.py
flask db upgrade
flask seed
python run.py
```

| Endpoint | الغرض |
|----------|--------|
| `GET /health` | صحة الخدمة |
| `GET /api/enums` | قيم enums |
| `GET /apidocs/` | Swagger UI |
| `flask publish-due-tests` | نشر الاختبارات المستحقة يدوياً |

---

## 12. سجل التحديثات على التقارير

| التاريخ | التغيير |
|---------|---------|
| 2026-06-17 | PHASE_1 — محاولات الامتحان و runtime |
| 2026-06-17 | PHASE_2 — proctoring كامل |
| 2026-06-26 | نشر تلقائي للاختبارات المجدولة (`jobs/`) |
| 2026-06-26 | فصل Swagger: **Student Exams** / **Tests** / **Proctoring** |
| 2026-06-26 | إنشاء **PROJECT_STATUS_REPORT.md** (هذا التقرير الشامل) |

---

## 13. الخلاصة

المشروع تجاوز مرحلة «إعادة البناء من ERD» وأصبح **منصة تقييم عاملة** تشمل:

- ✅ مصادقة متعددة المستأجرين مع OTP وموافقة المؤسسات  
- ✅ إدارة مواد و topics وبنوك أسئلة  
- ✅ اختبارات بلقطات ثابتة ومصادر متعددة للأسئلة  
- ✅ نشر فوري ومجدول وتلقائي  
- ✅ runtime كامل للمحاولات مع تصحيح آلي  
- ✅ مراقبة إلكترونية REST + WebSocket  

**الخطوة التالية المنطقية للمنتج:** تصحيح ESSAY، سياسة المحاولات، إعدادات سلوك الامتحان في `settings_config`، واختبارات تكامل آلية.

---

*للتفاصيل التقنية العميقة لكل مرحلة راجع PHASE_1_REPORT.md و PHASE_2_REPORT.md.*
