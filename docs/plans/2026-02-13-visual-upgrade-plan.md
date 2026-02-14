# Visual Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the AI Pictionary video visuals with a paper texture background, better drawing quality, and smoother contour-based stroke animation.

**Architecture:** Modify the Python video generator (`pictionary-python-generator.py`) to composite frames onto a scrolling paper texture and use OpenCV contour detection for stroke animation. Update the ComfyUI workflow template for higher resolution and refine the image generation prompts. No changes to game logic, upload pipeline, or JS orchestrator.

**Tech Stack:** Python (Pillow, OpenCV), ComfyUI (Stable Diffusion), Node.js (unchanged)

**Design doc:** `docs/plans/2026-02-13-visual-upgrade-design.md`

---

### Task 1: Generate Paper Texture Asset

**Files:**
- Create: `assets/paper_texture.png`

This task requires generating a seamless vertically-tiling paper texture using PIL. The texture should be 1080px wide (matching VIDEO_WIDTH) and ~1920px tall (one screen height) with subtle warm grain.

**Step 1: Create the texture generation script**

Create a script `generate_paper_texture.py` in the project root:

```python
"""Generate a seamless paper texture for the Pictionary video background."""
import os
import random
from PIL import Image, ImageDraw, ImageFilter

def generate_paper_texture(width=1080, height=1920, output_path="assets/paper_texture.png"):
    """Generate a warm, subtly textured paper background that tiles vertically."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Base color: warm off-white (sketchbook paper)
    base_r, base_g, base_b = 245, 240, 230

    img = Image.new('RGB', (width, height), (base_r, base_g, base_b))
    pixels = img.load()

    # Add subtle noise/grain
    random.seed(42)  # Reproducible texture
    for y in range(height):
        for x in range(width):
            # Small random variation per pixel
            noise = random.randint(-8, 8)
            r = max(0, min(255, base_r + noise))
            g = max(0, min(255, base_g + noise))
            b = max(0, min(255, base_b + noise - 2))  # Slightly less blue for warmth
            pixels[x, y] = (r, g, b)

    # Add very subtle horizontal fiber lines
    draw = ImageDraw.Draw(img)
    for _ in range(40):
        y_pos = random.randint(0, height - 1)
        opacity_variation = random.randint(-3, 3)
        line_color = (base_r + opacity_variation - 10,
                      base_g + opacity_variation - 10,
                      base_b + opacity_variation - 12)
        draw.line([(0, y_pos), (width, y_pos)], fill=line_color, width=1)

    # Slight blur to soften the grain
    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

    # Make vertically seamless: blend top and bottom 100px
    blend_height = 100
    for y in range(blend_height):
        alpha = y / blend_height  # 0 at top, 1 at blend_height
        for x in range(width):
            top_pixel = img.getpixel((x, y))
            bottom_pixel = img.getpixel((x, height - blend_height + y))
            blended = tuple(int(bottom_pixel[c] * (1 - alpha) + top_pixel[c] * alpha) for c in range(3))
            img.putpixel((x, y), blended)
            img.putpixel((x, height - blend_height + y), blended)

    img.save(output_path, 'PNG')
    print(f"Paper texture saved to {output_path} ({width}x{height})")

if __name__ == "__main__":
    generate_paper_texture()
```

**Step 2: Run the script to generate the texture**

Run: `python generate_paper_texture.py`
Expected: `assets/paper_texture.png` created (1080x1920 warm paper texture)

**Step 3: Visually inspect the texture**

Open `assets/paper_texture.png` and verify:
- Warm off-white color (not stark white, not yellow)
- Subtle grain visible at full size
- No obvious tiling seam at top/bottom edges

If the texture looks wrong, adjust `base_r/g/b`, noise range, or fiber line count and regenerate.

**Step 4: Commit**

```bash
git add assets/paper_texture.png generate_paper_texture.py
git commit -m "feat: add paper texture asset for video background"
```

---

### Task 2: Integrate Paper Texture Background into Video Generator

