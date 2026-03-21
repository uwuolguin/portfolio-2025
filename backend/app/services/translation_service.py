"""
Translation Service — LibreTranslate (self-hosted)

Self-hosted LibreTranslate instance running in the same Kubernetes cluster.
Exposes a documented REST API and runs fully offline after language models
are downloaded on first boot. Only en and es models are loaded
(LT_LOAD_ONLY=en,es in 16-libretranslate.yaml).

Translation quality is adequate for a demo. For production evaluate
DeepL or a managed service with SLA guarantees.
"""

import httpx
import structlog
from typing import Optional, Tuple

from app.config import settings

logger = structlog.get_logger(__name__)


class UniversalTranslator:

    # LibreTranslate endpoint — internal cluster DNS.
    # Configured via settings so it can be overridden in tests or
    # pointed at an external instance without code changes.
    TRANSLATE_URL = f"{settings.libretranslate_url}/translate"

    @staticmethod
    async def _translate_text(text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """
        Translate text using self-hosted LibreTranslate.
        Returns None if translation fails — callers fall back to duplication.
        """
        try:
            payload = {
                "q": text,
                "source": source_lang,
                "target": target_lang,
                "format": "text",
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    UniversalTranslator.TRANSLATE_URL,
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                translated = result.get("translatedText")

                if not translated:
                    logger.warning(
                        "libretranslate_empty_response",
                        source_lang=source_lang,
                        target_lang=target_lang,
                        text_preview=text[:50],
                    )
                    return None

                logger.info(
                    "translation_success",
                    source_lang=source_lang,
                    target_lang=target_lang,
                    original_length=len(text),
                    translated_length=len(translated),
                )

                return translated

        except httpx.TimeoutException:
            logger.warning(
                "translation_timeout",
                source_lang=source_lang,
                target_lang=target_lang,
                text_preview=text[:50],
            )
            return None

        except httpx.HTTPStatusError as e:
            logger.warning(
                "translation_http_error",
                status_code=e.response.status_code,
                source_lang=source_lang,
                target_lang=target_lang,
            )
            return None

        except Exception as e:
            logger.error(
                "translation_unexpected_error",
                error=str(e),
                error_type=type(e).__name__,
                source_lang=source_lang,
                target_lang=target_lang,
            )
            return None

    @staticmethod
    async def translate(
        text_es: Optional[str] = None,
        text_en: Optional[str] = None,
        field_name: str = "text",
    ) -> Tuple[str, str]:
        """
        Universal translation with fallback to duplication on failure.

        Fallback strategy:
        1. Both provided         → return as-is, no translation needed
        2. One provided, success → return (original, translated)
        3. One provided, failure → return (input, input) for both languages
        4. Neither provided      → raise ValueError
        """
        if text_es and text_en:
            logger.debug(
                f"both_{field_name}_provided",
                es_length=len(text_es),
                en_length=len(text_en),
            )
            return (text_es, text_en)

        if not text_es and not text_en:
            raise ValueError(
                f"At least one {field_name} (Spanish or English) must be provided"
            )

        # At this point exactly one is provided.
        if text_es:
            logger.debug(f"translating_{field_name}_es_to_en", text=text_es[:50])

            translated_en = await UniversalTranslator._translate_text(text_es, "es", "en")

            if translated_en is None:
                logger.warning(
                    "translation_failed_using_duplicate",
                    field_name=field_name,
                    original_lang="es",
                    original_text=text_es[:50],
                )
                return (text_es, text_es)

            if translated_en.lower().strip() == text_es.lower().strip():
                logger.info(
                    "translation_unchanged_using_original",
                    field_name=field_name,
                    text=text_es[:50],
                )
                return (text_es, text_es)

            return (text_es, translated_en)

        # text_en — guaranteed by the checks above
        logger.debug(f"translating_{field_name}_en_to_es", text=text_en[:50])

        translated_es = await UniversalTranslator._translate_text(text_en, "en", "es")

        if translated_es is None:
            logger.warning(
                "translation_failed_using_duplicate",
                field_name=field_name,
                original_lang="en",
                original_text=text_en[:50],
            )
            return (text_en, text_en)

        if translated_es.lower().strip() == text_en.lower().strip():
            logger.info(
                "translation_unchanged_using_original",
                field_name=field_name,
                text=text_en[:50],
            )
            return (text_en, text_en)

        return (translated_es, text_en)


async def translate_field(
    text_es: Optional[str] = None,
    text_en: Optional[str] = None,
    field_name: str = "text",
) -> Tuple[str, str]:
    """Generic translation helper for any bilingual field."""
    return await UniversalTranslator.translate(text_es, text_en, field_name=field_name)