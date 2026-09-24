from lingolay.translation.base import TranslationResult

__all__ = ['TranslationResult', 'create_translator']


def create_translator(settings):
    """
    Create and return the configured translation engine.
    Both engines implement the same interface:
      translate(text) → TranslationResult
      is_ready, init_error, device_name, last_latency_ms, cache_hit_rate
      warm_up(), clear_cache(), get_stats()
    """
    if settings.translation_engine == 'deepl':
        from lingolay.translation.deepl import DeepLTranslator
        return DeepLTranslator(
            from_lang=settings.source_lang,
            to_lang=settings.target_lang,
            api_key=settings.deepl_api_key,
            plan=settings.deepl_plan,
            cache_size=settings.cache_size,
        )
    from lingolay.translation.nllb import NLLBTranslator
    return NLLBTranslator(
        from_lang=settings.source_lang,
        to_lang=settings.target_lang,
        use_gpu=settings.use_gpu,
        cache_size=settings.cache_size,
    )
