import os
import subprocess
import argparse
from PIL import Image, ImageDraw, ImageFont
import math
import sys
import datetime

# Create directories
os.makedirs("temp_frames", exist_ok=True)
os.makedirs("temp_assets", exist_ok=True)

# Constants
VIDEO_WIDTH = 1080  # TikTok vertical video width
VIDEO_HEIGHT = 1920  # TikTok vertical video height
BACKGROUND_COLOR = (0, 0, 0)  # Black
TEXT_COLOR = (255, 255, 255)  # White
HIGHLIGHT_COLOR = (255, 255, 0)  # Yellow
GUESS_COLOR = (255, 50, 50)  # Red
DEFAULT_DURATION = 3  # Default duration for each card (seconds)
DEFAULT_FPS = 30  # Default frames per second
FADE_FRAMES = 15  # Number of frames for fade effects

# Font will be determined at runtime
FONT_PATH = None  

# Card dimensions
CARD_WIDTH = VIDEO_WIDTH - 160
CARD_HEIGHT = 800
CARD_PADDING = 40
TITLE_HEIGHT = 150

# Default data from your HTML (will be updated with proper image paths)
rounds_data = [
    {"number": 1, "prompt": "submarine", "image": "round_1_submarine.png", "guess": "Spaceship"},
    {"number": 2, "prompt": "Spaceship", "image": "round_2_spaceship.png", "guess": "Jet plane"},
    {"number": 3, "prompt": "Jet plane", "image": "round_3_jet_plane.png", "guess": "Helicopter"},
    {"number": 4, "prompt": "Helicopter", "image": "round_4_helicopter.png", "guess": "Airplane"},
    {"number": 5, "prompt": "Airplane", "image": "round_5_airplane.png", "guess": "Bird"},
    {"number": 6, "prompt": "Bird", "image": "round_6_bird.png", "guess": "Penguin"},
    {"number": 7, "prompt": "Penguin", "image": "round_7_penguin.png", "guess": "Owl"},
    {"number": 8, "prompt": "Owl", "image": "round_8_owl.png", "guess": "Penguin"},
    {"number": 9, "prompt": "Penguin", "image": "round_9_penguin.png", "guess": "Crow"},
    {"number": 10, "prompt": "Crow", "image": "round_10_crow.png", "guess": "Raven"},
]

# These will be initialized in main() based on command line arguments
all_rounds = []
TOTAL_ROUNDS = 0
DURATION = DEFAULT_DURATION
FPS = DEFAULT_FPS

# Get a system font that should be available
def get_default_font():
    """Find a default system font that's available"""
    # Try common fonts available on different systems
    potential_fonts = [
        "Arial.ttf",
        "DejaVuSans.ttf",
        "FreeSans.ttf",
        "LiberationSans-Regular.ttf",
        "Helvetica.ttf",
        "Verdana.ttf",
        "Tahoma.ttf",
        "Segoe UI.ttf"
    ]
    
    # Look in common font directories by platform
    if sys.platform.startswith('win'):
        font_dirs = [
            os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
        ]
    elif sys.platform.startswith('darwin'):  # macOS
        font_dirs = [
            '/Library/Fonts',
            '/System/Library/Fonts',
            os.path.expanduser('~/Library/Fonts')
        ]
    else:  # Linux and others
        font_dirs = [
            '/usr/share/fonts',
            '/usr/local/share/fonts',
            os.path.expanduser('~/.fonts')
        ]
    
    # Check for PIL's default font
    try:
        # This will use PIL's default font if available
        default_font = ImageFont.load_default()
        print("Using PIL's default font")
        return default_font
    except:
        pass
    
    # Try to find a system font
    for font_dir in font_dirs:
        if os.path.exists(font_dir):
            for font_name in potential_fonts:
                font_path = os.path.join(font_dir, font_name)
                if os.path.exists(font_path):
                    print(f"Using system font: {font_path}")
                    return font_path
    
    # If no font found, use a simple fallback approach
    print("Warning: No system font found. Using a simplified approach.")
    return None

def update_image_paths(image_dir):
    """Update image paths in rounds_data to use the specified directory"""
    global rounds_data
    
    # Verify directory exists
    if not os.path.isdir(image_dir):
        print(f"Error: Directory '{image_dir}' not found!")
        return False
    
    print(f"Looking for images in: {image_dir}")
    
    # Get all files in the directory
    all_files = os.listdir(image_dir)
    
    # Check for each round and find matching images
    for round_data in rounds_data:
        round_num = round_data["number"]
        pattern = f"round_{round_num}_"
        
        # Find all files that start with the pattern
        matching_files = [f for f in all_files if f.lower().startswith(pattern.lower())]
        
        if matching_files:
            # Use the first matching file
            image_name = matching_files[0]
            full_path = os.path.join(image_dir, image_name)
            round_data["image"] = full_path
            print(f"Found image for round {round_num}: {image_name}")
        else:
            print(f"Warning: No image found for round {round_num} (pattern: {pattern}*)")
            # Keep the original filename as a fallback, but it likely won't be found
    
    return True

