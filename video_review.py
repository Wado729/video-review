#!/usr/bin/env python3
"""
Video Review - Extract frames from videos on scene changes and map to transcript.

Uses scene change detection (40% pixel threshold) instead of fixed intervals
for more meaningful frame captures.

Usage:
    from video_review import VideoReviewer

    reviewer = VideoReviewer(scene_threshold=0.4)
    result = reviewer.process("https://youtube.com/watch?v=VIDEO_ID", "./output")
"""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Frame:
    """A captured frame with its timestamp."""
    path: str
    timestamp: float  # seconds

    @property
    def timestamp_str(self) -> str:
        """Format timestamp as HH:MM:SS."""
        h = int(self.timestamp // 3600)
        m = int((self.timestamp % 3600) // 60)
        s = int(self.timestamp % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


@dataclass
class TranscriptSegment:
    """A segment of transcript with timestamp."""
    start_time: float  # seconds
    end_time: float    # seconds
    text: str

    @property
    def timestamp(self) -> str:
        """Format start time as HH:MM:SS."""
        h = int(self.start_time // 3600)
        m = int((self.start_time % 3600) // 60)
        s = int(self.start_time % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


@dataclass
class ReviewResult:
    """Result of processing a video."""
    video_path: str
    frames_dir: str
    transcript_path: Optional[str]
    review_path: str
    frames: List[Frame]
    segments: List[TranscriptSegment]

    @property
    def frame_count(self) -> int:
        return len(self.frames)


class VideoReviewer:
    """Extract frames from videos on scene changes and map to transcript."""

    YT_DLP = "yt-dlp"

    def __init__(self, scene_threshold: float = 0.05, min_interval: float = 0.5,
                 max_interval: float = 120.0):
        """
        Initialize reviewer with scene change detection.

        Args:
            scene_threshold: Pixel change threshold (0.0-1.0). 0.4 = 40% pixels changed.
            min_interval: Minimum seconds between frames (prevents too many frames).
            max_interval: Maximum seconds between frames (ensures coverage).
        """
        self.scene_threshold = scene_threshold
        self.min_interval = min_interval
        self.max_interval = max_interval

    def list_channel_videos(self, channel_url: str, max_videos: int = 0) -> List[dict]:
        """
        List all videos from a YouTube channel/playlist URL.

        Args:
            channel_url: YouTube channel or playlist URL
            max_videos: Max videos to return (0 = all)

        Returns:
            List of dicts with 'url', 'title', 'id' per video
        """
        cmd = [
            self.YT_DLP,
            "--flat-playlist",
            "--print", "%(id)s\t%(title)s",
            channel_url,
        ]
        if max_videos > 0:
            cmd.extend(["--playlist-end", str(max_videos)])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp failed: {result.stderr.strip()}")

        videos = []
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t', 1)
            vid_id = parts[0]
            title = parts[1] if len(parts) > 1 else vid_id
            videos.append({
                "id": vid_id,
                "title": title,
                "url": f"https://www.youtube.com/watch?v={vid_id}",
            })
        return videos

    def process_channel(self, channel_url: str, output_dir: str,
                        max_videos: int = 0) -> List[ReviewResult]:
        """
        Process every video from a YouTube channel or playlist.

        Each video gets its own subdirectory under output_dir.
        A master index.md is generated linking all reviews.

        Args:
            channel_url: YouTube channel or playlist URL
            output_dir: Root output directory
            max_videos: Max videos to process (0 = all)

        Returns:
            List of ReviewResult, one per video
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"Listing videos from: {channel_url}")
        videos = self.list_channel_videos(channel_url, max_videos)
        print(f"Found {len(videos)} videos")

        results = []
        failed = []
        for i, video in enumerate(videos, 1):
            # Sanitize title for directory name (Windows strips trailing dots/spaces)
            safe_title = re.sub(r'[<>:"/\\|?*,#\']', '_', video["title"])
            safe_title = safe_title[:80].strip().rstrip('. ')
            video_dir = output_path / f"{i:03d}_{safe_title}"

            print(f"\n{'='*80}")
            print(f"[{i}/{len(videos)}] {video['title']}")
            print(f"  URL: {video['url']}")
            print(f"  Output: {video_dir}")
            print(f"{'='*80}")

            try:
                result = self.process(video["url"], str(video_dir))
                results.append(result)
                print(f"  Done: {result.frame_count} frames, "
                      f"{len(result.segments)} transcript segments")
            except Exception as e:
                print(f"  FAILED: {e}")
                failed.append({"video": video, "error": str(e)})

        # Generate master index
        self._generate_channel_index(output_path, videos, results, failed)

        print(f"\n{'='*80}")
        print(f"CHANNEL COMPLETE: {len(results)} succeeded, {len(failed)} failed")
        print(f"Index: {output_path / 'index.md'}")
        print(f"{'='*80}")

        return results

    def _generate_channel_index(self, output_dir: Path, videos: list,
                                 results: List['ReviewResult'], failed: list):
        """Generate a master index.md linking all video reviews."""
        index_path = output_dir / "index.md"
        lines = [
            "# Channel Video Reviews\n\n",
            f"**Total videos:** {len(videos)} | "
            f"**Processed:** {len(results)} | "
            f"**Failed:** {len(failed)}\n\n",
            "---\n\n",
        ]

        for i, result in enumerate(results, 1):
            rel_review = Path(result.review_path).relative_to(output_dir)
            lines.append(f"{i}. [{Path(result.review_path).parent.name}]({rel_review}) "
                         f"— {result.frame_count} frames, "
                         f"{len(result.segments)} transcript segments\n")

        if failed:
            lines.append("\n## Failed\n\n")
            for f in failed:
                lines.append(f"- {f['video']['title']} — {f['error']}\n")

        # Also save as JSON for programmatic use
        summary = {
            "total": len(videos),
            "processed": len(results),
            "failed_count": len(failed),
            "videos": [
                {
                    "title": Path(r.review_path).parent.name,
                    "review": str(Path(r.review_path).relative_to(output_dir)),
                    "frames": r.frame_count,
                    "transcript_segments": len(r.segments),
                }
                for r in results
            ],
            "failed": [{"title": f["video"]["title"], "error": f["error"]} for f in failed],
        }
        (output_dir / "index.json").write_text(json.dumps(summary, indent=2))
        index_path.write_text("".join(lines))

    def process(self, video_url: str, output_dir: str) -> ReviewResult:
        """
        Process a video: download, extract frames on scene changes, map transcript.

        Args:
            video_url: YouTube URL or local video path
            output_dir: Directory to save output

        Returns:
            ReviewResult with paths and segments
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        frames_dir = output_path / "frames"
        # Clear old frames to avoid stale results from previous runs
        if frames_dir.exists():
            for old_frame in frames_dir.glob("scene_*.jpg"):
                old_frame.unlink()
        frames_dir.mkdir(exist_ok=True)

        # Check if it's a URL or local file
        is_url = video_url.startswith(('http://', 'https://', 'www.'))

        if is_url:
            # Download transcript
            transcript_path = self._download_transcript(video_url, output_path)
            # Download video
            video_path = self._download_video(video_url, output_path)
        else:
            video_path = Path(video_url)
            transcript_path = None

        # Extract frames on scene changes
        frames = self._extract_frames_on_scene_change(video_path, frames_dir)

        # Parse transcript
        segments = self._parse_transcript(transcript_path) if transcript_path else []

        # Generate review markdown
        review_path = self._generate_review(output_path, frames, segments)

        # Save frame timestamps as JSON for programmatic use
        self._save_frame_data(output_path, frames, segments)

        return ReviewResult(
            video_path=str(video_path),
            frames_dir=str(frames_dir),
            transcript_path=str(transcript_path) if transcript_path else None,
            review_path=str(review_path),
            frames=frames,
            segments=segments
        )

    def _download_transcript(self, url: str, output_dir: Path) -> Optional[Path]:
        """Download transcript VTT file."""
        # Try auto-subs first
        subprocess.run([
            self.YT_DLP,
            "--no-playlist",
            "--write-auto-sub", "--sub-lang", "en",
            "--skip-download",
            "--output", str(output_dir / "%(title)s"),
            url
        ], capture_output=True)

        # Try manual subs
        subprocess.run([
            self.YT_DLP,
            "--no-playlist",
            "--write-sub", "--sub-lang", "en",
            "--skip-download",
            "--output", str(output_dir / "%(title)s"),
            url
        ], capture_output=True)

        # Find VTT file
        vtt_files = list(output_dir.glob("*.vtt"))
        return vtt_files[0] if vtt_files else None

    def _download_video(self, url: str, output_dir: Path) -> Path:
        """Download video file."""
        video_path = output_dir / "video.mp4"
        if video_path.exists():
            print(f"Video already exists: {video_path}")
            return video_path

        subprocess.run([
            self.YT_DLP,
            "--no-playlist",
            "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "--merge-output-format", "mp4",
            "--output", str(video_path),
            url
        ], check=True)
        return video_path

    def _extract_frames_on_scene_change(self, video_path: Path, frames_dir: Path) -> List[Frame]:
        """
        Extract frames using scene change detection or fixed interval.
        """
        frames = []

        # First, get video duration
        duration = self._get_video_duration(video_path)

        # If forced interval mode, skip scene detection entirely
        if getattr(self, '_force_interval', None):
            print(f"Extracting frames every {self._force_interval} seconds (interval mode)...")
            return self._extract_frames_interval(video_path, frames_dir, duration)

        # Use ffmpeg to detect scene changes and extract frames
        # The select filter detects scene changes, showinfo prints timestamps
        # We capture both scene changes AND periodic frames for coverage

        filter_complex = (
            f"select='gt(scene,{self.scene_threshold})+isnan(prev_selected_t)"
            f"+gte(t-prev_selected_t,{self.max_interval})',"
            f"showinfo"
        )

        # Run ffmpeg to extract frames with scene detection
        result = subprocess.run([
            "ffmpeg", "-i", str(video_path),
            "-vf", filter_complex,
            "-vsync", "vfr",
            "-q:v", "2",
            str(frames_dir / "scene_%04d.jpg"),
            "-hide_banner"
        ], capture_output=True, text=True)

        # Parse showinfo output to get timestamps
        timestamps = self._parse_showinfo_timestamps(result.stderr)

        # If scene detection didn't work well, fall back to interval-based
        frame_files = sorted(frames_dir.glob("scene_*.jpg"))

        if not frame_files:
            print("Scene detection found no frames, falling back to interval extraction...")
            return self._extract_frames_interval(video_path, frames_dir, duration)

        # Match timestamps to frame files
        for i, frame_path in enumerate(frame_files):
            timestamp = timestamps[i] if i < len(timestamps) else i * self.max_interval
            frames.append(Frame(path=str(frame_path), timestamp=timestamp))

        # Enforce minimum interval by removing too-close frames
        frames = self._enforce_min_interval(frames)

        print(f"Extracted {len(frames)} frames based on scene changes")
        return frames

    def _extract_frames_interval(self, video_path: Path, frames_dir: Path,
                                  duration: float) -> List[Frame]:
        """Extract frames at regular intervals."""
        if getattr(self, '_force_interval', None):
            interval = self._force_interval
        else:
            interval = min(self.max_interval, max(duration / 50, self.min_interval))

        subprocess.run([
            "ffmpeg", "-i", str(video_path),
            "-vf", f"fps=1/{interval}",
            "-q:v", "2",
            str(frames_dir / "scene_%04d.jpg"),
            "-hide_banner", "-loglevel", "error"
        ], check=True)

        frames = []
        for i, frame_path in enumerate(sorted(frames_dir.glob("scene_*.jpg"))):
            frames.append(Frame(path=str(frame_path), timestamp=i * interval))

        return frames

    def _get_video_duration(self, video_path: Path) -> float:
        """Get video duration in seconds."""
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ], capture_output=True, text=True)

        try:
            return float(result.stdout.strip())
        except ValueError:
            return 300.0  # Default 5 minutes

    def _parse_showinfo_timestamps(self, ffmpeg_output: str) -> List[float]:
        """Parse timestamps from ffmpeg showinfo filter output."""
        timestamps = []
        # showinfo output format: ... pts_time:123.456 ...
        pattern = r'pts_time:(\d+\.?\d*)'

        for match in re.finditer(pattern, ffmpeg_output):
            timestamps.append(float(match.group(1)))

        return timestamps

    def _enforce_min_interval(self, frames: List[Frame]) -> List[Frame]:
        """Remove frames that are too close together."""
        if not frames:
            return frames

        filtered = [frames[0]]
        for frame in frames[1:]:
            if frame.timestamp - filtered[-1].timestamp >= self.min_interval:
                filtered.append(frame)

        return filtered

    def _parse_transcript(self, vtt_path: Path) -> List[TranscriptSegment]:
        """Parse YouTube auto-caption VTT into clean, non-repeating segments.

        YouTube VTT has a pattern:
        - 'Real' blocks (~2-4s duration) have 2 lines: line1=previous text, line2=NEW text with <c> tags
        - 'Transition' blocks (~0.01s) just redisplay completed text — skip these
        We only extract the new content from real blocks.
        """
        segments = []
        content = vtt_path.read_text(encoding='utf-8')

        # Split into blocks separated by blank lines
        blocks = re.split(r'\n\n+', content)

        for block in blocks:
            block = block.strip()
            if not block or block.startswith('WEBVTT') or block.startswith('Kind:') or block.startswith('Language:'):
                continue

            # Match timestamp line
            ts_match = re.match(
                r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})',
                block
            )
            if not ts_match:
                continue

            start = self._parse_timestamp(ts_match.group(1))
            end = self._parse_timestamp(ts_match.group(2))

            # Skip transition blocks (duration < 0.1s)
            if (end - start) < 0.1:
                continue

            # Get text lines after the timestamp
            text_part = block[ts_match.end():].strip()
            text_lines = text_part.split('\n')

            # The NEW content is the line with <c> tags (usually line 2)
            # If only one line exists, use it
            new_text = None
            for line in text_lines:
                if '<c>' in line or '<' in line and '>' in line:
                    new_text = line
                    break

            if new_text is None and text_lines:
                # No <c> tags — might be manual subs, use all text
                new_text = ' '.join(text_lines)

            if new_text:
                # Strip all HTML/VTT tags and timestamps
                clean = re.sub(r'<[^>]+>', '', new_text).strip()
                clean = ' '.join(clean.split())
                if clean:
                    segments.append(TranscriptSegment(start, end, clean))

        return segments

    def _parse_timestamp(self, ts: str) -> float:
        """Parse VTT timestamp to seconds."""
        parts = ts.replace(',', '.').split(':')
        h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
        return h * 3600 + m * 60 + s

    def _find_transcript_for_timestamp(self, timestamp: float,
                                        segments: List[TranscriptSegment]) -> Optional[str]:
        """Find transcript text for a given timestamp."""
        for segment in segments:
            if segment.start_time <= timestamp < segment.end_time:
                return segment.text

        # If no exact match, find the closest previous segment
        closest = None
        for segment in segments:
            if segment.start_time <= timestamp:
                closest = segment
            else:
                break

        return closest.text if closest else None

    def _generate_review(self, output_dir: Path, frames: List[Frame],
                         segments: List[TranscriptSegment]) -> Path:
        """Generate review with continuous transcript section + frames section."""
        review_path = output_dir / "review.md"

        duration = frames[-1].timestamp if frames else 0
        mode = f"every {self._force_interval}s" if getattr(self, '_force_interval', None) else f"scene detection @ {self.scene_threshold*100:.0f}%"

        lines = [
            "# Video Review\n\n",
            f"**Duration:** {self._format_time(duration)} | **Frames:** {len(frames)} ({mode}) | **Transcript segments:** {len(segments)}\n\n",
            "---\n\n"
        ]

        # Section 1: Continuous transcript with inline timestamps
        lines.append("## Transcript\n\n")
        if segments:
            transcript_parts = []
            for seg in segments:
                ts_str = self._format_time(seg.start_time)
                transcript_parts.append(f"[{ts_str}] {seg.text}")
            lines.append(' '.join(transcript_parts) + "\n\n")
        else:
            lines.append("*No transcript available.*\n\n")

        lines.append("---\n\n")

        # Section 2: Frames with timestamps
        lines.append("## Frames\n\n")
        for i, frame in enumerate(frames):
            frame_name = Path(frame.path).name
            lines.append(f"[{frame.timestamp_str}] Frame {i+1} - {frame_name}\n\n")
            lines.append(f"![Frame {i+1}](frames/{frame_name})\n\n")

        review_path.write_text("".join(lines))
        return review_path

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as M:SS or H:MM:SS."""
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def _save_frame_data(self, output_dir: Path, frames: List[Frame],
                         segments: List[TranscriptSegment]):
        """Save frame data and full transcript as JSON."""
        data = {
            "transcript": [
                {
                    "start": seg.start_time,
                    "end": seg.end_time,
                    "text": seg.text
                }
                for seg in segments
            ],
            "full_transcript": ' '.join(seg.text for seg in segments),
            "frames": [
                {
                    "path": f.path,
                    "timestamp": f.timestamp,
                    "timestamp_str": f.timestamp_str
                }
                for f in frames
            ],
            "settings": {
                "scene_threshold": self.scene_threshold,
                "min_interval": self.min_interval,
                "max_interval": self.max_interval
            }
        }

        json_path = output_dir / "frames.json"
        json_path.write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract frames and transcript from YouTube videos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  Single video (interval mode):
    python video_review.py 'https://youtube.com/watch?v=...' ./output --interval 5

  Single video (scene detection):
    python video_review.py 'https://youtube.com/watch?v=...' ./output --scene-threshold 0.05

  Entire channel:
    python video_review.py --channel 'https://youtube.com/@ChannelName' ./output --interval 5

  Channel (latest 20 videos):
    python video_review.py --channel 'https://youtube.com/@ChannelName' ./output --max-videos 20
""",
    )
    parser.add_argument("url", help="YouTube video URL (or channel/playlist URL with --channel)")
    parser.add_argument("output", help="Output directory")
    parser.add_argument("--channel", action="store_true",
                        help="Treat URL as a channel/playlist and process all videos")
    parser.add_argument("--max-videos", type=int, default=0,
                        help="Max videos to process from channel (0 = all)")
    parser.add_argument("--interval", type=float, default=None,
                        help="Extract a frame every N seconds (recommended for analysis)")
    parser.add_argument("--scene-threshold", type=float, default=0.05,
                        help="Scene detection threshold 0.0-1.0 (default: 0.05)")
    parser.add_argument("--max-interval", type=float, default=120.0,
                        help="Max seconds between frames in scene mode (default: 120)")
    parser.add_argument("--min-interval", type=float, default=0.5,
                        help="Min seconds between frames (default: 0.5)")

    args = parser.parse_args()

    # Auto-detect channel/playlist URLs
    is_channel = args.channel
    if not is_channel:
        url_lower = args.url.lower()
        channel_patterns = ['/@', '/channel/', '/c/', '/user/', '/videos',
                            '/playlist?', '/playlists']
        if any(p in url_lower for p in channel_patterns):
            is_channel = True
            print(f"Auto-detected channel/playlist URL")

    # Build reviewer
    if args.interval:
        reviewer = VideoReviewer(scene_threshold=0.4, max_interval=args.interval, min_interval=0.5)
        reviewer._force_interval = args.interval
    else:
        reviewer = VideoReviewer(scene_threshold=args.scene_threshold,
                                 max_interval=args.max_interval,
                                 min_interval=args.min_interval)
        reviewer._force_interval = None

    if is_channel:
        results = reviewer.process_channel(args.url, args.output, max_videos=args.max_videos)
        print(f"\n=== Channel Complete ===")
        print(f"Processed {len(results)} videos to: {args.output}")
    else:
        result = reviewer.process(args.url, args.output)
        print(f"\n=== Complete ===")
        print(f"Extracted {result.frame_count} frames")
        print(f"Review saved to: {result.review_path}")
