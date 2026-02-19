import os
from moviepy import VideoFileClip, concatenate_videoclips

# 1. Set the directory where your videos are stored
folder_path = "output"
output_filename = "joined_video.mp4"

# 2. Get all video files and sort them (important for chunk1, chunk2, etc.)
files = [f for f in os.listdir(folder_path) if f.endswith(('.mp4', '.mov', '.avi'))]
files.sort()  # This ensures chunk1 comes before chunk2

# 3. Load the video clips
clips = [VideoFileClip(os.path.join(folder_path, f)) for f in files]

# 4. Concatenate (stitch) them together
final_clip = concatenate_videoclips(clips)

# 5. Write the result to a file
output_path = os.path.join(folder_path, output_filename)
print(f"📹 Merging {len(clips)} video files...")
print(f"   Files: {', '.join(files)}")
print(f"   Output: {output_path}")
final_clip.write_videofile(
    output_path,
    codec="libx264",
    audio_codec="aac",
    bitrate="2000k",
    preset="medium",
    threads=4,
    logger="bar",
)

print(f"\n✅ Video merging complete! Output saved to: {output_path}")
final_clip.close()
for clip in clips:
    clip.close()