**Files:**
- Modify: `pictionary-python-generator.py:30-35` (add texture loading to FrameGenerationConfig)
- Modify: `pictionary-python-generator.py:634` (use texture instead of flat color in generate_single_frame)

**Step 1: Add texture loading to FrameGenerationConfig.__init__**

In `pictionary-python-generator.py`, add a new parameter and texture-loading logic to the `FrameGenerationConfig.__init__` method (around line 32). After the existing `self.part_number = part_number` line:

```python
# Load paper texture for background
texture_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'paper_texture.png')
if os.path.exists(texture_path):
    self.paper_texture = Image.open(texture_path).convert('RGB')
    self.texture_height = self.paper_texture.height
    print(f"Loaded paper texture: {self.paper_texture.size}")
else:
    self.paper_texture = None
    self.texture_height = 0
    print("Warning: Paper texture not found, using plain white background")
```

**Step 2: Create a helper method to get the background for a frame**

Add a new method to `FrameGenerationConfig` class, after the `_preprocess_elements` method (after line 307):

```python
def get_background_frame(self, scroll_y):
    """Get the paper texture background for the current scroll position."""
    if self.paper_texture is None:
        return Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), BACKGROUND_COLOR)

    bg = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), BACKGROUND_COLOR)
    # Tile the texture vertically based on scroll position
    texture_y_offset = int(scroll_y) % self.texture_height
    y = -texture_y_offset
    while y < VIDEO_HEIGHT:
        bg.paste(self.paper_texture, (0, y))
        y += self.texture_height
    return bg
```

**Step 3: Update generate_single_frame to use the texture background**

In `generate_single_frame` (line 634), replace:

```python
image = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), BACKGROUND_COLOR)
```

with:

```python
image = config.get_background_frame(current_scroll)
```

Note: `current_scroll` is already calculated on line 646. Move the scroll lookup before the background creation:

```python
# Calculate round and progress
current_round = frame_num // config.frames_per_round
frame_in_round = frame_num % config.frames_per_round

# Get pre-calculated scroll position
current_scroll = config.scroll_states[frame_num]

# Create background with paper texture
image = config.get_background_frame(current_scroll)
draw = ImageDraw.Draw(image)
```

**Step 4: Update the loading indicator to use transparent background**

In `create_loading_indicator` (line 571), the loading indicator currently creates a white RGBA background. Change it to transparent so the paper texture shows through:

```python
loading_img = Image.new('RGBA', (VIDEO_WIDTH, LOADING_HEIGHT), (0, 0, 0, 0))
```

**Step 5: Test by generating a video from an existing game**

Run: `python pictionary-python-generator.py --game-dir games/pictionary_game_1770115973377 --output test_paper_texture.mp4 --max-rounds 3`

Expected: Video with paper texture background visible behind text and drawings. Loading indicators should not have white rectangles behind them.

**Step 6: Commit**

```bash
git add pictionary-python-generator.py
git commit -m "feat: add scrolling paper texture background to video frames"
```

---

### Task 3: Replace BFS Stroke Animation with Contour-Based Animation

**Files:**
- Modify: `pictionary-python-generator.py:430-474` (replace `_extract_black_strokes`)
- Modify: `pictionary-python-generator.py:602-627` (replace `create_drawing_animation`)

**Step 1: Install opencv-python**

Run: `pip install opencv-python`
Expected: Successfully installed opencv-python

**Step 2: Add cv2 import**

At the top of `pictionary-python-generator.py` (around line 1-16), add:

```python
import cv2
import numpy as np
```

**Step 3: Replace _extract_black_strokes method**

Replace the entire `_extract_black_strokes` method (lines 430-474) in class `FrameGenerationConfig`:

