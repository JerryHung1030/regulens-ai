from __future__ import annotations
from PySide6.QtCore import QObject, Signal
from .i18n import MESSAGES
from .settings import Settings

class Translator(QObject):
    language_changed = Signal()

    def __init__(self, settings: Settings, initial_language: str = "en"):
        super().__init__()  # Call QObject constructor
        self._messages = MESSAGES
        self._settings = settings
        
        # 從設定檔讀取語言設定，如果沒有則使用預設值
        saved_language = self._settings.get("language", initial_language)
        self._current_language = saved_language if saved_language in self._messages else "en"

    def set_language(self, lang_code: str) -> bool:
        """Sets the current language for translations.
        Returns True if language changed and is supported, False otherwise.
        """
        if lang_code in self._messages:
            changed = self._current_language != lang_code
            if changed:
                self._current_language = lang_code
                # 保存語言設定到設定檔
                self._settings.set("language", lang_code)
                self.language_changed.emit() # Emit signal
            return changed
        return False

    def get(self, key: str, default_override: str | None = None) -> str:
        """Gets the translated string for a given key.
        
        Args:
            key: The key for the string to translate.
            default_override: An optional value to return if the key is not found,
                              instead of the key itself.
                              
        Returns:
            The translated string, or the default_override if provided and key is missing,
            or the key itself if no translation and no default_override.
        """
        try:
            return self._messages[self._current_language][key]
        except KeyError:
            return default_override if default_override is not None else key

    def current_lang_code(self) -> str: # Helper method to get current language
        return self._current_language
