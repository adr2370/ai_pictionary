# Visual Upgrade Design

## Context

The AI Pictionary project has produced 4,200+ videos with a basic visual style: plain white backgrounds, inconsistent line drawings, and chunky pixel-based drawing animations. The goal is to upgrade the visuals across the board while keeping the infinite-scrolling format, the funny/imperfect AI drawing quality, and the existing pipeline intact.

## Design Decisions

### Background: Paper Texture (Scrolling)

Replace the plain white fill with a seamless paper texture.

- Source or generate a vertically-tiling paper texture at 1080px wide
- Warm off-white tones with subtle grain/fiber (sketchbook feel, not printer paper)
- Texture scrolls with the content -- the viewport pans down the "page" as rounds accumulate
- Implementation: generate a tall texture (or tile at render time) matching total content height, composite all elements on top

**Files affected**: `pictionary-python-generator.py` (frame generation), new texture asset in repo

### Drawings: Better LoRA + Higher Resolution

Improve drawing quality while keeping the simple line art style.

- Research and test 2-3 alternative sketch LoRAs (Google Quick Draw dataset LoRAs are a good starting point)
- Increase generation resolution from 512x512 to 768x768
- Refine positive prompt: add "centered composition, single object" guidance
- Refine negative prompt: trim the massive list, focus on what actually matters
- Keep DreamShaper 8 as the base model

**Files affected**: `pictionary_workflow_template.json` (resolution), `promptTemplates.js` (prompts), LoRA file swap in ComfyUI models directory

### Animation: Contour-Based Stroke Reveal

Replace BFS flood-fill pixel reveal with OpenCV contour detection.

- Use `cv2.findContours()` to extract ordered paths along shape edges
- Sort contours by position (top-to-bottom, left-to-right) for semi-natural reveal order
- Animate each contour by progressively drawing it with 3-5px line width
- Stagger start times: larger strokes start first, smaller details fill in later
- Keeps the unpredictable "AI is drawing this live" feel

**New dependency**: `opencv-python`
**Files affected**: `pictionary-python-generator.py` (`_extract_black_strokes` method and `create_drawing_animation`)

### Loading Indicator: Smoother Timing

Minor polish to the existing block-character loading animation.

- Update animation every 3-4 frames instead of every 6
- No structural changes to format or appearance

**Files affected**: `pictionary-python-generator.py` (`create_loading_indicator`)

### No Changes

- Text styling (bold black text, current font)
- Video dimensions (1080x1920)
- Title card
- Audio track generation
- Game logic and JS orchestrator
- Upload pipeline and CSV generation
- Scrolling behavior and round layout

## Dependencies

- `opencv-python` (new Python dependency for contour detection)
- Paper texture PNG asset (to be sourced/generated)
- Alternative sketch LoRA model file (to be researched and tested)

## Risks

- **LoRA research**: Finding the right LoRA requires testing. May need to try several before finding one that produces consistently recognizable drawings.
- **Contour detection quality**: OpenCV contour detection works well on clean line art but may behave unexpectedly on very sparse/minimal drawings. Need to handle edge cases.
- **768 resolution**: Slightly slower generation per image. Acceptable since generation is already the bottleneck and only adds a few seconds.
