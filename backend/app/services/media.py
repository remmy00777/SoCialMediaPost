from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any

from app.services.media_validation import probe_media
from app.services.storage import StorageManager


AUTHORIZED_SOURCE_RIGHTS = {"user_owned", "licensed", "public_domain", "explicit_permission"}


class MediaRenderError(RuntimeError):
    pass


class MediaRenderer:
    def __init__(self, storage: StorageManager | None = None) -> None:
        self.storage = storage or StorageManager()
        self.ffmpeg = shutil.which("ffmpeg")
        self.ffprobe = shutil.which("ffprobe")
        self.tts = shutil.which("espeak-ng") or shutil.which("espeak") or shutil.which("say")
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
        source_media = content.get("source_media") or None
        uses_authorized_source = bool(
            source_media
            and source_media.get("allow_full_reuse")
            and source_media.get("rights_status") in AUTHORIZED_SOURCE_RIGHTS
        )

        final_video = package_dir / "final_video.mp4"
        preview = package_dir / "preview.mp4"
        thumbnail = package_dir / "thumbnail.png"

        if uses_authorized_source:
            voice_path, intro_duration = self._prepare_voiceover(package_dir, content.get("voiceover_intro") or content["hook"])
            srt = self._intro_srt(content, intro_duration)
            self.storage.atomic_write_text(package_dir / "subtitles.srt", srt)
            self.storage.atomic_write_text(package_dir / "subtitles.vtt", self._vtt(srt))
            duration = self._render_authorized_source_remix(
                final_video,
                Path(str(source_media["path"])),
                voice_path,
                package_dir / "subtitles.srt",
                intro_duration,
            )
            render_mode = "authorized_source_with_voiceover_intro"
        else:
            duration = min(max(int(content.get("recommended_duration") or 30), 12), 45)
            if self.storage.settings.demo_mode:
                duration = min(duration, 12)
            srt = self._srt(content, duration)
            self.storage.atomic_write_text(package_dir / "subtitles.srt", srt)
            self.storage.atomic_write_text(package_dir / "subtitles.vtt", self._vtt(srt))
            self._render_original_video(final_video, package_dir / "subtitles.srt", duration)
            render_mode = "original_kinetic_typography"

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
                "render_mode": render_mode,
                "source_video_downloaded": False,
                "source_media_uploaded_by_user": uses_authorized_source,
                "rights": compliance.get("rights", {}),
                "generation_metadata": content.get("generation_metadata", {}),
                "rendered_duration_seconds": duration,
            },
        )
        self.storage.atomic_write_json(
            package_dir / "metadata.json",
            {
                **content,
                "package_id": package_id,
                "platform": platform,
                "content_quality_score": self.quality_score(content, originality, compliance),
                "rendered_duration_seconds": duration,
            },
        )
        self.storage.atomic_write_json(
            package_dir / "publishing_status.json",
            {"status": "draft", "platform": platform, "published": False, "simulated": False},
        )
        self.storage.atomic_write_json(package_dir / "analytics.json", {"status": "not_published", "metrics": {}})

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

    def _prepare_voiceover(self, package_dir: Path, text: str) -> tuple[Path, float]:
        if not self.tts:
            raise MediaRenderError("A local TTS command is required for voiceover-intro mode")
        raw = package_dir / ".voiceover.wav"
        if Path(self.tts).name == "say":
            aiff = package_dir / ".voiceover.aiff"
            self._run([self.tts, "-r", "165", "-o", str(aiff), text], timeout=90)
            self._run(
                [self.ffmpeg, "-y", "-i", str(aiff), "-ar", "48000", "-ac", "2", str(raw)],
                timeout=90,
            )
            aiff.unlink(missing_ok=True)
        else:
            self._run([self.tts, "-s", "165", "-w", str(raw), text], timeout=90)
        duration = self._probe_duration(raw)
        if duration <= 0:
            raise MediaRenderError("Generated voiceover has no measurable duration")
        return raw, duration

    def _render_authorized_source_remix(
        self,
        output: Path,
        source: Path,
        voice_path: Path,
        subtitles: Path,
        intro_duration: float,
    ) -> float:
        source = self.storage.ensure_inside_root(source)
        if not source.is_file():
            raise MediaRenderError("The authorized source media file is missing")
        source_probe = probe_media(source)
        if not source_probe.get("valid"):
            raise MediaRenderError(f"Authorized source media failed validation: {source_probe}")
        source_duration = float(source_probe.get("duration") or 0)
        if source_duration <= 0:
            raise MediaRenderError("Authorized source media has no measurable duration")

        intro = output.parent / ".intro.mp4"
        normalized = output.parent / ".source-normalized.mp4"
        escaped = self._escape_subtitles(subtitles)
        self._run(
            [
                self.ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c=0x101828:s=1080x1920:r=24:d={intro_duration + 0.15:.3f}",
                "-i",
                str(voice_path),
                "-vf",
                "subtitles='" + escaped + "':force_style='FontSize=22,PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&H00101828,BorderStyle=3,Outline=1,Shadow=0,MarginV=180,Alignment=2'",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "24",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                "-shortest",
                str(intro),
            ],
            timeout=180,
        )

        video_filter = (
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=24"
        )
        if source_probe.get("audio_codec"):
            command = [
                self.ffmpeg,
                "-y",
                "-i",
                str(source),
                "-vf",
                video_filter,
                "-af",
                "aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "24",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                str(normalized),
            ]
        else:
            command = [
                self.ffmpeg,
                "-y",
                "-i",
                str(source),
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=48000:cl=stereo",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-vf",
                video_filter,
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "24",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-shortest",
                "-movflags",
                "+faststart",
                str(normalized),
            ]
        self._run(command, timeout=600)
        self._run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                str(intro),
                "-i",
                str(normalized),
                "-filter_complex",
                "[0:v:0][0:a:0][1:v:0][1:a:0]concat=n=2:v=1:a=1[v][a]",
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                str(output),
            ],
            timeout=900,
        )
        for temporary in (voice_path, intro, normalized):
            temporary.unlink(missing_ok=True)
        return round(intro_duration + source_duration, 3)

    def _render_original_video(self, output: Path, subtitles: Path, duration: int) -> None:
        escaped = self._escape_subtitles(subtitles)
        filter_chain = (
            "subtitles='" + escaped + "':force_style='FontSize=22,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00101828,BorderStyle=3,Outline=1,Shadow=0,MarginV=180,Alignment=2'"
        )
        command = [
            self.ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x101828:s=1080x1920:r=24:d={duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=220:sample_rate=48000:duration={duration}",
            "-vf",
            filter_chain,
            "-af",
            "volume=0.025,loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "stillimage",
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
                "-i",
                str(source),
                "-vf",
                "scale=540:960",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "30",
                "-c:a",
                "aac",
                "-b:a",
                "64k",
                "-movflags",
                "+faststart",
                str(output),
            ],
            timeout=300,
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
    def _intro_srt(content: dict[str, Any], duration: float) -> str:
        text = textwrap.fill(str(content.get("voiceover_intro") or content.get("hook") or "Context before the clip"), width=34)
        return "\n".join(["1", f"00:00:00,000 --> {MediaRenderer._timestamp(duration)}", text, ""])

    @staticmethod
    def _vtt(srt: str) -> str:
        return "WEBVTT\n\n" + srt.replace(",", ".")

    @staticmethod
    def _timestamp(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        if millis == 1000:
            secs += 1
            millis = 0
        return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

    @staticmethod
    def _escape_subtitles(path: Path) -> str:
        return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")

    def _probe_duration(self, path: Path) -> float:
        result = subprocess.run(
            [
                self.ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            raise MediaRenderError(result.stderr[-1000:] or "ffprobe failed")
        return float(json.loads(result.stdout).get("format", {}).get("duration") or 0)

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
        result = subprocess.run(clean, capture_output=True, text=True, check=False, timeout=timeout)
        if result.returncode != 0:
            raise MediaRenderError(result.stderr[-3000:] or "media command failed")
