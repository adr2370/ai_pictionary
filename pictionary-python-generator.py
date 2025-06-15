import os
import subprocess
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math
import sys
import datetime
import re

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
SCROLL_SPEED = 50  # Increased for faster scrolling
TEXT_PADDING = 30  # Reduced padding between elements
TEXT_BOTTOM_PADDING = 60  # Added padding below text
SCROLL_ANIMATION_FRAMES = 15  # Number of frames for smooth scroll animation
LOADING_DOT_COUNT = 3  # Number of dots in loading animation

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
    
    # Try to find a system font
    for font_dir in font_dirs:
        if os.path.exists(font_dir):
            for font_name in potential_fonts:
                font_path = os.path.join(font_dir, font_name)
                if os.path.exists(font_path):
                    try:
                        # Test if we can actually load the font
                        test_font = ImageFont.truetype(font_path, 20)
                        print(f"Using system font: {font_path}")
                        return font_path
                    except Exception as e:
                        print(f"Could not load font {font_path}: {e}")
                        continue
    
    print("Warning: No system font found. Using PIL's default font.")
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
    
    # If we have the image path, try to composite it
    if 'image' in round_data and os.path.exists(round_data['image']):
        try:
            # Open the round image and resize to fit
            round_img = Image.open(round_data['image']).convert('RGBA')
            img_width, img_height = round_img.size
            
            # Calculate dimensions to fit the screen while maintaining aspect ratio
            ratio = min(VIDEO_WIDTH / img_width, VIDEO_HEIGHT / img_height)
            new_width = int(img_width * ratio)
            new_height = int(img_height * ratio)
            
            # Resize image
            round_img = round_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Adjust opacity if needed
            if opacity < 255:
                alpha = round_img.split()[3]
                alpha = alpha.point(lambda p: p * opacity // 255)
                r, g, b = round_img.split()[:3]
                round_img = Image.merge('RGBA', (r, g, b, alpha))
            
            # Calculate position to center the image
            img_x = int((VIDEO_WIDTH - new_width) // 2)
            img_y = int((VIDEO_HEIGHT - new_height) // 2)
            
            # Paste the image onto the frame
            image.paste(round_img, (img_x, img_y), round_img)
        except Exception as e:
            print(f"Error placing image: {e}")
            # Draw error text in the center
            draw.text((VIDEO_WIDTH//2 - 100, VIDEO_HEIGHT//2), f"Image loading error: {round_data['image']}", 
                      fill=(255, 0, 0, opacity), font=ImageFont.load_default())

def create_drawing_animation(image, progress):
    """Create a drawing animation effect by gradually revealing the image"""
    # Create a mask for the drawing effect
    mask = Image.new('L', image.size, 0)
    draw = ImageDraw.Draw(mask)
    
    # Calculate the number of lines to draw based on progress
    num_lines = int(image.height * progress)
    
    # Draw horizontal lines to create a drawing effect
    for y in range(num_lines):
        draw.line([(0, y), (image.width, y)], fill=255)
    
    # Apply the mask to the image
    result = Image.new('RGBA', image.size, (0, 0, 0, 0))
    result.paste(image, (0, 0), mask)
    return result

def create_loading_indicator(frame, total_frames, dot_count=LOADING_DOT_COUNT):
    """Create an animated loading indicator with dots"""
    # Create a new image for the loading indicator
    loading_img = Image.new('RGBA', (VIDEO_WIDTH, 40), (0, 0, 0, 0))
    draw = ImageDraw.Draw(loading_img)
    
    # Calculate dot positions and animation
    dot_spacing = 20
    total_width = (dot_count - 1) * dot_spacing
    start_x = (VIDEO_WIDTH - total_width) // 2
    
    # Animate dots with a wave effect
    for i in range(dot_count):
        # Calculate dot position
        x = start_x + (i * dot_spacing)
        y = 20  # Center vertically
        
        # Calculate opacity based on animation
        progress = (frame % total_frames) / total_frames
        dot_progress = (progress + (i / dot_count)) % 1.0
        opacity = int(255 * (0.3 + 0.7 * abs(math.sin(dot_progress * math.pi))))
        
        # Draw dot
        draw.ellipse([x-4, y-4, x+4, y+4], fill=(255, 255, 255, opacity))
    
    return loading_img

def create_text_element(text, font_size=140):
    """Create a text element with proper sizing"""
    # Create a new image with transparent background
    text_img = Image.new('RGBA', (VIDEO_WIDTH, 160 + TEXT_BOTTOM_PADDING), (0, 0, 0, 0))  # Added bottom padding
    draw = ImageDraw.Draw(text_img)
    
    # Load font
    font = None
    if FONT_PATH:
        try:
            font = ImageFont.truetype(FONT_PATH, font_size)
        except Exception as e:
            print(f"Error loading specified font: {e}")
    
    if not font:
        try:
            # Try to load a system font
            system_font = get_default_font()
            if system_font:
                font = ImageFont.truetype(system_font, font_size)
            else:
                # If all else fails, use PIL's default font
                font = ImageFont.load_default()
                print("Using PIL's default font - text may appear small")
        except Exception as e:
            print(f"Error loading system font: {e}")
            font = ImageFont.load_default()
    
    # Calculate text size
    try:
        text_width = draw.textlength(text, font=font)
    except:
        text_width = len(text) * font_size * 0.6
    
    # Draw the text
    draw.text(((VIDEO_WIDTH - text_width) // 2, 30),  # Adjusted y offset
              text, fill=(255, 255, 255, 255), font=font)
    
    return text_img

def generate_frames():
    """Generate all frames for the animation"""
    # Calculate timing for each phase
    frames_per_round = int(DURATION * FPS)
    initial_loading = int(frames_per_round * 0.1)    # 10% for initial loading
    text_phase = int(frames_per_round * 0.3)        # 30% for text display
    image_delay = int(frames_per_round * 0.1)       # 10% delay before image
    drawing_phase = int(frames_per_round * 0.4)     # 40% of time for drawing
    transition_phase = int(frames_per_round * 0.1)  # 10% for transition
    
    TOTAL_FRAMES = frames_per_round * TOTAL_ROUNDS
    
    print(f"Creating {TOTAL_FRAMES} frames for {TOTAL_ROUNDS} rounds...")
    
    # Track the scroll position
    current_scroll = 0
    target_scroll = 0
    last_round = -1
    scroll_start = 0
    scroll_frames = 0
    
    for frame in range(TOTAL_FRAMES):
        # Create base image with background
        image = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), BACKGROUND_COLOR)
        
        # Calculate which round we're on and the progress within that round
        current_round = frame // frames_per_round
        round_progress = (frame % frames_per_round) / frames_per_round
        frame_in_round = frame % frames_per_round
        
        # Keep track of visible elements for this frame
        visible_elements = []
        
        # Add elements from all previous rounds and current round
        for round_idx in range(current_round + 1):
            if round_idx < len(all_rounds):
                round_data = all_rounds[round_idx]
                
                # For current round, handle text and image timing
                if round_idx == current_round:
                    # Show initial loading animation
                    if frame_in_round < initial_loading:
                        loading_img = create_loading_indicator(frame, FPS)
                        visible_elements.append({
                            'type': 'loading',
                            'image': loading_img,
                            'y_offset': 0,
                            'opacity': 255
                        })
                    # Show text after initial loading
                    elif frame_in_round >= initial_loading:
                        text = f"{round_data['prompt']}"
                        text_img = create_text_element(text)
                        # Fade in text
                        text_opacity = min(255, int((frame_in_round - initial_loading) / (text_phase * 0.2) * 255))
                        visible_elements.append({
                            'type': 'text',
                            'image': text_img,
                            'y_offset': 0,
                            'opacity': text_opacity
                        })
                    
                    # Show loading indicator during image delay
                    if frame_in_round >= text_phase and frame_in_round < text_phase + image_delay:
                        loading_img = create_loading_indicator(frame, FPS)
                        visible_elements.append({
                            'type': 'loading',
                            'image': loading_img,
                            'y_offset': 0,
                            'opacity': 255
                        })
                    
                    # Show the image only after text delay
                    if frame_in_round >= text_phase + image_delay:
                        if 'image' in round_data and os.path.exists(round_data['image']):
                            try:
                                round_img = Image.open(round_data['image']).convert('RGBA')
                                img_width, img_height = round_img.size
                                
                                ratio = VIDEO_WIDTH / img_width
                                new_width = int(img_width * ratio)
                                new_height = int(img_height * ratio)
                                
                                round_img = round_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                                
                                # Calculate drawing progress
                                drawing_progress = min(1.0, (frame_in_round - (text_phase + image_delay)) / drawing_phase)
                                animated_img = create_drawing_animation(round_img, drawing_progress)
                                visible_elements.append({
                                    'type': 'image',
                                    'image': animated_img,
                                    'y_offset': 0,
                                    'opacity': 255
                                })
                            except Exception as e:
                                print(f"Error processing image: {e}")
                else:
                    # For previous rounds, show both text and image
                    text = f"{round_data['prompt']}"
                    text_img = create_text_element(text)
                    visible_elements.append({
                        'type': 'text',
                        'image': text_img,
                        'y_offset': 0,
                        'opacity': 255
                    })
                    
                    if 'image' in round_data and os.path.exists(round_data['image']):
                        try:
                            round_img = Image.open(round_data['image']).convert('RGBA')
                            img_width, img_height = round_img.size
                            
                            ratio = VIDEO_WIDTH / img_width
                            new_width = int(img_width * ratio)
                            new_height = int(img_height * ratio)
                            
                            round_img = round_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                            visible_elements.append({
                                'type': 'image',
                                'image': round_img,
                                'y_offset': 0,
                                'opacity': 255
                            })
                        except Exception as e:
                            print(f"Error processing image: {e}")
        
        # Calculate total height and handle scrolling
        total_height = sum(elem['image'].height + TEXT_PADDING for elem in visible_elements)
        target_scroll = max(0, total_height - VIDEO_HEIGHT)
        
        if current_round != last_round:
            scroll_start = current_scroll
            scroll_frames = 0
            last_round = current_round
        
        if scroll_frames < SCROLL_ANIMATION_FRAMES:
            scroll_progress = scroll_frames / SCROLL_ANIMATION_FRAMES
            scroll_progress = 1 - (1 - scroll_progress) ** 3
            current_scroll = scroll_start + (target_scroll - scroll_start) * scroll_progress
            scroll_frames += 1
        else:
            current_scroll = target_scroll
        
        # Position elements with smooth scrolling
        current_y = 0
        for elem in visible_elements:
            elem['y_offset'] = current_y - current_scroll
            current_y += elem['image'].height + TEXT_PADDING
        
        # Draw all visible elements
        for elem in visible_elements:
            y_pos = elem['y_offset']
            if y_pos < VIDEO_HEIGHT and y_pos + elem['image'].height > 0:
                if elem['type'] == 'image':
                    if 'opacity' in elem and elem['opacity'] < 255:
                        # Apply opacity to image
                        alpha = elem['image'].split()[3]
                        alpha = alpha.point(lambda p: p * elem['opacity'] // 255)
                        r, g, b = elem['image'].split()[:3]
                        elem['image'] = Image.merge('RGBA', (r, g, b, alpha))
                    image.paste(elem['image'], (0, int(y_pos)), elem['image'])
                else:
                    if 'opacity' in elem and elem['opacity'] < 255:
                        # Apply opacity to text or loading indicator
                        alpha = elem['image'].split()[3]
                        alpha = alpha.point(lambda p: p * elem['opacity'] // 255)
                        r, g, b = elem['image'].split()[:3]
                        elem['image'] = Image.merge('RGBA', (r, g, b, alpha))
                    image.paste(elem['image'], (0, int(y_pos)), elem['image'])
        
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

def read_game_log(game_dir):
    """Read the game log directory and return rounds data"""
    if not os.path.isdir(game_dir):
        print(f"Error: Game directory '{game_dir}' not found!")
        return None
    
    rounds_data = []
    round_files = {}
    
    # First, collect all files and organize them by round number
    for file in os.listdir(game_dir):
        if file.startswith("round_") and file.endswith(".png"):
            round_num = int(file.split("_")[1])
            if round_num not in round_files:
                round_files[round_num] = {}
            round_files[round_num]["image"] = os.path.join(game_dir, file)
        elif file.startswith("round_") and file.endswith("_summary.txt"):
            round_num = int(file.split("_")[1])
            if round_num not in round_files:
                round_files[round_num] = {}
            round_files[round_num]["summary"] = os.path.join(game_dir, file)
    
    # Process each round in order
    for round_num in sorted(round_files.keys()):
        round_data = round_files[round_num]
        if "summary" in round_data and "image" in round_data:
            # Read the summary file to get the prompt
            with open(round_data["summary"], "r") as f:
                summary_content = f.read()
                # Extract the actual word from the summary
                actual_word_match = re.search(r"Actual Word: (.*)", summary_content)
                if actual_word_match:
                    prompt = actual_word_match.group(1).strip()
                    rounds_data.append({
                        "number": round_num,
                        "prompt": prompt,
                        "image": round_data["image"]
                    })
    
    return rounds_data

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate a TikTok video from Pictionary Chain Game images')
    parser.add_argument('--game-dir', '-g', type=str, required=True,
                        help='Directory containing the game log files')
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
    
    # Read game log data
    all_rounds = read_game_log(args.game_dir)
    if not all_rounds:
        print("Failed to read game log data. Please check the game directory path.")
        return
    
    TOTAL_ROUNDS = len(all_rounds)
    print(f"Creating animation with {TOTAL_ROUNDS} rounds")
    
    # Run the generation process
    generate_frames()
    create_video(output_path, args.music)
    cleanup()
    
    print(f"Process completed successfully! Video saved as: {output_path}")

if __name__ == "__main__":
    main()