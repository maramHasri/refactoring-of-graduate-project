"""
Send transactional emails via Gmail SMTP (Google App Password).

Requires in .env:
  GMAIL_USER=your@gmail.com
  GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   (spaces are stripped automatically)
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
    def send_verification_email(self, *, to_email: str, full_name: str, raw_token: str) -> None:
        verify_url = self._verification_link(raw_token)
        subject = "Verify your edu_forms account"
        html = f"""
        <p>Hello {full_name},</p>
        <p>Please verify your email address by clicking the link below:</p>
        <p><a href="{verify_url}">{verify_url}</a></p>
        <p>This link expires in {current_app.config.get('EMAIL_VERIFICATION_EXPIRES_HOURS', 48)} hours.</p>
        <p>If you did not create an account, ignore this email.</p>
        """
        text = (
            f"Hello {full_name},\n\n"
            f"Verify your email: {verify_url}\n\n"
            f"This link expires in {current_app.config.get('EMAIL_VERIFICATION_EXPIRES_HOURS', 48)} hours."
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

    def _verification_link(self, raw_token: str) -> str:
        base = current_app.config.get("APP_URL", "http://localhost:3000").rstrip("/")
        path = current_app.config.get("EMAIL_VERIFICATION_PATH", "/verify-email")
        return f"{base}{path}?token={raw_token}"

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
