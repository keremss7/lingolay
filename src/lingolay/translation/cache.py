from collections import OrderedDict


class TranslationCache:
    """Simple LRU translation cache."""

    def __init__(self, max_size=500):
        self._max_size = max_size
        self._cache = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, text):
        """Return the cached translation, or None if not found."""
        if text in self._cache:
            self._cache.move_to_end(text)
            self._hits += 1
            return self._cache[text]
        self._misses += 1
        return None

    def put(self, text, translation):
        """Store a translation in the cache."""
        if text in self._cache:
            self._cache.move_to_end(text)
        self._cache[text] = translation
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def clear(self):
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def hit_rate(self):
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self):
        return len(self._cache)
