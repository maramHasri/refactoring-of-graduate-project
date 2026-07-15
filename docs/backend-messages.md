# Backend Response Messages

Stable English API response messages used by the backend.

Frontend teams can build translation dictionaries from this catalog.

**Source of truth:** `utils/messages.py`

Do not change these strings casually — they are part of the API contract.

## Authentication

| Constant | English Message | Description |
|----------|-----------------|-------------|
| ACCOUNT_ALREADY_EXISTS_PLEASE_LOGIN_FIRST | Account already exists. Please login first. | API response message. |
| ACCOUNT_IS_DISABLED | Account is disabled | API response message. |
| ACCOUNT_IS_SUSPENDED | Account is suspended | API response message. |
| ALL_SESSIONS_REVOKED | All sessions revoked | API response message. |
| CURRENT_PASSWORD_IS_INCORRECT | Current password is incorrect | API response message. |
| EMAIL_IS_ALREADY_REGISTERED | Email is already registered | API response message. |
| EMAIL_IS_ALREADY_VERIFIED | Email is already verified | API response message. |
| EMAIL_NOT_VERIFIED | Email not verified | API response message. |
| EMAIL_NOT_VERIFIED_ENTER_THE_OTP_SENT_TO_YOUR_EMAIL_VIA_POST_AUTH_VERIFY_OTP | Email not verified. Enter the OTP sent to your email via POST /auth/verify-otp | API response message. |
| GMAIL_IS_NOT_CONFIGURED_SET_GMAIL_USER_AND_GMAIL_APP_PASSWORD_IN_ENV | Gmail is not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD in .env | API response message. |
| HF_TOKEN_IS_REQUIRED_WHEN_AI_QUESTION_PROVIDER_HUGGINGFACE | HF_TOKEN is required when AI_QUESTION_PROVIDER=huggingface | Validation or authorization failure message. |
| IF_THE_ACCOUNT_EXISTS_A_RESET_CODE_WAS_SENT | If the account exists, a reset code was sent | API response message. |
| INSTITUTION_REGISTRATION_REJECTED_REASON | Your institution registration was rejected. Reason: {reason} | API response message. |
| INSTITUTION_REGISTRATION_REQUEST_NOT_FOUND | Institution registration request not found | Returned when the requested resource does not exist. |
| INSTITUTION_REGISTRATION_UNDER_REVIEW_EMAIL_NOTICE | Your institution registration request is currently under review. You will receive an email once it has been approved. | API response message. |
| INVALID_ACCESS_TOKEN | Invalid access token | Validation or authorization failure message. |
| INVALID_EMAIL_OR_PASSWORD | Invalid email or password | Validation or authorization failure message. |
| INVALID_OR_EXPIRED_OTP | Invalid or expired OTP | Validation or authorization failure message. |
| INVALID_OR_EXPIRED_TOKEN | Invalid or expired token | Validation or authorization failure message. |
| INVALID_OTP_REMAINING_ATTEMPT_S_REMAINING | Invalid OTP. {remaining} attempt(s) remaining. | Validation or authorization failure message. |
| INVALID_REFRESH_TOKEN | Invalid refresh token | Validation or authorization failure message. |
| INVALID_SUPER_ADMIN_CREDENTIALS | Invalid super admin credentials | Validation or authorization failure message. |
| INVITE_EMAIL_DOES_NOT_MATCH_AUTHENTICATED_USER | Invite email does not match authenticated user | API response message. |
| LOGGED_OUT | Logged out | API response message. |
| MAXIMUM_VERIFICATION_ATTEMPTS_EXCEEDED_REQUEST_A_NEW_OTP | Maximum verification attempts exceeded. Request a new OTP. | API response message. |
| MISSING_AUTHORIZATION_TOKEN | Missing authorization token | API response message. |
| MISSING_TOKEN | Missing token | API response message. |
| NO_ACCOUNT_OR_PENDING_REGISTRATION_FOUND_FOR_THIS_EMAIL | No account or pending registration found for this email. | API response message. |
| NO_ACCOUNT_OR_PENDING_REGISTRATION_FOUND_USE_POST_AUTH_REGISTER | No account or pending registration found for this email. Use POST /auth/register first. | API response message. |
| NO_PENDING_INSTITUTION_REGISTRATION_FOUND_FOR_THIS_USER | No pending institution registration found for this user | API response message. |
| NO_REGISTRATION_FOUND_FOR_THIS_EMAIL | No registration found for this email | API response message. |
| OPENROUTER_INSUFFICIENT_CREDITS | OpenRouter error (402): insufficient credits for this model. Use a free model (set OPENROUTER_MODEL to a ':free' model such as 'meta-llama/llama-3.3-70b-instruct:free'), lower AI_MAX_OUTPUT_TOKENS, or add credits at https://openrouter.ai/settings/credits. | Authorization / permission failure message. |
| OTP_RESEND_LIMIT_REACHED_TRY_AGAIN_LATER | OTP resend limit reached. Try again later. | API response message. |
| OTP_VERIFIED_SET_YOUR_NEW_PASSWORD_VIA_POST_AUTH_RESET_PASSWORD | OTP verified. Set your new password via POST /auth/reset-password. | API response message. |
| PASSWORD_CHANGED | Password changed | API response message. |
| PASSWORD_RESET_OTP_NOT_VERIFIED_CALL_POST_AUTH_VERIFY_OTP_FIRST | Password reset OTP not verified. Call POST /auth/verify-otp first. | API response message. |
| PASSWORD_RESET_SUCCESSFUL | Password reset successful | API response message. |
| PENDING_INVITE_ALREADY_EXISTS_FOR_THIS_EMAIL | Pending invite already exists for this email | API response message. |
| PLEASE_WAIT_WAIT_SECOND_S_BEFORE_REQUESTING_ANOTHER_OTP | Please wait {wait} second(s) before requesting another OTP | API response message. |
| PROCTORING_SESSION_ACTIVE | Proctoring session active | API response message. |
| PROCTORING_SESSION_IS_NOT_ACTIVE | Proctoring session is not active | API response message. |
| PROCTORING_SESSION_NOT_FOUND | Proctoring session not found | Returned when the requested resource does not exist. |
| PROCTORING_SESSION_NOT_FOUND_START_SESSION_FIRST | Proctoring session not found — start session first | Returned when the requested resource does not exist. |
| PROCTORING_SESSION_REQUIRES_AN_IN_PROGRESS_ATTEMPT | Proctoring session requires an in-progress attempt | API response message. |
| QWEN_PROVIDER_REQUIRES_DASHSCOPE_API_KEY_OR_HF_TOKEN_IN_ENVIRONMENT | Qwen provider requires DASHSCOPE_API_KEY or HF_TOKEN in environment | API response message. |
| REFRESH_TOKEN_MISMATCH | Refresh token mismatch | API response message. |
| REGISTRATION_STARTED_CHECK_YOUR_EMAIL_FOR_THE_VERIFICATION_CODE | Registration started. Check your email for the verification code. | API response message. |
| REGISTRATION_SUCCESSFUL_CHECK_YOUR_EMAIL_FOR_THE_VERIFICATION_CODE | Registration successful. Check your email for the verification code. | API response message. |
| SESSION_HAS_EXPIRED | Session has expired | API response message. |
| SESSION_IS_INVALID_OR_EXPIRED | Session is invalid or expired | Validation or authorization failure message. |
| SESSION_IS_NO_LONGER_ACTIVE | Session is no longer active | API response message. |
| STUDENT_REGISTERED_CHECK_YOUR_EMAIL_FOR_THE_VERIFICATION_CODE | Student registered. Check your email for the verification code. | API response message. |
| SUPER_ADMINS_CANNOT_SUSPEND_THEIR_OWN_ACCOUNT | Super admins cannot suspend their own account | API response message. |
| THIS_INSTITUTION_REGISTRATION_WAS_REJECTED | This institution registration was rejected | API response message. |
| USER_ACCOUNT_IS_NOT_ACTIVE | User account is not active | API response message. |
| USE_ACCESS_TOKEN_FROM_LOGIN_NOT_REFRESH_TOKEN | Use access_token from login, not refresh_token | API response message. |
| YOUR_INSTITUTION_REGISTRATION_REQUEST_IS_CURRENTLY_UNDER_REVIEW | Your institution registration request is currently under review. | API response message. |

