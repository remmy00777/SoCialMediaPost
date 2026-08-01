from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any

from app.services.media_validation import probe_media
from app.services.storage import StorageManager


class MediaRenderError(RuntimeError):
    pass


class MediaRenderer:
    def __init__(self, storage: StorageManager | None = None) -> None:
        self.storage = storage or StorageManager()
        self.ffmpeg = shutil.which("ffmpeg")
        self.ffprobe = shutil.which("ffprobe")
        if not self.ffmpeg or not self.ffprobe:
            raise MediaRenderError("ffmpeg and ffprobe are required")

    def render_platform_package(
        self,
        package_dir: Path,
        content: dict[str, Any],
        analysis: dict[str, Any],
        originality: dict[str, Any],
        compliance: dict[str, Any],
        platform: str,
        package_id: str,
    ) -> dict[str, Any]:
        package_dir.mkdir(parents=True, exist_ok=True)
        duration = min(max(int(content.get("recommended_duration") or 30), 12), 45)
        if self.storage.settings.demo_mode:
            duration = min(duration, 12)
        srt = self._srt(content, duration)
        vtt = self._vtt(srt)
        self.storage.atomic_write_text(package_dir / "subtitles.srt", srt)
        self.storage.atomic_write_text(package_dir / "subtitles.vtt", vtt)
        self.storage.atomic_write_text(package_dir / "script.md", f"# Script\n\n{content['script']}\n")
        self.storage.atomic_write_text(package_dir / "caption.txt", content["caption"])
        self.storage.atomic_write_text(package_dir / "title.txt", content["title"])
        self.storage.atomic_write_text(package_dir / "description.txt", content.get("description", content["caption"]))
        self.storage.atomic_write_text(package_dir / "hashtags.txt", " ".join(content.get("hashtags", [])))
        self.storage.atomic_write_json(package_dir / "trend_analysis.json", analysis)
        self.storage.atomic_write_json(package_dir / "originality_report.json", originality)
        self.storage.atomic_write_json(package_dir / "compliance_report.json", compliance)
        self.storage.atomic_write_json(
            package_dir / "generation_report.json",
            {
                "package_id": package_id,
                "platform": platform,
                "provider": "local_ffmpeg",
                "render_mode": "original_kinetic_typography",
                "source_video_downloaded": False,
                "rights": compliance.get("rights", {}),
                "generation_metadata": content.get("generation_metadata", {}),
            },
        )
        self.storage.atomic_write_json(
            package_dir / "metadata.json",
            {
                **content,
                "package_id": package_id,
                "platform": platform,
                "content_quality_score": self.quality_score(content, originality, compliance),
            },
        )
        self.storage.atomic_write_json(
            package_dir / "publishing_status.json",
            {"status": "draft", "platform": platform, "published": False, "simulated": False},
        )
        self.storage.atomic_write_json(package_dir / "analytics.json", {"status": "not_published", "metrics": {}})
        final_video = package_dir / "final_video.mp4"
        preview = package_dir / "preview.mp4"
        thumbnail = package_dir / "thumbnail.png"
        self._render_video(final_video, package_dir / "subtitles.srt", duration)
        self._render_preview(final_video, preview)
        self._render_thumbnail(final_video, thumbnail)
        validation = probe_media(final_video)
        if not validation.get("valid") or validation.get("duration", 0) <= 0:
            raise MediaRenderError(f"Rendered media failed validation: {validation}")
        return {
            "final_video": str(final_video),
            "preview": str(preview),
            "thumbnail": str(thumbnail),
            "subtitles": str(package_dir / "subtitles.srt"),
            "validation": validation,
            "quality_score": self.quality_score(content, originality, compliance),
        }

    def _render_video(self, output: Path, subtitles: Path, duration: int) -> None:
        escaped = str(subtitles).replace("\", "/").replace(":", "\:").replace("'", "\'")
        filter_chain = (
            "subtitles='" + escaped + "':force_style='FontSize=22,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00101828,BorderStyle=3,Outline=1,Shadow=0,MarginV=180,Alignment=2'"
        )

        # Railway containers can report a high CPU count while having limited
        # memory. Explicitly constrain FFmpeg and x264 resource consumption.
        demo_mode = self.storage.settings.demo_mode
        frame_size = "720x1280" if demo_mode else "1080x1920"
        frame_rate = 20 if demo_mode else 24
        audio_filter = (
            "volume=0.025,aresample=48000"
            if demo_mode
            else "volume=0.025,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000"
        )

        command = [
            self.ffmpeg,
            "-y",
            "-filter_threads",
            "1",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x101828:s={frame_size}:r={frame_rate}:d={duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=220:sample_rate=48000:duration={duration}",
            "-vf",
            filter_chain,
            "-af",
            audio_filter,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "stillimage",
            "-threads:v",
            "2",
            "-x264-params",
            "threads=2",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "-level",
            "4.0",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output),
        ]
        self._run(command, timeout=180)

    def _render_preview(self, source: Path, output: Path) -> None:
        self._run(
            [
                self.ffmpeg,
                "-y",
                "-filter_threads",
                "1",
                "-i",
                str(source),
                "-vf",
                "scale=540:960",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-threads:v",
                "2",
                "-x264-params",
                "threads=2",
                "-crf",
                "30",
                "-c:a",
                "aac",
                "-b:a",
                "64k",
                "-ar",
                "48000",
                "-movflags",
                "+faststart",
                str(output),
            ],
            timeout=120,
        )

    def _render_thumbnail(self, source: Path, output: Path) -> None:
        self._run(
            [self.ffmpeg, "-y", "-ss", "1", "-i", str(source), "-frames:v", "1", "-vf", "scale=1080:1920", str(output)],
            timeout=60,
        )

    @staticmethod
    def _srt(content: dict[str, Any], duration: int) -> str:
        segments = [content.get("hook", "A better way to evaluate this trend")]
        segments.extend(content.get("on_screen_text", [])[1:4])
        segments.append(content.get("call_to_action", "What do you think?"))
        segments = [textwrap.fill(str(segment), width=34) for segment in segments if segment]
        step = duration / max(len(segments), 1)
        lines = []
        for index, segment in enumerate(segments, 1):
            start = (index - 1) * step
            end = min(index * step, duration)
            lines.extend([str(index), f"{MediaRenderer._timestamp(start)} --> {MediaRenderer._timestamp(end)}", segment, ""])
        return "\n".join(lines)

    @staticmethod
    def _vtt(srt: str) -> str:
        return "WEBVTT\n\n" + srt.replace(",", ".")

    @staticmethod
    def _timestamp(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

    @staticmethod
    def quality_score(content: dict[str, Any], originality: dict[str, Any], compliance: dict[str, Any]) -> float:
        completeness_fields = ["title", "script", "caption", "description", "hashtags", "call_to_action"]
        completeness = sum(bool(content.get(field)) for field in completeness_fields) / len(completeness_fields)
        originality_score = 1 - max(originality.get("component_scores", {}).values(), default=0)
        compliance_score = 1.0 if compliance.get("passed") else 0.0
        return round(100 * (0.4 * completeness + 0.35 * originality_score + 0.25 * compliance_score), 2)

    @staticmethod
    def _run(command: list[str | None], timeout: int) -> None:
        clean = [item for item in command if item is not None]
        try:
            result = subprocess.run(
                clean,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise MediaRenderError(
                f"FFmpeg timed out after {timeout} seconds"
            ) from exc

        if result.returncode != 0:
            details = result.stderr[-4000:] or "FFmpeg command failed"
            raise MediaRenderError(
                f"FFmpeg exited with code {result.returncode}: {details}"
            )
