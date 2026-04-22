from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptWord(BaseModel):
    word: str = Field(..., description="Recognized token.")
    start: float | None = Field(default=None, description="Word start time in seconds.")
    end: float | None = Field(default=None, description="Word end time in seconds.")
    confidence: float | None = Field(default=None, description="Word confidence score.")
    speaker: str | None = Field(default=None, description="Speaker label for this word.")


class TranscriptSegment(BaseModel):
    start: float = Field(..., description="Segment start time in seconds.")
    end: float = Field(..., description="Segment end time in seconds.")
    text: str = Field(..., description="Recognized text for the segment.")
    speaker: str | None = Field(default=None, description="Speaker label for segment.")
    words: list[TranscriptWord] = Field(default_factory=list, description="Word-level details.")


class TranscribeResult(BaseModel):
    language: str = Field(..., description="Detected or provided language code.")
    asr_model: str = Field(..., description="ASR model used for transcription.")
    diarization_model: str = Field(..., description="Speaker diarization model id.")
    speakers: list[str] = Field(default_factory=list, description="Speaker labels in output.")
    segments: list[TranscriptSegment] = Field(default_factory=list, description="Diarized segments.")

