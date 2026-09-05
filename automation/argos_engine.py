"""Fail-closed optional Argos provider; no model download occurs here."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .errors import TranslationProviderUnavailable, VerificationError

def verify_model_lock(model_path: Path, lock_path: Path) -> dict:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("package_name") != "translate-en_tr" or lock.get("from_language") != "en" or lock.get("to_language") != "tr" or lock.get("version") != "1.5":
        raise VerificationError("Argos model-lock package, version or language pair is invalid")
    expected = lock.get("sha256")
    if not isinstance(expected, str) or expected == "PENDING_FIRST_VERIFICATION":
        raise VerificationError("Argos model is not hash-locked; translation and state writes are forbidden")
    expected_size = lock.get("size_bytes")
    if not isinstance(expected_size, int) or expected_size <= 0:
        raise VerificationError("Argos model-lock size is invalid")
    if not model_path.is_file() or model_path.stat().st_size != expected_size:
        raise VerificationError("Argos model size does not match model-lock.json")
    actual = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if actual.lower() != expected.lower():
        raise VerificationError("Argos model SHA-256 does not match model-lock.json")
    return lock

def locked_argos(model_path: Path, lock_path: Path):
    verify_model_lock(model_path, lock_path)
    try:
        import argostranslate.translate  # type: ignore
    except ImportError as exc:
        raise TranslationProviderUnavailable("TRANSLATION_PROVIDER_UNAVAILABLE: hash-locked Argos runtime is unavailable") from exc
    languages = argostranslate.translate.get_installed_languages()
    source = next((x for x in languages if x.code == "en"), None)
    target = next((x for x in languages if x.code == "tr"), None)
    if source is None or target is None:
        raise TranslationProviderUnavailable("TRANSLATION_PROVIDER_UNAVAILABLE: installed Argos EN/TR language pair is unavailable")
    translation = source.get_translation(target)
    if translation is None: raise TranslationProviderUnavailable("TRANSLATION_PROVIDER_UNAVAILABLE: installed Argos EN/TR translator is unavailable")
    return translation.translate


def install_locked_model(model_path: Path, lock_path: Path):
    """Verify, install and load the model without downloading anything implicitly."""
    verify_model_lock(model_path, lock_path)
    try:
        from argostranslate import package  # type: ignore
        package.install_from_path(model_path)
    except ImportError as exc:
        raise TranslationProviderUnavailable("TRANSLATION_PROVIDER_UNAVAILABLE: Argos package runtime is unavailable") from exc
    except Exception as exc:
        raise VerificationError("Argos model installation failed") from exc
    return locked_argos(model_path, lock_path)