## Users

| Constant | English Message | Description |
|----------|-----------------|-------------|
| AT_LEAST_ONE_PROFILE_FIELD_IS_REQUIRED | At least one profile field is required | Validation or authorization failure message. |
| ORGANIZATION_IS_ALREADY_SUSPENDED | Organization is already suspended | API response message. |
| ORGANIZATION_IS_NOT_SUSPENDED | Organization is not suspended | API response message. |
| ORGANIZATION_RESTORED_SUCCESSFULLY | Organization restored successfully | Returned after a successful operation. |
| ORGANIZATION_SUSPENDED_SUCCESSFULLY | Organization suspended successfully | Returned after a successful operation. |
| PROFILE_UPDATED_SUCCESSFULLY | Profile updated successfully | Returned after a successful operation. |
| SUPER_ADMIN_ACCESS_REQUIRED | Super admin access required | Validation or authorization failure message. |
| SUSPENSION_REASON_IS_REQUIRED | Suspension reason is required | Validation or authorization failure message. |
| USER_IS_ALREADY_SUSPENDED | User is already suspended | API response message. |
| USER_IS_NOT_SUSPENDED | User is not suspended | API response message. |
| USER_NOT_FOUND | User not found | Returned when the requested resource does not exist. |
| USER_RESTORED_SUCCESSFULLY | User restored successfully | Returned after a successful operation. |
| USER_SUSPENDED_SUCCESSFULLY | User suspended successfully | Returned after a successful operation. |

## Workspaces

| Constant | English Message | Description |
|----------|-----------------|-------------|
| ALREADY_A_MEMBER_OF_THIS_WORKSPACE | Already a member of this workspace | API response message. |
| ATTEMPT_IS_NOT_A_WORKSPACE_ROLE | Attempt is not a workspace {role} | API response message. |
| A_SUBJECT_WITH_THIS_NAME_ALREADY_EXISTS_IN_THE_WORKSPACE | A subject with this name already exists in the workspace | API response message. |
| CANNOT_REMOVE_THE_WORKSPACE_OWNER | Cannot remove the workspace owner | API response message. |
| COULD_NOT_GENERATE_UNIQUE_JOIN_CODE | Could not generate unique join code | API response message. |
| GROUP_MEMBERS_UPDATED | Group members updated | Returned after a successful operation. |
| INVALID_JOIN_CODE | Invalid join code | Validation or authorization failure message. |
| INVALID_WORKSPACE_KIND | Invalid workspace kind | Validation or authorization failure message. |
| JOINED_WORKSPACE | Joined workspace | API response message. |
| MEMBERSHIP_ALREADY_HAS_A_DIFFERENT_SUBJECT_ROLE_ON_THIS_SUBJECT | Membership already has a different subject role on this subject | API response message. |
| MEMBERSHIP_IS_NOT_ACTIVE | Membership is not active | API response message. |
| MEMBERSHIP_IS_NOT_A_WORKSPACE_ROLE | Membership is not a workspace {role} | API response message. |
| MEMBERSHIP_NOT_FOUND_IN_THIS_WORKSPACE | Membership not found in this workspace | Returned when the requested resource does not exist. |
| MEMBERSHIP_ROLE_MUST_BE_STUDENT | Membership role must be STUDENT | Validation or authorization failure message. |
| MEMBERSHIP_STUDENT_MEMBERSHIP_ID_IS_NOT_A_STUDENT | Membership {student_membership_id} is not a student | API response message. |
| MEMBERSHIP_S_ARE_NOT_ACTIVE_INACTIVE_MEMBERSHIPS | Membership(s) are not active: {inactive_memberships} | API response message. |
| MEMBERSHIP_S_NOT_FOUND_IN_WORKSPACE_MISSING_IN_WORKSPACE | Membership(s) not found in workspace: {missing_in_workspace} | Returned when the requested resource does not exist. |
| MEMBER_DETAILS_ARE_ONLY_AVAILABLE_FOR_STUDENTS_AND_TEACHERS | Member details are only available for students and teachers | API response message. |
| MEMBER_REMOVED_FROM_GROUP | Member removed from group | API response message. |
| NOT_AN_ACTIVE_MEMBER_OF_THIS_WORKSPACE | Not an active member of this workspace | API response message. |
| NOT_A_MEMBER_OF_THIS_WORKSPACE | Not a member of this workspace | API response message. |
| ONLY_ADMIN_OWNER_OR_ASSIGNED_SUBJECT_TEACHERS_CAN_ENROLL_STUDENTS | Only admin, owner, or assigned subject teachers can enroll students | Authorization / permission failure message. |
| ONLY_STUDENT_MEMBERSHIPS_ARE_ALLOWED_NOT_STUDENT_ROLE | Only STUDENT memberships are allowed: {not_student_role} | Authorization / permission failure message. |
| ONLY_SUBJECT_TEACHERS_OR_WORKSPACE_ADMINS_CAN_MANAGE_STUDENT_GROUPS | Only subject teachers or workspace admins can manage student groups | Authorization / permission failure message. |
| ONLY_THE_CREATOR_OR_WORKSPACE_ADMIN_CAN_DELETE_THIS_BANK | Only the creator or workspace admin can delete this bank | Authorization / permission failure message. |
| ONLY_THE_CREATOR_OR_WORKSPACE_ADMIN_CAN_UPDATE_THIS_BANK | Only the creator or workspace admin can update this bank | Authorization / permission failure message. |
| ONLY_THE_INSTITUTION_OWNER_OR_WORKSPACE_ADMIN_CAN_LIST_WORKSPACE_MEMBERS | Only the institution owner or workspace admin can list workspace members | Authorization / permission failure message. |
| ONLY_THE_WORKSPACE_OWNER_CAN_DELETE_THIS_WORKSPACE | Only the workspace owner can delete this workspace | Authorization / permission failure message. |
| ONLY_THE_WORKSPACE_OWNER_OR_ADMIN_CAN_LIST_STUDENTS | Only the workspace owner or admin can list students | Authorization / permission failure message. |
| ONLY_THE_WORKSPACE_OWNER_OR_ADMIN_CAN_MANAGE_WORKSPACE_MEMBERS | Only the workspace owner or admin can manage workspace members | Authorization / permission failure message. |
| ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_ARCHIVE_SUBJECTS | Only workspace owner or admin can archive subjects | Authorization / permission failure message. |
| ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_ASSIGN_SUBJECTS_TO_STUDENTS | Only workspace owner or admin can assign subjects to students | Authorization / permission failure message. |
| ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_ASSIGN_TEACHERS | Only workspace owner or admin can assign teachers | Authorization / permission failure message. |
| ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_CREATE_SUBJECTS | Only workspace owner or admin can create subjects | Authorization / permission failure message. |
| ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_MANAGE_TOPICS | Only workspace owner or admin can manage topics | Authorization / permission failure message. |
| ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_REMOVE_STUDENT_SUBJECT_ASSIGNMENTS | Only workspace owner or admin can remove student subject assignments | Authorization / permission failure message. |
| ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_REMOVE_TEACHERS | Only workspace owner or admin can remove teachers | Authorization / permission failure message. |
| ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_UPDATE_STUDENT_SUBJECT_ASSIGNMENTS | Only workspace owner or admin can update student subject assignments | Authorization / permission failure message. |
| ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_UPDATE_SUBJECTS | Only workspace owner or admin can update subjects | Authorization / permission failure message. |
| ONLY_WORKSPACE_TEACHERS_OR_ADMINS_CAN_BE_ASSIGNED_AS_SUBJECT_TEACHERS | Only workspace teachers or admins can be assigned as subject teachers | Authorization / permission failure message. |
| ORGANIZATION_NOT_FOUND | Organization not found | Returned when the requested resource does not exist. |
| QUESTION_QUESTION_ID_NOT_FOUND_IN_WORKSPACE | Question {question_id} not found in workspace | Returned when the requested resource does not exist. |
| SOLO_WORKSPACES_CAN_ONLY_INVITE_STUDENTS_OWNER_IS_THE_TEACHER | SOLO workspaces can only invite students (owner is the teacher) | API response message. |
| STUDENT_IS_NOT_A_MEMBER_OF_THIS_GROUP | Student is not a member of this group | API response message. |
| STUDENT_MEMBERSHIPS_NOT_ENROLLED_IN_EXAM_SUBJECT | Student membership(s) are not enrolled in the exam subject: {membership_ids} | API response message. |
| STUDENT_MEMBERSHIP_IDS_MUST_CONTAIN_AT_LEAST_ONE_ID | student_membership_ids must contain at least one id | Validation or authorization failure message. |
| STUDENT_MEMBERSHIP_S_ARE_NOT_ENROLLED_IN_THE_EXAM_SUBJECT | Student membership(s) are not enrolled in the exam subject: | API response message. |
| STUDENT_REMOVED_FROM_WORKSPACE_SUCCESSFULLY | Student removed from workspace successfully. | Returned after a successful operation. |
| STUDENT_STUDENT_MEMBERSHIP_ID_IS_NOT_AN_ACTIVE_WORKSPACE_MEMBER | Student {student_membership_id} is not an active workspace member | API response message. |
| STUDENT_STUDENT_MEMBERSHIP_ID_IS_NOT_A_MEMBER_OF_THIS_WORKSPACE | Student {student_membership_id} is not a member of this workspace | API response message. |
| STUDENT_STUDENT_MEMBERSHIP_ID_IS_NOT_ENROLLED_IN_THIS_SUBJECT | Student {student_membership_id} is not enrolled in this subject | API response message. |
| SUBJECT_NOT_FOUND_IN_THIS_WORKSPACE | Subject not found in this workspace | Returned when the requested resource does not exist. |
| TEACHER_REMOVED_FROM_WORKSPACE_SUCCESSFULLY | Teacher removed from workspace successfully. | Returned after a successful operation. |
| TEST_NOT_FOUND_IN_THIS_WORKSPACE | Test not found in this workspace | Returned when the requested resource does not exist. |
| THIS_ENDPOINT_IS_ONLY_AVAILABLE_FOR_INSTITUTION_WORKSPACES | This endpoint is only available for institution workspaces | API response message. |
| THIS_INSTITUTION_IS_NOT_YET_APPROVED_FOR_MEMBERS | This institution is not yet approved for members | API response message. |
| THIS_WORKSPACE_IS_NOT_ACCEPTING_NEW_MEMBERS | This workspace is not accepting new members | API response message. |
| UNSUPPORTED_WORKSPACE_TYPE_FOR_MEMBER_MANAGEMENT | Unsupported workspace type for member management | API response message. |
| UNSUPPORTED_WORKSPACE_TYPE_FOR_STUDENT_LISTING | Unsupported workspace type for student listing | API response message. |
| WORKSPACE_CREATED | Workspace created | Returned after a successful operation. |
| WORKSPACE_DELETED | Workspace deleted | Returned after a successful operation. |
| WORKSPACE_ID_QUERY_PARAMETER_IS_REQUIRED | workspace_id query parameter is required | Validation or authorization failure message. |
| WORKSPACE_IS_NOT_ACTIVE | Workspace is not active | API response message. |
| WORKSPACE_MEMBER_UPDATED_SUCCESSFULLY | Workspace member updated successfully | Returned after a successful operation. |
| WORKSPACE_NOT_FOUND | Workspace not found | Returned when the requested resource does not exist. |
| WORKSPACE_SLUG_ALREADY_EXISTS | Workspace slug already exists | API response message. |
| WORKSPACE_SLUG_IS_NO_LONGER_AVAILABLE | Workspace slug is no longer available | API response message. |
| WORKSPACE_UPDATED | Workspace updated | Returned after a successful operation. |
| X_WORKSPACE_ID_HEADER_IS_REQUIRED | X-Workspace-Id header is required | Validation or authorization failure message. |

