from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

app = FastAPI(title="Local ASR Microservice", version="1.0.0")

_MODEL = None
_MODEL_META: dict[str, str] = {}


def _load_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception as err:  # pragma: no cover
        raise RuntimeError(f"faster-whisper not available: {err}") from err
    # 固定 CPU，避免 Windows 环境缺少 cublas64_12.dll 导致推理阶段报错。
    _MODEL = WhisperModel("large-v3", device="cpu", compute_type="int8")
    _MODEL_META["runtime"] = "cpu/int8"
    return _MODEL


def _reload_cpu_model():
    global _MODEL
    from faster_whisper import WhisperModel  # type: ignore

    _MODEL = WhisperModel("large-v3", device="cpu", compute_type="int8")
    _MODEL_META["runtime"] = "cpu/int8"
    return _MODEL


def _transcribe_local_file(path: Path) -> str:
    model = _load_model()
    segments, _info = model.transcribe(str(path), language="zh")
    text = " ".join(seg.text.strip() for seg in segments if getattr(seg, "text", "").strip()).strip()
    return text


class UrlTranscribeIn(BaseModel):
    audio_url: str = Field(min_length=1, max_length=4096)
    file_name: str = Field(default="audio.wav", max_length=255)


class TranscribeOut(BaseModel):
    text: str
    model: str
    source: str
    runtime: str = ""


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True}


@app.post("/transcribe_by_url", response_model=TranscribeOut)
def transcribe_by_url(payload: UrlTranscribeIn):
    try:
        with tempfile.NamedTemporaryFile(suffix=Path(payload.file_name).suffix or ".wav", delete=False) as tf:
            tmp_path = Path(tf.name)
        try:
            with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                resp = client.get(payload.audio_url)
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"拉取音频失败：{resp.status_code}")
            tmp_path.write_bytes(resp.content)
            text = _transcribe_local_file(tmp_path)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"ASR 转写失败：{err}") from err

    if not text:
        raise HTTPException(status_code=422, detail="转写结果为空")
    return TranscribeOut(
        text=text,
        model="faster-whisper-large-v3",
        source="local_asr_microservice",
        runtime=_MODEL_META.get("runtime", ""),
    )


@app.post("/transcribe_file", response_model=TranscribeOut)
async def transcribe_file(file: UploadFile = File(...)):
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
        tmp_path = Path(tf.name)
    try:
        raw = await file.read()
        tmp_path.write_bytes(raw)
        text = _transcribe_local_file(tmp_path)
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"ASR 转写失败：{err}") from err
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        await file.close()

    if not text:
        raise HTTPException(status_code=422, detail="转写结果为空")
    return TranscribeOut(
        text=text,
        model="faster-whisper-large-v3",
        source="local_asr_microservice",
        runtime=_MODEL_META.get("runtime", ""),
    )

