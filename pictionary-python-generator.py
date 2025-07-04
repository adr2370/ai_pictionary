import os
import subprocess
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math
import sys
import datetime
import re
import random
from collections import deque
import tempfile
import shutil

# Create directories
os.makedirs("temp_frames", exist_ok=True)
os.makedirs("temp_assets", exist_ok=True)

# Constants
VIDEO_WIDTH = 1080  # TikTok vertical video width
VIDEO_HEIGHT = 1920  # TikTok vertical video height
BACKGROUND_COLOR = (255, 255, 255)  # White
TEXT_COLOR = (33, 33, 33)  # Dark gray, almost black
HIGHLIGHT_COLOR = (0, 120, 212)  # Blue
GUESS_COLOR = (220, 53, 69)  # Red
DEFAULT_DURATION = 3  # Default duration for each card (seconds)
DEFAULT_FPS = 30  # Default frames per second
FADE_FRAMES = 15  # Number of frames for fade effects
SCROLL_SPEED = 50  # Increased for faster scrolling
TEXT_PADDING = 30  # Reduced padding between elements
SCROLL_ANIMATION_FRAMES = 15  # Number of frames for smooth scroll animation
LOADING_DOT_COUNT = 3  # Number of dots in loading animation
LOADING_EXTRA_PADDING = 24  # Extra vertical space above loading indicator if not first

# Font will be determined at runtime
FONT_PATH = None  

# Card dimensions
CARD_WIDTH = VIDEO_WIDTH - 160
CARD_HEIGHT = 800
CARD_PADDING = 40
TITLE_HEIGHT = 150

# Bottom padding for all content
BOTTOM_PADDING = 90

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

