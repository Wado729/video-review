# Video Review Skill

**Claude Code can't watch videos. But it can look at hundreds of screenshots.**

Extract keyframes from any video and map them to the transcript - giving Claude full visual context.

## The Problem

You get a client video (Loom walkthrough, screen recording, meeting) but Claude can't watch it.

## The Solution

1. Extract 100-400+ keyframes using scene change detection
2. Map each frame to the transcript timestamp
3. Feed the screenshots + transcript to Claude

Now Claude understands the UI, workflows, and pain points.

## Usage

```bash
# Local video file (client recording, Loom export, etc.)
python video_review.py ./client-walkthrough.mp4 ./output 0.1

# YouTube URL (downloads video + transcript)
python video_review.py "https://youtube.com/watch?v=VIDEO_ID" ./output
```

## Scene Threshold

| Threshold | Use Case |
|-----------|----------|
| 0.4 | Clear scene cuts (presentations) |
| 0.2 | Slide decks, demos |
| 0.1 | UI walkthroughs (recommended for client videos) |
| 0.05 | Capture subtle changes |

## Output

```
output/
├── frames/           # 100-400+ keyframes
│   ├── scene_0001.jpg
│   └── ...
├── frames.json       # Timestamps for programmatic use
└── review.md         # Screenshots + transcript markdown
```

## Python API

```python
from video_review import VideoReviewer

reviewer = VideoReviewer(
    scene_threshold=0.1,  # 10% pixel change
    min_interval=1.0,     # Min 1 sec between frames
    max_interval=30.0     # Max 30 sec gap
)

result = reviewer.process("./video.mp4", "./output")
print(f"Extracted {result.frame_count} frames")
```

## Requirements

- `ffmpeg` on PATH: `brew install ffmpeg` (macOS) / `winget install Gyan.FFmpeg` (Windows) / `sudo apt install ffmpeg` (Linux)
- `yt-dlp`: `pip install yt-dlp` (only for YouTube URLs)

## Triggers

- "review this video"
- "extract frames from video"
- "analyze client walkthrough"
- "process screen recording"
- "give Claude video context"
