"""
Send transactional emails via Gmail SMTP (Google App Password).
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when email could not be sent."""


class EmailDeliveryService:
    def send_otp_email(self, *, to_email: str, full_name: str, otp_code: str) -> None:
        expires = current_app.config.get("OTP_EXPIRES_MINUTES", 10)
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
        preview_url = self._invite_preview_link(raw_token)
        register_hint = self._invite_register_link(raw_token)
        accept_hint = self._invite_accept_link(raw_token)
        api_base = current_app.config.get("API_URL", "http://127.0.0.1:5000").rstrip("/")
        subject = f"Invitation to join {workspace_name} on edu_forms"
        html = f"""
        <p>You have been invited to join <strong>{workspace_name}</strong> as <strong>{assigned_role}</strong>.</p>
        <p>Preview: <a href="{preview_url}">{preview_url}</a></p>
        <p><strong>New account?</strong> Register with POST <code>{register_hint}</code><br>
        Body: <code>{{"full_name": "...", "password": "..."}}</code><br>
        (email is fixed to <strong>{to_email}</strong> from this invitation)</p>
        <p><strong>Already have an account?</strong> Log in as {to_email}, then POST <code>{accept_hint}</code>
        with Bearer access_token.</p>
        <p>Swagger: <a href="{api_base}/apidocs/">{api_base}/apidocs/</a></p>
        """
        text = (
            f"Invitation to {workspace_name} as {assigned_role}.\n\n"
            f"Preview: {preview_url}\n"
            f"New user: POST {register_hint} with full_name and password only.\n"
            f"Existing user: log in as {to_email}, then POST {accept_hint}\n"
        )
        self._send(to_email=to_email, subject=subject, html_body=html, text_body=text)

    def send_password_reset_email(self, *, to_email: str, full_name: str, raw_token: str) -> None:
        reset_url = self._password_reset_link(raw_token)
        subject = "Reset your edu_forms password"
        html = f"""
        <p>Hello {full_name},</p>
        <p>Reset your password using this link:</p>
        <p><a href="{reset_url}">{reset_url}</a></p>
        <p>If you did not request a reset, ignore this email.</p>
        """
        text = f"Hello {full_name},\n\nReset your password: {reset_url}"
        self._send(to_email=to_email, subject=subject, html_body=html, text_body=text)

    def _password_reset_link(self, raw_token: str) -> str:
        base = current_app.config.get("APP_URL", "http://localhost:3000").rstrip("/")
        path = current_app.config.get("PASSWORD_RESET_PATH", "/reset-password")
        return f"{base}{path}?token={raw_token}"

    def _invite_preview_link(self, raw_token: str) -> str:
        base = current_app.config.get("API_URL", "http://127.0.0.1:5000").rstrip("/")
        return f"{base}/invites/{raw_token}"

    def _invite_register_link(self, raw_token: str) -> str:
        base = current_app.config.get("API_URL", "http://127.0.0.1:5000").rstrip("/")
        return f"{base}/invites/{raw_token}/register"

    def _invite_accept_link(self, raw_token: str) -> str:
        base = current_app.config.get("API_URL", "http://127.0.0.1:5000").rstrip("/")
        return f"{base}/invites/{raw_token}/accept"

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
