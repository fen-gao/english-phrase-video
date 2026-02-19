"""
English Phrases - Audio + Subtitled Video Generator
Run locally on Manjaro Linux.
Usage: python generate.py
"""

import os
import asyncio
import io

# Set ImageMagick binary before importing moviepy
os.environ["IMAGEMAGICK_BINARY"] = "/usr/bin/convert"

import edge_tts
from pydub import AudioSegment
from moviepy import AudioFileClip, ColorClip, CompositeVideoClip, TextClip

# ============================================================
# CONFIGURATION
# ============================================================
VOICE = "en-US-GuyNeural"
RATE = "-10%"
REPETITIONS = 5
PAUSE_SECONDS = 4
INTER_PHRASE_PAUSE = 1
TITLE_SILENCE_SECONDS = 6

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 24
BG_COLOR = (15, 15, 25)
TEXT_COLOR = "white"
ACCENT_COLOR = "#4FC3F7"
COUNTER_COLOR = "#FFAB40"
FONT_SIZE = 120
COUNTER_FONT_SIZE = 56
PROGRESS_FONT_SIZE = 40
FONT_BOLD = "/usr/share/fonts/liberation/LiberationSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/liberation/LiberationSans-Regular.ttf"
OUTPUT_DIR = "output"  # Change this to any folder name inside the project directory
TITLE_CARD_TEXT = "Responding to Apologies"
OUTPUT_VIDEO = "english_phrases_video.mp4"
OUTPUT_AUDIO = "english_phrases_audio.mp3"
TTS_MAX_CONCURRENCY = 10
RENDER_THREADS = max(1, os.cpu_count() or 1)


def get_output_index(output_dir):
    """Get next index based on count of .mp4 files in output folder. Returns 1 if empty."""
    if not output_dir or not os.path.isdir(output_dir):
        return 1
    mp4_files = [f for f in os.listdir(output_dir) if f.endswith(".mp4")]
    return len(mp4_files) + 1


def sanitize_filename(text):
    """Make text safe for use in filenames (e.g. / becomes -)."""
    return text.replace("/", "-")

# ============================================================
# PHRASES
# ============================================================
phrases = [
  "No worries.",
  "It's fine, honestly.",
  "Don't worry about it.",
  "It's all good.",
  "Water under the bridge.",
  "No harm done.",
  "It happens.",
  "Forget about it.",
  "It's nothing.",
  "Apology accepted.",
];
# ============================================================
# AUDIO GENERATION
# ============================================================
async def generate_phrase_audio(phrase, voice=VOICE, rate=RATE, output_dir=None):
    clean_phrase = phrase.replace('\\"', '"').replace('\\', '').strip()
    communicate = edge_tts.Communicate(clean_phrase, voice, rate=rate)
    mp3_bytes = bytearray()

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_bytes.extend(chunk["data"])

    if not mp3_bytes:
        raise RuntimeError(f"No audio data returned for phrase: {phrase}")

    return AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")


async def generate_phrase_audios(phrases):
    results = [None] * len(phrases)
    semaphore = asyncio.Semaphore(TTS_MAX_CONCURRENCY)

    async def worker(index, phrase):
        async with semaphore:
            try:
                audio = await generate_phrase_audio(phrase)
                return index, audio, None
            except Exception as exc:
                return index, None, exc

    tasks = [asyncio.create_task(worker(i, phrase)) for i, phrase in enumerate(phrases)]

    completed = 0
    for task in asyncio.as_completed(tasks):
        idx, audio, error = await task
        results[idx] = (audio, error)
        completed += 1
        if completed % 10 == 0 or completed == len(phrases):
            print(f"   ✅ Audio synthesized: {completed}/{len(phrases)}")

    return results


def silence_like(duration_ms, reference_audio):
    return (
        AudioSegment.silent(duration=duration_ms, frame_rate=reference_audio.frame_rate)
        .set_channels(reference_audio.channels)
        .set_sample_width(reference_audio.sample_width)
    )


def normalize_audio_format(audio, reference_audio):
    if audio.frame_rate != reference_audio.frame_rate:
        audio = audio.set_frame_rate(reference_audio.frame_rate)
    if audio.channels != reference_audio.channels:
        audio = audio.set_channels(reference_audio.channels)
    if audio.sample_width != reference_audio.sample_width:
        audio = audio.set_sample_width(reference_audio.sample_width)
    return audio


def concatenate_segments(segments, reference_audio):
    joined = b"".join(segment.raw_data for segment in segments)
    return AudioSegment(
        data=joined,
        sample_width=reference_audio.sample_width,
        frame_rate=reference_audio.frame_rate,
        channels=reference_audio.channels,
    )


