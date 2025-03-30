// Pictionary AI Incorrect Guesser
// This script takes an image and returns a plausible but incorrect guess using OpenAI's Vision API

const axios = require("axios");
const fs = require("fs");
const path = require("path");
const readline = require("readline");
const FormData = require("form-data");

// Set up readline interface for user input
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

// Configure your OpenAI API key here
const OPENAI_API_KEY =
  "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"; // Replace with your actual API key

// Function to encode the image to base64
function encodeImage(imagePath) {
  const imageBuffer = fs.readFileSync(imagePath);
  return imageBuffer.toString("base64");
}

// Function to get a deliberately incorrect but plausible guess for the image
async function getPlausibleWrongGuess(imagePath) {
  try {
    console.log("Analyzing image and generating a plausible wrong guess...");

    const base64Image = encodeImage(imagePath);

    const response = await axios.post(
      "https://api.openai.com/v1/chat/completions",
      {
        model: "gpt-4o",
        messages: [
          {
            role: "system",
            content:
              "You are an AI playing Pictionary. Your job is to analyze the drawing and provide a DELIBERATELY INCORRECT but plausible guess - something that's close enough that a human might reasonably guess it when seeing the drawing, but definitely not the exact right answer. Make your guess a single word or short phrase like a real Pictionary player would.",
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

    return response.data.choices[0].message.content.trim();
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

// Main function to run the script
async function main() {
  rl.question("Enter the path to the Pictionary image: ", async (imagePath) => {
    if (!imagePath.trim() || !fs.existsSync(imagePath)) {
      console.log("Please enter a valid image path.");
      rl.close();
      return;
    }

    // Then get the plausible wrong guess
    const wrongGuess = await getPlausibleWrongGuess(imagePath);

    if (wrongGuess) {
      console.log("\n🎮 Pictionary AI Incorrect Guess 🎮");
      console.log("---------------------------------");
      console.log(`AI's guess: "${wrongGuess}"`);
    }

    rl.close();
  });
}

// Check if API key is configured
if (OPENAI_API_KEY === "your-api-key-here") {
  console.log("Please set your OpenAI API key in the script before running.");
  process.exit(1);
}

// Run the script
main();
