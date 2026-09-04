"""Build searchable dialogue segments from a timed word transcript."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Sequence

from vidxp.capabilities.speech.transcript import TimedWord

SegmentationMode = Literal[
    "fixed_words",
    "overlapping_windows",
    "sentence",
]

SENTENCE_END = re.compile(r"[.!?…][\"')\]]*$")


@dataclass(frozen=True)
class DialoguePhrase:
    phrase_id: int
    text: str
    start: float
    end: float
    word_start: int
    word_end: int
    segmentation_mode: SegmentationMode

    @property
    def local_id(self) -> str:
        """Stable ID for the same transcript span and segmentation mode."""

        return (
            f"{self.segmentation_mode}:"
            f"w{self.word_start:08d}-{self.word_end:08d}"
        )


def _phrase_from_words(
    words: Sequence[TimedWord],
    *,
    mode: SegmentationMode,
    phrase_id: int,
) -> DialoguePhrase:
    if not words:
        raise ValueError("A dialogue phrase requires at least one word.")
    text = " ".join(word.text for word in words)
    return DialoguePhrase(
        phrase_id=phrase_id,
        text=text,
        start=words[0].start,
        end=words[-1].end,
        word_start=words[0].index,
        word_end=words[-1].index,
        segmentation_mode=mode,
    )


def _non_overlapping_phrases(
    words: Sequence[TimedWord],
    *,
    words_per_phrase: int,
) -> list[DialoguePhrase]:
    if words_per_phrase <= 0:
        raise ValueError("words_per_phrase must be greater than zero.")
    phrases: list[DialoguePhrase] = []
    for offset in range(0, len(words), words_per_phrase):
        group = words[offset:offset + words_per_phrase]
        phrases.append(
            _phrase_from_words(
                group,
                mode="fixed_words",
                phrase_id=len(phrases),
            )
        )
    return phrases


def _overlapping_phrases(
    words: Sequence[TimedWord],
    *,
    words_per_phrase: int,
    window_stride_words: int,
) -> list[DialoguePhrase]:
    if words_per_phrase <= 0:
        raise ValueError("words_per_phrase must be greater than zero.")
    if window_stride_words <= 0:
        raise ValueError("window_stride_words must be greater than zero.")
    phrases: list[DialoguePhrase] = []
    if not words:
        return phrases
    offset = 0
    while True:
        group = words[offset:offset + words_per_phrase]
        phrases.append(
            _phrase_from_words(
                group,
                mode="overlapping_windows",
                phrase_id=len(phrases),
            )
        )
        if offset + words_per_phrase >= len(words):
            break
        offset += window_stride_words
        if offset >= len(words):
            break
    return phrases


def _ends_sentence(word: TimedWord) -> bool:
    return bool(SENTENCE_END.search(word.text))


def _sentence_phrases(
    words: Sequence[TimedWord],
    *,
    max_words: int,
) -> list[DialoguePhrase]:
    if max_words <= 0:
        raise ValueError("words_per_phrase must be greater than zero.")
    phrases: list[DialoguePhrase] = []
    current: list[TimedWord] = []
    for word in words:
        current.append(word)
        boundary = _ends_sentence(word) or len(current) >= max_words
        if not boundary:
            continue
        phrases.append(
            _phrase_from_words(
                current,
                mode="sentence",
                phrase_id=len(phrases),
            )
        )
        current = []
    if current:
        phrases.append(
            _phrase_from_words(
                current,
                mode="sentence",
                phrase_id=len(phrases),
            )
        )
    return phrases


def build_dialogue_phrases_from_words(
    words: Sequence[TimedWord],
    *,
    segmentation_mode: SegmentationMode = "fixed_words",
    words_per_phrase: int = 5,
    window_stride_words: int = 2,
) -> list[DialoguePhrase]:
    """Segment timed words into searchable phrases.

    ``fixed_words`` retains the historical five-word baseline. Other modes
    exist so retrieval quality can be compared (see issue #76 / #89).
    """

    if segmentation_mode == "fixed_words":
        return _non_overlapping_phrases(
            words,
            words_per_phrase=words_per_phrase,
        )
    if segmentation_mode == "overlapping_windows":
        return _overlapping_phrases(
            words,
            words_per_phrase=words_per_phrase,
            window_stride_words=window_stride_words,
        )
    if segmentation_mode == "sentence":
        return _sentence_phrases(words, max_words=words_per_phrase)
    raise ValueError(
        "segmentation_mode must be one of: fixed_words, "
        "overlapping_windows, sentence."
    )
