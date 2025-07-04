// Pictionary Chain Game Generator using Local ComfyUI
// This script chains together image generation and guessing in a loop
// creating a fun sequence of pictionary drawings and guesses

const axios = require("axios");
const fs = require("fs");
const path = require("path");
const { promisify } = require("util");
const exec = promisify(require("child_process").exec);
const { getPictionaryPrompt } = require("./promptTemplates");

// Configuration
const COMFYUI_API_URL = "http://127.0.0.1:8188"; // Local ComfyUI server address
const OPENAI_API_KEY =
  "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"; // Still need this for the guessing part
const GAMES_ROOT = path.join(__dirname, "games");
if (!fs.existsSync(GAMES_ROOT)) {
  fs.mkdirSync(GAMES_ROOT);
}
const GAME_DIR = path.join(GAMES_ROOT, "pictionary_game_" + Date.now());

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

// Check if ComfyUI server is running
async function checkComfyUIServer() {
  try {
    const response = await axios.get(`${COMFYUI_API_URL}/system_stats`);
    return response.status === 200;
  } catch (error) {
    return false;
  }
}

// Load the ComfyUI workflow template
function loadWorkflowTemplate() {
  // This is the path to your workflow template JSON file
  // You'll need to create this file using ComfyUI and export it
  const templatePath = path.join(
    __dirname,
    "pictionary_workflow_template.json"
  );
  if (!fs.existsSync(templatePath)) {
    throw new Error(
      `Workflow template not found at ${templatePath}. You need to create a ComfyUI workflow and save it as JSON.`
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
        `${COMFYUI_API_URL}/history/${promptId}`
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
      }
    );

    // Save the image to a file
    const sanitizedPrompt = prompt.replace(/[^a-z0-9]/gi, "_").toLowerCase();
    const localImagePath = path.join(
      GAME_DIR,
      `round_${roundNumber}_${sanitizedPrompt}.png`
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
async function getPlausibleWrongGuess(imagePath) {
  try {
    console.log("Analyzing image and generating a plausible wrong guess...");
    logToFile("Analyzing image and generating a plausible wrong guess...");

    const base64Image = encodeImage(imagePath);

    const response = await axios.post(
      "https://api.openai.com/v1/chat/completions",
      {
        model: "gpt-4o",
        messages: [
          {
            role: "system",
            content: `You are an AI playing Pictionary. Analyze the drawing and provide a plausible but deliberately incorrect guess—a word or short phrase that a human might reasonably guess, but is not the exact right answer. Do not ask questions or provide explanations; just give the guess as a single word or short phrase.`,
          },
          {
            role: "user",
            content: [
              {
                type: "text",
                text: "What does this Pictionary drawing look like? Please give me a plausible WRONG answer—something that's close to what it might be but deliberately incorrect. Just give me the guess as a single word or short phrase, with no explanations.",
              },
              {
                type: "image_url",
                image_url: {
                  url: `data:image/jpeg;base64,${base64Image}`,
                },
              },
            ],
          },
        ],
        max_tokens: 100,
      },
      {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${OPENAI_API_KEY}`,
        },
      }
    );

    const guess = response.data.choices[0].message.content.trim();

    // Remove any trailing period, exclamation mark, or question mark
    const cleanedGuess = guess.replace(/[.!?]+$/, "");

    // Capitalize the guess
    return cleanedGuess.charAt(0).toUpperCase() + cleanedGuess.slice(1);
  } catch (error) {
    console.error("Error analyzing image:");
    if (error.response) {
      console.error("OpenAI response:", error.response.data);
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
    // Check if ComfyUI server is running
    const serverRunning = await checkComfyUIServer();
    if (!serverRunning) {
      console.error(
        "ComfyUI server is not running. Please start the server first."
      );
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
          `Failed to generate image for round ${round}. Stopping game.`
        );
        logToFile(
          `Failed to generate image for round ${round}. Stopping game.`
        );
        break;
      }

      // Get a wrong guess based on the image
      const wrongGuess = await getPlausibleWrongGuess(imagePath);
      if (!wrongGuess) {
        console.error(
          `Failed to get a wrong guess for round ${round}. Stopping game.`
        );
        logToFile(
          `Failed to get a wrong guess for round ${round}. Stopping game.`
        );
        break;
      }

      console.log(`🤔 Wrong guess: "${wrongGuess}"`);
      logToFile(`AI's wrong guess: "${wrongGuess}"\n`);

      // Create a text file for this round
      const roundFilePath = path.join(GAME_DIR, `round_${round}_summary.txt`);
      fs.writeFileSync(
        roundFilePath,
        `Round ${round}\n` +
          `--------\n` +
          `Actual Word: ${currentWord}\n` +
          `Image File: ${path.basename(imagePath)}\n` +
          `AI's Wrong Guess: ${wrongGuess}\n`
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

    return GAME_DIR;
  } catch (error) {
    console.error("Game error:", error);
    logToFile(`Game error: ${error.message}`);
    return null;
  }
}

// Check if API key is configured
if (OPENAI_API_KEY === "your-api-key-here") {
  console.log("Please set your OpenAI API key in the script before running.");
  process.exit(1);
}

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
