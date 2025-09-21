// Pictionary Chain Game Generator using Local ComfyUI
// This script chains together image generation and guessing in a loop
// creating a fun sequence of pictionary drawings and guesses
//
// NEW: This script now automatically starts and stops ComfyUI and Ollama as needed.
// No need to manually start ComfyUI or Ollama before running the script.
// The script will:
// 1. Check if ComfyUI and Ollama are already running
// 2. Start ComfyUI and Ollama if they're not running
// 3. Run the pictionary game
// 4. Stop ComfyUI and Ollama when the game is complete (only if we started them)
// 5. Handle cleanup on script interruption (Ctrl+C)

const axios = require("axios");
const fs = require("fs");
const path = require("path");
const { promisify } = require("util");
const exec = promisify(require("child_process").exec);
const { spawn } = require("child_process");
const { getPictionaryPrompt } = require("./promptTemplates");

// Configuration
const COMFYUI_API_URL = "http://127.0.0.1:8188"; // Local ComfyUI server address
const OLLAMA_BASE_URL = "http://localhost:11434"; // Default Ollama URL
const MODEL_NAME = "llava:7b"; // Using 7b model for lower GPU memory usage
const GAMES_ROOT = path.join(__dirname, "games");
if (!fs.existsSync(GAMES_ROOT)) {
  fs.mkdirSync(GAMES_ROOT);
}
const GAME_DIR = path.join(GAMES_ROOT, "pictionary_game_" + Date.now());

// Process management
let comfyuiProcess = null;
let comfyuiStartedByUs = false;
let ollamaProcess = null;
let ollamaStartedByUs = false;
const COMFYUI_DIR = path.join(__dirname, "ComfyUI");

