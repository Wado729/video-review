# Video Review

**Claude Code can't watch videos. But it can look at hundreds of screenshots.**

Extract keyframes from any video and map them to the transcript — giving Claude (or any AI) full visual context in seconds.

Inspired by [adampaulwalker/video-review](https://github.com/adampaulwalker/video-review).

## Why This Exists

When working with clients or reviewing content, you often get:
- Video walkthroughs of an app
- Screen recordings of workflows
- Loom videos explaining pain points
- Meeting recordings
- YouTube tutorials or presentations

Claude Code can't process video. But feed it 400 screenshots with timestamps and transcript? Now it understands the UI, the workflows, the context.

## How It Works

1. **Takes any video** — local files, YouTube URLs, or client recordings
2. **Extracts keyframes** using ffmpeg scene change detection (captures when >X% of pixels change)
3. **Downloads and parses transcript** (YouTube auto-captions or manual subs)
4. **Maps frames to transcript** with timestamps
5. **Outputs `review.md`** — screenshots + transcript text that Claude can analyze
6. **Outputs `frames.json`** — structured data for programmatic use

## Requirements

- **Python 3.7+**
- **ffmpeg** and **ffprobe** (must be on PATH)
- **yt-dlp** (only needed for YouTube URLs)

```bash
# macOS
brew install ffmpeg
pip install yt-dlp

# Windows (winget)
winget install Gyan.FFmpeg
pip install yt-dlp

# Windows (choco)
choco install ffmpeg
pip install yt-dlp

# Linux (apt)
sudo apt install ffmpeg
pip install yt-dlp
```

Verify installation:
```bash
ffmpeg -version
ffprobe -version
yt-dlp --version   # only if using YouTube URLs
```

## Quick Start

```bash
# Clone the repo
git clone https://github.com/Wado729/video-review.git
cd video-review

# Process a YouTube video (interval mode — 1 frame every 5 seconds)
python video_review.py "https://youtube.com/watch?v=VIDEO_ID" ./output --interval 5

# Process a local video file (scene detection)
python video_review.py ./recording.mp4 ./output

# Feed the output to Claude
# Open ./output/review.md and the frames in ./output/frames/
```

## Usage

### Command Line

```bash
# Scene detection (default) — captures frames on visual changes
python video_review.py <video-url-or-path> <output-dir>

# Interval mode — capture a frame every N seconds (recommended for analysis)
python video_review.py <video-url-or-path> <output-dir> --interval 5

# Custom scene threshold (lower = more frames)
python video_review.py <video-url-or-path> <output-dir> --scene-threshold 0.1

# Process an entire YouTube channel or playlist
python video_review.py --channel "https://youtube.com/@ChannelName" ./output

# Channel with limit
python video_review.py --channel "https://youtube.com/@ChannelName" ./output --max-videos 20
```

### All CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--interval N` | — | Extract a frame every N seconds (overrides scene detection) |
| `--scene-threshold X` | `0.05` | Scene change sensitivity (0.0–1.0) |
| `--min-interval N` | `0.5` | Minimum seconds between frames |
| `--max-interval N` | `120` | Maximum seconds between frames (ensures coverage) |
| `--channel` | — | Treat URL as a channel/playlist and process all videos |
| `--max-videos N` | `0` (all) | Max videos to process from a channel |

### Python API

```python
from video_review import VideoReviewer

# Scene change detection
reviewer = VideoReviewer(
    scene_threshold=0.1,  # 10% pixel change (more frames for UI walkthroughs)
    min_interval=1.0,     # At least 1 sec between frames
    max_interval=30.0     # At most 30 sec between frames
)

result = reviewer.process("./client-video.mp4", "./output")

print(f"Extracted {result.frame_count} frames")
print(f"Transcript segments: {len(result.segments)}")

for frame in result.frames:
    print(f"{frame.timestamp_str}: {frame.path}")
```

#### Interval Mode (Python API)

```python
reviewer = VideoReviewer()
reviewer._force_interval = 5.0  # 1 frame every 5 seconds

result = reviewer.process("https://youtube.com/watch?v=VIDEO_ID", "./output")
```

#### Process a Channel

```python
reviewer = VideoReviewer()
reviewer._force_interval = 5.0

results = reviewer.process_channel(
    "https://youtube.com/@ChannelName",
    "./channel_output",
    max_videos=10
)

for r in results:
    print(f"{r.frame_count} frames — {r.review_path}")
```

## Scene Threshold Guide

| Threshold | Use Case | Frames |
|-----------|----------|--------|
| 0.4 | Videos with clear scene cuts | Fewer |
| 0.2 | Presentations, slide decks | Medium |
| 0.1 | UI walkthroughs, demos | More |
| 0.05 (default) | Capture subtle UI changes | Many |

**Tip:** For most analysis tasks, `--interval 2` or `--interval 5` gives the most consistent results. Scene detection works best for videos with distinct visual transitions (presentations, multi-scene content).

## Output Structure

```
output/
├── frames/
│   ├── scene_0001.jpg
│   ├── scene_0002.jpg
│   └── ... (potentially 400+ frames)
├── frames.json        # Timestamps + transcript + settings (for programmatic use)
├── review.md          # Markdown with transcript + embedded frame references
└── video.mp4          # (if downloaded from YouTube)
```

### review.md

The review file has two sections:

1. **Transcript** — continuous text with inline timestamps
2. **Frames** — each frame with its timestamp and embedded image

```markdown
## Transcript

[0:05] So here's our dashboard... [0:12] When a user clicks this button...

---

## Frames

[00:00:05] Frame 1 - scene_0001.jpg

![Frame 1](frames/scene_0001.jpg)

[00:00:12] Frame 2 - scene_0002.jpg

![Frame 2](frames/scene_0002.jpg)
```

### frames.json

```json
{
  "transcript": [
    {"start": 5.0, "end": 8.5, "text": "So here's our dashboard..."},
    {"start": 12.0, "end": 15.2, "text": "When a user clicks this button..."}
  ],
  "full_transcript": "So here's our dashboard... When a user clicks this button...",
  "frames": [
    {"path": "output/frames/scene_0001.jpg", "timestamp": 5.0, "timestamp_str": "00:00:05"}
  ],
  "settings": {
    "scene_threshold": 0.05,
    "min_interval": 0.5,
    "max_interval": 120.0
  }
}
```

### Channel Output

When processing a channel, each video gets its own subdirectory plus a master index:

```
channel_output/
├── index.md           # Links to all video reviews
├── index.json         # Structured summary
├── 001_Video_Title/
│   ├── frames/
│   ├── frames.json
│   ├── review.md
│   └── video.mp4
├── 002_Another_Video/
│   └── ...
```

## Example Workflows

### Client Video Review
```bash
python video_review.py ./client-loom.mp4 ./output --interval 2
# Then tell Claude: "Review the frames in ./output/frames/ and read ./output/review.md.
# What are the main UX issues in this walkthrough?"
```

### YouTube Tutorial Analysis
```bash
python video_review.py "https://youtube.com/watch?v=VIDEO_ID" ./output --interval 5
# Then tell Claude: "Read ./output/review.md and look at the frames.
# Summarize the key concepts and give me a step-by-step guide."
```

### Bulk Channel Processing
```bash
python video_review.py --channel "https://youtube.com/@ChannelName" ./output --max-videos 10 --interval 5
# Then: "Read ./output/index.md and summarize what topics this channel covers."
```

## Claude Code Skill

This repo includes a `SKILL.md` file for use as a [Claude Code custom skill](https://docs.anthropic.com/en/docs/claude-code). Copy it to your project or reference it directly.

## How It Handles YouTube Transcripts

YouTube auto-captions have a quirky VTT format with duplicate lines and transition blocks. The parser:
- Filters out transition blocks (< 0.1s duration)
- Extracts only new content from `<c>` tagged lines
- Strips all HTML/VTT markup
- Falls back gracefully to manual subs when available
- Works with no transcript at all (frames-only mode)

## License

MIT

## Credits

Inspired by [adampaulwalker/video-review](https://github.com/adampaulwalker/video-review).
