# AI Pictionary Chain Game

An AI-powered Pictionary game that creates a chain of drawings and guesses, automatically generating TikTok-style videos from the gameplay. This project combines image generation, AI guessing, and video creation to produce entertaining content.

## 🎮 Project Overview

This project simulates a Pictionary game where:

1. **AI generates drawings** from word prompts using either OpenAI's DALL-E or local ComfyUI
2. **AI analyzes the drawings** and makes deliberately incorrect but plausible guesses
3. **The chain continues** with each guess becoming the next drawing prompt
4. **Videos are automatically generated** showing the progression of drawings and guesses

The result is a humorous chain of misinterpretations that creates engaging content perfect for social media platforms like TikTok.

## 📁 Project Structure

```
ai_pictionary/
├── pictionary-chain-local.js      # Main game orchestrator (JavaScript)
├── pictionary-guesser.js          # AI guessing component (JavaScript)
├── image-generator.js             # OpenAI DALL-E image generator (JavaScript)
├── pictionary-python-generator.py # Video creation from game results (Python)
├── promptTemplates.js             # Prompt templates for image generation
├── pictionary_workflow_template.json # ComfyUI workflow template
├── package.json                   # Node.js dependencies
├── ComfyUI/                       # Local ComfyUI installation (optional)
├── videos/                        # Generated video outputs
└── pictionary_game_*/             # Game session directories
```

## 🚀 Core Components

### 1. **Game Orchestrator** (`pictionary-chain-local.js`)

- **Purpose**: Main controller that runs the complete Pictionary chain game
- **Features**:
  - Manages the game flow between image generation and guessing
  - Supports both OpenAI DALL-E and local ComfyUI for image generation
  - Tracks game progress and creates detailed logs
  - Generates HTML summaries of each game session
  - Prevents word repetition across rounds

### 2. **AI Guesser** (`pictionary-guesser.js`)

- **Purpose**: Analyzes drawings and provides deliberately incorrect guesses
- **Features**:
  - Uses OpenAI's GPT-4 Vision API to analyze images
  - Generates plausible but wrong answers that seem reasonable
  - Ensures guesses are close enough to be believable but definitely incorrect
  - Can be run independently for single image analysis

### 3. **Image Generator** (`image-generator.js`)

- **Purpose**: Creates hand-drawn style images from word prompts
- **Features**:
  - Uses OpenAI's DALL-E 3 API for high-quality image generation
  - Optimized prompts for Pictionary-style minimalist drawings
  - Downloads and saves generated images locally
  - Can be used as a standalone tool

### 4. **Video Generator** (`pictionary-python-generator.py`)

- **Purpose**: Creates TikTok-style videos from game sessions
- **Features**:
  - Generates vertical videos (1080x1920) optimized for mobile viewing
  - Creates smooth animations with drawing effects and transitions
  - Supports custom timing, fonts, and background music
  - Uses FFmpeg for video compilation
  - Includes loading animations and text overlays

### 5. **Prompt Templates** (`promptTemplates.js`)

- **Purpose**: Provides optimized prompts for consistent image generation
- **Features**:
  - Ensures all generated images have a consistent Pictionary style
  - Uses minimalist vector-style line drawings
  - Maintains simple black outlines on white backgrounds

## 🛠️ Setup and Installation

### Prerequisites

- **Node.js** (v14 or higher)
- **Python** (v3.7 or higher)
- **FFmpeg** (for video generation)
- **OpenAI API Key** (for image generation and guessing)
- **ComfyUI** (optional, for local image generation)

### Installation

1. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd ai_pictionary
   ```

2. **Install Node.js dependencies**:

   ```bash
   npm install
   ```

3. **Install Python dependencies**:

   ```bash
   pip install pillow
   ```

4. **Set up your OpenAI API key**:

   - Edit the API key in the JavaScript files or set as environment variable
   - Ensure you have sufficient credits for image generation and analysis

5. **Install FFmpeg** (for video generation):
   - **Windows**: Download from https://ffmpeg.org/download.html
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg`

### Optional: ComfyUI Setup

For local image generation (recommended for cost savings):

1. **Install ComfyUI**:

   ```bash
   git clone https://github.com/comfyanonymous/ComfyUI.git
   cd ComfyUI
   pip install -r requirements.txt
   ```