## Subjects

| Constant | English Message | Description |
|----------|-----------------|-------------|
| A_GROUP_WITH_THIS_NAME_ALREADY_EXISTS_IN_THE_SUBJECT | A group with this name already exists in the subject | API response message. |
| A_SUBJECT_WITH_THIS_NAME_ALREADY_EXISTS | A subject with this name already exists | API response message. |
| A_TOPIC_WITH_THIS_NAME_ALREADY_EXISTS_IN_THE_SUBJECT | A topic with this name already exists in the subject | API response message. |
| BANK_BANK_ID_BELONGS_TO_SUBJECT_BANK_SUBJECT_ID_BUT_THE_EXAM | Bank {bank_id} belongs to subject {bank_subject_id}, but the exam is for subject {test_subject_id} | API response message. |
| FIELD_PREFIX_TOPIC_ID_MUST_REFERENCE_AN_EXISTING_TOPIC_IN_THE_BANK | {field_prefix}: topic_id must reference an existing topic in the bank's subject (subject_id={subject_id}) | Validation or authorization failure message. |
| INSUFFICIENT_PERMISSIONS_TO_LIST_SUBJECTS | Insufficient permissions to list subjects | Authorization / permission failure message. |
| INSUFFICIENT_PERMISSIONS_TO_REMOVE_STUDENT_ENROLLMENT | Insufficient permissions to remove student enrollment | Authorization / permission failure message. |
| INSUFFICIENT_PERMISSIONS_TO_VIEW_STUDENT_SUBJECT_ASSIGNMENTS | Insufficient permissions to view student subject assignments | Authorization / permission failure message. |
| ONLY_STUDENTS_CAN_BE_ENROLLED_IN_A_SUBJECT | Only students can be enrolled in a subject | Authorization / permission failure message. |
| ONLY_STUDENTS_ENROLLED_IN_THE_SUBJECT_CAN_TAKE_TESTS | Only students enrolled in the subject can take tests | Authorization / permission failure message. |
| QUESTION_QUESTION_ID_DOES_NOT_BELONG_TO_THE_TEST_SUBJECT | Question {question_id} does not belong to the test subject | API response message. |
| ROW_ROW_NUMBER_TOPIC_ID_TOPIC_ID_DOES_NOT_BELONG_TO_THE | Row {row_number}: Topic ID {topic_id} does not belong to the exam subject | API response message. |
| SELECTED_BANK_DOES_NOT_BELONG_TO_EXAM_SUBJECT | Selected bank does not belong to exam subject | API response message. |
| STUDENT_ENROLLED_IN_SUBJECT | Student enrolled in subject | API response message. |
| STUDENT_ENROLLMENT_NOT_FOUND | Student enrollment not found | Returned when the requested resource does not exist. |
| STUDENT_IS_ALREADY_ENROLLED_IN_THIS_SUBJECT | Student is already enrolled in this subject | API response message. |
| STUDENT_REMOVED_FROM_SUBJECT | Student removed from subject | API response message. |
| STUDENT_SUBJECT_ASSIGNMENTS_UPDATED | Student subject assignments updated | Returned after a successful operation. |
| STUDENT_SUBJECT_ASSIGNMENT_NOT_FOUND | Student subject assignment not found | Returned when the requested resource does not exist. |
| STUDENT_SUBJECT_ENROLLMENT_REQUIRED | Student subject enrollment required | Validation or authorization failure message. |
| SUBJECTS_ASSIGNED_TO_STUDENT | Subjects assigned to student | API response message. |
| SUBJECT_ARCHIVED | Subject archived | API response message. |
| SUBJECT_CREATED | Subject created | Returned after a successful operation. |
| SUBJECT_IDS_IS_REQUIRED | subject_ids is required | Validation or authorization failure message. |
| SUBJECT_NOT_FOUND | Subject not found | Returned when the requested resource does not exist. |
| SUBJECT_REMOVED_FROM_STUDENT | Subject removed from student | API response message. |
| SUBJECT_UPDATED | Subject updated | Returned after a successful operation. |
| TEACHERS_CAN_ONLY_INVITE_STUDENTS | Teachers can only invite students | API response message. |
| TEACHERS_MAY_ONLY_LIST_STUDENTS_FOR_SUBJECTS_THEY_TEACH | Teachers may only list students for subjects they teach | API response message. |
| TEACHER_ASSIGNED_TO_SUBJECT | Teacher assigned to subject | API response message. |
| TEACHER_ASSIGNMENT_NOT_FOUND | Teacher assignment not found | Returned when the requested resource does not exist. |
| TEACHER_IS_ALREADY_ASSIGNED_TO_THIS_SUBJECT | Teacher is already assigned to this subject | API response message. |
| TEACHER_REMOVED_FROM_SUBJECT | Teacher removed from subject | API response message. |
| TEST_MUST_HAVE_A_SUBJECT_FOR_AI_QUESTION_GENERATION | Test must have a subject for AI question generation | Validation or authorization failure message. |
| THE_TEACHER_ALREADY_HAS_ANOTHER_SCHEDULED_EXAM_DURING_THIS_TIME | The teacher already has another scheduled exam during this time. | API response message. |
| TOPIC_ID_S_DO_NOT_BELONG_TO_THE_EXAM_SUBJECT_MISSING | topic_id(s) do not belong to the exam subject: {missing} | API response message. |
| TOPIC_ID_TOPIC_ID_DOES_NOT_BELONG_TO_THE_EXAM_SUBJECT | topic_id {topic_id} does not belong to the exam subject | API response message. |
| YOU_ARE_NOT_ALLOWED_TO_CREATE_EXAMS_FOR_THIS_SUBJECT | You are not allowed to create exams for this subject | API response message. |
| YOU_ARE_NOT_ENROLLED_IN_THIS_TESTS_SUBJECT | You are not enrolled in this test's subject | API response message. |
| YOU_DO_NOT_HAVE_ACCESS_TO_THIS_SUBJECT | You do not have access to this subject | API response message. |
| YOU_MUST_BE_ASSIGNED_TO_THIS_SUBJECT_AS_TEACHER_TO_MANAGE_QUESTION_BANKS | You must be assigned to this subject as TEACHER to manage question banks | Validation or authorization failure message. |
| YOU_NEED_AN_ACTIVE_ASSIGNMENT_TO_THIS_SUBJECT_TO_ACCESS_TOPICS | You need an active assignment to this subject to access topics | API response message. |

