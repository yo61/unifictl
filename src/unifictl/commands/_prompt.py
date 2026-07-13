"""Shared interactive prompts for command modules."""

from __future__ import annotations

import questionary


def prompt_api_key() -> str:
    """Prompt for an API key with hidden input; returns '' if cancelled."""
    return str(questionary.password("API key:").ask() or "")
