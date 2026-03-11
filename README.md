# Video Review

**Claude Code can't watch videos. But it can look at hundreds of screenshots.**

This skill extracts keyframes from any video and maps them to the transcript, giving Claude full visual context in seconds.

## Why This Exists

When working with clients, you often get:
- Video walkthroughs of their app
- Screen recordings of workflows
- Loom videos explaining pain points
- Meeting recordings

Claude Code can't process video. But feed it 400 screenshots with timestamps and transcript? Now it understands the UI, the workflows, the context.

## How It Works

1. **Takes any video** - local files, YouTube URLs, client recordings
2. **Extracts keyframes** using scene change detection (captures when >X% of pixels change)
3. **Maps frames to transcript** with timestamps
4. **Outputs review.md** - screenshots + text that Claude can analyze

## Requirements

- **Python 3.7+**
- **ffmpeg** (must be on PATH)
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

## Usage

### Local Video Files

```bash
# Extract frames from a client recording
python video_review.py ./client-walkthrough.mp4 ./output

# Lower threshold = more frames (good for UI walkthroughs)
python video_review.py ./client-walkthrough.mp4 ./output 0.1
```

### YouTube URLs

```bash
# Also works with YouTube (downloads video + transcript)
python video_review.py "https://youtube.com/watch?v=VIDEO_ID" ./output
```

### Python API

```python
from video_review import VideoReviewer

# Scene change detection - captures frames when pixels change
reviewer = VideoReviewer(
    scene_threshold=0.1,  # 10% pixel change (more frames for UI walkthroughs)
    min_interval=1.0,     # At least 1 sec between frames
    max_interval=30.0     # At most 30 sec between frames
)

result = reviewer.process("./client-video.mp4", "./output")

print(f"Extracted {result.frame_count} frames")
for frame in result.frames:
    print(f"{frame.timestamp_str}: {frame.path}")
```

## Scene Threshold Guide

| Threshold | Use Case | Frames |
|-----------|----------|--------|
| 0.4 (default) | Videos with clear scene cuts | Fewer |
| 0.2 | Presentations, slide decks | Medium |
| 0.1 | UI walkthroughs, demos | More |
| 0.05 | Capture subtle UI changes | Many |

## Output

```
output/
├── frames/
│   ├── scene_0001.jpg
│   ├── scene_0002.jpg
│   └── ... (potentially 400+ frames)
├── frames.json        # Timestamps + metadata for programmatic use
├── review.md          # Markdown with embedded screenshots + transcript
└── video.mp4          # (if downloaded from URL)
```

The `review.md` file is what you feed to Claude:

```markdown
## 00:00:05
![Frame](frames/scene_0001.jpg)
> "So here's our dashboard..."

## 00:00:12
![Frame](frames/scene_0002.jpg)
> "When a user clicks this button..."
```

## Example Workflow

1. Client sends you a 10-minute Loom walkthrough
2. Run: `python video_review.py ./client-loom.mp4 ./output 0.1`
3. Get: 200 keyframes mapped to transcript
4. Tell Claude: "Review the screenshots in ./output/frames and the transcript. What are the main UX issues?"

Now Claude understands the client's app without you manually explaining every screen.

## License

MIT