## Topics

| Constant | English Message | Description |
|----------|-----------------|-------------|
| BANK_BANK_ID_DOES_NOT_CONTAIN_TOPIC_TOPIC_ID | Bank {bank_id} does not contain Topic {topic_id} | API response message. |
| BANK_BANK_ID_DOES_NOT_CONTAIN_TOPIC_TOPIC_LABEL | Bank {bank_id} does not contain Topic {topic_label} | API response message. |
| CANNOT_DELETE_TOPIC_QUESTION_COUNT_QUESTION_S_STILL_REFERENCE_IT | Cannot delete topic: {question_count} question(s) still reference it | API response message. |
| DIFFICULTY_PERCENTAGES_MUST_TOTAL_100_INSIDE_TOPIC_TOPIC_NAME_GOT_DIFF | Difficulty percentages must total 100% inside Topic {topic_name} (got {diff_sum}%) | Validation or authorization failure message. |
| DUPLICATE_TOPIC_ID_ENTRIES_ARE_NOT_ALLOWED_FOR_BANK_BANK_ID | Duplicate topic_id entries are not allowed for bank {bank_id} | API response message. |
| FIELD_PREFIX_TOPIC_ID_MUST_BE_A_VALID_INTEGER | {field_prefix}: topic_id must be a valid integer | Validation or authorization failure message. |
| NOT_ENOUGH_SLOT_DIFFICULTY_QUESTIONS_INSIDE_TOPIC_TOPIC_LABEL_BANK_SLO | Not enough {slot_difficulty} questions inside Topic {topic_label} (bank {slot_bank_id}): requested {slot_count}, found {len_batch} | API response message. |
| NOT_ENOUGH_SLOT_DIFFICULTY_QUESTIONS_INSIDE_TOPIC_TOPIC_LABEL_REQUESTE | Not enough {slot_difficulty} questions inside Topic {topic_label}: requested {slot_count}, only {available} exist | API response message. |
| ROW_ROW_NUMBER_TOPIC_ID_MUST_BE_A_VALID_INTEGER | Row {row_number}: Topic ID must be a valid integer | Validation or authorization failure message. |
| ROW_ROW_NUMBER_TOPIC_ID_MUST_BE_POSITIVE | Row {row_number}: Topic ID must be positive | Validation or authorization failure message. |
| TOPIC_CREATED | Topic created | Returned after a successful operation. |
| TOPIC_DELETED | Topic deleted | Returned after a successful operation. |
| TOPIC_IDS_MUST_CONTAIN_AT_LEAST_ONE_TOPIC | topic_ids must contain at least one topic | Validation or authorization failure message. |
| TOPIC_IDS_MUST_CONTAIN_POSITIVE_INTEGERS | topic_ids must contain positive integers | Validation or authorization failure message. |
| TOPIC_ID_MUST_BE_A_VALID_INTEGER | topic_id must be a valid integer | Validation or authorization failure message. |
| TOPIC_NOT_FOUND | Topic not found | Returned when the requested resource does not exist. |
| TOPIC_PERCENTAGES_MUST_TOTAL_100_FOR_BANK_BANK_ID_GOT_SUM_TOPIC | Topic percentages must total 100% for bank {bank_id} (got {sum_topic_weights_values}%) | Validation or authorization failure message. |
| TOPIC_TOPIC_ID_DOES_NOT_EXIST | Topic {topic_id} does not exist | API response message. |
| TOPIC_UPDATED | Topic updated | Returned after a successful operation. |

## Question Banks

| Constant | English Message | Description |
|----------|-----------------|-------------|
| INVALID_VISIBILITY_VALUE | Invalid visibility value | Validation or authorization failure message. |
| QUESTION_BANK_ARCHIVED | Question bank archived | API response message. |
| QUESTION_BANK_CREATED | Question bank created | Returned after a successful operation. |
| QUESTION_BANK_NOT_FOUND | Question bank not found | Returned when the requested resource does not exist. |
| QUESTION_BANK_SELECTION_ADDED | Question bank selection added | API response message. |
| QUESTION_BANK_UPDATED | Question bank updated | Returned after a successful operation. |
| QUESTION_NOT_FOUND_IN_THIS_BANK | Question not found in this bank | Returned when the requested resource does not exist. |
| QUESTION_QUESTION_ID_NOT_FOUND_IN_SELECTED_BANK | Question {question_id} not found in selected bank | Returned when the requested resource does not exist. |
| YOU_DO_NOT_HAVE_ACCESS_TO_THIS_QUESTION_BANK | You do not have access to this question bank | API response message. |

## Questions