def create_title_text(draw, font, y_offset=0):
    """Draw the title at the top of the frame"""
    # Use provided font or load default if None
    if font is None:
        if FONT_PATH:
            try:
                title_font = ImageFont.truetype(FONT_PATH, 80)
            except:
                # If truetype fails, use default
                title_font = ImageFont.load_default()
        else:
            title_font = ImageFont.load_default()
    else:
        title_font = font
        
    title_text = "Pictionary Chain Game"
    
    # Get text size - handle different PIL versions
    try:
        title_width, title_height = draw.textsize(title_text, font=title_font)
    except AttributeError:
        # For newer PIL versions
        try:
            title_width, title_height = draw.textbbox((0, 0), title_text, font=title_font)[2:]
        except:
            # Fallback to an approximate size
            title_width, title_height = len(title_text) * 40, 80
    
    draw.text(((VIDEO_WIDTH - title_width) // 2, 50 + y_offset), 
              title_text, fill=TEXT_COLOR, font=title_font)
    return title_height + 50

def draw_card(image, round_data, y_position, opacity=255):
    """Draw a single round card at the specified y position with given opacity"""
    draw = ImageDraw.Draw(image, 'RGBA')
    
    # Card background (rounded rectangle)
    card_color = (40, 40, 40, opacity)
    card_x = 80
    card_y = y_position
    
    # Draw card background with opacity
    draw.rectangle([card_x, card_y, card_x + CARD_WIDTH, card_y + CARD_HEIGHT], 
                  fill=card_color, outline=(80, 80, 80, opacity), width=3)
    
    # Prepare fonts (handling potential font errors)
    try:
        if FONT_PATH:
            round_font = ImageFont.truetype(FONT_PATH, 60)
            prompt_font = ImageFont.truetype(FONT_PATH, 50)
            guess_label_font = ImageFont.truetype(FONT_PATH, 50)
            guess_font = ImageFont.truetype(FONT_PATH, 70)
        else:
            # Use default font with different sizes
            round_font = ImageFont.load_default()
            prompt_font = ImageFont.load_default()
            guess_label_font = ImageFont.load_default()
            guess_font = ImageFont.load_default()
    except:
        # Fallback to default font if any error occurs
        round_font = ImageFont.load_default()
        prompt_font = ImageFont.load_default()
        guess_label_font = ImageFont.load_default()
        guess_font = ImageFont.load_default()
    
    # Draw round number
    draw.text((card_x + 30, card_y + 30), f"Round {round_data['number']}", 
              fill=(255, 255, 255, opacity), font=round_font)
    
    # Draw prompt
    prompt_text = f"Prompt: \"{round_data['prompt']}\""
    draw.text((card_x + 30, card_y + 120), prompt_text, 
              fill=(HIGHLIGHT_COLOR[0], HIGHLIGHT_COLOR[1], HIGHLIGHT_COLOR[2], opacity), font=prompt_font)
    
    # Place for image (centered)
    image_box_top = card_y + 200
    image_box_height = 350
    
    # Draw image placeholder (would be replaced with actual image)
    draw.rectangle([card_x + 30, image_box_top, card_x + CARD_WIDTH - 30, image_box_top + image_box_height], 
                  fill=(20, 20, 20, opacity), outline=(60, 60, 60, opacity), width=2)
    
    # If we have the image path, try to composite it
    if 'image' in round_data and os.path.exists(round_data['image']):
        try:
            # Open the round image and resize to fit
            round_img = Image.open(round_data['image']).convert('RGBA')
            img_width, img_height = round_img.size
            
            # Calculate dimensions to fit in the box while maintaining aspect ratio
            img_box_width = CARD_WIDTH - 60
            ratio = min(img_box_width / img_width, image_box_height / img_height)
            new_width = int(img_width * ratio)
            new_height = int(img_height * ratio)
            
            # Resize image - ensure integer values for size
            round_img = round_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Adjust opacity if needed
            if opacity < 255:
                alpha = round_img.split()[3]
                alpha = alpha.point(lambda p: p * opacity // 255)
                r, g, b = round_img.split()[:3]
                round_img = Image.merge('RGBA', (r, g, b, alpha))
            
            # Calculate position to center the image in the box - ensure integers
            img_x = int(card_x + 30 + (img_box_width - new_width) // 2)
            img_y = int(image_box_top + (image_box_height - new_height) // 2)
            
            # Paste the image onto the frame
            image.paste(round_img, (img_x, img_y), round_img)
        except Exception as e:
            print(f"Error placing image: {e}")
            # Draw error text in the image box
            draw.text((card_x + 50, image_box_top + 50), f"Image loading error: {round_data['image']}", 
                      fill=(255, 0, 0, opacity), font=prompt_font)
    
    # Draw AI's guess
    draw.text((card_x + 30, card_y + CARD_HEIGHT - 150), "AI's wrong guess:", 
              fill=(GUESS_COLOR[0], GUESS_COLOR[1], GUESS_COLOR[2], opacity), font=guess_label_font)
    
    draw.text((card_x + 30, card_y + CARD_HEIGHT - 90), f"\"{round_data['guess']}\"", 
              fill=(255, 255, 255, opacity), font=guess_font)

def generate_frames():
    """Generate all frames for the animation"""
    # Calculate total content height for scrolling
    TOTAL_CONTENT_HEIGHT = TITLE_HEIGHT + (CARD_HEIGHT + CARD_PADDING) * TOTAL_ROUNDS
    TOTAL_FRAMES = DURATION * FPS * TOTAL_ROUNDS
    
    print(f"Creating {TOTAL_FRAMES} frames for {TOTAL_ROUNDS} rounds...")
    
    current_frame = 0
    
    # Calculate how much to scroll per frame for smooth scrolling
    scroll_per_frame = TOTAL_CONTENT_HEIGHT / TOTAL_FRAMES
    
    for frame in range(TOTAL_FRAMES):
        # Create base image with background
        image = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), BACKGROUND_COLOR)
        draw = ImageDraw.Draw(image)
        
        # Calculate current scroll position
        scroll_y = frame * scroll_per_frame
        
        # Draw title (fixed position)
        title_y = max(0, scroll_y)
        if title_y < VIDEO_HEIGHT:  # Only draw if visible
            create_title_text(draw, None, -title_y)
        
        # Determine which rounds are visible
        start_y = TITLE_HEIGHT - scroll_y + CARD_PADDING
        
        for i, round_data in enumerate(all_rounds):
            card_y = start_y + i * (CARD_HEIGHT + CARD_PADDING)
            
            # Only draw cards partially or fully visible
            if card_y + CARD_HEIGHT > 0 and card_y < VIDEO_HEIGHT:
                # Calculate fade effect for cards entering/exiting screen
                opacity = 255
                if card_y < 100:
                    # Fading in from top
                    opacity = int(255 * (card_y + CARD_HEIGHT) / 200)
                elif card_y + CARD_HEIGHT > VIDEO_HEIGHT - 100:
                    # Fading out at bottom
                    opacity = int(255 * (VIDEO_HEIGHT - card_y) / 200)
                
                opacity = max(0, min(255, opacity))
                draw_card(image, round_data, card_y, opacity)
        
        # Add frame counter for tracking (using default font)
        try:
            counter_font = ImageFont.load_default()
            draw.text((10, 10), f"Frame: {frame}/{TOTAL_FRAMES}", fill=(128, 128, 128), font=counter_font)
        except:
            # Skip counter if font fails
            pass
        
        # Save the frame
        frame_path = f"temp_frames/frame_{frame:05d}.png"
        image.save(frame_path)
        
        # Progress indicator
        if frame % 30 == 0 or frame == TOTAL_FRAMES - 1:
            completion = (frame + 1) / TOTAL_FRAMES * 100
            print(f"Generated frame {frame+1}/{TOTAL_FRAMES} ({completion:.1f}%)")

def create_video(output_file="pictionary_chain.mp4", music_file=None):
    """Combine frames into a video using ffmpeg"""
    print("Creating video from frames...")
    
    # Create a temporary file list for ffmpeg
    frame_list_path = "temp_frames/frames.txt"
    with open(frame_list_path, "w") as f:
        # Get all frame files and sort them numerically
        frame_files = sorted([file for file in os.listdir("temp_frames") if file.startswith("frame_") and file.endswith(".png")])
        for frame_file in frame_files:
            # Use file prefix syntax instead of glob pattern
            f.write(f"file '{os.path.join(frame_file)}'\n")
    
    try:
        # Try primary approach with concat demuxer
        print("Attempting to create video using concat demuxer...")
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-r", str(FPS),  # Input frame rate
            "-f", "concat",
            "-safe", "0",
            "-i", frame_list_path,
            "-vsync", "vfr",  # Variable frame rate handling
            "-avoid_negative_ts", "make_zero",  # Avoid negative timestamps
            "-c:v", "libx264", 
            "-pix_fmt", "yuv420p",
            "-crf", "23",
            "-preset", "medium",
            output_file
        ]
        
        # Run ffmpeg command
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        # Check if there was an error
        if result.returncode != 0:
            print(f"Warning: First approach failed with error: {result.stderr}")
            print("Trying alternative approach...")
            
            # Alternative approach using direct pattern matching
            alt_ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-framerate", str(FPS),
                "-i", "temp_frames/frame_%05d.png",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "23", 
                "-preset", "medium",
                output_file
            ]
            subprocess.run(alt_ffmpeg_cmd)
        
        print(f"Video created: {output_file}")
        
    except Exception as e:
        print(f"Error creating video: {e}")
        print("Trying alternative approach...")
        
        # Fallback to simpler approach
        alt_ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", "temp_frames/frame_%05d.png",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "23", 
            "-preset", "medium",
            output_file
        ]
        subprocess.run(alt_ffmpeg_cmd)
        print(f"Video created: {output_file}")
    
    # Add music if specified
    if music_file and os.path.exists(music_file):
        print(f"Adding background music from {music_file}...")
        audio_output = os.path.splitext(output_file)[0] + "_with_audio.mp4"
        
        ffmpeg_audio_cmd = [
            "ffmpeg", "-y",
            "-i", output_file,
            "-i", music_file,
            "-map", "0:v", 
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            audio_output
        ]
        subprocess.run(ffmpeg_audio_cmd)
        print(f"Video with audio created: {audio_output}")

