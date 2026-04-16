from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.config.settings import settings

logger = logging.getLogger(__name__)


def _transformers_device_id() -> int:
    """0 = first CUDA device, -1 = CPU. Falls back to CPU if cuda is requested but unavailable."""
    if settings.model_detect_device != "cuda":
        return -1
    try:
        import torch

        if torch.cuda.is_available():
            return 0
    except Exception:
        pass
    logger.warning("model_detect_device=cuda but CUDA is unavailable; using CPU for transformers")
    return -1


class MultimodalDetectService:
    """MVP: OCR + ASR + 文本分类 + AI 语音二分类。"""

    def __init__(self) -> None:
        self._ocr = None
        self._ocr_backend = ""
        self._text_classifier = None
        self._audio_classifier = None
        self._asr_model = None

    @property
    def fraud_labels(self) -> list[str]:
        return [x.strip() for x in settings.model_detect_fraud_labels.split(",") if x.strip()]

    def _ensure_ocr(self):
        if self._ocr is not None:
            return self._ocr
        try:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore

            self._ocr = RapidOCR()
            self._ocr_backend = "rapidocr"
            return self._ocr
        except Exception as e:  # pragma: no cover - optional dependency
            logger.warning("RapidOCR init failed, fallback to PaddleOCR: %s", e)
        try:
            from paddleocr import PaddleOCR  # type: ignore

            self._ocr = PaddleOCR(use_angle_cls=True, lang=settings.model_detect_ocr_lang)
            self._ocr_backend = "paddleocr"
            return self._ocr
        except Exception as e:  # pragma: no cover - optional dependency
            logger.warning("OCR init failed: %s", e)
            return None

    def _ensure_asr(self):
        if self._asr_model is not None:
            return self._asr_model
        try:
            from faster_whisper import WhisperModel  # type: ignore

            self._asr_model = WhisperModel(
                settings.model_detect_asr_model,
                device=settings.model_detect_device,
                compute_type="float16" if settings.model_detect_device == "cuda" else "int8",
            )
            return self._asr_model
        except Exception as e:  # pragma: no cover - optional dependency
            logger.warning("ASR init failed: %s", e)
            return None

    def _ensure_text_classifier(self):
        if self._text_classifier is not None:
            return self._text_classifier
        try:
            from transformers import pipeline  # type: ignore

            self._text_classifier = pipeline(
                "zero-shot-classification",
                model=settings.model_detect_text_cls_model,
                device=_transformers_device_id(),
            )
            return self._text_classifier
        except Exception as e:  # pragma: no cover - optional dependency
            logger.warning("Text classifier init failed: %s", e)
            return None

    def _ensure_audio_classifier(self):
        if self._audio_classifier is not None:
            return self._audio_classifier
        if not settings.model_detect_ai_voice_model.strip():
            return None
        try:
            from transformers import pipeline  # type: ignore

            self._audio_classifier = pipeline(
                "audio-classification",
                model=settings.model_detect_ai_voice_model,
                device=_transformers_device_id(),
            )
            return self._audio_classifier
        except Exception as e:  # pragma: no cover - optional dependency
            logger.warning("AI voice classifier init failed: %s", e)
            return None

    def _run_ocr(self, image_path: Path) -> str:
        ocr = self._ensure_ocr()
        if ocr is None:
            return ""
        try:
            if self._ocr_backend == "rapidocr":
                # RapidOCR returns (result, elapsed) where result is list-like.
                res = ocr(str(image_path))  # type: ignore[misc]
                result_items = res[0] if isinstance(res, tuple) and len(res) > 0 else res
                chunks: list[str] = []
                for item in result_items or []:
                    if not item or len(item) < 2:
                        continue
                    txt = item[1]
                    if isinstance(txt, (list, tuple)):
                        txt = txt[0] if txt else ""
                    if txt:
                        chunks.append(str(txt))
                return "\n".join(chunks)

            try:
                # Prefer legacy signature; fallback for newer PaddleOCR APIs.
                res = ocr.ocr(str(image_path), cls=True)  # type: ignore[attr-defined]
            except TypeError:
                res = ocr.ocr(str(image_path))  # type: ignore[attr-defined]
            chunks: list[str] = []
            for block in res or []:
                for line in block or []:
                    txt = (line[1][0] if len(line) > 1 and line[1] else "") or ""
                    if txt:
                        chunks.append(str(txt))
            return "\n".join(chunks)
        except Exception as e:
            logger.warning("OCR run failed: %s", e)
            return ""

    def _run_asr(self, audio_path: Path) -> str:
        asr = self._ensure_asr()
        if asr is None:
            return ""
        try:
            segments, _ = asr.transcribe(str(audio_path), language="zh")
            return " ".join(seg.text.strip() for seg in segments if getattr(seg, "text", "").strip())
        except Exception as e:
            logger.warning("ASR run failed: %s", e)
            return ""

    def _run_text_classification(self, text: str) -> dict[str, Any]:
        clf = self._ensure_text_classifier()
        if clf is None or not text.strip() or not self.fraud_labels:
            return {"labels": {}, "top_label": "", "top_score": 0.0}
        try:
            out = clf(text, candidate_labels=self.fraud_labels, multi_label=True)
            labels: list[str] = out.get("labels", [])
            scores: list[float] = out.get("scores", [])
            pairs = {str(k): round(float(v), 4) for k, v in zip(labels, scores)}
            top_label = labels[0] if labels else ""
            top_score = float(scores[0]) if scores else 0.0
            return {"labels": pairs, "top_label": top_label, "top_score": round(top_score, 4)}
        except Exception as e:
            logger.warning("Text classification failed: %s", e)
            return {"labels": {}, "top_label": "", "top_score": 0.0}

    def _run_ai_voice_detect(self, audio_path: Path) -> dict[str, Any]:
        clf = self._ensure_audio_classifier()
        if clf is None:
            return {
                "probability": None,
                "judgment": "",
                "evidence": "AI voice model not configured",
            }
        try:
            out = clf(str(audio_path), top_k=5)
            if isinstance(out, dict):
                out = [out]
            max_prob = 0.0
            max_label = ""
            for item in out or []:
                label = str(item.get("label", ""))
                score = float(item.get("score", 0.0))
                l = label.lower()
                if any(k in l for k in ["spoof", "synthetic", "fake", "tts", "ai"]):
                    if score > max_prob:
                        max_prob = score
                        max_label = label
            if max_label:
                return {
                    "probability": round(max_prob, 4),
                    "judgment": "ai_synthetic_voice",
                    "evidence": f"model_label={max_label}",
                }
            return {
                "probability": 0.0,
                "judgment": "likely_human_voice",
                "evidence": "no spoof-like labels found",
            }
        except Exception as e:
            logger.warning("AI voice detect failed: %s", e)
            return {"probability": None, "judgment": "", "evidence": str(e)}

    def _extract_video_features(self, video_path: Path) -> tuple[str, str, Path | None]:
        with tempfile.TemporaryDirectory(prefix="md_video_") as td:
            tdir = Path(td)
            frames_pattern = tdir / "frame_%03d.jpg"
            audio_path = tdir / "audio.wav"
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(video_path),
                        "-vf",
                        "fps=1",
                        "-frames:v",
                        str(settings.model_detect_max_video_frames),
                        str(frames_pattern),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(video_path),
                        "-vn",
                        "-ac",
                        "1",
                        "-ar",
                        "16000",
                        str(audio_path),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except FileNotFoundError:
                logger.warning("ffmpeg not found, video extraction skipped")
                return "", "", None

            frame_texts: list[str] = []
            for fp in sorted(tdir.glob("frame_*.jpg"))[: settings.model_detect_max_video_frames]:
                t = self._run_ocr(fp)
                if t.strip():
                    frame_texts.append(t.strip())

            asr_text = self._run_asr(audio_path) if audio_path.exists() else ""

            # 复制一个临时音频供后续模型读取（退出上下文后原文件会删）
            keep_audio = None
            if audio_path.exists():
                keep_audio = Path(tempfile.mkstemp(prefix="md_audio_", suffix=".wav")[1])
                keep_audio.write_bytes(audio_path.read_bytes())
            return "\n".join(frame_texts), asr_text, keep_audio

    def detect(self, media_type: str, text: str | None = None, media_path: Path | None = None) -> dict[str, Any]:
        mt = media_type.strip().lower()
        notes: list[str] = []
        ocr_text = ""
        asr_text = ""
        extracted = (text or "").strip()
        ai_voice = {"probability": None, "judgment": "", "evidence": ""}
        temp_audio_for_detect: Path | None = None

        if mt == "text":
            pass
        elif mt == "image":
            if not media_path:
                raise ValueError("media_path is required for image")
            ocr_text = self._run_ocr(media_path)
            extracted = ocr_text or extracted
        elif mt == "audio":
            if not media_path:
                raise ValueError("media_path is required for audio")
            asr_text = self._run_asr(media_path)
            extracted = asr_text or extracted
            ai_voice = self._run_ai_voice_detect(media_path)
        elif mt == "video":
            if not media_path:
                raise ValueError("media_path is required for video")
            ocr_text, asr_text, temp_audio_for_detect = self._extract_video_features(media_path)
            extracted = "\n".join(x for x in [ocr_text, asr_text] if x.strip())
            if temp_audio_for_detect and temp_audio_for_detect.exists():
                ai_voice = self._run_ai_voice_detect(temp_audio_for_detect)
        else:
            raise ValueError("media_type must be text|image|audio|video")

        fraud = self._run_text_classification(extracted)
        if not extracted:
            notes.append("No text extracted for classification")
        if ai_voice.get("probability") is None and mt in {"audio", "video"}:
            notes.append("AI voice detection unavailable (configure model_detect_ai_voice_model)")

        if temp_audio_for_detect and temp_audio_for_detect.exists():
            try:
                temp_audio_for_detect.unlink()
            except OSError:
                pass

        return {
            "media_type": mt,
            "extracted_text": extracted,
            "fraud_classification": fraud,
            "ai_voice_detection": ai_voice,
            "ocr_text": ocr_text,
            "asr_text": asr_text,
            "notes": notes,
        }


service = MultimodalDetectService()