```python
def _extract_black_strokes(self, image, threshold=80):
    """Extract contour-based strokes from image for animation using OpenCV."""
    # Convert PIL image to numpy array for OpenCV
    img_array = np.array(image.convert('L'))

    # Threshold to binary (invert so black strokes are white)
    _, binary = cv2.threshold(img_array, threshold, 255, cv2.THRESH_BINARY_INV)

    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    if not contours:
        return []

    # Sort contours: largest first (main shapes), then smaller details
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    # Filter out tiny noise contours (less than 10 pixels)
    contours = [c for c in contours if len(c) >= 10]

    if not contours:
        return []

    # Prepare stroke timings with staggered starts
    stroke_timings = []
    for i, contour in enumerate(contours):
        # Convert contour points to list of (x, y) tuples
        points = [(int(pt[0][0]), int(pt[0][1])) for pt in contour]

        # Stagger start times: larger strokes start earlier
        start = i / len(contours) * 0.5  # First half of animation starts all strokes
        end = 1.0

        # Alternate direction for visual variety
        if i % 2 == 1:
            points = list(reversed(points))

        stroke_timings.append((points, start, end))

    return stroke_timings
```

**Step 4: Replace create_drawing_animation function**

Replace the entire `create_drawing_animation` function (lines 602-627):

```python
def create_drawing_animation(strokes, progress):
    """Create animated drawing effect using contour-based paths."""
    if not strokes:
        return Image.new('RGBA', (VIDEO_WIDTH, 400), (0, 0, 0, 0))

    # Get image size from stroke bounds
    max_x = max(max(x for x, y in points) for points, _, _ in strokes)
    max_y = max(max(y for x, y in points) for points, _, _ in strokes)
    width = max_x + 1
    height = max_y + 1

    # Create numpy array for OpenCV drawing (much faster than putpixel)
    result_array = np.zeros((height, width, 4), dtype=np.uint8)

    LINE_THICKNESS = 3  # Pen-like line width

    for points, start, end in strokes:
        if progress >= end:
            # Draw complete contour
            pts = np.array(points, dtype=np.int32).reshape(-1, 1, 2)
            cv2.drawContours(result_array, [pts], -1, (0, 0, 0, 255), LINE_THICKNESS)
        elif progress > start:
            # Draw partial contour based on progress
            local_progress = (progress - start) / (end - start)
            reveal_count = max(2, int(len(points) * local_progress))
            partial_points = points[:reveal_count]
            if len(partial_points) >= 2:
                pts = np.array(partial_points, dtype=np.int32)
                cv2.polylines(result_array, [pts], isClosed=False,
                              color=(0, 0, 0, 255), thickness=LINE_THICKNESS)

    # Convert numpy array back to PIL Image
    result = Image.fromarray(result_array, 'RGBA')
    return result
```

**Step 5: Test the animation with an existing game**

Run: `python pictionary-python-generator.py --game-dir games/pictionary_game_1770115973377 --output test_contour_anim.mp4 --max-rounds 3`

Expected: Video where drawings are revealed along contour paths instead of pixel blobs. Lines should look smoother with visible pen thickness. The staggered timing should still create an unpredictable drawing feel.

**Step 6: Commit**

```bash
git add pictionary-python-generator.py
git commit -m "feat: replace BFS flood-fill animation with contour-based stroke reveal"
```

---

### Task 4: Polish Loading Indicator Timing

**Files:**
- Modify: `pictionary-python-generator.py:574` (loading animation speed)

**Step 1: Update the animation speed**

In `create_loading_indicator` (line 574), change:

```python
random.seed(frame // 6)
```

to:

```python
random.seed(frame // 4)
```

