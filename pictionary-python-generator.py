import os
import subprocess
import argparse
from PIL import Image, ImageDraw, ImageFont
import sys
import datetime
import re
import random
from collections import deque
import tempfile
import shutil
import multiprocessing as mp
from functools import partial
import concurrent.futures
import json
import time

# Constants
VIDEO_WIDTH = 1080  # Vertical video width
VIDEO_HEIGHT = 1920  # Vertical video height
BACKGROUND_COLOR = (255, 255, 255)  # White
TEXT_COLOR = (33, 33, 33)  # Dark gray, almost black
DEFAULT_DURATION = 3  # Default duration for each card (seconds)
DEFAULT_FPS = 30  # Default frames per second
TEXT_PADDING = 30  # Reduced padding between elements
SCROLL_ANIMATION_FRAMES = 15  # Number of frames for smooth scroll animation
LOADING_EXTRA_PADDING = 24  # Extra vertical space above loading indicator if not first
BOTTOM_PADDING = 90  # Bottom padding for all content

class FrameGenerationConfig:
    """Configuration class to hold all frame generation parameters"""
    def __init__(self, all_rounds, total_rounds, duration, fps, font_path, 
                 frames_per_round, initial_loading, text_phase, image_delay, 
                 drawing_phase, title_duration_frames, part_number=None):
        self.all_rounds = all_rounds
        self.total_rounds = total_rounds
        self.duration = duration
        self.fps = fps
        self.font_path = font_path
        self.frames_per_round = frames_per_round
        self.initial_loading = initial_loading
        self.text_phase = text_phase
        self.image_delay = image_delay
        self.drawing_phase = drawing_phase
        self.title_duration_frames = title_duration_frames
        self.part_number = part_number
        
        # Pre-calculate all scroll states for each frame
        self.scroll_states = self._calculate_scroll_states()
        
        # Pre-process all images and text elements
        self.processed_elements = self._preprocess_elements()
        
    def _calculate_scroll_states(self):
        """Pre-calculate scroll states for all frames to avoid coordination issues"""
        scroll_states = []
        current_scroll = 0
        last_round = -1
        scroll_start = 0
        scroll_frames = 0
        
        for frame in range(self.frames_per_round * self.total_rounds):
            current_round = frame // self.frames_per_round
            frame_in_round = frame % self.frames_per_round
            
            # Calculate total height based on what's actually visible at this frame
            total_height = 150  # Start with top padding to match positioning
            
            # Add completed rounds (always show text + image)
            for round_idx in range(current_round):
                if round_idx < len(self.all_rounds):
                    # Text height
                    text = self.all_rounds[round_idx]['prompt']
                    text_height = self._estimate_text_height(text)
                    total_height += text_height + TEXT_PADDING
                    
                    # Image height if exists
                    if 'image' in self.all_rounds[round_idx]:
                        img_height = self._estimate_image_height(self.all_rounds[round_idx]['image'])
                        total_height += img_height + TEXT_PADDING
            
            # Add current round content based on the current phase
            if current_round < len(self.all_rounds):
                if current_round == 0:
                    # First round logic
                    GENERATE_DELAY_FRAMES = int(self.frames_per_round * 0.18)
                    
                    # Always show text for first round
                    text = self.all_rounds[current_round]['prompt']
                    text_height = self._estimate_text_height(text)
                    total_height += text_height + TEXT_PADDING
                    
                    # Add loading or image based on phase
                    if frame_in_round >= GENERATE_DELAY_FRAMES and frame_in_round < GENERATE_DELAY_FRAMES + self.image_delay - 3:
                        total_height += LOADING_EXTRA_PADDING + 160 + TEXT_PADDING  # Loading indicator
                    elif frame_in_round >= GENERATE_DELAY_FRAMES + self.image_delay - 3:
                        if 'image' in self.all_rounds[current_round]:
                            img_height = self._estimate_image_height(self.all_rounds[current_round]['image'])
                            total_height += img_height + TEXT_PADDING
                else:
                    # Subsequent rounds logic
                    if frame_in_round < self.initial_loading:
                        # Analyzing phase: only loading
                        total_height += LOADING_EXTRA_PADDING + 160 + TEXT_PADDING
                    elif frame_in_round < self.initial_loading + self.text_phase - 3:
                        # Word reveal phase: only text
                        text = self.all_rounds[current_round]['prompt']
                        text_height = self._estimate_text_height(text)
                        total_height += text_height + TEXT_PADDING
                    elif frame_in_round < self.initial_loading + self.text_phase + self.image_delay - 3:
                        # Generating phase: text + loading
                        text = self.all_rounds[current_round]['prompt']
                        text_height = self._estimate_text_height(text)
                        total_height += text_height + TEXT_PADDING + LOADING_EXTRA_PADDING + 160 + TEXT_PADDING
                    elif frame_in_round >= self.initial_loading + self.text_phase + self.image_delay - 3:
                        # Drawing/reveal phase: text + image
                        text = self.all_rounds[current_round]['prompt']
                        text_height = self._estimate_text_height(text)
                        total_height += text_height + TEXT_PADDING
                        if 'image' in self.all_rounds[current_round]:
                            img_height = self._estimate_image_height(self.all_rounds[current_round]['image'])
                            total_height += img_height + TEXT_PADDING
            
            # Add bottom padding
            total_height += 90
            
            # Only scroll if content actually exceeds the video height
            # No buffer - precise calculation
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
                
            scroll_states.append(current_scroll)
            
        return scroll_states
    
    def _calculate_total_height(self, visible_rounds):
        """Calculate total height for a given number of visible rounds"""
        total_height = 90  # Add top padding to match the positioning logic
        for round_idx in range(min(visible_rounds, len(self.all_rounds))):
            # Text height
            text = self.all_rounds[round_idx]['prompt']
            text_height = self._estimate_text_height(text)
            total_height += text_height
            
            # Image height if exists
            if 'image' in self.all_rounds[round_idx]:
                img_height = self._estimate_image_height(self.all_rounds[round_idx]['image'])
                total_height += img_height
            
            # Loading indicator height only for current round (round_idx > 0)
            # For completed rounds, no loading indicator is shown
            if round_idx > 0 and round_idx == visible_rounds - 1:
                # This is the current round, add loading indicator height
                total_height += LOADING_EXTRA_PADDING + 160  # Loading indicator height
            
            # Padding between rounds
            if round_idx < visible_rounds - 1:
                total_height += TEXT_PADDING
        
        return total_height + BOTTOM_PADDING
    
    def _estimate_text_height(self, text, font_size=140):
        """Estimate text height for layout calculation"""
        # Use the same logic as _create_text_element for accurate estimation
        font_path = self.font_path if self.font_path else get_default_font(bold=True)
        try:
            font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
        
        # Wrap text (same logic as _create_text_element)
        max_width = VIDEO_WIDTH - 80
        words = text.split()
        lines = []
        current_line = ""
        dummy_img = Image.new('RGBA', (VIDEO_WIDTH, 10), (0,0,0,0))
        draw = ImageDraw.Draw(dummy_img)
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w > max_width and current_line:
                lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
        
        # Calculate total height (same as _create_text_element)
        bbox = draw.textbbox((0, 0), 'A', font=font)
        line_height = (bbox[3] - bbox[1]) + 10
        EXTRA_BOTTOM_PADDING = 30
        total_height = line_height * len(lines) + 40 + EXTRA_BOTTOM_PADDING
        
        return total_height
    
    def _estimate_image_height(self, image_path):
        """Estimate image height after resizing"""
        try:
            with Image.open(image_path) as img:
                img_width, img_height = img.size
                ratio = VIDEO_WIDTH / img_width
                new_height = int(img_height * ratio)
                return new_height
        except:
            return 400  # Default fallback
    
    def _preprocess_elements(self):
        """Pre-process all text and image elements to avoid repeated processing"""
        processed = {}
        
        # Process text elements
        for i, round_data in enumerate(self.all_rounds):
            text = round_data['prompt']
            processed[f'text_{i}'] = self._create_text_element(text)
            
            # Process images
            if 'image' in round_data and os.path.exists(round_data['image']):
                try:
                    processed[f'image_{i}'] = self._resize_image(round_data['image'])
                    processed[f'strokes_{i}'] = self._extract_black_strokes(processed[f'image_{i}'])
                except Exception as e:
                    print(f"Error processing image {round_data['image']}: {e}")
                    processed[f'image_{i}'] = None
                    processed[f'strokes_{i}'] = []
        
        return processed
    
    def _create_text_element(self, text, font_size=140):
        """Create a text element with proper sizing and wrapping"""
        font_path = self.font_path if self.font_path else get_default_font(bold=True)
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
            w = bbox[2] - bbox[0]
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
        EXTRA_BOTTOM_PADDING = 30
        total_height = line_height * len(lines) + 40 + EXTRA_BOTTOM_PADDING
        
        text_img = Image.new('RGBA', (VIDEO_WIDTH, total_height), (0,0,0,0))
        draw = ImageDraw.Draw(text_img)
        y = 20
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            draw.text(((VIDEO_WIDTH - w) // 2, y), line, fill=(0,0,0,255), font=font)
            y += line_height
        
        return text_img
    
    def _resize_image(self, image_path):
        """Resize image to fit video width"""
        img = Image.open(image_path).convert('RGBA')
        img_width, img_height = img.size
        ratio = VIDEO_WIDTH / img_width
        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def _extract_black_strokes(self, image, threshold=80):
        """Extract black strokes from image for animation"""
        gray = image.convert('L')
        pixels = gray.load()
        width, height = image.size
        visited = [[False] * height for _ in range(width)]
        strokes = []

        for y in range(height):
            for x in range(width):
                if not visited[x][y] and pixels[x, y] < threshold:
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
        
        # Sort by length and prepare timings
        strokes.sort(key=len, reverse=True)
        stroke_timings = []
        if len(strokes) > 1:
            for i, stroke in enumerate(strokes):
                start = i / len(strokes)
                end = 1.0
                if i % 2 == 1:
                    stroke = list(reversed(stroke))
                stroke_timings.append((stroke, start, end))
        else:
            if strokes:
                stroke_timings.append((strokes[0], 0.0, 1.0))
        
        return stroke_timings

def get_default_font(bold=False):
    """Find a default system font that's available"""
    if bold:
        potential_fonts = [
            "Arialbd.ttf", "arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", 
            "Verdana Bold.ttf", "Tahoma Bold.ttf", "SegoeUIBold.ttf", "segoeuib.ttf", 
            "Calibri Bold.ttf", "calibrib.ttf"
        ]
    else:
        potential_fonts = [
            "Arial.ttf", "DejaVuSans.ttf", "FreeSans.ttf", "LiberationSans-Regular.ttf", 
            "Helvetica.ttf", "Verdana.ttf", "Tahoma.ttf", "Segoe UI.ttf"
        ]
    
    # Look in common font directories by platform
    if sys.platform.startswith('win'):
        font_dirs = [os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')]
    elif sys.platform.startswith('darwin'):  # macOS
        font_dirs = ['/Library/Fonts', '/System/Library/Fonts', os.path.expanduser('~/Library/Fonts')]
    else:  # Linux and others
        font_dirs = ['/usr/share/fonts', '/usr/local/share/fonts', os.path.expanduser('~/.fonts')]
    
    # Try to find a system font
    for font_dir in font_dirs:
        if os.path.exists(font_dir):
            for font_name in potential_fonts:
                font_path = os.path.join(font_dir, font_name)
                if os.path.exists(font_path):
                    try:
                        test_font = ImageFont.truetype(font_path, 20)
                        return font_path
                    except Exception:
                        continue
    
    return None

def create_title_text(draw, font_path, part_number=None, bottom_padding=120):
    """Draw the title at the bottom"""
    base_title = "The World's Longest Game of Pictionary"
    if part_number is not None:
        base_title += f" Part {part_number}"
    
    # Use a smaller font for triple-digit part numbers
    if part_number is not None and int(part_number) >= 100:
        title_font_size = 110
    else:
        title_font_size = 120
    
    title_font_path = font_path if font_path else get_default_font(bold=True)
    try:
        title_font = ImageFont.truetype(title_font_path, title_font_size) if title_font_path else ImageFont.load_default()
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
    line_height = (bbox[3] - bbox[1]) + 24
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

def create_loading_indicator(frame, font_path, mode='analyzing'):
    """Create a loading indicator with animated pattern"""
    chars = ['█', '▓', '▒', '░']
    LOADING_HEIGHT = 160
    FONT_SIZE = 80
    LEFT_MARGIN = 60
    PATTERN_LEN = 8
    
    loading_img = Image.new('RGBA', (VIDEO_WIDTH, LOADING_HEIGHT), (255, 255, 255, 255))
    draw = ImageDraw.Draw(loading_img)
    
    random.seed(frame // 6)
    pattern = ''.join(random.choices(chars, k=PATTERN_LEN))
    
    text_prefix = "Generating: [" if mode == 'generating' else "Analyzing: ["
    text_suffix = "]"
    
    font_path_to_use = font_path if font_path else get_default_font()
    try:
        font = ImageFont.truetype(font_path_to_use, FONT_SIZE) if font_path_to_use else ImageFont.load_default()
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

def create_drawing_animation(strokes, progress):
    """Create animated drawing effect"""
    if not strokes:
        return Image.new('RGBA', (VIDEO_WIDTH, 400), (0, 0, 0, 0))
    
    # Get image size from first stroke
    if strokes:
        max_x = max(max(x for x, y in stroke) for stroke, _, _ in strokes)
        max_y = max(max(y for x, y in stroke) for stroke, _, _ in strokes)
        result = Image.new('RGBA', (max_x + 1, max_y + 1), (0, 0, 0, 0))
    else:
        result = Image.new('RGBA', (VIDEO_WIDTH, 400), (0, 0, 0, 0))
    
    for stroke, start, end in strokes:
        if progress >= end:
            for x, y in stroke:
                if 0 <= x < result.width and 0 <= y < result.height:
                    result.putpixel((x, y), (0, 0, 0, 255))
        elif progress > start:
            local_progress = (progress - start) / (end - start)
            reveal_count = int(len(stroke) * local_progress)
            for x, y in stroke[:reveal_count]:
                if 0 <= x < result.width and 0 <= y < result.height:
                    result.putpixel((x, y), (0, 0, 0, 255))
    
    return result

def generate_single_frame(frame_info):
    """Generate a single frame - this function will be called in parallel"""
    frame_num, config = frame_info
    
    try:
        image = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), BACKGROUND_COLOR)
        draw = ImageDraw.Draw(image)
        
        # Show title for first 3 seconds
        if frame_num < config.title_duration_frames:
            create_title_text(draw, config.font_path, part_number=config.part_number, bottom_padding=120)
        
        # Calculate round and progress
        current_round = frame_num // config.frames_per_round
        frame_in_round = frame_num % config.frames_per_round
        
        # Get pre-calculated scroll position
        current_scroll = config.scroll_states[frame_num]
        
        # Build visible elements
        visible_elements = []
        
        # Add elements from all previous rounds and current round
        for round_idx in range(current_round + 1):
            if round_idx < len(config.all_rounds):
                round_data = config.all_rounds[round_idx]
                
                # Handle current round timing
                if round_idx == current_round:
                    if current_round == 0:
                        # First round logic (keep as is)
                        GENERATE_DELAY_FRAMES = int(config.frames_per_round * 0.18)
                        text_img = config.processed_elements.get(f'text_{round_idx}')
                        if text_img:
                            visible_elements.append({
                                'type': 'text',
                                'image': text_img,
                                'opacity': 255
                            })
                        if frame_in_round >= GENERATE_DELAY_FRAMES and frame_in_round < GENERATE_DELAY_FRAMES + config.image_delay - 3:
                            loading_img = create_loading_indicator(frame_num, config.font_path, mode='generating')
                            visible_elements.append({
                                'type': 'loading',
                                'image': loading_img,
                                'opacity': 255
                            })
                        elif frame_in_round >= GENERATE_DELAY_FRAMES + config.image_delay - 3:
                            # Show drawing animation or final image
                            round_img = config.processed_elements.get(f'image_{round_idx}')
                            strokes = config.processed_elements.get(f'strokes_{round_idx}', [])
                            if round_img and frame_in_round < GENERATE_DELAY_FRAMES + config.image_delay + config.drawing_phase - 3:
                                drawing_progress = min(1.0, max(0.0, (frame_in_round - (GENERATE_DELAY_FRAMES + config.image_delay - 3)) / (config.drawing_phase - 3)))
                                animated_img = create_drawing_animation(strokes, drawing_progress)
                                if animated_img.width > 0 and animated_img.height > 0:
                                    visible_elements.append({
                                        'type': 'image',
                                        'image': animated_img,
                                        'opacity': 255
                                    })
                            elif round_img:
                                visible_elements.append({
                                    'type': 'image',
                                    'image': round_img,
                                    'opacity': 255
                                })
                    else:
                        # Subsequent rounds logic (fix: only show text during word reveal phase)
                        if frame_in_round < config.initial_loading:
                            # Analyzing phase: only show loading
                            loading_img = create_loading_indicator(frame_num, config.font_path, mode='analyzing')
                            visible_elements.append({
                                'type': 'loading',
                                'image': loading_img,
                                'opacity': 255
                            })
                        elif frame_in_round < config.initial_loading + config.text_phase - 3:
                            # Word reveal phase: only show text
                            text_img = config.processed_elements.get(f'text_{round_idx}')
                            if text_img:
                                visible_elements.append({
                                    'type': 'text',
                                    'image': text_img,
                                    'opacity': 255
                                })
                        elif frame_in_round < config.initial_loading + config.text_phase + config.image_delay - 3:
                            # Generating phase: show text AND loading
                            text_img = config.processed_elements.get(f'text_{round_idx}')
                            if text_img:
                                visible_elements.append({
                                    'type': 'text',
                                    'image': text_img,
                                    'opacity': 255
                                })
                            loading_img = create_loading_indicator(frame_num, config.font_path, mode='generating')
                            visible_elements.append({
                                'type': 'loading',
                                'image': loading_img,
                                'opacity': 255
                            })
                        elif frame_in_round >= config.initial_loading + config.text_phase + config.image_delay - 3:
                            # Drawing/reveal phase: show text AND drawing animation or final image
                            text_img = config.processed_elements.get(f'text_{round_idx}')
                            if text_img:
                                visible_elements.append({
                                    'type': 'text',
                                    'image': text_img,
                                    'opacity': 255
                                })
                            round_img = config.processed_elements.get(f'image_{round_idx}')
                            strokes = config.processed_elements.get(f'strokes_{round_idx}', [])
                            if round_img and frame_in_round < config.initial_loading + config.text_phase + config.image_delay + config.drawing_phase - 3:
                                drawing_progress = min(1.0, max(0.0, (frame_in_round - (config.initial_loading + config.text_phase + config.image_delay - 3)) / (config.drawing_phase - 3)))
                                animated_img = create_drawing_animation(strokes, drawing_progress)
                                if animated_img.width > 0 and animated_img.height > 0:
                                    visible_elements.append({
                                        'type': 'image',
                                        'image': animated_img,
                                        'opacity': 255
                                    })
                            elif round_img:
                                visible_elements.append({
                                    'type': 'image',
                                    'image': round_img,
                                    'opacity': 255
                                })
                else:
                    # Previous rounds - show final image and text
                    text_img = config.processed_elements.get(f'text_{round_idx}')
                    if text_img:
                        visible_elements.append({
                            'type': 'text',
                            'image': text_img,
                            'opacity': 255
                        })
                    round_img = config.processed_elements.get(f'image_{round_idx}')
                    if round_img:
                        visible_elements.append({
                            'type': 'image',
                            'image': round_img,
                            'opacity': 255
                        })
        
        # Position and draw elements
        current_y = 150  # Add more top padding to start content lower on screen
        for idx, elem in enumerate(visible_elements):
            if idx > 0 and elem['type'] == 'loading':
                current_y += LOADING_EXTRA_PADDING
            
            y_pos = current_y - current_scroll
            
            if y_pos < VIDEO_HEIGHT and y_pos + elem['image'].height > 0:
                image.paste(elem['image'], (0, int(y_pos)), elem['image'])
            
            current_y += elem['image'].height + TEXT_PADDING
        
        # Save frame
        frame_path = f"temp_frames/frame_{frame_num:05d}.png"
        image.save(frame_path)
        
        return frame_num
        
    except Exception as e:
        print(f"Error generating frame {frame_num}: {e}")
        return None

def generate_frames_parallel(config, num_processes=None):
    """Generate frames in parallel using ThreadPoolExecutor (Windows-optimized)"""
    from concurrent.futures import ThreadPoolExecutor
    
    if num_processes is None:
        num_processes = mp.cpu_count() * 2
    
    # Create directories
    os.makedirs("temp_frames", exist_ok=True)
    
    total_frames = config.frames_per_round * config.total_rounds
    print(f"Creating {total_frames} frames using {num_processes} threads (ThreadPoolExecutor)...")
    
    # Create frame info tuples
    frame_infos = [(frame_num, config) for frame_num in range(total_frames)]
    
    # Track progress
    completed_frames = 0
    start_time = time.time()
    
    # Use ThreadPoolExecutor instead of ProcessPoolExecutor
    with ThreadPoolExecutor(max_workers=num_processes) as executor:
        # Submit all jobs
        future_to_frame = {executor.submit(generate_single_frame, frame_info): frame_info[0] 
                          for frame_info in frame_infos}
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_frame):
            frame_num = future_to_frame[future]
            try:
                result = future.result()
                if result is not None:
                    completed_frames += 1
                    
                    # Progress update every 30 frames or at the end
                    if completed_frames % 30 == 0 or completed_frames == total_frames:
                        elapsed_time = time.time() - start_time
                        completion = completed_frames / total_frames * 100
                        frames_per_second = completed_frames / elapsed_time if elapsed_time > 0 else 0
                        
                        print(f"Generated {completed_frames}/{total_frames} frames ({completion:.1f}%) - "
                              f"{frames_per_second:.1f} frames/sec")
                        
                else:
                    print(f"Failed to generate frame {frame_num}")
                    
            except Exception as e:
                print(f"Error processing frame {frame_num}: {e}")

def create_video(output_file="pictionary_chain.mp4", fps=30, custom_audio=None):
    """Combine frames into a video using ffmpeg"""
    print("Creating video from frames...")
    
    # Use the image2 demuxer approach (simpler and more reliable)
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", "temp_frames/frame_%05d.png",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "23", 
        "-preset", "medium",
        "-loglevel", "error",  # Reduce log output
        output_file
    ]
    
    try:
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Video created: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error creating video: {e}")
        raise
    
    # Add custom audio if present
    if custom_audio and os.path.exists(custom_audio):
        print(f"Adding custom audio from {custom_audio}...")
        temp_video = output_file + ".tmp.mp4"
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
        subprocess.run(ffmpeg_audio_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Video with audio created: {output_file}")
        
        if os.path.exists(temp_video):
            os.remove(temp_video)

def create_audio_track(fps, rounds, initial_loading, text_phase, image_delay, drawing_phase, frames_per_round, thinking_file, drawing_file, output_audio):
    """Create an audio track that alternates between thinking and drawing files"""
    temp_dir = tempfile.mkdtemp()
    segment_files = []
    
    for i, round_data in enumerate(rounds):
        if i == 0:
            # Round 0: word only, then generating, then drawing, then reveal
            GENERATE_DELAY_FRAMES = int(frames_per_round * 0.18)
            image_delay = int(frames_per_round * 0.18)
            drawing_phase = int(frames_per_round * 0.4)
            
            # 1. Word only (no music)
            if GENERATE_DELAY_FRAMES > 0:
                silence1 = os.path.join(temp_dir, f"r0_silence1.wav")
                subprocess.run(
                    f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t {GENERATE_DELAY_FRAMES / fps} "{silence1}"',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                segment_files.append(silence1)
            
            # 2. Generating (silence)
            if image_delay > 0:
                gen = os.path.join(temp_dir, f"r0_gen.wav")
                subprocess.run(
                    f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t {image_delay / fps} "{gen}"',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                segment_files.append(gen)
            
            # 3. Drawing (drawing.mp3)
            if drawing_phase > 0:
                draw = os.path.join(temp_dir, f"r0_draw.wav")
                subprocess.run(
                    f'ffmpeg -y -t {drawing_phase / fps} -i "{drawing_file}" -af "apad=pad_dur={drawing_phase / fps}" -acodec pcm_s16le "{draw}"',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                segment_files.append(draw)
            
            # 4. Reveal (rest, silence)
            reveal_frames = frames_per_round - (GENERATE_DELAY_FRAMES + image_delay + drawing_phase)
            if reveal_frames > 0:
                silence2 = os.path.join(temp_dir, f"r0_silence2.wav")
                subprocess.run(
                    f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t {reveal_frames / fps} "{silence2}"',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
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
                subprocess.run(
                    f'ffmpeg -y -t {initial_loading / fps} -i "{thinking_file}" -af "volume=0.05,apad=pad_dur={initial_loading / fps}" -acodec pcm_s16le "{ana}"',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                segment_files.append(ana)
            
            # 2. Word only (silence)
            if text_phase > 0:
                silence1 = os.path.join(temp_dir, f"r{i}_silence1.wav")
                subprocess.run(
                    f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t {text_phase / fps} "{silence1}"',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                segment_files.append(silence1)
            
            # 3. Generating (silence)
            if image_delay > 0:
                gen = os.path.join(temp_dir, f"r{i}_gen.wav")
                subprocess.run(
                    f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t {image_delay / fps} "{gen}"',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                segment_files.append(gen)
            
            # 4. Drawing (drawing.mp3)
            if drawing_phase > 0:
                draw = os.path.join(temp_dir, f"r{i}_draw.wav")
                subprocess.run(
                    f'ffmpeg -y -t {drawing_phase / fps} -i "{drawing_file}" -af "apad=pad_dur={drawing_phase / fps}" -acodec pcm_s16le "{draw}"',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                segment_files.append(draw)
            
            # 5. Reveal (rest, silence)
            reveal_frames = frames_per_round - (initial_loading + text_phase + image_delay + drawing_phase)
            if reveal_frames > 0:
                silence2 = os.path.join(temp_dir, f"r{i}_silence2.wav")
                subprocess.run(
                    f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t {reveal_frames / fps} "{silence2}"',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                segment_files.append(silence2)
    
    # Concatenate all segments
    concat_file = os.path.join(temp_dir, "concat.txt")
    with open(concat_file, "w") as f:
        for seg in segment_files:
            f.write(f"file '{seg}'\n")
    
    subprocess.run(
        f'ffmpeg -y -f concat -safe 0 -i "{concat_file}" -c copy "{output_audio}"',
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    
    shutil.rmtree(temp_dir)

def cleanup():
    """Clean up temporary files"""
    print("Cleaning up temporary files...")
    try:
        for file in os.listdir("temp_frames"):
            try:
                os.remove(os.path.join("temp_frames", file))
            except:
                pass
        try:
            shutil.rmtree("temp_frames", ignore_errors=True)
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
    """Main function to orchestrate the parallel video generation"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate a video from Pictionary Chain Game images (Parallel Version)')
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
    parser.add_argument('--processes', '-p', type=int, default=None,
                        help='Number of parallel processes to use (default: min(12, cpu_count()))')
    
    args = parser.parse_args()
    
    # Generate a unique filename with timestamp if not specified
    if args.output is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"pictionary_chain_{timestamp}.mp4"
        output_path = os.path.join(args.game_dir, output_filename)
    else:
        output_path = os.path.join(args.game_dir, args.output)
    
    # Set font path if provided
    font_path = None
    if args.font and os.path.exists(args.font):
        font_path = args.font
        print(f"Using specified font: {font_path}")
    else:
        font_path = get_default_font()
        if font_path:
            print(f"Using system font: {font_path}")
        else:
            print("Using PIL's default font")
    
    print("Starting Parallel Pictionary Chain Generator")
    
    # Read game log data
    all_rounds = read_game_log(args.game_dir)
    if not all_rounds:
        print("Failed to read game log data. Please check the game directory path.")
        return
    
    # Limit number of rounds if requested
    if args.max_rounds is not None:
        all_rounds = all_rounds[:args.max_rounds]
    
    total_rounds = len(all_rounds)
    print(f"Creating animation with {total_rounds} rounds")
    
    # Calculate timing parameters
    frames_per_round = int(args.duration * args.fps)
    initial_loading = int(frames_per_round * 0.18)
    text_phase = int(frames_per_round * 0.26)
    image_delay = int(frames_per_round * 0.18)
    drawing_phase = int(frames_per_round * 0.4)
    title_duration_frames = int(3 * args.fps)
    
    # Create configuration object
    config = FrameGenerationConfig(
        all_rounds=all_rounds,
        total_rounds=total_rounds,
        duration=args.duration,
        fps=args.fps,
        font_path=font_path,
        frames_per_round=frames_per_round,
        initial_loading=initial_loading,
        text_phase=text_phase,
        image_delay=image_delay,
        drawing_phase=drawing_phase,
        title_duration_frames=title_duration_frames,
        part_number=args.part
    )
    
    # Generate custom audio track if music files are present
    custom_audio = None
    if os.path.exists("thinking.flac") and os.path.exists("drawing.mp3"):
        custom_audio = os.path.join(args.game_dir, "custom_audio.wav")
        print("Creating custom audio track...")
        create_audio_track(
            fps=args.fps,
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
    
    # Generate frames in parallel
    print("Starting parallel frame generation...")
    start_time = time.time()
    
    generate_frames_parallel(config, num_processes=args.processes)
    
    # --- THUMBNAIL EXTRACTION ---
    # The title is shown for the first N frames (title_duration_frames)
    # We'll use the last title frame as the thumbnail
    last_title_frame_num = config.title_duration_frames - 1
    last_title_frame_path = f"temp_frames/frame_{last_title_frame_num:05d}.png"
    if os.path.exists(last_title_frame_path):
        # Save thumbnail to videos directory
        videos_dir = os.path.join(os.path.dirname(__file__), 'videos')
        os.makedirs(videos_dir, exist_ok=True)
        part_number = args.part if args.part is not None else 'unknown'
        thumbnail_name = f"the_worlds_longest_game_of_pictionary_part_{part_number}_thumbnail.png"
        thumbnail_path = os.path.join(videos_dir, thumbnail_name)
        import shutil
        shutil.copyfile(last_title_frame_path, thumbnail_path)
        print(f"Thumbnail saved to: {thumbnail_path}")
    else:
        print(f"Warning: Could not find title frame for thumbnail at {last_title_frame_path}")
    # --- END THUMBNAIL EXTRACTION ---
    
    generation_time = time.time() - start_time
    print(f"Frame generation completed in {generation_time:.2f} seconds")
    
    # Create video
    create_video(output_path, fps=args.fps, custom_audio=custom_audio)
    
    # Cleanup
    cleanup()
    
    total_time = time.time() - start_time
    print(f"Process completed successfully in {total_time:.2f} seconds!")
    print(f"Video saved as: {output_path}")
    
    # Performance summary
    total_frames = frames_per_round * total_rounds
    avg_fps = total_frames / generation_time if generation_time > 0 else 0
    print(f"Performance: {avg_fps:.1f} frames/second average generation speed")

if __name__ == "__main__":
    main()