| Constant | English Message | Description |
|----------|-----------------|-------------|
| AI_GENERATED_QUESTION_DELETED | AI generated question deleted | Returned after a successful operation. |
| AI_GENERATED_QUESTION_NOT_FOUND | AI generated question not found | Returned when the requested resource does not exist. |
| AI_GENERATED_QUESTION_UPDATED | AI generated question updated | Returned after a successful operation. |
| AI_QUESTIONS_GENERATED_FOR_REVIEW | AI questions generated for review | API response message. |
| AI_QUESTIONS_IMPORTED_INTO_TEST | AI questions imported into test | API response message. |
| AI_QUESTION_ALREADY_IMPORTED | AI question {question_id} already imported | API response message. |
| AI_QUESTION_GENERATION_FAILED_EXC | AI question generation failed: {exc} | API response message. |
| AI_QUESTION_IS_MISSING_BODY_TEXT | AI question #{index} is missing body text | API response message. |
| AI_QUESTION_IS_NOT_AN_OBJECT | AI question #{index} is not an object | API response message. |
| AI_RESPONSE_DID_NOT_INCLUDE_A_QUESTIONS_ARRAY | AI response did not include a questions array | API response message. |
| AI_RETURNED_LEN_QUESTIONS_QUESTION_S_EXPECTED_EXPECTED | AI returned {len_questions} question(s), expected {expected} | API response message. |
| ALL_QUESTIONS_MUST_BE_ANSWERED_BEFORE_SUBMISSION | All questions must be answered before submission. | Validation or authorization failure message. |
| ALL_QUESTIONS_MUST_BE_ANSWERED_BEFORE_SUBMISSION_MISSING_ANSWERS_FOR_QUESTION_ID | All questions must be answered before submission. Missing answers for question IDs: {missing_question_ids} | Validation or authorization failure message. |
| CANNOT_MODIFY_EXAM_QUESTIONS_AFTER_STUDENT_ATTEMPTS_HAVE_BEEN_RECORDED | Cannot modify exam questions after student attempts have been recorded | API response message. |
| CHOICE_AT_INDEX_IDX_MUST_HAVE_A_NON_EMPTY_BODY | Choice at index {idx} must have a non-empty body | Validation or authorization failure message. |
| CHOICE_AT_INDEX_IDX_MUST_INCLUDE_IS_CORRECT | Choice at index {idx} must include is_correct | Validation or authorization failure message. |
| CSV_FILE_MUST_CONTAIN_AT_LEAST_ONE_NON_EMPTY_QUESTION_ROW | CSV file must contain at least one non-empty question row | Validation or authorization failure message. |
| CSV_FILE_MUST_CONTAIN_AT_LEAST_ONE_QUESTION_ROW | CSV file must contain at least one question row | Validation or authorization failure message. |
| CSV_QUESTIONS_IMPORTED | CSV questions imported | API response message. |
| EARNED_SCORE_FOR_QUESTION_TEST_QUESTION_ID_CANNOT_EXCEED_MAX_POINTS | earned_score for question {test_question_id} cannot exceed {max_points} | API response message. |
| ESSAY_QUESTIONS_CANNOT_INCLUDE_SELECTED_CHOICE_INDICES | ESSAY questions cannot include selected_choice_indices | API response message. |
| ESSAY_QUESTIONS_MUST_NOT_INCLUDE_CHOICES | ESSAY questions must not include choices | Validation or authorization failure message. |
| GEMINI_API_KEY_IS_REQUIRED_WHEN_AI_QUESTION_PROVIDER_GEMINI | GEMINI_API_KEY is required when AI_QUESTION_PROVIDER=gemini | Validation or authorization failure message. |
| INVALID_DIFFICULTY_VALUE | invalid difficulty value | Validation or authorization failure message. |
| MANUAL_QUESTIONS_ADDED | Manual questions added | API response message. |
| MANUAL_QUESTION_ADDED | Manual question added | API response message. |
| MCQ_QUESTIONS_MUST_HAVE_AT_LEAST_TWO_CHOICES | MCQ questions must have at least two choices | Validation or authorization failure message. |
| MCQ_QUESTIONS_MUST_HAVE_EXACTLY_ONE_CORRECT_CHOICE | MCQ questions must have exactly one correct choice | Validation or authorization failure message. |
| MISSING_ANSWERS_FOR_QUESTION_IDS_MISSING_QUESTION_IDS | Missing answers for question IDs: {missing_question_ids} | API response message. |
| MULTI_SELECT_QUESTIONS_MUST_HAVE_AT_LEAST_ONE_CORRECT_CHOICE | MULTI_SELECT questions must have at least one correct choice | Validation or authorization failure message. |
| MULTI_SELECT_QUESTIONS_MUST_HAVE_AT_LEAST_TWO_CHOICES | MULTI_SELECT questions must have at least two choices | Validation or authorization failure message. |
| NORMALIZED_QUESTIONS_REQUIRE_AT_LEAST_ONE_CHOICE | {normalized} questions require at least one choice | API response message. |
| ONLY_PENDING_REVIEW_AI_QUESTIONS_CAN_BE_EDITED | Only pending review AI questions can be edited | Authorization / permission failure message. |
| OPENROUTER_API_KEY_IS_REQUIRED_WHEN_AI_QUESTION_PROVIDER_OPENROUTER | OPENROUTER_API_KEY is required when AI_QUESTION_PROVIDER=openrouter | Validation or authorization failure message. |
| POINTS_MUST_BE_NON_NEGATIVE | points must be non-negative | Validation or authorization failure message. |
| PREFIX_INVALID_DIFFICULTY_VALUE | {prefix}: invalid difficulty value | Validation or authorization failure message. |
| PREFIX_POINTS_MUST_BE_NON_NEGATIVE | {prefix}: points must be non-negative | Validation or authorization failure message. |
| PREFIX_QUESTION_TYPE_TYPE_CODE_IS_NOT_CONFIGURED_RUN_FLASK_SEED | {prefix}: question type '{type_code}' is not configured. Run flask seed. | API response message. |
| QUESTIONS_ADDED_TO_TEST | Questions added to test | API response message. |
| QUESTIONS_CAN_ONLY_BE_ADDED_WHILE_TEST_IS_DRAFT | Questions can only be added while test is DRAFT | API response message. |
| QUESTIONS_CAN_ONLY_BE_MODIFIED_WHILE_TEST_IS_DRAFT | Questions can only be modified while test is DRAFT | API response message. |
| QUESTIONS_CREATED | Questions created | Returned after a successful operation. |
| QUESTIONS_MUST_CONTAIN_AT_LEAST_ONE_ITEM | questions must contain at least one item | Validation or authorization failure message. |
| QUESTION_BODY_IS_REQUIRED | Question body is required | Validation or authorization failure message. |
| QUESTION_DELETED | Question deleted | Returned after a successful operation. |
| QUESTION_IDS_MUST_CONTAIN_AT_LEAST_ONE_ID | question_ids must contain at least one id | Validation or authorization failure message. |
| QUESTION_IDS_MUST_CONTAIN_AT_LEAST_ONE_ITEM | question_ids must contain at least one item | Validation or authorization failure message. |
| QUESTION_TYPE_TYPE_CODE_IS_NOT_CONFIGURED_RUN_FLASK_SEED | Question type '{type_code}' is not configured. Run flask seed. | API response message. |
| QUESTION_UPDATED | Question updated | Returned after a successful operation. |
| ROW_ROW_NUMBER_AT_LEAST_ONE_CHOICE_IS_REQUIRED | Row {row_number}: at least one choice is required | Validation or authorization failure message. |
| ROW_ROW_NUMBER_CHOICES_MUST_BE_VALID_JSON_ARRAY | Row {row_number}: choices must be valid JSON array | Validation or authorization failure message. |
| ROW_ROW_NUMBER_ESSAY_QUESTIONS_MUST_LEAVE_CORRECT_ANSWERS_EMPTY | Row {row_number}: ESSAY questions must leave Correct Answers empty | Validation or authorization failure message. |
| ROW_ROW_NUMBER_INVALID_QUESTION_TYPE_RAW_TYPE_ALLOWED_MCQ_TRUE_FALSE | Row {row_number}: invalid question type '{raw_type}'. Allowed: MCQ, TRUE_FALSE, MULTI_SELECT, ESSAY | Validation or authorization failure message. |
| ROW_ROW_NUMBER_MCQ_QUESTIONS_MUST_HAVE_EXACTLY_ONE_CORRECT_ANSWER | Row {row_number}: MCQ questions must have exactly one correct answer | Validation or authorization failure message. |
| ROW_ROW_NUMBER_MULTI_SELECT_QUESTIONS_MUST_HAVE_AT_LEAST_ONE_CORRECT | Row {row_number}: MULTI_SELECT questions must have at least one correct answer | Validation or authorization failure message. |
| ROW_ROW_NUMBER_POINTS_MUST_BE_A_NUMBER | Row {row_number}: Points must be a number | Validation or authorization failure message. |
| ROW_ROW_NUMBER_POINTS_MUST_BE_GREATER_THAN_0 | Row {row_number}: Points must be greater than 0 | Validation or authorization failure message. |
| ROW_ROW_NUMBER_QUESTION_TEXT_IS_REQUIRED | Row {row_number}: Question text is required | Validation or authorization failure message. |
| ROW_ROW_NUMBER_QUESTION_TYPE_IS_REQUIRED | Row {row_number}: Question Type is required | Validation or authorization failure message. |
| ROW_ROW_NUMBER_TRUE_FALSE_QUESTIONS_MAY_ONLY_USE_CHOICE_A_AND | Row {row_number}: TRUE_FALSE questions may only use Choice A and Choice B | API response message. |
| SELECTED_CHOICE_INDICES_MUST_BE_AN_ARRAY_OF_INTEGERS | selected_choice_indices must be an array of integers | Validation or authorization failure message. |
| SOME_QUESTION_IDS_DO_NOT_BELONG_TO_THE_GENERATION_REQUEST | Some question_ids do not belong to the generation request | API response message. |
| TEST_QUESTION_ID_TEST_QUESTION_ID_IS_NOT_PART_OF_THIS_EXAM | test_question_id {test_question_id} is not part of this exam | API response message. |
| TEST_QUESTION_ID_TEST_QUESTION_ID_IS_NOT_PENDING_MANUAL_GRADING | test_question_id {test_question_id} is not pending manual grading | API response message. |
| TEST_QUESTION_NOT_FOUND | Test question not found | Returned when the requested resource does not exist. |
| TEST_QUESTION_NOT_FOUND_IN_THIS_EXAM | Test question not found in this exam | Returned when the requested resource does not exist. |
| TEST_QUESTION_REMOVED | Test question removed | API response message. |
| TEST_QUESTION_TEST_QUESTION_ID_NOT_FOUND_IN_THIS_EXAM | Test question {test_question_id} not found in this exam | Returned when the requested resource does not exist. |
| TEST_QUESTION_UPDATED | Test question updated | Returned after a successful operation. |
| TRUE_FALSE_QUESTIONS_MUST_HAVE_EXACTLY_ONE_CORRECT_CHOICE | TRUE_FALSE questions must have exactly one correct choice | Validation or authorization failure message. |
| TRUE_FALSE_QUESTIONS_MUST_HAVE_EXACTLY_TWO_CHOICES | TRUE_FALSE questions must have exactly two choices | Validation or authorization failure message. |
| TYPE_CODE_QUESTIONS_REQUIRE_SELECTED_CHOICE_INDICES | {type_code} questions require selected_choice_indices | API response message. |
| UNRECOGNIZED_CSV_FORMAT_DOWNLOAD_THE_TEMPLATE_FROM_GET_TEMPLATES_EXAM_QUESTIONS | Unrecognized CSV format. Download the template from GET /templates/exam-questions-csv | API response message. |

