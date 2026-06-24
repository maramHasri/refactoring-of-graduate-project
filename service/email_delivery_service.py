"""
Send transactional emails via Gmail SMTP (Google App Password).
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

from utils.invite_links import invite_accept_url, invite_preview_url, invite_register_url

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when email could not be sent."""


class EmailDeliveryService:
    def send_otp_email(self, *, to_email: str, full_name: str, otp_code: str) -> None:
        expires = current_app.config.get("OTP_EXPIRES_MINUTES", 15)
        subject = "Your edu_forms verification code"
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto;">
          <h2 style="color: #1a365d;">Verify your email</h2>
          <p>Hello {full_name},</p>
          <p>Use the one-time code below to continue registration:</p>
          <p style="font-size: 28px; letter-spacing: 6px; font-weight: bold; color: #2b6cb0;
             background: #ebf8ff; padding: 16px; text-align: center; border-radius: 8px;">
            {otp_code}
          </p>
          <p>This code expires in <strong>{expires} minutes</strong> and can only be used once.</p>
          <p>If you did not request this, you can safely ignore this email.</p>
          <p style="color: #718096; font-size: 12px;">edu_forms — Exam &amp; Proctoring Platform</p>
        </div>
        """
        text = (
            f"Hello {full_name},\n\n"
            f"Your edu_forms verification code: {otp_code}\n\n"
            f"Expires in {expires} minutes. One-time use only.\n"
        )
        self._send(to_email=to_email, subject=subject, html_body=html, text_body=text)

    def send_institution_pending_review_email(
        self, *, to_email: str, full_name: str, institution_name: str
    ) -> None:
        subject = "Institution registration received — under review"
        html = f"""
        <p>Hello {full_name},</p>
        <p>Thank you for registering <strong>{institution_name}</strong> on edu_forms.</p>
        <p>The registration request has been received and is currently under review
        by the platform administration.</p>
        <p>You will receive an email once it has been approved. You cannot sign in until
        approval is complete.</p>
        """
        text = (
            f"Hello {full_name},\n\n"
            f"Registration for {institution_name} is under review.\n"
            f"You will be notified by email when approved.\n"
        )
        self._send(to_email=to_email, subject=subject, html_body=html, text_body=text)

    def send_institution_approved_email(
        self, *, to_email: str, full_name: str, institution_name: str
    ) -> None:
        subject = f"{institution_name} — registration approved"
        html = f"""
        <p>Hello {full_name},</p>
        <p>Your institution <strong>{institution_name}</strong> has been approved.</p>
        <p>You may now sign in and start using edu_forms.</p>
        """
        text = (
            f"Hello {full_name},\n\n"
            f"{institution_name} has been approved. You can sign in now.\n"
        )
        self._send(to_email=to_email, subject=subject, html_body=html, text_body=text)

    def send_institution_rejected_email(
        self, *, to_email: str, full_name: str, institution_name: str, reason: str
    ) -> None:
        subject = f"{institution_name} — registration not approved"
        html = f"""
        <p>Hello {full_name},</p>
        <p>Your institution registration for <strong>{institution_name}</strong>
        was not approved.</p>
        <p><strong>Reason:</strong> {reason}</p>
        <p>If you have questions, contact platform support.</p>
        """
        text = (
            f"Hello {full_name},\n\n"
            f"Registration for {institution_name} was rejected.\n"
            f"Reason: {reason}\n"
        )
        self._send(to_email=to_email, subject=subject, html_body=html, text_body=text)

    def send_workspace_invite_email(
        self,
        *,
        to_email: str,
        workspace_name: str,
        assigned_role: str,
        raw_token: str,
    ) -> None:
        preview_url = invite_preview_url(raw_token)
        register_url = invite_register_url(raw_token)
        accept_url = invite_accept_url(raw_token)
        subject = f"دعوة للانضمام إلى {workspace_name} | Invitation to {workspace_name}"
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto; color: #1a202c;">
          <h2 style="color: #1a365d; margin-bottom: 8px;">دعوة للانضمام إلى edu_forms</h2>
          <p style="margin-top: 0;">تمت دعوتك للانضمام إلى <strong>{workspace_name}</strong>
             بدور <strong>{assigned_role}</strong>.</p>
          <p style="color: #4a5568; font-size: 14px;">
            البريد المدعو: <strong>{to_email}</strong>
          </p>
          <p style="color: #4a5568; font-size: 14px; margin-bottom: 24px;">
            You have been invited to join <strong>{workspace_name}</strong>
            as <strong>{assigned_role}</strong> ({to_email}).
          </p>

          <p style="font-weight: bold; margin-bottom: 8px;">مستخدم جديد؟ / New here?</p>
          <p style="margin-top: 0; margin-bottom: 20px;">
            <a href="{register_url}"
               style="display: inline-block; background: #2b6cb0; color: #ffffff; text-decoration: none;
                      padding: 14px 28px; border-radius: 8px; font-weight: bold; font-size: 16px;">
              إنشاء حساب · Create account
            </a>
          </p>

          <p style="font-weight: bold; margin-bottom: 8px;">لديك حساب بالفعل؟ / Already have an account?</p>
          <p style="margin-top: 0; margin-bottom: 28px;">
            <a href="{accept_url}"
               style="display: inline-block; background: #276749; color: #ffffff; text-decoration: none;
                      padding: 14px 28px; border-radius: 8px; font-weight: bold; font-size: 16px;">
              قبول الدعوة · Accept invitation
            </a>
          </p>

          <p style="font-size: 14px; color: #4a5568; margin-bottom: 8px;">
            معاينة الدعوة / Preview invitation:
          </p>
          <p style="margin-top: 0;">
            <a href="{preview_url}" style="color: #2b6cb0;">{preview_url}</a>
          </p>

          <p style="color: #718096; font-size: 12px; margin-top: 32px; border-top: 1px solid #e2e8f0; padding-top: 16px;">
            افتح الروابط من المتصفح للوصول إلى موقع edu_forms. لا حاجة لأي إعدادات تقنية.
            <br>edu_forms — Exam &amp; Proctoring Platform
          </p>
        </div>
        """
        text = (
            f"دعوة للانضمام إلى {workspace_name} بدور {assigned_role}\n"
            f"Invitation to {workspace_name} as {assigned_role}\n"
            f"Email: {to_email}\n\n"
            f"مستخدم جديد / New account:\n{register_url}\n\n"
            f"مستخدم موجود / Existing account:\n{accept_url}\n\n"
            f"معاينة / Preview:\n{preview_url}\n"
        )
        self._send(to_email=to_email, subject=subject, html_body=html, text_body=text)

    def send_password_reset_otp_email(
        self, *, to_email: str, full_name: str, otp_code: str
    ) -> None:
        expires = current_app.config.get("OTP_EXPIRES_MINUTES", 15)
        subject = "Your edu_forms password reset code"
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto;">
          <h2 style="color: #1a365d;">Reset your password</h2>
          <p>Hello {full_name},</p>
          <p>Use the one-time code below to reset your password:</p>
          <p style="font-size: 28px; letter-spacing: 6px; font-weight: bold; color: #2b6cb0;
             background: #ebf8ff; padding: 16px; text-align: center; border-radius: 8px;">
            {otp_code}
          </p>
          <p>This code expires in <strong>{expires} minutes</strong> and can only be used once.</p>
          <p>If you did not request a password reset, you can safely ignore this email.</p>
          <p style="color: #718096; font-size: 12px;">edu_forms — Exam &amp; Proctoring Platform</p>
        </div>
        """
        text = (
            f"Hello {full_name},\n\n"
            f"Your edu_forms password reset code: {otp_code}\n\n"
            f"Expires in {expires} minutes. One-time use only.\n"
        )
        self._send(to_email=to_email, subject=subject, html_body=html, text_body=text)

    def _send(self, *, to_email: str, subject: str, html_body: str, text_body: str) -> None:
        gmail_user = current_app.config.get("GMAIL_USER")
        gmail_pass = (current_app.config.get("GMAIL_APP_PASSWORD") or "").replace(" ", "")

        if not gmail_user or not gmail_pass:
            logger.warning(
                "GMAIL_USER / GMAIL_APP_PASSWORD missing in .env — email not sent to %s",
                to_email,
            )
            print(f"\n[DEV EMAIL] To: {to_email}\nSubject: {subject}\n{text_body}\n")
            raise EmailDeliveryError(
                "Gmail is not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD in .env"
            )

        self._send_via_gmail(
            gmail_user=gmail_user,
            gmail_pass=gmail_pass,
            from_addr=gmail_user,
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    def _send_via_gmail(
        self,
        *,
        gmail_user: str,
        gmail_pass: str,
        from_addr: str,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_email
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
                server.login(gmail_user, gmail_pass)
                server.sendmail(from_addr, [to_email], msg.as_string())
        except smtplib.SMTPException as exc:
            raise EmailDeliveryError(f"Gmail SMTP error: {exc}") from exc

        logger.info("Email sent via Gmail to %s", to_email)
