from backend.app.config import Settings


def test_database_credentials_are_excluded_from_settings_representation():
    settings = Settings(
        database_url="postgresql://user:private-password@localhost/codemafia"
    )
    assert "private-password" not in repr(settings)
