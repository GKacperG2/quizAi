from quiz_assistant.ai.key_store import ApiKeyStore


class FakeErrors:
    class PasswordDeleteError(Exception):
        pass


class FakeBackend:
    errors = FakeErrors

    def __init__(self) -> None:
        self.value = None

    def get_password(self, _service, _user):
        return self.value

    def set_password(self, _service, _user, value):
        self.value = value

    def delete_password(self, _service, _user):
        if self.value is None:
            raise self.errors.PasswordDeleteError()
        self.value = None


def test_key_is_saved_and_loaded_without_exposing_it(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend = FakeBackend()
    store = ApiKeyStore(backend)
    store.save_key("  sk-test-secret  ")
    assert store.get_key() == "sk-test-secret"
    store.delete_key()
    assert store.get_key() is None


def test_environment_key_has_priority(monkeypatch) -> None:
    backend = FakeBackend()
    backend.value = "sk-credential"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-environment")
    assert ApiKeyStore(backend).get_key() == "sk-environment"