def get_default_font(bold=False):
    """Find a default system font that's available. If bold=True, prefer bold fonts."""
    # Try common fonts available on different systems
    if bold:
        potential_fonts = [
            "Arialbd.ttf", "arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "Verdana Bold.ttf", "Tahoma Bold.ttf", "SegoeUIBold.ttf", "segoeuib.ttf", "Calibri Bold.ttf", "calibrib.ttf"
        ]
    else:
        potential_fonts = [
            "Arial.ttf", "DejaVuSans.ttf", "FreeSans.ttf", "LiberationSans-Regular.ttf", "Helvetica.ttf", "Verdana.ttf", "Tahoma.ttf", "Segoe UI.ttf"
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

def create_title_text(draw, font, part_number=None, extra_bold=False, bottom_padding=120):
    """Draw the title at the bottom: 'The World's Longest Game of Pictionary' (wrapped), extra bold, black, large, with optional part number as last line."""
    base_title = "The World's Longest Game of Pictionary"
    if part_number is not None:
        base_title += f" Part {part_number}"
    title_font_path = FONT_PATH if FONT_PATH else get_default_font(bold=True)
    try:
        title_font = ImageFont.truetype(title_font_path, 120) if title_font_path else ImageFont.load_default()
    except Exception:
        title_font = ImageFont.load_default()
    max_width = VIDEO_WIDTH - 80
    words = base_title.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        bbox = draw.textbbox((0, 0), test_line, font=title_font)
        w = bbox[2] - bbox[0]
        if w > max_width and current_line:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)
    bbox = draw.textbbox((0, 0), 'A', font=title_font)
    line_height = (bbox[3] - bbox[1]) + 24  # Increased line spacing
    total_height = line_height * len(lines)
    y = VIDEO_HEIGHT - total_height - bottom_padding
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        w = bbox[2] - bbox[0]
        # Simulate extra bold by drawing text multiple times with slight offsets
        for dx in [-2, -1, 0, 1, 2]:
            for dy in [-2, -1, 0, 1, 2]:
                draw.text(((VIDEO_WIDTH - w) // 2 + dx, y + dy), line, fill=(0,0,0), font=title_font)
        y += line_height
    return VIDEO_HEIGHT - bottom_padding

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

def extract_black_strokes(image, threshold=80):
    """Return a list of strokes, each stroke is a list of (x, y) pixels."""
    gray = image.convert('L')
    pixels = gray.load()
    width, height = image.size
    visited = [[False] * height for _ in range(width)]
    strokes = []

    for y in range(height):
        for x in range(width):
            if not visited[x][y] and pixels[x, y] < threshold:
                # Start a new stroke
                stroke = []
                queue = deque()
                queue.append((x, y))
                visited[x][y] = True
                while queue:
                    cx, cy = queue.popleft()
                    stroke.append((cx, cy))
                    # Check 8 neighbors
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            if dx == 0 and dy == 0:
                                continue
                            nx, ny = cx + dx, cy + dy
                            if (0 <= nx < width and 0 <= ny < height and
                                not visited[nx][ny] and pixels[nx, ny] < threshold):
                                visited[nx][ny] = True
                                queue.append((nx, ny))
                strokes.append(stroke)
    return strokes

def create_drawing_animation(image, progress, strokes_cache=None, image_path=None):
    """
    Animate black strokes being drawn from one end to the other, with all strokes finishing by the end of the drawing phase.
    """
    if strokes_cache is None:
        strokes_cache = {}
    cache_key = (image_path, image.size) if image_path else (None, image.size)
    if cache_key not in strokes_cache:
        strokes = extract_black_strokes(image)
        strokes.sort(key=len, reverse=True)  # Sort by number of points, longest first
        stroke_duration = 0.2  # Each stroke takes 20% of the drawing phase to draw
        stroke_timings = []
        if len(strokes) > 1:
            for i, stroke in enumerate(strokes):
                start = i / len(strokes)
                end = 1.0
                if i % 2 == 1:
                    stroke = list(reversed(stroke))
                stroke_timings.append((stroke, start, end))
        else:
            # Only one stroke
            stroke_timings.append((strokes[0], 0.0, 1.0))
        strokes_cache[cache_key] = stroke_timings
    else:
        stroke_timings = strokes_cache[cache_key]

    result = Image.new('RGBA', image.size, (0, 0, 0, 0))
    for stroke, start, end in stroke_timings:
        if progress >= end:
            for x, y in stroke:
                result.putpixel((x, y), (0, 0, 0, 255))
        elif progress > start:
            local_progress = (progress - start) / (end - start)
            reveal_count = int(len(stroke) * local_progress)
            for x, y in stroke[:reveal_count]:
                result.putpixel((x, y), (0, 0, 0, 255))
        # else: not started yet
    return result

def create_loading_indicator(frame, total_frames, dot_count=LOADING_DOT_COUNT, mode='analyzing'):
    """Create a matrix/code style loading indicator with animated pattern and left-aligned text, so the prefix stays fixed. Mode can be 'analyzing' or 'generating'."""
    chars = ['█', '▓', '▒', '░']
    LOADING_HEIGHT = 160
    FONT_SIZE = 80
    LEFT_MARGIN = 60
    PATTERN_LEN = 8
    loading_img = Image.new('RGBA', (VIDEO_WIDTH, LOADING_HEIGHT), (255, 255, 255, 255))
    draw = ImageDraw.Draw(loading_img)
    random.seed(frame // 6)
    pattern = ''.join(random.choices(chars, k=PATTERN_LEN))
    if mode == 'generating':
        text_prefix = "Generating: ["
    else:
        text_prefix = "Analyzing: ["
    text_suffix = "]"
    font_path = FONT_PATH if FONT_PATH else get_default_font()
    try:
        font = ImageFont.truetype(font_path, FONT_SIZE) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    prefix_bbox = draw.textbbox((0, 0), text_prefix, font=font)
    prefix_width = prefix_bbox[2] - prefix_bbox[0]
    text_y = 20 + (LOADING_HEIGHT - 40 - (prefix_bbox[3] - prefix_bbox[1])) // 2
    draw.text((LEFT_MARGIN, text_y), text_prefix, fill=TEXT_COLOR, font=font)
    pattern_x = LEFT_MARGIN + prefix_width
    draw.text((pattern_x, text_y), pattern, fill=TEXT_COLOR, font=font)
    pattern_bbox = draw.textbbox((0, 0), pattern, font=font)
    pattern_width = pattern_bbox[2] - pattern_bbox[0]
    suffix_x = pattern_x + pattern_width
    draw.text((suffix_x, text_y), text_suffix, fill=TEXT_COLOR, font=font)
    return loading_img

def create_text_element(text, font_size=140):
    """Create a text element with proper sizing and wrapping, using bold black font."""
    # Use bold font
    font_path = FONT_PATH if FONT_PATH else get_default_font(bold=True)
    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    # Wrap text
    max_width = VIDEO_WIDTH - 80
    words = text.split()
    lines = []
    current_line = ""
    dummy_img = Image.new('RGBA', (VIDEO_WIDTH, 10), (0,0,0,0))
    draw = ImageDraw.Draw(dummy_img)
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if w > max_width and current_line:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)
    # Calculate total height
    bbox = draw.textbbox((0, 0), 'A', font=font)
    line_height = (bbox[3] - bbox[1]) + 10
    EXTRA_BOTTOM_PADDING = 30  # Increased bottom padding for more space under words
    total_height = line_height * len(lines) + 40 + EXTRA_BOTTOM_PADDING
    text_img = Image.new('RGBA', (VIDEO_WIDTH, total_height), (0,0,0,0))
    draw = ImageDraw.Draw(text_img)
    y = 20
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((VIDEO_WIDTH - w) // 2, y), line, fill=(0,0,0,255), font=font)
        y += line_height
    return text_img

def get_intro_overlay(intro_text, frame_idx, num_frames=45):
    """Return an RGBA overlay image with the intro text for the given frame index (for fade in/out)."""
    font_size = 90
    if FONT_PATH:
        try:
            font = ImageFont.truetype(FONT_PATH, font_size)
        except Exception:
            font = ImageFont.load_default()
    else:
        font = ImageFont.load_default()
    # Animate opacity (fade in and out)
    if frame_idx < num_frames // 3:
        opacity = int(255 * (frame_idx / (num_frames // 3)))
    elif frame_idx > 2 * num_frames // 3:
        opacity = int(255 * ((num_frames - frame_idx) / (num_frames // 3)))
    else:
        opacity = 255
    # Draw text centered
    dummy_img = Image.new('RGBA', (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy_img)
    bbox = draw.textbbox((0, 0), intro_text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    text_img = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    text_draw = ImageDraw.Draw(text_img)
    text_draw.text((0, 0), intro_text, font=font, fill=(*HIGHLIGHT_COLOR, opacity))
    dummy_img.paste(text_img, ((VIDEO_WIDTH - w) // 2, (VIDEO_HEIGHT - h) // 2), text_img)
    return dummy_img

def create_audio_track(total_frames, fps, rounds, initial_loading, text_phase, image_delay, drawing_phase, frames_per_round, thinking_file, drawing_file, output_audio):
    """
    Create an audio track that alternates between thinking_file and drawing_file
    according to the phase timing for each round, with silence for non-music phases.
    """
    temp_dir = tempfile.mkdtemp()
    segment_files = []
    for i, round_data in enumerate(rounds):
        round_start = i * frames_per_round
        if i == 0:
            # Round 0: word only, then generating, then drawing, then reveal
            GENERATE_DELAY_FRAMES = int(frames_per_round * 0.18)
            image_delay = int(frames_per_round * 0.18)
            drawing_phase = int(frames_per_round * 0.4)
            # 1. Word only (no music)
            if GENERATE_DELAY_FRAMES > 0:
                silence1 = os.path.join(temp_dir, f"r0_silence1.wav")
                os.system(f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t {GENERATE_DELAY_FRAMES / fps} "{silence1}"')
                segment_files.append(silence1)
            # 2. Generating (thinking.flac)
            if image_delay > 0:
                gen = os.path.join(temp_dir, f"r0_gen.wav")
                os.system(f'ffmpeg -y -t {image_delay / fps} -i "{thinking_file}" -af "volume=0.5,apad=pad_dur={image_delay / fps}" -acodec pcm_s16le "{gen}"')
                segment_files.append(gen)
            # 3. Drawing (drawing.mp3)
            if drawing_phase > 0:
                draw = os.path.join(temp_dir, f"r0_draw.wav")
                os.system(f'ffmpeg -y -t {drawing_phase / fps} -i "{drawing_file}" -af "apad=pad_dur={drawing_phase / fps}" -acodec pcm_s16le "{draw}"')
                segment_files.append(draw)
            # 4. Reveal (rest, silence)
            reveal_frames = frames_per_round - (GENERATE_DELAY_FRAMES + image_delay + drawing_phase)
            if reveal_frames > 0:
                silence2 = os.path.join(temp_dir, f"r0_silence2.wav")
                os.system(f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t {reveal_frames / fps} "{silence2}"')
                segment_files.append(silence2)
        else:
            # Round 1+: analyzing, word, generating, drawing, reveal
            initial_loading = int(frames_per_round * 0.18)
            text_phase = int(frames_per_round * 0.26)
            image_delay = int(frames_per_round * 0.18)
            drawing_phase = int(frames_per_round * 0.4)
            # 1. Analyzing (thinking.flac)
            if initial_loading > 0:
                ana = os.path.join(temp_dir, f"r{i}_ana.wav")
                os.system(f'ffmpeg -y -t {initial_loading / fps} -i "{thinking_file}" -af "volume=0.5,apad=pad_dur={initial_loading / fps}" -acodec pcm_s16le "{ana}"')
                segment_files.append(ana)
            # 2. Word only (silence)
            if text_phase > 0:
                silence1 = os.path.join(temp_dir, f"r{i}_silence1.wav")
                os.system(f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t {text_phase / fps} "{silence1}"')
                segment_files.append(silence1)
            # 3. Generating (thinking.flac)
            if image_delay > 0:
                gen = os.path.join(temp_dir, f"r{i}_gen.wav")
                os.system(f'ffmpeg -y -t {image_delay / fps} -i "{thinking_file}" -af "volume=0.5,apad=pad_dur={image_delay / fps}" -acodec pcm_s16le "{gen}"')
                segment_files.append(gen)
            # 4. Drawing (drawing.mp3)
            if drawing_phase > 0:
                draw = os.path.join(temp_dir, f"r{i}_draw.wav")
                os.system(f'ffmpeg -y -t {drawing_phase / fps} -i "{drawing_file}" -af "apad=pad_dur={drawing_phase / fps}" -acodec pcm_s16le "{draw}"')
                segment_files.append(draw)
            # 5. Reveal (rest, silence)
            reveal_frames = frames_per_round - (initial_loading + text_phase + image_delay + drawing_phase)
            if reveal_frames > 0:
                silence2 = os.path.join(temp_dir, f"r{i}_silence2.wav")
                os.system(f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t {reveal_frames / fps} "{silence2}"')
                segment_files.append(silence2)
    # Concatenate all segments
    concat_file = os.path.join(temp_dir, "concat.txt")
    with open(concat_file, "w") as f:
        for seg in segment_files:
            f.write(f"file '{seg}'\n")
    os.system(f'ffmpeg -y -f concat -safe 0 -i "{concat_file}" -c copy "{output_audio}"')
    shutil.rmtree(temp_dir)

def generate_frames(part_number=None):
    """Generate all frames for the animation, passing part_number to title."""
    intro_text = None
    intro_overlay_frames = 0
    frames_per_round = int(DURATION * FPS)
    initial_loading = int(frames_per_round * 0.18)  # Increased loading duration
    text_phase = int(frames_per_round * 0.26)       # Slightly reduced text phase
    image_delay = int(frames_per_round * 0.18)      # Increased image delay
    drawing_phase = int(frames_per_round * 0.4)
    transition_phase = int(frames_per_round * 0.1)
    TOTAL_FRAMES = frames_per_round * TOTAL_ROUNDS
    print(f"Creating {TOTAL_FRAMES} frames for {TOTAL_ROUNDS} rounds...")
    current_scroll = 0
    target_scroll = 0
    last_round = -1
    scroll_start = 0
    scroll_frames = 0
    title_duration_frames = int(3 * FPS)
    for frame in range(TOTAL_FRAMES):
        image = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), BACKGROUND_COLOR)
        draw = ImageDraw.Draw(image)
        # Only show the title for the first 3 seconds
        if frame < title_duration_frames:
            create_title_text(draw, None, part_number=part_number, extra_bold=True, bottom_padding=120)
        
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
                    if current_round == 0:
                        # For the first round, show the word immediately, no loading indicator
                        text = f"{round_data['prompt']}"
                        text_img = create_text_element(text)
                        # Only add the word once per frame
                        word_added = False
                        # Add a short delay before showing the 'Generating' loading indicator for the image
                        GENERATE_DELAY_FRAMES = int(frames_per_round * 0.18)
                        if frame_in_round < GENERATE_DELAY_FRAMES:
                            visible_elements.append({
                                'type': 'text',
                                'image': text_img,
                                'y_offset': 0,
                                'opacity': 255
                            })
                            word_added = True
                        if frame_in_round >= GENERATE_DELAY_FRAMES and frame_in_round < GENERATE_DELAY_FRAMES + image_delay:
                            visible_elements.append({
                                'type': 'text',
                                'image': text_img,
                                'y_offset': 0,
                                'opacity': 255
                            })
                            loading_img = create_loading_indicator(frame, FPS, mode='generating')
                            visible_elements.append({
                                'type': 'loading',
                                'image': loading_img,
                                'y_offset': 0,
                                'opacity': 255
                            })
                            word_added = True
                        if frame_in_round >= GENERATE_DELAY_FRAMES + image_delay and frame_in_round < GENERATE_DELAY_FRAMES + image_delay + drawing_phase:
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
                                    drawing_progress = min(1.0, max(0.0, (frame_in_round - (GENERATE_DELAY_FRAMES + image_delay)) / drawing_phase))
                                    animated_img = create_drawing_animation(round_img, drawing_progress, image_path=round_data['image'])
                                    visible_elements.append({
                                        'type': 'image',
                                        'image': animated_img,
                                        'y_offset': 0,
                                        'opacity': 255,
                                        'drawing_progress': drawing_progress
                                    })
                                except Exception as e:
                                    print(f"Error processing image: {e}")
                            word_added = True
                        if frame_in_round >= GENERATE_DELAY_FRAMES + image_delay + drawing_phase:
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
                            word_added = True
                    else:
                        # Show initial loading animation for the word
                        if frame_in_round < initial_loading:
                            loading_img = create_loading_indicator(frame, FPS, mode='analyzing')
                            visible_elements.append({
                                'type': 'loading',
                                'image': loading_img,
                                'y_offset': 0,
                                'opacity': 255
                            })
                        # Show text after initial_loading
                        elif frame_in_round >= initial_loading and frame_in_round < initial_loading + text_phase:
                            text = f"{round_data['prompt']}"
                            text_img = create_text_element(text)
                            text_opacity = min(255, int((frame_in_round - initial_loading) / (text_phase * 0.2) * 255))
                            visible_elements.append({
                                'type': 'text',
                                'image': text_img,
                                'y_offset': 0,
                                'opacity': text_opacity
                            })
                        # Show loading indicator for the image (short, only during image_delay), but keep the word visible above
                        if frame_in_round >= initial_loading + text_phase and frame_in_round < initial_loading + text_phase + image_delay:
                            # Ensure the word is visible above the loading indicator
                            text = f"{round_data['prompt']}"
                            text_img = create_text_element(text)
                            visible_elements.append({
                                'type': 'text',
                                'image': text_img,
                                'y_offset': 0,
                                'opacity': 255
                            })
                            loading_img = create_loading_indicator(frame, FPS, mode='generating')
                            visible_elements.append({
                                'type': 'loading',
                                'image': loading_img,
                                'y_offset': 0,
                                'opacity': 255
                            })
                        # Show image drawing animation during drawing_phase
                        if frame_in_round >= initial_loading + text_phase + image_delay and frame_in_round < initial_loading + text_phase + image_delay + drawing_phase:
                            # Ensure the word is visible above the image
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
                                    drawing_progress = min(1.0, max(0.0, (frame_in_round - (initial_loading + text_phase + image_delay)) / drawing_phase))
                                    animated_img = create_drawing_animation(round_img, drawing_progress, image_path=round_data['image'])
                                    visible_elements.append({
                                        'type': 'image',
                                        'image': animated_img,
                                        'y_offset': 0,
                                        'opacity': 255,
                                        'drawing_progress': drawing_progress
                                    })
                                except Exception as e:
                                    print(f"Error processing image: {e}")
                        # Show fully revealed image after drawing phase
                        if frame_in_round >= initial_loading + text_phase + image_delay + drawing_phase:
                            # Ensure the word is visible above the image
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
        
        # Calculate total height for scrolling
        total_height = 0
        for idx, elem in enumerate(visible_elements):
            if idx > 0 and elem['type'] == 'loading':
                total_height += LOADING_EXTRA_PADDING
            total_height += elem['image'].height
            if idx < len(visible_elements) - 1:
                total_height += TEXT_PADDING
        # Add bottom padding so last element never touches the bottom
        total_height += BOTTOM_PADDING
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
        for idx, elem in enumerate(visible_elements):
            if idx > 0 and elem['type'] == 'loading':
                current_y += LOADING_EXTRA_PADDING
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
        
        # Overlay intro text on the first N frames
        if frame < intro_overlay_frames:
            intro_overlay = get_intro_overlay(intro_text, frame, intro_overlay_frames)
            image = image.convert('RGBA')
            image.alpha_composite(intro_overlay)
            image = image.convert('RGB')  # Convert back for saving as PNG

        # Save the frame
        frame_path = f"temp_frames/frame_{frame:05d}.png"
        image.save(frame_path)
        
        # Progress indicator
        if frame % 30 == 0 or frame == TOTAL_FRAMES - 1:
            completion = (frame + 1) / TOTAL_FRAMES * 100
            print(f"Generated frame {frame+1}/{TOTAL_FRAMES} ({completion:.1f}%)")

def create_video(output_file="pictionary_chain.mp4", custom_audio=None):
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
    
    # Always add custom audio if present
    if custom_audio and os.path.exists(custom_audio):
        print(f"Adding custom audio from {custom_audio}...")
        temp_video = output_file + ".tmp.mp4"
        # Rename the original video to a temp file
        os.rename(output_file, temp_video)
        ffmpeg_audio_cmd = [
            "ffmpeg", "-y",
            "-i", temp_video,
            "-i", custom_audio,
            "-map", "0:v", 
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_file
        ]
        subprocess.run(ffmpeg_audio_cmd)
        print(f"Video with audio created: {output_file}")
        # Remove the temp video file
        if os.path.exists(temp_video):
            os.remove(temp_video)

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
    parser.add_argument('--font', type=str, default=None,
                        help='Path to a font file to use (optional, will use system font if not specified)')
    parser.add_argument('--max-rounds', type=int, default=None,
                        help='Maximum number of rounds to process (for faster testing)')
    parser.add_argument('--part', type=int, default=None,
                        help='Part number to display in the title (e.g., 1 for Part 1)')
    
    args = parser.parse_args()
    
    # Generate a unique filename with timestamp if not specified
    if args.output is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"pictionary_chain_{timestamp}.mp4"
        output_path = os.path.join(args.game_dir, output_filename)
    else:
        # If output was specified, put it in the game directory
        output_path = os.path.join(args.game_dir, args.output)
    
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
    
    # Limit number of rounds if requested
    if args.max_rounds is not None:
        all_rounds = all_rounds[:args.max_rounds]
    global TOTAL_ROUNDS
    TOTAL_ROUNDS = len(all_rounds)
    print(f"Creating animation with {TOTAL_ROUNDS} rounds")
    
    # Always generate custom audio track if music files are present
    custom_audio = None
    if os.path.exists("thinking.flac") and os.path.exists("drawing.mp3"):
        custom_audio = os.path.join(args.game_dir, "custom_audio.wav")
        frames_per_round = int(DURATION * FPS)
        initial_loading = int(frames_per_round * 0.18)
        text_phase = int(frames_per_round * 0.26)
        image_delay = int(frames_per_round * 0.18)
        drawing_phase = int(frames_per_round * 0.4)
        create_audio_track(
            total_frames=frames_per_round * TOTAL_ROUNDS,
            fps=FPS,
            rounds=all_rounds,
            initial_loading=initial_loading,
            text_phase=text_phase,
            image_delay=image_delay,
            drawing_phase=drawing_phase,
            frames_per_round=frames_per_round,
            thinking_file="thinking.flac",
            drawing_file="drawing.mp3",
            output_audio=custom_audio
        )
    
    # Run the generation process
    generate_frames(part_number=args.part)
    create_video(output_path, custom_audio=custom_audio)
    cleanup()
    
    print(f"Process completed successfully! Video saved as: {output_path}")

if __name__ == "__main__":
    main()