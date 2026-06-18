"""Descarga la transcripción de un vídeo de YouTube y la guarda como .md.

No usa ningún LLM: lee los subtítulos que YouTube ya genera (manuales o
automáticos). Si no hay subtítulos disponibles vía youtube-transcript-api,
cae en yt-dlp como respaldo.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

DEFAULT_LANGS = ["es", "en"]
OUTPUT_DIR = Path("output")


def extract_video_id(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/")
    if parsed.hostname and "youtube.com" in parsed.hostname:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
            if video_id:
                return video_id
        for prefix in ("/shorts/", "/embed/", "/live/"):
            if parsed.path.startswith(prefix):
                return parsed.path[len(prefix):].split("/")[0]
    raise ValueError(f"No se pudo extraer el video_id de la URL: {url}")


def fetch_via_transcript_api(video_id: str, langs: list[str]):
    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)
    try:
        transcript = transcript_list.find_transcript(langs)
    except NoTranscriptFound:
        transcript = transcript_list.find_generated_transcript(langs)
    fetched = transcript.fetch()
    text = "\n".join(snippet.text.strip() for snippet in fetched if snippet.text.strip())
    return text, transcript.language_code


def fetch_via_yt_dlp(url: str, langs: list[str]):
    with tempfile.TemporaryDirectory() as tmpdir:
        out_template = str(Path(tmpdir) / "%(id)s")
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-subs",
            "--write-subs",
            "--sub-langs",
            ",".join(langs),
            "--sub-format",
            "vtt",
            "--output",
            out_template,
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp falló: {result.stderr.strip()}")

        vtt_files = sorted(Path(tmpdir).glob("*.vtt"))
        if not vtt_files:
            raise RuntimeError("yt-dlp no generó ningún archivo de subtítulos")

        chosen = None
        for lang in langs:
            for f in vtt_files:
                if f.stem.endswith(lang):
                    chosen = f
                    break
            if chosen:
                break
        chosen = chosen or vtt_files[0]
        lang_code = chosen.stem.split(".")[-1]
        return clean_vtt(chosen.read_text(encoding="utf-8")), lang_code


def clean_vtt(raw: str) -> str:
    lines = raw.splitlines()
    seen = set()
    cleaned = []
    timestamp_re = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->")
    tag_re = re.compile(r"<[^>]+>")

    for line in lines:
        line = line.strip()
        if not line or line == "WEBVTT":
            continue
        if line.startswith(("Kind:", "Language:")):
            continue
        if timestamp_re.match(line):
            continue
        if line.isdigit():
            continue
        line = tag_re.sub("", line).strip()
        if not line or line in seen:
            continue
        seen.add(line)
        cleaned.append(line)

    return "\n".join(cleaned)


def get_video_title(url: str) -> str:
    result = subprocess.run(
        ["yt-dlp", "--skip-download", "--print", "%(title)s", url],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        title = result.stdout.strip()
        if title:
            return title
    return "video"


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text or "transcripcion"


def build_markdown(title: str, url: str, lang: str, method: str, transcript: str) -> str:
    return (
        f"# {title}\n\n"
        f"- **URL:** {url}\n"
        f"- **Idioma:** {lang}\n"
        f"- **Método:** {method}\n\n"
        "## Transcripción\n\n"
        f"{transcript}\n"
    )


def transcribe(url: str, langs: list[str]) -> Path:
    video_id = extract_video_id(url)
    method = "youtube-transcript-api"
    lang_used = langs[0]

    try:
        text, lang_used = fetch_via_transcript_api(video_id, langs)
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable, Exception):
        text, lang_used = fetch_via_yt_dlp(url, langs)
        method = "yt-dlp (auto-subs)"

    if not text.strip():
        raise RuntimeError("No se pudo obtener una transcripción no vacía para este vídeo")

    title = get_video_title(url)
    markdown = build_markdown(title, url, lang_used, method, text)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"{slugify(title)}.md"
    out_path.write_text(markdown, encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Genera un archivo .md con la transcripción de un vídeo de YouTube."
    )
    parser.add_argument("url", help="URL del vídeo de YouTube")
    parser.add_argument(
        "--lang",
        action="append",
        dest="langs",
        help="Idioma preferido (puede repetirse, ej. --lang es --lang en). Por defecto: es, en",
    )
    args = parser.parse_args()
    langs = args.langs or DEFAULT_LANGS

    try:
        out_path = transcribe(args.url, langs)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Transcripción guardada en: {out_path}")


if __name__ == "__main__":
    main()
