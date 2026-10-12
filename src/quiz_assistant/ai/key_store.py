from __future__ import annotations

import os

import keyring


class ApiKeyStore:
    SERVICE_NAME = "QuizAssistantPoC.OpenAI"
    USER_NAME = "default"

    def __init__(self, backend=None) -> None:
        if backend is None:
            # Never accept a third-party plaintext keyring fallback.
            from keyring.backends.Windows import WinVaultKeyring
            backend = WinVaultKeyring()
        self._backend = backend
        self._delete_error = getattr(backend, "errors", keyring.errors).PasswordDeleteError

    def get_key(self) -> str | None:
        environment_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if environment_key:
            return environment_key
        value = self._backend.get_password(self.SERVICE_NAME, self.USER_NAME)
        return value.strip() if value and value.strip() else None

    def save_key(self, api_key: str) -> None:
        cleaned = api_key.strip()
        if not cleaned:
            raise ValueError("Klucz API nie może być pusty.")
        self._backend.set_password(self.SERVICE_NAME, self.USER_NAME, cleaned)

    def delete_key(self) -> None:
        try:
            self._backend.delete_password(self.SERVICE_NAME, self.USER_NAME)
        except self._delete_error:
            return

    def source_label(self) -> str:
        if os.environ.get("OPENAI_API_KEY", "").strip():
            return "zmienna OPENAI_API_KEY"
        return "Windows Credential Manager"