## Tests

| Constant | English Message | Description |
|----------|-----------------|-------------|
| ARCHIVED_TESTS_CANNOT_BE_CLOSED | Archived tests cannot be closed | API response message. |
| BLUEPRINT_GENERATED_SUCCESSFULLY | Blueprint generated successfully | Returned after a successful operation. |
| CLOSED_OR_ARCHIVED_TESTS_CANNOT_BE_PUBLISHED | Closed or archived tests cannot be published | API response message. |
| CLOSED_OR_ARCHIVED_TESTS_CANNOT_BE_SCHEDULED | Closed or archived tests cannot be scheduled | API response message. |
| CSV_FILE_IS_REQUIRED | csv_file is required | Validation or authorization failure message. |
| CSV_HEADERS_ARE_REQUIRED | CSV headers are required | Validation or authorization failure message. |
| EXAM_HAS_ALREADY_ENDED | Exam has already ended | API response message. |
| EXAM_IS_NO_LONGER_AVAILABLE_FOR_RESUME | Exam is no longer available for resume | API response message. |
| GRADED_TEST_RESULT_NOT_FOUND | Graded test result not found | Returned when the requested resource does not exist. |
| NO_IN_PROGRESS_ATTEMPT_FOR_THIS_TEST | No in-progress attempt for this test | API response message. |
| ONLY_DRAFT_TESTS_ARE_EDITABLE | Only DRAFT tests are editable | Authorization / permission failure message. |
| ONLY_THE_TEST_CREATOR_CAN_DELETE_THIS_TEST | Only the test creator can delete this test | Authorization / permission failure message. |
| PROCTORING_IS_NOT_ENABLED_FOR_THIS_TEST | Proctoring is not enabled for this test | API response message. |
| PUBLISH_AT_IS_REQUIRED | publish_at is required | Validation or authorization failure message. |
| PUBLISH_AT_MUST_BE_IN_THE_FUTURE | publish_at must be in the future | Validation or authorization failure message. |
| REQUEST_ID_DOES_NOT_BELONG_TO_THIS_TEST | request_id does not belong to this test | API response message. |
| SCHEDULED_TESTS_CAN_ONLY_BE_EDITED_AT_LEAST_30_MINUTES_BEFORE_PUBLISH_TIME | Scheduled tests can only be edited at least 30 minutes before publish time | API response message. |
| SCHEDULED_TEST_IS_MISSING_SCHEDULED_PUBLISH_AT | Scheduled test is missing scheduled_publish_at | API response message. |
| SLUG_ALREADY_IN_USE | Slug already in use | API response message. |
| SLUG_CANNOT_BE_EMPTY | slug cannot be empty | API response message. |
| SLUG_MUST_CONTAIN_AT_LEAST_ONE_LATIN_LETTER_OR_DIGIT_A_Z_0_9 | slug must contain at least one latin letter or digit (a-z, 0-9) | Validation or authorization failure message. |
| TEST_ARCHIVED | Test archived | API response message. |
| TEST_ATTEMPT_IS_NOT_FULLY_GRADED | Test attempt is not fully graded | API response message. |
| TEST_CLOSED | Test closed | API response message. |
| TEST_CREATED_SUCCESSFULLY | Test created successfully | Returned after a successful operation. |
| TEST_DELETED_SUCCESSFULLY | Test deleted successfully | Returned after a successful operation. |
| TEST_DURATION_IS_NOT_CONFIGURED | Test duration is not configured | API response message. |
| TEST_HAS_NOT_STARTED_YET | Test has not started yet | API response message. |
| TEST_IS_NOT_PUBLISHED | Test is not published | API response message. |
| TEST_NOT_FOUND | Test not found | Returned when the requested resource does not exist. |
| TEST_PUBLISHED | Test published | API response message. |
| TEST_SCHEDULED | Test scheduled | API response message. |
| TEST_SLUG_SLUG_IS_ALREADY_USED_BY_TEST_ID_EXISTING_ID | Test slug '{slug}' is already used by test id {existing_id} | API response message. |
| TEST_STARTS_AT_AND_DURATION_MINUTES_ARE_REQUIRED_FOR_SCHEDULED_EXAMS | Test starts_at and duration_minutes are required for scheduled exams | Validation or authorization failure message. |
| TEST_START_TIME_IS_NOT_CONFIGURED | Test start time is not configured | API response message. |
| TEST_UPDATED | Test updated | Returned after a successful operation. |
| THIS_EXAM_OVERLAPS_WITH_ANOTHER_SCHEDULED_EXAM_FOR_ONE_OR_MORE_STUDENTS | This exam overlaps with another scheduled exam for one or more students. | API response message. |
| UPLOADED_CSV_FILE_IS_EMPTY | Uploaded CSV file is empty | API response message. |
| YOU_ARE_NOT_ASSIGNED_TO_THIS_EXAM | You are not assigned to this exam | API response message. |
| YOU_DO_NOT_HAVE_ACCESS_TO_THIS_TEST | You do not have access to this test | API response message. |