// List of starter words for the first round
const STARTER_WORDS = [
  "Aircraft carrier",
  "Airplane",
  "Alarm clock",
  "Ambulance",
  "Angel",
  "Animal migration",
  "Ant",
  "Anvil",
  "Apple",
  "Arm",
  "Asparagus",
  "Axe",
  "Backpack",
  "Banana",
  "Bandage",
  "Barn",
  "Baseball",
  "Baseball bat",
  "Basket",
  "Basketball",
  "Bat",
  "Bathtub",
  "Beach",
  "Bear",
  "Beard",
  "Bed",
  "Bee",
  "Belt",
  "Bench",
  "Bicycle",
  "Binoculars",
  "Bird",
  "Birthday cake",
  "Blackberry",
  "Blueberry",
  "Book",
  "Boomerang",
  "Bottlecap",
  "Bowtie",
  "Bracelet",
  "Brain",
  "Bread",
  "Bridge",
  "Broccoli",
  "Broom",
  "Bucket",
  "Bulldozer",
  "Bus",
  "Bush",
  "Butterfly",
  "Cactus",
  "Cake",
  "Calculator",
  "Calendar",
  "Camel",
  "Camera",
  "Camouflage",
  "Campfire",
  "Candle",
  "Cannon",
  "Canoe",
  "Car",
  "Carrot",
  "Castle",
  "Cat",
  "Ceiling fan",
  "Cello",
  "Cell phone",
  "Chair",
  "Chandelier",
  "Church",
  "Circle",
  "Clarinet",
  "Clock",
  "Cloud",
  "Coffee cup",
  "Compass",
  "Computer",
  "Cookie",
  "Cooler",
  "Couch",
  "Cow",
  "Crab",
  "Crayon",
  "Crocodile",
  "Crown",
  "Cruise ship",
  "Cup",
  "Diamond",
  "Dishwasher",
  "Diving board",
  "Dog",
  "Dolphin",
  "Donut",
  "Door",
  "Dragon",
  "Dresser",
  "Drill",
  "Drums",
  "Duck",
  "Dumbbell",
  "Ear",
  "Elbow",
  "Elephant",
  "Envelope",
  "Eraser",
  "Eye",
  "Eyeglasses",
  "Face",
  "Fan",
  "Feather",
  "Fence",
  "Finger",
  "Fire hydrant",
  "Fireplace",
  "Firetruck",
  "Fish",
  "Flamingo",
  "Flashlight",
  "Flip flops",
  "Floor lamp",
  "Flower",
  "Flying saucer",
  "Foot",
  "Fork",
  "Frog",
  "Frying pan",
  "Garden",
  "Garden hose",
  "Giraffe",
  "Goatee",
  "Golf club",
  "Grapes",
  "Grass",
  "Guitar",
  "Hamburger",
  "Hammer",
  "Hand",
  "Harp",
  "Hat",
  "Headphones",
  "Hedgehog",
  "Helicopter",
  "Helmet",
  "Hexagon",
  "Hockey puck",
  "Hockey stick",
  "Horse",
  "Hospital",
  "Hot air balloon",
  "Hot dog",
  "Hot tub",
  "Hourglass",
  "House",
  "House plant",
  "Hurricane",
  "Ice cream",
  "Jacket",
  "Jail",
  "Kangaroo",
  "Key",
  "Keyboard",
  "Knee",
  "Knife",
  "Ladder",
  "Lantern",
  "Laptop",
  "Leaf",
  "Leg",
  "Light bulb",
  "Lighter",
  "Lighthouse",
  "Lightning",
  "Line",
  "Lion",
  "Lipstick",
  "Lobster",
  "Lollipop",
  "Mailbox",
  "Map",
  "Marker",
  "Matches",
  "Megaphone",
  "Mermaid",
  "Microphone",
  "Microwave",
  "Monkey",
  "Moon",
  "Mosquito",
  "Motorbike",
  "Mountain",
  "Mouse",
  "Moustache",
  "Mouth",
  "Mug",
  "Mushroom",
  "Nail",
  "Necklace",
  "Nose",
  "Ocean",
  "Octagon",
  "Octopus",
  "Onion",
  "Oven",
  "Owl",
  "Paintbrush",
  "Paint can",
  "Palm tree",
  "Panda",
  "Pants",
  "Paper clip",
  "Parachute",
  "Parrot",
  "Passport",
  "Peanut",
  "Pear",
  "Peas",
  "Pencil",
  "Penguin",
  "Piano",
  "Pickup truck",
  "Picture frame",
  "Pig",
  "Pillow",
  "Pineapple",
  "Pizza",
  "Pliers",
  "Police car",
  "Pond",
  "Pool",
  "Popsicle",
  "Postcard",
  "Potato",
  "Power outlet",
  "Purse",
  "Rabbit",
  "Raccoon",
  "Radio",
  "Rain",
  "Rainbow",
  "Rake",
  "Remote control",
  "Rhinoceros",
  "Rifle",
  "River",
  "Roller coaster",
  "Rollerskates",
  "Sailboat",
  "Sandwich",
  "Saw",
  "Saxophone",
  "School bus",
  "Scissors",
  "Scorpion",
  "Screwdriver",
  "Sea turtle",
  "See saw",
  "Shark",
  "Sheep",
  "Shoe",
  "Shorts",
  "Shovel",
  "Sink",
  "Skateboard",
  "Skull",
  "Skyscraper",
  "Sleeping bag",
  "Smiley face",
  "Snail",
  "Snake",
  "Snorkel",
  "Snowflake",
  "Snowman",
  "Soccer ball",
  "Sock",
  "Speedboat",
  "Spider",
  "Spoon",
  "Spreadsheet",
  "Square",
  "Squiggle",
  "Squirrel",
  "Stairs",
  "Star",
  "Steak",
  "Stereo",
  "Stethoscope",
  "Stitches",
  "Stop sign",
  "Stove",
  "Strawberry",
  "Streetlight",
  "String bean",
  "Submarine",
  "Suitcase",
  "Sun",
  "Swan",
  "Sweater",
  "Swing set",
  "Sword",
  "Syringe",
  "Table",
  "Teapot",
  "Teddy-bear",
  "Telephone",
  "Television",
  "Tennis racquet",
  "Tent",
  "The Eiffel Tower",
  "The Great Wall of China",
  "The Mona Lisa",
  "Tiger",
  "Toaster",
  "Toe",
  "Toilet",
  "Tooth",
  "Toothbrush",
  "Toothpaste",
  "Tornado",
  "Tractor",
  "Traffic light",
  "Train",
  "Tree",
  "Triangle",
  "Trombone",
  "Truck",
  "Trumpet",
  "T-shirt",
  "Umbrella",
  "Underwear",
  "Van",
  "Vase",
  "Violin",
  "Washing machine",
  "Watermelon",
  "Waterslide",
  "Whale",
  "Wheel",
  "Windmill",
  "Wine bottle",
  "Wine glass",
  "Wristwatch",
  "Yoga",
  "Zebra",
  "Zigzag",
];

// Create directory for the game results
if (!fs.existsSync(GAME_DIR)) {
  fs.mkdirSync(GAME_DIR);
}

// Create a log file to track the game progress
const LOG_FILE = path.join(GAME_DIR, "game_log.txt");
fs.writeFileSync(LOG_FILE, "PICTIONARY CHAIN GAME\n=====================\n\n");

// Function to log messages to the log file
function logToFile(message) {
  fs.appendFileSync(LOG_FILE, message + "\n");
}