This makes the block character pattern update every 4 frames instead of every 6 (at 30fps, that's ~7.5 updates/sec instead of 5 updates/sec).

**Step 2: Test**

Run: `python pictionary-python-generator.py --game-dir games/pictionary_game_1770115973377 --output test_loading.mp4 --max-rounds 3`

Expected: Loading animation cycles slightly faster. Subtle change.

**Step 3: Commit**

```bash
git add pictionary-python-generator.py
git commit -m "feat: smooth loading indicator animation timing"
```

---

### Task 5: Update ComfyUI Workflow for Higher Resolution

**Files:**
- Modify: `pictionary_workflow_template.json` (lines 13-15, resolution)

**Step 1: Update the resolution**

In `pictionary_workflow_template.json`, change the `EmptyLatentImage` node (node "3") from:

```json
"width": 512,
"height": 512,
```

to:

```json
"width": 768,
"height": 768,
```

**Step 2: Commit**

```bash
git add pictionary_workflow_template.json
git commit -m "feat: increase image generation resolution to 768x768"
```

---

### Task 6: Refine Image Generation Prompts

**Files:**
- Modify: `promptTemplates.js:11` (positive prompt)
- Modify: `pictionary_workflow_template.json` (negative prompt, node "9")

**Step 1: Update the positive prompt template**

In `promptTemplates.js` line 11, change:

```javascript
return `(${prompt}:1.3), simple line drawing, minimalist sketch, clean black lines only, (white background:1.2), monochrome, black and white only`;
```

to:

```javascript
return `(${prompt}:1.3), simple line drawing, minimalist sketch, clean black lines only, (white background:1.2), monochrome, black and white only, centered composition, single object, clear outline`;
```

**Step 2: Trim the negative prompt**

In `pictionary_workflow_template.json`, node "9" (negative prompt), replace the text with a more focused version:

```
"text": "color, colored, shading, shadows, gradient, solid black areas, filled shapes, dark shading, thick black areas, messy lines, detailed shading, watercolor, painting, realistic, photorealistic, blurry, low quality, artifacts, noise, complex background, cluttered, textured background, gray background, colored background"
```

This removes redundant entries (like listing every individual color) and focuses on the patterns that actually cause bad outputs.

**Step 3: Commit**

```bash
git add promptTemplates.js pictionary_workflow_template.json
git commit -m "feat: refine image generation prompts for clearer drawings"
```

---

### Task 7: Research and Test Better Sketch LoRA

**Files:**
- Modify: `pictionary_workflow_template.json` (LoRA name, node "10")
- Add: new LoRA file to `ComfyUI/models/loras/`

This task requires manual research and is the most exploratory.

**Step 1: Research sketch LoRAs**

Search CivitAI and Hugging Face for sketch/doodle LoRAs compatible with SD 1.5 / DreamShaper 8. Key search terms:
- "quick draw sketch lora sd1.5"
- "doodle line art lora"
- "simple sketch lora stable diffusion"

Look for LoRAs that produce:
- Consistent line weight
- Recognizable single objects
- Clean black-on-white output
- Good variety across different subjects

**Step 2: Download and test 2-3 candidates**

Place each LoRA in `ComfyUI/models/loras/`. For each candidate:
1. Update the LoRA name in `pictionary_workflow_template.json` node "10"
2. Run a game: `node pictionary-chain-local.js`
3. Inspect the generated images in the game directory
4. Compare quality across different word types (animals, objects, buildings, abstract)

**Step 3: Select the best LoRA and update the workflow**

In `pictionary_workflow_template.json` node "10", update `lora_name` to the selected LoRA filename. Also experiment with `strength_model` and `strength_clip` values (current: 1.0) -- try 0.7-1.0 range.

**Step 4: Commit**

```bash
git add pictionary_workflow_template.json
git commit -m "feat: switch to improved sketch LoRA for better drawing quality"
```

Note: The LoRA model file itself should NOT be committed to git (too large). Document the LoRA name/source in the design doc or a README note.

---

### Task 8: End-to-End Integration Test

**Files:** None (testing only)

**Step 1: Run a full game + video generation**

```bash
python main.py --count 1 --dry-run
```

This runs one complete game (JS game + video generation) without uploading. Verify:
- Game runs successfully (10 rounds)
- Images are generated at 768x768 resolution
- Video is generated with paper texture background
- Drawing animations use contour-based reveal
- Loading indicators animate smoothly
- Text is unchanged and readable
- Scrolling works correctly with the paper texture
- No errors or visual artifacts

**Step 2: Compare old vs new**

Open an old video from `videos/` and the newly generated video side by side. The new video should visibly have:
- Warm paper background instead of stark white
- Smoother drawing reveal animations
- Crisper drawings (from 768 resolution)

**Step 3: Fix any issues found during testing**

If there are problems, iterate on the specific task that introduced the issue.

**Step 4: Final commit with any fixes**

```bash
git add -A
git commit -m "fix: address integration test findings for visual upgrade"
```
