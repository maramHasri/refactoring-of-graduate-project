"""
Email OTP issuance and verification with rate limits.
"""
from datetime import datetime, timedelta, timezone

from flask import current_app

from models import EmailOtp, User
from repositories.otp_repository import EmailOtpRepository
from service.exceptions import ValidationError
from utils.db import db
from utils.enums import EmailOtpPurpose
from utils.otp import generate_numeric_otp, hash_otp


class OtpService:
    def __init__(self):
        self.otps = EmailOtpRepository()

    def issue_otp(
        self,
        *,
        email: str,
        purpose: str,
        user_id: int | None = None,
    ) -> str:
        """
        Invalidate previous OTPs, create a new hashed OTP row, return plain OTP (for email only).
        """
        email = email.lower().strip()
        self._enforce_resend_limits(email)

        self.otps.invalidate_active_for_email(email)

        plain = generate_numeric_otp()
        expires_minutes = current_app.config.get("OTP_EXPIRES_MINUTES", 10)
        row = EmailOtp(
            email=email,
            user_id=user_id,
            otp_hash=hash_otp(plain),
            purpose=purpose,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
            verify_attempts=0,
        )
        self.otps.add(row)
        return plain

    def verify_otp(self, *, email: str, otp: str) -> EmailOtp:
        email = email.lower().strip()
        row = self.otps.find_active_for_email(email)
        if not row:
            raise ValidationError("Invalid or expired OTP")

        max_attempts = current_app.config.get("OTP_MAX_VERIFY_ATTEMPTS", 5)
        if row.verify_attempts >= max_attempts:
            row.is_used = True
            row.used_at = datetime.now(timezone.utc)
            db.session.flush()
            raise ValidationError("Maximum verification attempts exceeded. Request a new OTP.")

        if hash_otp(otp) != row.otp_hash:
            row.verify_attempts += 1
            db.session.flush()
            remaining = max_attempts - row.verify_attempts
            if remaining <= 0:
                row.is_used = True
                row.used_at = datetime.now(timezone.utc)
                raise ValidationError(
                    "Maximum verification attempts exceeded. Request a new OTP."
                )
            raise ValidationError(f"Invalid OTP. {remaining} attempt(s) remaining.")

        row.is_used = True
        row.used_at = datetime.now(timezone.utc)
        return row

    def _enforce_resend_limits(self, email: str) -> None:
        interval = current_app.config.get("OTP_RESEND_INTERVAL_SECONDS", 60)
        latest = self.otps.latest_created_at(email)
        if latest:
            elapsed = (datetime.now(timezone.utc) - latest).total_seconds()
            if elapsed < interval:
                wait = int(interval - elapsed)
                raise ValidationError(
                    f"Please wait {wait} second(s) before requesting another OTP"
                )

        max_per_hour = current_app.config.get("OTP_MAX_RESEND_PER_HOUR", 5)
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        if self.otps.count_sent_since(email, since) >= max_per_hour:
            raise ValidationError("OTP resend limit reached. Try again later.")
