import subprocess
from pathlib import Path


def download_audio(source: str, output_dir: str, on_progress=None) -> dict:
    """
    Prepare audio from a YouTube URL or a local video/audio file for transcription.

    For URLs, yt-dlp downloads the best available audio stream.
    For local files, the file is used directly without copying.
    In both cases the audio is checked against the 1.5-hour limit, then
    normalized with ffmpeg's loudnorm filter and converted to 16 kHz mono mp3
    (the optimal format for speech-to-text APIs).

    Args:
        source:      YouTube URL or local file path (mp4, mp3, wav, m4a, webm, …).
        output_dir:  Directory where the processed mp3 will be saved.
        on_progress: Optional callback(fraction: float) called with 0.0–1.0 during
                     the yt-dlp download phase. Not called for local file sources.

    Returns:
        dict with keys:
            path             (str)   – absolute path to the processed mp3
            duration_seconds (float) – audio duration in seconds
            title            (str)   – video title (from metadata) or filename stem

    Raises:
        ValueError:   source video exceeds 1.5 hours; URL is private / geo-blocked /
                      unavailable; local file does not exist.
        RuntimeError: ffprobe or ffmpeg exited with an error.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    is_url = source.startswith("http://") or source.startswith("https://")

    if is_url:
        raw_path, title = _download_from_url(source, output_dir, on_progress)
    else:
        raw_path = Path(source)
        if not raw_path.exists():
            raise ValueError(f"File not found: {source}")
        title = raw_path.stem

    duration = _get_duration(raw_path)

    if duration > 5400:
        if is_url:
            raw_path.unlink(missing_ok=True)
        raise ValueError(
            f"This video is {duration / 3600:.1f} hours long. "
            "The maximum allowed length is 1.5 hours (5400 seconds). "
            "Please trim the video or use a shorter clip."
        )

    safe_title = _safe_stem(title)
    output_path = output_dir / f"{safe_title}_processed.mp3"
    _normalize_audio(raw_path, output_path)

    if is_url and raw_path.resolve() != output_path.resolve():
        raw_path.unlink(missing_ok=True)

    return {
        "path": str(output_path.resolve()),
        "duration_seconds": duration,
        "title": title,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _download_from_url(url: str, output_dir: Path, on_progress=None) -> tuple[Path, str]:
    """Download best audio from a URL via yt-dlp. Returns (raw_mp3_path, title)."""
    try:
        import yt_dlp
    except ImportError:
        raise RuntimeError("yt-dlp is not installed. Run: pip install yt-dlp")

    def _ydl_hook(d: dict) -> None:
        if on_progress is None or d.get("status") != "downloading":
            return
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        if total and total > 0:
            on_progress(min(d.get("downloaded_bytes", 0) / total, 1.0))

    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        # Use the video ID so the filename is always predictable after postprocessing.
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_ydl_hook],
        # Android client is less aggressively blocked by YouTube on cloud IPs.
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info["id"]
            title = info.get("title", video_id)
            # After FFmpegExtractAudio the file is renamed to <id>.mp3
            raw_path = output_dir / f"{video_id}.mp3"
            return raw_path, title
    except Exception as e:
        msg = str(e).lower()
        if "private" in msg:
            raise ValueError("This video is private and cannot be downloaded.")
        if "not available" in msg or "geo" in msg:
            raise ValueError(
                "This video is not available. It may be geo-blocked, age-restricted, or removed."
            )
        raise ValueError(
            f"Could not download the video. Please check the URL and try again. "
            f"(Error: {type(e).__name__}: {str(e)[:300]})"
        )


def _get_duration(path: Path) -> float:
    """Return audio/video duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffprobe could not read the file.\n"
            f"Is ffmpeg installed and on your PATH?\n"
            f"Details: {result.stderr.strip()}"
        )
    try:
        return float(result.stdout.strip())
    except ValueError:
        raise RuntimeError(f"ffprobe returned an unexpected duration value for: {path}")


def _normalize_audio(input_path: Path, output_path: Path) -> None:
    """
    Convert audio to 16 kHz mono mp3 with loudnorm volume normalization.
    Overwrites output_path if it already exists.
    """
    result = subprocess.run(
        [
            "ffmpeg", "-i", str(input_path),
            "-af", "loudnorm=I=-16:LRA=11:TP=-1.5",
            "-ar", "16000",   # 16 kHz — optimal for speech-to-text
            "-ac", "1",       # mono
            "-y",             # overwrite without asking
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg audio normalization failed.\n"
            f"Details: {result.stderr.strip()}"
        )


def _safe_stem(title: str) -> str:
    """Convert a title string into a filesystem-safe filename stem (max 80 chars)."""
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    return safe.strip()[:80] or "audio"
