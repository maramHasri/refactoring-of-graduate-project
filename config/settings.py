import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/edu_forms",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    HF_TOKEN = os.getenv("HF_TOKEN")
    GMAIL_USER = os.getenv("GMAIL_USER")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
    SHAM_CASH_API_KEY = os.getenv("SHAM_CASH_API_KEY")

    # Email (Gmail App Password only) + frontend/API links
    APP_URL = os.getenv("APP_URL", "http://localhost:3000")
    API_URL = os.getenv("API_URL", "http://127.0.0.1:5000")
    PASSWORD_RESET_PATH = os.getenv("PASSWORD_RESET_PATH", "/reset-password")

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    INVITE_TOKEN_EXPIRES_DAYS = 7
    PASSWORD_RESET_EXPIRES_HOURS = 24
    REGISTRATION_INTENT_EXPIRES_HOURS = int(
        os.getenv("REGISTRATION_INTENT_EXPIRES_HOURS", "48")
    )

    OTP_EXPIRES_MINUTES = int(os.getenv("OTP_EXPIRES_MINUTES", "10"))
    OTP_RESEND_INTERVAL_SECONDS = int(os.getenv("OTP_RESEND_INTERVAL_SECONDS", "60"))
    OTP_MAX_VERIFY_ATTEMPTS = int(os.getenv("OTP_MAX_VERIFY_ATTEMPTS", "5"))
    OTP_MAX_RESEND_PER_HOUR = int(os.getenv("OTP_MAX_RESEND_PER_HOUR", "5"))

    # Development only: include plain OTP in API JSON + server console (never True in production)
    EXPOSE_OTP_IN_DEV_RESPONSE = os.getenv(
        "EXPOSE_OTP_IN_DEV_RESPONSE", "false"
    ).lower() in ("1", "true", "yes")

    SUPER_ADMIN_EMAIL = os.getenv("SUPER_ADMIN_EMAIL", "superadmin@eduforms.local")
    SUPER_ADMIN_PASSWORD = os.getenv("SUPER_ADMIN_PASSWORD", "SuperAdmin@123")
    SUPER_ADMIN_FULL_NAME = os.getenv("SUPER_ADMIN_FULL_NAME", "Platform Super Admin")


class DevelopmentConfig(Config):
    DEBUG = True
    EXPOSE_OTP_IN_DEV_RESPONSE = os.getenv(
        "EXPOSE_OTP_IN_DEV_RESPONSE", "true"
    ).lower() in ("1", "true", "yes")


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/edu_forms_test",
    )


def get_config():
    env = os.getenv("FLASK_ENV", "development")
    if env == "production":
        return ProductionConfig
    if env == "testing":
        return TestingConfig
    return DevelopmentConfig