// Start ComfyUI server
async function startComfyUI() {
  try {
    // Check if ComfyUI is already running
    const alreadyRunning = await checkComfyUIServer();
    if (alreadyRunning) {
      console.log("ComfyUI server is already running.");
      logToFile("ComfyUI server is already running.");
      comfyuiStartedByUs = false; // We didn't start it
      return true;
    }

    console.log("Starting ComfyUI server...");
    logToFile("Starting ComfyUI server...");

    // Check if ComfyUI directory exists
    if (!fs.existsSync(COMFYUI_DIR)) {
      throw new Error(
        `ComfyUI directory not found at ${COMFYUI_DIR}. Please make sure ComfyUI is installed in the ComfyUI subdirectory.`,
      );
    }

    // Check if main.py exists in ComfyUI directory
    const mainPyPath = path.join(COMFYUI_DIR, "main.py");
    if (!fs.existsSync(mainPyPath)) {
      throw new Error(
        `ComfyUI main.py not found at ${mainPyPath}. Please make sure ComfyUI is properly installed.`,
      );
    }

    // Start ComfyUI process
    let pythonPath = process.platform === "win32" ? "python" : "python3";

    // Try to find Python executable
    try {
      await exec(`${pythonPath} --version`);
    } catch (error) {
      // Try alternative Python command
      const altPythonPath = process.platform === "win32" ? "python3" : "python";
      try {
        await exec(`${altPythonPath} --version`);
        pythonPath = altPythonPath;
      } catch (altError) {
        throw new Error(
          `Python not found. Please make sure Python is installed and available in your PATH.`,
        );
      }
    }

    comfyuiProcess = spawn(pythonPath, ["main.py"], {
      cwd: COMFYUI_DIR,
      stdio: ["pipe", "pipe", "pipe"],
      detached: false,
    });

    // Suppress all ComfyUI output
    comfyuiProcess.stdout.on("data", () => {});
    comfyuiProcess.stderr.on("data", () => {});

    comfyuiProcess.on("error", (error) => {
      console.error("Failed to start ComfyUI:", error.message);
      logToFile(`Failed to start ComfyUI: ${error.message}`);
    });

    // Wait for ComfyUI to start up
    console.log("Waiting for ComfyUI to start...");
    logToFile("Waiting for ComfyUI to start...");

    let attempts = 0;
    const maxAttempts = 60; // Wait up to 60 seconds

    while (attempts < maxAttempts) {
      try {
        const response = await axios.get(`${COMFYUI_API_URL}/system_stats`, {
          timeout: 2000,
        });
        if (response.status === 200) {
          console.log("ComfyUI server started successfully!");
          logToFile("ComfyUI server started successfully!");
          comfyuiStartedByUs = true; // We started it
          return true;
        }
      } catch (error) {
        // Server not ready yet, continue waiting
      }

      await new Promise((resolve) => setTimeout(resolve, 1000));
      attempts++;
    }

    throw new Error("ComfyUI failed to start within the timeout period");
  } catch (error) {
    console.error("Error starting ComfyUI:", error.message);
    logToFile(`Error starting ComfyUI: ${error.message}`);

    // Clean up the process if it was created
    if (comfyuiProcess) {
      try {
        comfyuiProcess.kill("SIGKILL");
      } catch (killError) {
        console.error("Error killing ComfyUI process:", killError.message);
      }
      comfyuiProcess = null;
    }

    return false;
  }
}

// Stop ComfyUI server
async function stopComfyUI() {
  try {
    // Only stop if we started it
    if (!comfyuiStartedByUs) {
      console.log("ComfyUI was not started by us, leaving it running.");
      logToFile("ComfyUI was not started by us, leaving it running.");
      return;
    }

    if (comfyuiProcess) {
      console.log("Stopping ComfyUI server...");
      logToFile("Stopping ComfyUI server...");

      // Get the process ID and kill all child processes
      const pid = comfyuiProcess.pid;

      try {
        // On Windows, use taskkill to kill the process tree
        if (process.platform === "win32") {
          await exec(`taskkill /F /T /PID ${pid}`);
        } else {
          // On Unix-like systems, kill the process group
          process.kill(-pid, "SIGTERM");

          // Wait a bit then force kill if needed
          await new Promise((resolve) => setTimeout(resolve, 2000));
          try {
            process.kill(-pid, "SIGKILL");
          } catch (e) {
            // Process might already be dead
          }
        }
      } catch (killError) {
        console.log(
          "Process kill error (might already be dead):",
          killError.message,
        );
      }

      // Wait for the process to terminate
      await new Promise((resolve) => {
        const timeout = setTimeout(() => {
          console.log("Force killing remaining ComfyUI processes...");
          logToFile("Force killing remaining ComfyUI processes...");

          // Try to kill any remaining python processes that might be ComfyUI
          if (process.platform === "win32") {
            exec("taskkill /F /IM python.exe").catch(() => {});
          } else {
            exec("pkill -f 'python.*main.py'").catch(() => {});
          }
          resolve();
        }, 3000); // Wait 3 seconds before force kill

        comfyuiProcess.on("close", (code) => {
          clearTimeout(timeout);
          console.log(`ComfyUI process exited with code ${code}`);
          logToFile(`ComfyUI process exited with code ${code}`);
          resolve();
        });
      });

      comfyuiProcess = null;
      comfyuiStartedByUs = false;
      console.log("ComfyUI server stopped successfully!");
      logToFile("ComfyUI server stopped successfully!");
    }
  } catch (error) {
    console.error("Error stopping ComfyUI:", error.message);
    logToFile(`Error stopping ComfyUI: ${error.message}`);
  }
}