def cleanup():
    """Remove temporary files"""
    print("Cleaning up temporary files...")
    try:
        import shutil
        # Attempt to clean up the frame files
        for file in os.listdir("temp_frames"):
            try:
                os.remove(os.path.join("temp_frames", file))
            except:
                pass
        
        # Try to remove the directories
        try:
            shutil.rmtree("temp_frames", ignore_errors=True)
        except:
            pass
        try:
            shutil.rmtree("temp_assets", ignore_errors=True)
        except:
            pass
    except Exception as e:
        print(f"Note: Some temporary files may remain. Manual cleanup recommended. Error: {e}")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate a TikTok video from Pictionary Chain Game images')
    parser.add_argument('--image-dir', '-i', type=str, default='.',
                        help='Directory containing the image files (default: current directory)')
    parser.add_argument('--duration', '-d', type=float, default=DEFAULT_DURATION,
                        help=f'Duration for each round in seconds (default: {DEFAULT_DURATION})')
    parser.add_argument('--fps', '-f', type=int, default=DEFAULT_FPS,
                        help=f'Frames per second (default: {DEFAULT_FPS})')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output video filename (default: auto-generated with timestamp)')
    parser.add_argument('--music', '-m', type=str, default=None,
                        help='Background music file (optional)')
    parser.add_argument('--font', type=str, default=None,
                        help='Path to a font file to use (optional, will use system font if not specified)')
    
    args = parser.parse_args()
    
    # Create videos directory if it doesn't exist
    videos_dir = "videos"
    os.makedirs(videos_dir, exist_ok=True)
    
    # Generate a unique filename with timestamp if not specified
    if args.output is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"pictionary_chain_{timestamp}.mp4"
        output_path = os.path.join(videos_dir, output_filename)
    else:
        # If output was specified, still put it in the videos directory
        output_path = os.path.join(videos_dir, args.output)
    
    # Update global variables based on arguments
    global DURATION, FPS, all_rounds, TOTAL_ROUNDS, FONT_PATH
    DURATION = args.duration
    FPS = args.fps
    
    # Set font path if provided
    if args.font and os.path.exists(args.font):
        FONT_PATH = args.font
        print(f"Using specified font: {FONT_PATH}")
    else:
        # Try to find a system font
        FONT_PATH = get_default_font()
    
    print("Starting Pictionary Chain TikTok Generator")
    
    # Update image paths
    if not update_image_paths(args.image_dir):
        print("Failed to find images. Please check the directory path.")
        return
    
    all_rounds = rounds_data
    TOTAL_ROUNDS = len(all_rounds)
    print(f"Creating animation with {TOTAL_ROUNDS} rounds")
    
    # Run the generation process
    generate_frames()
    create_video(output_path, args.music)
    cleanup()
    
    print(f"Process completed successfully! Video saved as: {output_path}")

if __name__ == "__main__":
    main()