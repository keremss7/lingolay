"""Backwards-compatible re-export of the stabilizer API."""
from lingolay.text.cleaning import StabilizedText, TextStabilizer, seq_ratio

__all__ = ['TextStabilizer', 'StabilizedText', 'seq_ratio']
