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
  "elephant",
  "bicycle",
  "pizza",
  "airplane",
  "guitar",
  "cat",
  "lighthouse",
  "umbrella",
  "cactus",
  "submarine",
  "hamburger",
  "rocket",
  "penguin",
  "castle",
  "volcano",
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

    // Update the prompt in the workflow
    // This assumes your workflow has a node with the class_type "CLIPTextEncode"
    // Modify this to match your actual workflow structure
    for (const nodeId in workflow) {
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
async function getPlausibleWrongGuess(imagePath, actualWord, usedWords) {
  try {
    console.log("Analyzing image and generating a plausible wrong guess...");
    logToFile("Analyzing image and generating a plausible wrong guess...");

    const base64Image = encodeImage(imagePath);

    // Convert usedWords Set to an array for the prompt
    const usedWordsList = Array.from(usedWords).join('", "');

    const response = await axios.post(
      "https://api.openai.com/v1/chat/completions",
      {
        model: "gpt-4o",
        messages: [
          {
            role: "system",
            content: `You are an AI playing Pictionary. Your job is to analyze the drawing and provide a DELIBERATELY INCORRECT but plausible guess - something that's close enough that a human might reasonably guess it when seeing the drawing, but definitely not the exact right answer. The actual word represented is "${actualWord}", so do NOT say this as your guess. Additionally, you must NOT use any of these previously used words: "${usedWordsList}". Make your guess a single word or short phrase like a real Pictionary player would.`,
          },
          {
            role: "user",
            content: [
              {
                type: "text",
                text: "What does this Pictionary drawing look like? Please give me a plausible WRONG answer - something that's close to what it might be but deliberately incorrect. Just give me the guess as a single word or short phrase, with no explanations.",
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

    // Double check that the guess isn't in usedWords (case insensitive)
    const normalizedGuess = guess.toLowerCase();
    if (
      Array.from(usedWords).some(
        (word) => word.toLowerCase() === normalizedGuess
      )
    ) {
      // If the guess is in usedWords, try again with a more explicit prompt
      return getPlausibleWrongGuess(imagePath, actualWord, usedWords);
    }

    return guess;
  } catch (error) {
    console.error("Error analyzing image:");
    if (error.response) {
      console.error(error.response.data);
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

    // Keep track of all words used in the game
    const usedWords = new Set([currentWord]);

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
      const wrongGuess = await getPlausibleWrongGuess(
        imagePath,
        currentWord,
        usedWords
      );
      if (!wrongGuess) {
        console.error(
          `Failed to get a wrong guess for round ${round}. Stopping game.`
        );
        logToFile(
          `Failed to get a wrong guess for round ${round}. Stopping game.`
        );
        break;
      }

      // Add the wrong guess to used words
      usedWords.add(wrongGuess);

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

      // Open the HTML file in default browser if we're on Windows
      if (process.platform === "win32") {
        exec(`start ${path.join(gameDir, "index.html")}`);
      } else if (process.platform === "darwin") {
        // macOS
        exec(`open ${path.join(gameDir, "index.html")}`);
      } else {
        // Linux
        exec(`xdg-open ${path.join(gameDir, "index.html")}`);
      }
    }
  })
  .catch((error) => {
    console.error("Failed to run game:", error);
  });