// Start Ollama service
async function startOllama() {
  try {
    // Check if Ollama is already running
    const alreadyRunning = await checkOllamaStatus();
    if (alreadyRunning) {
      console.log("Ollama service is already running.");
      logToFile("Ollama service is already running.");
      ollamaStartedByUs = false; // We didn't start it
      return true;
    }

    console.log("Starting Ollama service...");
    logToFile("Starting Ollama service...");

    // Start Ollama process
    const ollamaPath = process.platform === "win32" ? "ollama" : "ollama";

    // Try to find Ollama executable
    try {
      await exec(`${ollamaPath} --version`);
    } catch (error) {
      throw new Error(
        `Ollama not found. Please make sure Ollama is installed and available in your PATH.`,
      );
    }

    ollamaProcess = spawn(ollamaPath, ["serve"], {
      stdio: ["pipe", "pipe", "pipe"],
      detached: false,
    });

    // Suppress all Ollama output
    ollamaProcess.stdout.on("data", () => {});
    ollamaProcess.stderr.on("data", () => {});

    ollamaProcess.on("error", (error) => {
      console.error("Failed to start Ollama:", error.message);
      logToFile(`Failed to start Ollama: ${error.message}`);
    });

    // Wait for Ollama to start up
    console.log("Waiting for Ollama to start...");
    logToFile("Waiting for Ollama to start...");

    let attempts = 0;
    const maxAttempts = 30; // Wait up to 30 seconds

    while (attempts < maxAttempts) {
      try {
        const response = await axios.get(`${OLLAMA_BASE_URL}/api/tags`, {
          timeout: 2000,
        });
        if (response.status === 200) {
          console.log("Ollama service started successfully!");
          logToFile("Ollama service started successfully!");
          ollamaStartedByUs = true; // We started it
          return true;
        }
      } catch (error) {
        // Server not ready yet, continue waiting
      }

      await new Promise((resolve) => setTimeout(resolve, 1000));
      attempts++;
    }

    throw new Error("Ollama failed to start within the timeout period");
  } catch (error) {
    console.error("Error starting Ollama:", error.message);
    logToFile(`Error starting Ollama: ${error.message}`);

    // Clean up the process if it was created
    if (ollamaProcess) {
      try {
        ollamaProcess.kill("SIGKILL");
      } catch (killError) {
        console.error("Error killing Ollama process:", killError.message);
      }
      ollamaProcess = null;
    }

    return false;
  }
}

// Stop Ollama service
async function stopOllama() {
  try {
    // Only stop if we started it
    if (!ollamaStartedByUs) {
      console.log("Ollama was not started by us, leaving it running.");
      logToFile("Ollama was not started by us, leaving it running.");
      return;
    }

    if (ollamaProcess) {
      console.log("Stopping Ollama service...");
      logToFile("Stopping Ollama service...");

      // Get the process ID and kill all child processes
      const pid = ollamaProcess.pid;

      try {
        // On Windows, use taskkill to kill the process tree
        if (process.platform === "win32") {
          await exec(`taskkill /F /T /PID ${pid}`);
        } else {
          // On Unix-like systems, kill the process group
          process.kill(-pid, "SIGTERM");

          // Wait a bit then force kill if needed
          await new Promise((resolve) => setTimeout(resolve, 2000));
          try {
            process.kill(-pid, "SIGKILL");
          } catch (e) {
            // Process might already be dead
          }
        }
      } catch (killError) {
        console.log(
          "Process kill error (might already be dead):",
          killError.message,
        );
      }

      // Wait for the process to terminate
      await new Promise((resolve) => {
        const timeout = setTimeout(() => {
          console.log("Force killing remaining Ollama processes...");
          logToFile("Force killing remaining Ollama processes...");

          // Try to kill any remaining ollama processes
          if (process.platform === "win32") {
            exec("taskkill /F /IM ollama.exe").catch(() => {});
          } else {
            exec("pkill -f ollama").catch(() => {});
          }
          resolve();
        }, 3000); // Wait 3 seconds before force kill

        ollamaProcess.on("close", (code) => {
          clearTimeout(timeout);
          console.log(`Ollama process exited with code ${code}`);
          logToFile(`Ollama process exited with code ${code}`);
          resolve();
        });
      });

      ollamaProcess = null;
      ollamaStartedByUs = false;
      console.log("Ollama service stopped successfully!");
      logToFile("Ollama service stopped successfully!");
    }
  } catch (error) {
    console.error("Error stopping Ollama:", error.message);
    logToFile(`Error stopping Ollama: ${error.message}`);
  }
}

