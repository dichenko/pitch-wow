import asyncio

import structlog

logger = structlog.get_logger()


async def get_audio_duration(file_path: str) -> float:
    """Return audio duration in seconds using ffprobe. Returns 0.0 on failure."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return float(stdout.decode().strip())
    except Exception as e:
        logger.warning("ffprobe_duration_failed", error=str(e))
        return 0.0


async def convert_to_wav(input_path: str) -> str:
    """
    Convert any audio format to 16 kHz mono WAV using ffmpeg.
    Returns the path to the resulting .wav file (caller must clean up).
    Raises RuntimeError if ffmpeg fails.
    """
    output_path = input_path + ".wav"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        "-f", "wav",
        output_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {proc.returncode}): {stderr.decode()[:300]}"
        )
    logger.info("audio_converted_to_wav", input=input_path, output=output_path)
    return output_path


async def prepare_audio(file_path: str) -> str:
    """
    Ensure the file is 16 kHz mono WAV suitable for STT APIs.
    - If the file is already .wav, still re-encode to 16 kHz mono to be safe.
    - Otherwise convert via ffmpeg.
    Returns the path to the WAV file. The caller must clean up temp files.
    """
    return await convert_to_wav(file_path)