2. **Create workflow template**:
   - Open ComfyUI in your browser
   - Create a workflow with CLIPTextEncode and image generation nodes
   - Export as JSON and save as `pictionary_workflow_template.json`

## 🎯 Usage

### Running a Complete Game Session

1. **Start the main game**:

   ```bash
   node pictionary-chain-local.js
   ```

   This will:

   - Generate 10 rounds of drawings and guesses
   - Save all images and logs to a timestamped directory
   - Create an HTML summary of the game

2. **Generate a video from the game**:
   ```bash
   python pictionary-python-generator.py --game-dir pictionary_game_[timestamp]
   ```

### Individual Components

**Generate a single image**:

```bash
node image-generator.js
```

**Analyze a single image**:

```bash
node pictionary-guesser.js
```

**Create video with custom settings**:

```bash
python pictionary-python-generator.py \
  --game-dir pictionary_game_[timestamp] \
  --duration 4 \
  --fps 30 \
  --output my_video.mp4 \
  --music background.mp3
```

## 🎨 Video Generation Features

The Python video generator creates engaging TikTok-style content with:

- **Vertical format** (1080x1920) optimized for mobile viewing
- **Smooth animations** with drawing effects that gradually reveal images
- **Loading indicators** with animated dots
- **Text overlays** showing prompts and guesses
- **Smooth scrolling** as content accumulates
- **Customizable timing** and frame rates
- **Background music support**
- **Professional transitions** between rounds

### Video Generation Options

```bash
python pictionary-python-generator.py --help
```

**Available options**:

- `--game-dir`: Directory containing game session files
- `--duration`: Seconds per round (default: 3)
- `--fps`: Frames per second (default: 30)
- `--output`: Output filename
- `--music`: Background music file
- `--font`: Custom font file path

## 📊 Game Session Structure

Each game session creates a directory with:

```
pictionary_game_[timestamp]/
├── game_log.txt                    # Detailed game progress log
├── index.html                      # Interactive game summary
├── round_1_[word].png             # Generated images
├── round_1_[word]_summary.txt     # Round details
├── round_2_[word].png
├── round_2_[word]_summary.txt
└── ...
```

## 🔧 Configuration

### API Keys

Set your OpenAI API key in the JavaScript files:

```javascript
const OPENAI_API_KEY = "your-api-key-here";
```

### ComfyUI Configuration

For local image generation, ensure ComfyUI is running on `http://127.0.0.1:8188`

### Video Settings

Modify constants in `pictionary-python-generator.py`:

- `VIDEO_WIDTH` and `VIDEO_HEIGHT`: Video dimensions
- `DEFAULT_DURATION`: Seconds per round
- `DEFAULT_FPS`: Frame rate
- `BACKGROUND_COLOR`: Video background color

## 🎭 Example Game Flow

1. **Round 1**: "elephant" → AI draws elephant → AI guesses "rhinoceros"
2. **Round 2**: "rhinoceros" → AI draws rhinoceros → AI guesses "hippopotamus"
3. **Round 3**: "hippopotamus" → AI draws hippopotamus → AI guesses "crocodile"
4. **...and so on**

The humor comes from the AI's "misinterpretations" - each guess is plausible but wrong, creating a chain of increasingly amusing misunderstandings.

## 🎬 Output Examples

The system generates:

- **Individual images** for each round
- **HTML summaries** with interactive viewing
- **TikTok-style videos** with smooth animations
- **Detailed logs** for analysis and debugging

## 🤝 Contributing

Contributions are welcome! Areas for improvement:

- Additional image generation backends
- More sophisticated guessing algorithms
- Enhanced video effects and transitions
- Web interface for game management
- Multiplayer support

## 📝 License

This project is open source. Please check individual files for specific licensing information.

## 🆘 Troubleshooting

**Common Issues**:

- **API Key Errors**: Ensure your OpenAI API key is valid and has sufficient credits
- **FFmpeg Not Found**: Install FFmpeg and ensure it's in your system PATH
- **ComfyUI Connection**: Verify ComfyUI is running and accessible at the configured URL
- **Font Issues**: The Python generator will automatically find system fonts, but you can specify a custom font file

**Getting Help**:

- Check the game logs in the session directory for detailed error information
- Verify all dependencies are properly installed
- Ensure sufficient disk space for image and video generation