// Check if ComfyUI server is running
async function checkComfyUIServer() {
  try {
    const response = await axios.get(`${COMFYUI_API_URL}/system_stats`);
    return response.status === 200;
  } catch (error) {
    return false;
  }
}

// Function to check if Ollama is running and model is available
async function checkOllamaStatus() {
  try {
    const response = await axios.get(`${OLLAMA_BASE_URL}/api/tags`);
    const availableModels = response.data.models.map((m) => m.name);

    if (!availableModels.some((model) => model.includes("llava"))) {
      console.log("LLaVA model not found. Please run: ollama pull llava:13b");
      return false;
    }
    return true;
  } catch (error) {
    console.log("Ollama not running. Please start Ollama first.");
    return false;
  }
}

// Load the ComfyUI workflow template
function loadWorkflowTemplate() {
  // This is the path to your workflow template JSON file
  // You'll need to create this file using ComfyUI and export it
  const templatePath = path.join(
    __dirname,
    "pictionary_workflow_template.json",
  );
  if (!fs.existsSync(templatePath)) {
    throw new Error(
      `Workflow template not found at ${templatePath}. You need to create a ComfyUI workflow and save it as JSON.`,
    );
  }
  return JSON.parse(fs.readFileSync(templatePath, "utf8"));
}

// Generate an image using ComfyUI
async function generateImage(prompt, roundNumber) {
  try {
    console.log(`Generating image for: "${prompt}"...`);
    logToFile(`Generating image for: "${prompt}"...`);

    // Load the workflow template
    const workflow = loadWorkflowTemplate();

    // Set a random seed for the KSampler node
    for (const nodeId in workflow) {
      if (workflow[nodeId]._meta.title === "KSampler") {
        workflow[nodeId].inputs.seed = Math.floor(Math.random() * 4294967295); // 32-bit unsigned int
      }
      if (workflow[nodeId]._meta.title === "Positive Prompt") {
        workflow[nodeId].inputs.text = getPictionaryPrompt(prompt);
      }
    }

    // Queue the prompt
    const promptResponse = await axios.post(`${COMFYUI_API_URL}/prompt`, {
      prompt: workflow,
    });
    const promptId = promptResponse.data.prompt_id;

    // Wait for the image to be generated
    let imageFilename = null;
    let complete = false;
    let maxTries = 60; // Wait up to 60 seconds

    while (!complete && maxTries > 0) {
      await new Promise((resolve) => setTimeout(resolve, 1000)); // Wait 1 second

      const historyResponse = await axios.get(
        `${COMFYUI_API_URL}/history/${promptId}`,
      );
      if (
        historyResponse.data &&
        historyResponse.data[promptId] &&
        historyResponse.data[promptId].outputs
      ) {
        for (const nodeId in historyResponse.data[promptId].outputs) {
          const output = historyResponse.data[promptId].outputs[nodeId];
          if (output.images && output.images.length > 0) {
            imageFilename = output.images[0].filename;
            complete = true;
            break;
          }
        }
      }

      maxTries--;
    }

    if (!imageFilename) {
      throw new Error("Failed to generate image within the timeout period");
    }

    // Download the image
    const imageResponse = await axios.get(
      `${COMFYUI_API_URL}/view?filename=${imageFilename}`,
      {
        responseType: "arraybuffer",
      },
    );

    // Save the image to a file
    const localImagePath = path.join(
      GAME_DIR,
      `round_${roundNumber}.png`,
    );
    fs.writeFileSync(localImagePath, Buffer.from(imageResponse.data));

    console.log(`Image saved to: ${localImagePath}`);
    logToFile(`Image saved to: ${path.basename(localImagePath)}`);

    return localImagePath;
  } catch (error) {
    console.error("Error generating image:", error.message);
    logToFile(`Error generating image: ${error.message}`);
    return null;
  }
}

