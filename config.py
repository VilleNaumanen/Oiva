import os

WORKSPACE = r"C:\Users\VilleNaumanen\OneDrive - Kempower\Desktop\Ville Work"
_DB_DEFAULT = os.path.join(WORKSPACE, "database", "ville_work.db")
_INBOX_DEFAULT = os.path.join(WORKSPACE, "Team inbox")
_SIIRI_PREFS_DEFAULT = os.path.join(WORKSPACE, "Oiva team", "siiri-preferences.md")
_UPLOADS_DEFAULT = os.path.join(os.path.dirname(__file__), "uploads")


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(24))
    DB_PATH = os.environ.get("DB_PATH", _DB_DEFAULT)
    INBOX = os.environ.get("OIVA_INBOX", _INBOX_DEFAULT)
    SIIRI_PREFS = os.environ.get("SIIRI_PREFS", _SIIRI_PREFS_DEFAULT)
    UPLOADS = os.environ.get("OIVA_UPLOADS", _UPLOADS_DEFAULT)
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    SIIRI_DAILY_HOUR = int(os.environ.get("SIIRI_DAILY_HOUR", "7"))


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = False
    # DB_PATH and INBOX are overridden per-test via fixtures


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