## Attempts

| Constant | English Message | Description |
|----------|-----------------|-------------|
| ANSWERS_SAVED | Answers saved | API response message. |
| ANSWER_UPDATED | Answer updated | Returned after a successful operation. |
| ATTEMPT_FORCE_SUBMITTED | Attempt force-submitted | API response message. |
| ATTEMPT_IS_ALREADY_FINALIZED | Attempt is already finalized | API response message. |
| ATTEMPT_IS_NOT_IN_PROGRESS | Attempt is not in progress | API response message. |
| ATTEMPT_NOT_FOUND | Attempt not found | Returned when the requested resource does not exist. |
| ATTEMPT_RESUMED | Attempt resumed | API response message. |
| ATTEMPT_STARTED | Attempt started | API response message. |
| ATTEMPT_SUBMITTED | Attempt submitted | API response message. |
| AT_LEAST_ONE_ANSWER_GRADE_IS_REQUIRED | At least one answer grade is required | Validation or authorization failure message. |
| CANNOT_VIEW_ANOTHER_STUDENTS_ATTEMPT_IN_STUDENT_MODE | Cannot view another student's attempt in student mode | API response message. |
| GRADING_IS_NOT_AVAILABLE_FOR_THIS_ATTEMPT_STATUS | Grading is not available for this attempt status. | API response message. |
| GRADING_RESULTS_ARE_AVAILABLE_ONLY_AFTER_SUBMISSION | Grading results are available only after submission | API response message. |
| INSUFFICIENT_PERMISSIONS_TO_MANAGE_ATTEMPTS | Insufficient permissions to manage attempts | Authorization / permission failure message. |
| INSUFFICIENT_PERMISSIONS_TO_VIEW_THIS_ATTEMPTS_GRADING_RESULT | Insufficient permissions to view this attempt's grading result | Authorization / permission failure message. |
| MANUAL_GRADING_IS_ONLY_AVAILABLE_WHILE_THE_ATTEMPT_IS_AWAITING_REVIEW | Manual grading is only available while the attempt is awaiting review | API response message. |
| NO_ANSWERS_ARE_PENDING_MANUAL_GRADING | No answers are pending manual grading | API response message. |
| ROW_ROW_NUMBER_DUPLICATE_CORRECT_ANSWER_LETTER_S_JOIN_DUPLICATES | Row {row_number}: duplicate correct answer letter(s): {join_duplicates} | API response message. |
| ROW_ROW_NUMBER_INVALID_CORRECT_ANSWER_LETTER_S_JOIN_SORTED_SET_INVALID | Row {row_number}: invalid correct answer letter(s): {join_sorted_set_invalid}. Use A-F only | Validation or authorization failure message. |
| SETTINGS_CONFIGANSWER_RULES_MUST_BE_AN_OBJECT | settings_config.answer_rules must be an object | Validation or authorization failure message. |
| SETTINGS_CONFIGATTEMPT_SETTINGSMAX_ATTEMPTS_MUST_BE_1 | settings_config.attempt_settings.max_attempts must be >= 1 | Validation or authorization failure message. |
| SETTINGS_CONFIGATTEMPT_SETTINGSMAX_ATTEMPTS_MUST_BE_AN_INTEGER | settings_config.attempt_settings.max_attempts must be an integer | Validation or authorization failure message. |
| SETTINGS_CONFIGATTEMPT_SETTINGS_MUST_BE_AN_OBJECT | settings_config.attempt_settings must be an object | Validation or authorization failure message. |
| THIS_ATTEMPT_IS_WAITING_FOR_MANUAL_GRADING | This attempt is waiting for manual grading. | API response message. |
| YOU_CAN_ONLY_ACCESS_YOUR_OWN_ATTEMPT | You can only access your own attempt | API response message. |
| YOU_CAN_ONLY_MODIFY_YOUR_OWN_ATTEMPT | You can only modify your own attempt | API response message. |
| YOU_CAN_ONLY_SUBMIT_YOUR_OWN_ATTEMPT | You can only submit your own attempt | API response message. |
| YOU_HAVE_REACHED_THE_MAXIMUM_ALLOWED_ATTEMPTS_MAX_ATTEMPTS | You have reached the maximum allowed attempts ({max_attempts}) | API response message. |

## Proctoring

| Constant | English Message | Description |
|----------|-----------------|-------------|
| EVIDENCE_PACKAGE_NOT_FOUND | Evidence package not found | Returned when the requested resource does not exist. |
| EVIDENCE_PACKAGE_NOT_GENERATED_FOR_LOW_SEVERITY | Evidence package not generated for LOW severity | API response message. |
| INSUFFICIENT_PERMISSIONS_FOR_PROCTORING_ACCESS | Insufficient permissions for proctoring access | Authorization / permission failure message. |
| INSUFFICIENT_PERMISSIONS_TO_VIEW_THIS_VIOLATION | Insufficient permissions to view this violation | Authorization / permission failure message. |
| SETTINGS_CONFIGPROCTORING_MUST_BE_AN_OBJECT | settings_config.proctoring must be an object | Validation or authorization failure message. |
| VIOLATION_NOT_FOUND | Violation not found | Returned when the requested resource does not exist. |
| VIOLATION_REVIEWED | Violation reviewed | API response message. |

## Reports

| Constant | English Message | Description |
|----------|-----------------|-------------|
| REPORT_CREATED_SUCCESSFULLY | Report created successfully | Returned after a successful operation. |
| REPORT_DOES_NOT_BELONG_TO_USER | Report does not belong to user | Authorization / permission failure message. |
| REPORT_NOT_FOUND | Report not found | Returned when the requested resource does not exist. |
| REPORT_STATUS_UPDATED_SUCCESSFULLY | Report status updated successfully | Returned after a successful operation. |

## Invitations

| Constant | English Message | Description |
|----------|-----------------|-------------|
| INSUFFICIENT_PERMISSIONS_TO_INVITE_THIS_ROLE | Insufficient permissions to invite this role | Authorization / permission failure message. |
| INVALID_ROLE_FOR_INVITATION | Invalid role for invitation | Validation or authorization failure message. |
| INVITATION_ACCEPTED | Invitation accepted | API response message. |
| INVITATION_HAS_ALREADY_BEEN_ACCEPTED | Invitation has already been accepted | API response message. |
| INVITATION_HAS_BEEN_REVOKED | Invitation has been revoked | API response message. |
| INVITATION_HAS_EXPIRED | Invitation has expired | API response message. |
| INVITATION_IS_NO_LONGER_VALID | Invitation is no longer valid | API response message. |
| INVITATION_NOT_FOUND | Invitation not found | Returned when the requested resource does not exist. |
| INVITATION_REJECTED | Invitation rejected | API response message. |
| INVITATION_WAS_REJECTED | Invitation was rejected | API response message. |
| PENDING_INVITATION_NOT_FOUND | Pending invitation not found | Returned when the requested resource does not exist. |
| STUDENTS_CANNOT_SEND_INVITATIONS | Students cannot send invitations | API response message. |

## Files