async def create_audio_with_timing(phrases, output_dir=None):
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        audio_path = os.path.join(output_dir, OUTPUT_AUDIO)
    else:
        audio_path = OUTPUT_AUDIO

    print(f"🎤 Generating audio for {len(phrases)} phrases...")
    print(f"   Voice: {VOICE} | Rate: {RATE} | Reps: {REPETITIONS}")
    print(f"   TTS concurrency: {TTS_MAX_CONCURRENCY}")
    print(f"   Title intro silence: {TITLE_SILENCE_SECONDS}s\n")

    phrase_results = await generate_phrase_audios(phrases)
    successful_phrase_audio = next((audio for audio, err in phrase_results if audio is not None), None)
    if successful_phrase_audio is None:
        raise RuntimeError("Audio generation failed for all phrases.")

    pause = silence_like(PAUSE_SECONDS * 1000, successful_phrase_audio)
    short_pause = silence_like(INTER_PHRASE_PAUSE * 1000, successful_phrase_audio)
    title_silence = silence_like(TITLE_SILENCE_SECONDS * 1000, successful_phrase_audio)

    segments = [title_silence]
    timing = []
    current_ms = len(title_silence)

    for i, phrase in enumerate(phrases):
        phrase_audio, error = phrase_results[i]
        if error:
            print(f"   ❌ Error on phrase {i + 1}: {phrase[:40]}... - {error}")
            continue

        phrase_audio = normalize_audio_format(phrase_audio, successful_phrase_audio)

        for rep in range(REPETITIONS):
            start_ms = current_ms
            segments.append(phrase_audio)
            current_ms += len(phrase_audio)
            end_ms = current_ms
            timing.append((phrase, start_ms, end_ms, rep + 1, i + 1))
            segments.append(pause)
            current_ms += len(pause)

        segments.append(short_pause)
        current_ms += len(short_pause)

    print(f"\n💾 Saving audio to {audio_path}...")
    combined = concatenate_segments(segments, successful_phrase_audio)
    combined.export(audio_path, format="mp3", bitrate="192k")
    duration_min = len(combined) / 1000 / 60
    print(f"   Duration: {duration_min:.1f} minutes")

    return audio_path, timing, len(combined)