// Function to encode the image to base64
function encodeImage(imagePath) {
  const imageBuffer = fs.readFileSync(imagePath);
  return imageBuffer.toString("base64");
}

// Function to get a deliberately incorrect but plausible guess for the image
async function getPlausibleWrongGuess(
  imagePath,
  actualWord,
  recentCorrectGuesses = 0,
) {
  try {
    console.log("Analyzing image locally with Ollama...");
    logToFile("Analyzing image locally with Ollama...");

    const base64Image = encodeImage(imagePath);

    // First attempt - don't tell the model the correct answer
    let prompt = `You are an AI playing Pictionary. Analyze this drawing and respond with ONLY a single word or short phrase that you think it represents. Do not include any explanations, labels, or additional text. Just the guess word/phrase.`;

    const response = await axios.post(
      `${OLLAMA_BASE_URL}/api/generate`,
      {
        model: MODEL_NAME,
        prompt: prompt,
        images: [base64Image],
        stream: false,
        options: {
          temperature: 1.2,
          top_p: 0.9,
          max_tokens: 50,
        },
      },
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
    );

    let guess = response.data.response.trim();
    guess = guess.replace(/[.!?]+$/, ""); // Remove trailing punctuation
    guess = guess.charAt(0).toUpperCase() + guess.slice(1); // Capitalize

    // Check if the guess was correct
    if (guess.toLowerCase().trim() === actualWord.toLowerCase().trim()) {
      // 30% chance to allow the correct guess
      const allowCorrectGuess = Math.random() < 0.3;

      if (allowCorrectGuess) {
        console.log(
          `Model guessed correctly: "${guess}". Allowing this correct guess (30% chance).`,
        );
        logToFile(
          `Model guessed correctly: "${guess}". Allowing this correct guess (30% chance).`,
        );
      } else {
        console.log(
          `Model guessed correctly: "${guess}". Asking for a different guess...`,
        );
        logToFile(
          `Model guessed correctly: "${guess}". Asking for a different guess...`,
        );

        // Second attempt - now tell it the correct answer and ask for something else
        const retryPrompt = `You are an AI playing Pictionary. The actual word being drawn is: "${actualWord}". You guessed correctly, but I need you to provide a DIFFERENT guess - something that is NOT the correct answer. Analyze the drawing and respond with ONLY a single word or short phrase that is plausible but wrong. Do not include any explanations, labels, or additional text. Just the guess word/phrase.`;

        const retryResponse = await axios.post(
          `${OLLAMA_BASE_URL}/api/generate`,
          {
            model: MODEL_NAME,
            prompt: retryPrompt,
            images: [base64Image],
            stream: false,
            options: {
              temperature: 1.2,
              top_p: 0.9,
              max_tokens: 50,
            },
          },
          {
            headers: {
              "Content-Type": "application/json",
            },
          },
        );

        guess = retryResponse.data.response.trim();
        guess = guess.replace(/[.!?]+$/, ""); // Remove trailing punctuation
        guess = guess.charAt(0).toUpperCase() + guess.slice(1); // Capitalize
      }
    }

    return guess;
  } catch (error) {
    console.error("Error analyzing image:");
    if (error.response) {
      console.error("Ollama response:", error.response.data);
    } else {
      console.error(error.message);
    }
    return null;
  }
}