| Constant | English Message | Description |
|----------|-----------------|-------------|
| IMAGE_FILE_IS_REQUIRED | image file is required | Validation or authorization failure message. |
| IMAGE_IS_TOO_LARGE | Image is too large. Maximum allowed size is {max_mb:.0f}MB | API response message. |
| IMAGE_UPLOADED | Image uploaded | API response message. |
| INVALID_FILE_TYPE_ONLY_IMAGE_FILES_ARE_ALLOWED | Invalid file type. Only image files are allowed | Validation or authorization failure message. |
| INVALID_JSON_IN_MULTIPART_PAYLOAD | Invalid JSON in multipart payload | Validation or authorization failure message. |
| ROW_ROW_NUMBER_IMAGE_URL_MUST_BE_AT_MOST_512_CHARACTERS | Row {row_number}: image_url must be at most 512 characters | Validation or authorization failure message. |
| ROW_ROW_NUMBER_INVALID_IMAGE_URL_EMPTY_PATH_AFTER_UPLOADS | Row {row_number}: invalid image_url (empty path after /uploads/) | Validation or authorization failure message. |
| ROW_ROW_NUMBER_INVALID_IMAGE_URL_MALFORMED_URL | Row {row_number}: invalid image_url (malformed URL) | Validation or authorization failure message. |
| UNSUPPORTED_IMAGE_EXTENSION_ALLOWED_JPG_JPEG_PNG_WEBP | Unsupported image extension. Allowed: JPG, JPEG, PNG, WEBP | API response message. |
| UPLOADED_IMAGE_IS_EMPTY | Uploaded image is empty | API response message. |

## AI

| Constant | English Message | Description |
|----------|-----------------|-------------|
| AI_GENERATION_REQUEST_NOT_FOUND | AI generation request not found | Returned when the requested resource does not exist. |
| AI_RESPONSE_WAS_NOT_VALID_JSON | AI response was not valid JSON | API response message. |
| COULD_NOT_REACH_AI_API_EXCREASON | Could not reach AI API: {exc.reason} | API response message. |
| COULD_NOT_REACH_AI_API_REASON | Could not reach AI API: {reason} | API response message. |
| GEMINI_API_IS_TEMPORARILY_BUSY_503_UNAVAILABLE | Gemini API is temporarily busy (503 UNAVAILABLE). | API response message. |
| GEMINI_API_IS_TEMPORARILY_BUSY_PLEASE_RETRY_SHORTLY | Gemini API is temporarily busy. Please retry shortly. | API response message. |
| GEMINI_API_TEMPORARILY_BUSY_503 | Gemini API is temporarily busy (503 UNAVAILABLE). Please retry in a few seconds. | API response message. |
| ONLY_COMPLETED_GENERATION_REQUESTS_CAN_BE_IMPORTED | Only completed generation requests can be imported | Authorization / permission failure message. |
| OPENROUTER_ERROR_402_INSUFFICIENT_CREDITS_FOR_THIS_MODEL | OpenRouter error (402): insufficient credits for this model. | Authorization / permission failure message. |
| PROVIDER_LABEL_RETURNED_EMPTY_CONTENT | {provider_label} returned empty content | API response message. |
| UNEXPECTED_GEMINI_RESPONSE_FORMAT | Unexpected Gemini response format | API response message. |
| UNEXPECTED_PROVIDER_LABEL_RESPONSE_FORMAT | Unexpected {provider_label} response format | API response message. |
| UNSUPPORTED_AI_PROVIDER_KIND | Unsupported AI provider: {kind} | API response message. |
| YOU_CAN_ONLY_MANAGE_YOUR_OWN_AI_GENERATION_REQUESTS | You can only manage your own AI generation requests | API response message. |

## Student Groups

| Constant | English Message | Description |
|----------|-----------------|-------------|
| GROUP_CREATED_SUCCESSFULLY | Group created successfully | Returned after a successful operation. |
| GROUP_DELETED_SUCCESSFULLY | Group deleted successfully | Returned after a successful operation. |
| GROUP_NAME_IS_REQUIRED | Group name is required | Validation or authorization failure message. |
| GROUP_NOT_FOUND | Group not found | Returned when the requested resource does not exist. |
| GROUP_UPDATED_SUCCESSFULLY | Group updated successfully | Returned after a successful operation. |

## System

| Constant | English Message | Description |
|----------|-----------------|-------------|
| ADMIN_ACCESS_REQUIRED | Admin access required | Validation or authorization failure message. |
| ALL_LEN_FAILED_ROWS_ROW_S_FAILED_VALIDATION_FIRST_ERROR_ROW_FAILED | All {len_failed_rows} row(s) failed validation. First error (row {failed_rows_0_row}): {failed_rows_0_error} | API response message. |
| ENTRY_WINDOW_HAS_CLOSED | Entry window has closed. | API response message. |
| EVENT_RECORDED | Event recorded | API response message. |
| FIELD_NAME_MUST_BE_NON_NEGATIVE | {field_name} must be non-negative | Validation or authorization failure message. |
| FIELD_NAME_MUST_BE_NUMERIC | {field_name} must be numeric | Validation or authorization failure message. |
| FULL_NAME_CANNOT_BE_EMPTY | full_name cannot be empty | API response message. |
| GMAIL_SMTP_ERROR_EXC | Gmail SMTP error: {exc} | API response message. |
| INTERNAL_SERVER_ERROR | Internal server error | API response message. |
| INVALID_JSON_MESSAGE | Invalid JSON message | Validation or authorization failure message. |
| LABEL_ERROR_CODE_DETAIL | {label} error ({code}): {detail} | API response message. |
| PASSING_SCORE_CANNOT_BE_GREATER_THAN_TOTAL_SCORE | passing_score cannot be greater than total_score | API response message. |
| REJECTION_REASON_IS_REQUIRED | Rejection reason is required | Validation or authorization failure message. |
| ROW_ROW_NUMBER_TYPE_CODE_AND_BODY_ARE_REQUIRED | Row {row_number}: type_code and body are required | Validation or authorization failure message. |
| SEE_SERVER_LOGS_FOR_TRACEBACK | See server logs for traceback | API response message. |
| SETTINGS_CONFIGDISPLAY_SETTINGS_MUST_BE_AN_OBJECT | settings_config.display_settings must be an object | Validation or authorization failure message. |
| SETTINGS_CONFIGNAVIGATION_SETTINGS_MUST_BE_AN_OBJECT | settings_config.navigation_settings must be an object | Validation or authorization failure message. |
| SETTINGS_CONFIGREVIEW_SETTINGS_MUST_BE_AN_OBJECT | settings_config.review_settings must be an object | Validation or authorization failure message. |
| SETTINGS_CONFIG_MUST_BE_AN_OBJECT | settings_config must be an object | Validation or authorization failure message. |
| STATUS_MUST_BE_ONE_OF | status must be one of: {allowed} | Validation or authorization failure message. |
| STUDENTS_ASSIGNED_SUCCESSFULLY | Students assigned successfully | Returned after a successful operation. |
| STUDENT_ACCESS_REQUIRED | Student access required | Validation or authorization failure message. |
| STUDENT_ASSIGNMENT_NOT_FOUND | Student assignment not found | Returned when the requested resource does not exist. |
| STUDENT_REMOVED_FROM_ASSIGNED_LIST | Student removed from assigned list | API response message. |
| TOTAL_MUST_BE_NON_NEGATIVE | total must be non-negative | Validation or authorization failure message. |
| UNSUPPORTED_TYPE_CODE_ALLOWED_JOIN_SORTED_SUPPORTED_TYPE_CODES | Unsupported type_code. Allowed: {join_sorted_supported_type_codes} | API response message. |
| WEIGHTS_MUST_SUM_TO_100_GOT_WEIGHT_SUM | weights must sum to 100 (got {weight_sum}) | Validation or authorization failure message. |