# ============================================================
# VIDEO GENERATION
# ============================================================
def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def create_video_from_timing(audio_path, timing, total_duration_ms, output_dir=None):
    total_phrases = len(phrases)
    total_duration_s = total_duration_ms / 1000.0

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        video_path = os.path.join(output_dir, OUTPUT_VIDEO)
    else:
        video_path = OUTPUT_VIDEO

    print(f"\n🎬 Creating video ({VIDEO_WIDTH}x{VIDEO_HEIGHT} @ {FPS}fps)...")
    print(f"   Total duration: {format_time(total_duration_s)}")
    print(f"   Subtitle font size: {FONT_SIZE}px (BIG)")

    progress_width = 350
    progress_height = int(PROGRESS_FONT_SIZE * 1.8)
    progress_x = VIDEO_WIDTH - progress_width - 40

    audio = AudioFileClip(audio_path)
    bg = ColorClip(
        size=(VIDEO_WIDTH, VIDEO_HEIGHT),
        color=BG_COLOR,
        duration=total_duration_s
    )

    title_clips = []
    phrase_clips = []
    counter_clips = []
    progress_clips = []
    phrase_template_cache = {}
    counter_template_cache = {}
    progress_template_cache = {}
    phrase_windows = {}

    # === TITLE CARD (plays during silent intro, BEFORE any phrases) ===
    try:
        # Calculate safe height for title (2 lines, font_size 90)
        title_font_size = 90
        title_safe_height = int(title_font_size * 2.5)  # Extra padding for 2 lines + ascenders
        title = TextClip(
            text=TITLE_CARD_TEXT,
            font_size=title_font_size,
            color=ACCENT_COLOR,
            font=FONT_BOLD,
            method="caption",
            size=(VIDEO_WIDTH - 400, title_safe_height),  # Explicit height with padding
            text_align="center",
            duration=TITLE_SILENCE_SECONDS - 0.5,
        ).with_position("center").with_start(0)
        title_clips.append(title)
        print(f"   🎬 Title card: 0s to {TITLE_SILENCE_SECONDS - 0.5}s")
    except Exception as e:
        print(f"   ⚠️ Title card skipped: {e}")

    for phrase_text, start_ms, end_ms, rep_num, phrase_idx in timing:
        start_s = start_ms / 1000.0
        end_s = (end_ms / 1000.0) + PAUSE_SECONDS

        window = phrase_windows.get(phrase_idx)
        if window is None:
            phrase_windows[phrase_idx] = [phrase_text, start_s, end_s]
        else:
            window[2] = end_s

        event_duration = end_s - start_s
        counter_template = counter_template_cache.get(rep_num)
        if counter_template is None:
            counter_text = f"[ {rep_num} / {REPETITIONS} ]"
            counter_template = TextClip(
                text=counter_text,
                font_size=COUNTER_FONT_SIZE,
                color=COUNTER_COLOR,
                font=FONT_REGULAR,
                duration=1,
            ).with_position(("center", VIDEO_HEIGHT * 0.82))
            counter_template_cache[rep_num] = counter_template

        counter_clips.append(counter_template.with_start(start_s).with_duration(event_duration))

    # === PHRASE SUBTITLES ===
    for idx, phrase_idx in enumerate(sorted(phrase_windows)):
        phrase_text, start_s, end_s = phrase_windows[phrase_idx]
        duration_s = end_s - start_s

        display_text = phrase_text

        phrase_template = phrase_template_cache.get(display_text)
        if phrase_template is None:
            safe_height = (2 * int(FONT_SIZE * 1.4)) + 80  # Always allow up to 2 lines

            phrase_template = TextClip(
                text=display_text,
                font_size=FONT_SIZE,
                color=TEXT_COLOR,
                font=FONT_BOLD,
                method="caption",
                size=(VIDEO_WIDTH - 320, safe_height),  # Dynamic height based on number of lines
                text_align="center",
                duration=1,
            ).with_position("center")
            phrase_template_cache[display_text] = phrase_template

        progress_template = progress_template_cache.get(phrase_idx)
        if progress_template is None:
            progress_text = f"Phrase {phrase_idx} / {total_phrases}"
            progress_template = TextClip(
                text=progress_text,
                font_size=PROGRESS_FONT_SIZE,
                color="#888888",
                font=FONT_REGULAR,
                method="caption",  # Use caption method with explicit size for better control
                size=(progress_width, progress_height),  # Explicit size prevents cutting
                text_align="right",  # Right-align text within the container
                duration=1,
            ).with_position((progress_x, 40))
            progress_template_cache[phrase_idx] = progress_template

        phrase_clips.append(phrase_template.with_start(start_s).with_duration(duration_s))
        progress_clips.append(progress_template.with_start(start_s).with_duration(duration_s))

        if (idx + 1) % 100 == 0:
            print(f"   📝 Created phrase-level overlays for {idx + 1}/{len(phrase_windows)} phrases")

    text_clips = title_clips + phrase_clips + counter_clips + progress_clips

    print(f"   🔧 Compositing {len(text_clips)} text clips...")
    video = CompositeVideoClip([bg] + text_clips)
    video = video.with_audio(audio)

    print(f"   💾 Rendering to {video_path} (this will take a while)...")
    video.write_videofile(
        video_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate="2000k",
        preset="ultrafast",
        threads=RENDER_THREADS,
        ffmpeg_params=["-tune", "stillimage"],
        logger="bar",
    )

    video.close()
    audio.close()
    bg.close()

    print(f"\n✅ Video saved: {video_path}")
    print(f"   Resolution: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")
    print(f"   Duration: {format_time(total_duration_s)}")
    return video_path


# ============================================================
# MAIN
# ============================================================
async def main():
    global OUTPUT_VIDEO, OUTPUT_AUDIO, TITLE_CARD_TEXT
    print("=" * 60)
    print("  English Phrases - Audio + Subtitled Video Generator")
    print("=" * 60)
    print(f"\n📋 {len(phrases)} phrases to process")
    print(f"🔁 {REPETITIONS} repetitions each")
    est_duration = len(phrases) * REPETITIONS * 6
    print(f"⏱️  Estimated duration: ~{est_duration // 60} minutes")
    
    # Create output directory if specified
    output_dir = OUTPUT_DIR if OUTPUT_DIR else None
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        folder_index = get_output_index(output_dir)
        base_title = TITLE_CARD_TEXT
        safe_title = sanitize_filename(base_title)
        OUTPUT_VIDEO = f"{folder_index}-{safe_title}.mp4"
        OUTPUT_AUDIO = f"{folder_index}-{safe_title}.mp3"
        TITLE_CARD_TEXT = f"{folder_index} - {base_title}"
        print(f"📁 Output directory: {output_dir}")
        print(f"📂 Folder index: {folder_index} (next file: {folder_index}-{safe_title}.mp4)\n")
    else:
        print()

    audio_path, timing, total_ms = await create_audio_with_timing(phrases, output_dir=output_dir)
    video_path = create_video_from_timing(audio_path, timing, total_ms, output_dir=output_dir)

    print("\n" + "=" * 60)
    print("  🎉 DONE!")
    print(f"  📹 Video: {video_path}")
    print(f"  🎵 Audio: {audio_path}")
    print("=" * 60)

    return video_path, audio_path


if __name__ == "__main__":
    video_file, audio_file = asyncio.run(main())
    print(f"\n📂 Files ready:\n   {os.path.abspath(video_file)}\n   {os.path.abspath(audio_file)}")