// Function to create an HTML file to view all game results
function createHtmlIndex(numRounds) {
  let html = `
  <!DOCTYPE html>
  <html>
  <head>
    <title>Pictionary Chain Game</title>
    <style>
      body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
      h1 { text-align: center; }
      .round { margin-bottom: 30px; border: 1px solid #ccc; padding: 15px; border-radius: 5px; }
      .round h2 { margin-top: 0; }
      .guess { font-size: 1.2em; font-weight: bold; }
      .image-container { text-align: center; margin: 15px 0; }
      img { max-width: 100%; height: auto; border: 1px solid #eee; }
      .prompt { font-style: italic; color: #666; }
    </style>
  </head>
  <body>
    <h1>Pictionary Chain Game</h1>
  `;

  // Get all image files and sort them by round number
  const files = fs.readdirSync(GAME_DIR);
  const rounds = {};

  files.forEach((file) => {
    if (file.startsWith("round_") && file.endsWith(".png")) {
      const roundNumber = parseInt(file.split("_")[1]);
      if (!rounds[roundNumber]) {
        rounds[roundNumber] = {};
      }
      rounds[roundNumber].image = file;
    } else if (file.startsWith("round_") && file.endsWith("_summary.txt")) {
      const roundNumber = parseInt(file.split("_")[1]);
      if (!rounds[roundNumber]) {
        rounds[roundNumber] = {};
      }
      rounds[roundNumber].summary = file;
    }
  });

  // Add each round to the HTML
  for (let round = 1; round <= numRounds; round++) {
    if (rounds[round]) {
      const summaryPath = path.join(GAME_DIR, rounds[round].summary);
      let actualWord = "";
      let wrongGuess = "";

      if (fs.existsSync(summaryPath)) {
        const summary = fs.readFileSync(summaryPath, "utf8");
        const actualWordMatch = summary.match(/Actual Word: (.*)/);
        const wrongGuessMatch = summary.match(/AI's Wrong Guess: (.*)/);

        if (actualWordMatch) actualWord = actualWordMatch[1];
        if (wrongGuessMatch) wrongGuess = wrongGuessMatch[1];
      }

      html += `
      <div class="round">
        <h2>Round ${round}</h2>
        <p class="prompt">Prompt: "${actualWord}"</p>
        <div class="image-container">
          <img src="${rounds[round].image}" alt="Drawing of ${actualWord}">
        </div>
        <p class="guess">AI's wrong guess: "${wrongGuess}"</p>
      </div>
      `;
    }
  }

  html += `
  </body>
  </html>
  `;

  fs.writeFileSync(path.join(GAME_DIR, "index.html"), html);
  console.log(`Created HTML summary: ${path.join(GAME_DIR, "index.html")}`);
  logToFile(`Created HTML summary: index.html`);
}

// Main function to run the game
async function runGame(numRounds = 10, startWord = null) {
  try {
    // Start ComfyUI server
    const serverStarted = await startComfyUI();
    if (!serverStarted) {
      console.error("Failed to start ComfyUI server. Stopping game.");
      return null;
    }

    // Start Ollama service
    const ollamaStarted = await startOllama();
    if (!ollamaStarted) {
      console.error("Failed to start Ollama service. Stopping game.");
      return null;
    }

    // Load the Ollama model into memory
    const modelLoaded = await loadOllamaModel();
    if (!modelLoaded) {
      console.error("Failed to load Ollama model. Stopping game.");
      return null;
    }

    // Use provided start word or select a random starter word
    let currentWord =
      startWord ||
      STARTER_WORDS[Math.floor(Math.random() * STARTER_WORDS.length)];

    console.log("\n🎮 PICTIONARY CHAIN GAME 🎮");
    console.log("=========================");
    console.log(`Starting word: "${currentWord}"`);
    logToFile(`ROUND 1: Starting with word: "${currentWord}"\n`);

    for (let round = 1; round <= numRounds; round++) {
      console.log(`\n📝 Round ${round}: Drawing "${currentWord}"...`);

      // Generate an image based on the current word
      const imagePath = await generateImage(currentWord, round);
      if (!imagePath) {
        console.error(
          `Failed to generate image for round ${round}. Stopping game.`,
        );
        logToFile(
          `Failed to generate image for round ${round}. Stopping game.`,
        );
        break;
      }

      // Get a wrong guess based on the image
      const wrongGuess = await getPlausibleWrongGuess(imagePath, currentWord);
      if (!wrongGuess) {
        console.error(
          `Failed to get a wrong guess for round ${round}. Stopping game.`,
        );
        logToFile(
          `Failed to get a wrong guess for round ${round}. Stopping game.`,
        );
        break;
      }

      // Check if the guess was correct (this should rarely happen now)
      const isCorrectGuess =
        wrongGuess.toLowerCase().trim() === currentWord.toLowerCase().trim();

      if (isCorrectGuess) {
        console.log(`🎯 Correct guess: "${wrongGuess}"`);
        logToFile(`AI's correct guess: "${wrongGuess}"\n`);
      } else {
        console.log(`🤔 Wrong guess: "${wrongGuess}"`);
        logToFile(`AI's wrong guess: "${wrongGuess}"\n`);
      }

      // Create a text file for this round
      const roundFilePath = path.join(GAME_DIR, `round_${round}_summary.txt`);
      fs.writeFileSync(
        roundFilePath,
        `Round ${round}\n` +
          `--------\n` +
          `Actual Word: ${currentWord}\n` +
          `Image File: ${path.basename(imagePath)}\n` +
          `AI's Guess: ${wrongGuess}\n` +
          `Was Correct: ${isCorrectGuess}\n`,
      );

      // Set up for the next round
      if (round < numRounds) {
        currentWord = wrongGuess;
        console.log(`Next round will use: "${currentWord}"`);
        logToFile(`ROUND ${round + 1}: Using word: "${currentWord}"\n`);
      }
    }

    console.log("\n🎉 Game complete! 🎉");
    console.log(`All game files saved to: ${GAME_DIR}`);

    // Create an index.html file to view all results
    createHtmlIndex(numRounds);

    // Stop Ollama service
    await stopOllama();

    // Stop ComfyUI server
    await stopComfyUI();

    return GAME_DIR;
  } catch (error) {
    console.error("Game error:", error);
    logToFile(`Game error: ${error.message}`);

    // Try to stop Ollama even if there was an error
    try {
      await stopOllama();
    } catch (stopError) {
      console.error(
        "Error stopping Ollama after game error:",
        stopError.message,
      );
    }

    // Try to stop ComfyUI even if there was an error
    try {
      await stopComfyUI();
    } catch (stopError) {
      console.error(
        "Error stopping ComfyUI after game error:",
        stopError.message,
      );
    }

    return null;
  }
}

// Ollama service should be running for local image analysis

// Cleanup function to handle script termination
async function cleanup() {
  console.log("\nCleaning up...");
  try {
    await stopComfyUI();
    await stopOllama();
  } catch (error) {
    console.error("Error during cleanup:", error.message);
  }
  process.exit(0);
}

// Handle process termination signals
process.on("SIGINT", cleanup);
process.on("SIGTERM", cleanup);

// Parse command line arguments
const customStartWord = process.argv[2];

// Run the game with 10 rounds and optional custom start word
runGame(10, customStartWord)
  .then((gameDir) => {
    if (gameDir) {
      console.log("\nGame files are in:", gameDir);
    }
  })
  .catch((error) => {
    console.error("Failed to run game:", error);
  });

// Function to ensure the Ollama model is available with retry logic
async function loadOllamaModel(maxRetries = 5, baseDelay = 2000) {
  console.log(`Trying to load model: ${MODEL_NAME}`);
  logToFile(`Trying to load model: ${MODEL_NAME}`);

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(
        `Attempt ${attempt}/${maxRetries} to load model ${MODEL_NAME}...`,
      );
      logToFile(
        `Attempt ${attempt}/${maxRetries} to load model ${MODEL_NAME}...`,
      );

      // First check if the model is already available
      try {
        const statusResponse = await axios.get(`${OLLAMA_BASE_URL}/api/tags`);
        const availableModels = statusResponse.data.models.map((m) => m.name);

        if (availableModels.includes(MODEL_NAME)) {
          console.log(`Model ${MODEL_NAME} is already available!`);
          logToFile(`Model ${MODEL_NAME} is already available!`);
          return true;
        }
      } catch (statusError) {
        console.log("Could not check model status, proceeding with pull...");
        logToFile("Could not check model status, proceeding with pull...");
      }

      // Try to pull the model
      const response = await axios.post(
        `${OLLAMA_BASE_URL}/api/pull`,
        {
          name: MODEL_NAME,
          stream: false,
        },
        {
          headers: {
            "Content-Type": "application/json",
          },
          timeout: 30000, // 30 second timeout
        },
      );

      console.log(`Model ${MODEL_NAME} is available and ready to use`);
      logToFile(`Model ${MODEL_NAME} is available and ready to use`);
      return true;
    } catch (error) {
      const isLastAttempt = attempt === maxRetries;
      const errorMessage = error.response
        ? `HTTP ${error.response.status}: ${error.response.statusText}`
        : error.message;

      console.error(
        `Attempt ${attempt}/${maxRetries} failed for ${MODEL_NAME}: ${errorMessage}`,
      );
      logToFile(
        `Attempt ${attempt}/${maxRetries} failed for ${MODEL_NAME}: ${errorMessage}`,
      );

      // Log detailed error information
      if (error.response) {
        console.error(`Response status: ${error.response.status}`);
        console.error(`Response data:`, error.response.data);
        logToFile(`Response status: ${error.response.status}`);
        logToFile(`Response data: ${JSON.stringify(error.response.data)}`);
      }

      // If this is the last attempt, return false
      if (isLastAttempt) {
        console.error(
          `Failed to load model ${MODEL_NAME} after ${maxRetries} attempts.`,
        );
        logToFile(
          `Failed to load model ${MODEL_NAME} after ${maxRetries} attempts.`,
        );
        return false;
      }

      // Calculate delay with exponential backoff
      const delay = baseDelay * Math.pow(2, attempt - 1);
      const jitter = Math.random() * 1000; // Add up to 1 second of random jitter
      const totalDelay = delay + jitter;

      console.log(
        `Waiting ${Math.round(totalDelay / 1000)} seconds before retry...`,
      );
      logToFile(
        `Waiting ${Math.round(totalDelay / 1000)} seconds before retry...`,
      );

      // Wait before retrying
      await new Promise((resolve) => setTimeout(resolve, totalDelay));
    }
  }

  return false;
}
