// OpenAI Image Generator Script
// This script takes a word prompt and generates a hand-drawn style image using OpenAI's DALL-E API

const axios = require("axios");
const fs = require("fs");
const path = require("path");
const readline = require("readline");

// Set up readline interface for user input
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

// Configure your OpenAI API key here
const OPENAI_API_KEY =
  "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";

// Function to generate an image using OpenAI API
async function generateImage(prompt) {
  try {
    console.log(`Generating hand-drawn image for: "${prompt}"...`);

    const response = await axios.post(
      "https://api.openai.com/v1/images/generations",
      {
        model: "dall-e-3", // Using DALL-E 3 for higher quality images
        prompt: `A single, extremely simple drawing of exactly one of ${prompt}. Just basic black lines on a plain white background. Imagine a quick sketch made with a black pen on a computer in 10 seconds. Keep it minimalist - just the essential lines needed to recognize the concept. Nothing else in the image.`,
        n: 1, // Number of images to generate
        size: "1024x1024", // Image size
        quality: "standard",
        style: "natural", // For a more illustrative style
      },
      {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${OPENAI_API_KEY}`,
        },
      }
    );

    return response.data.data[0].url;
  } catch (error) {
    console.error("Error generating image:");
    if (error.response) {
      console.error(error.response.data);
    } else {
      console.error(error.message);
    }
    return null;
  }
}

// Function to download the generated image
async function downloadImage(imageUrl, prompt) {
  try {
    const response = await axios({
      url: imageUrl,
      method: "GET",
      responseType: "stream",
    });

    // Create directory if it doesn't exist
    const outputDir = path.join(__dirname, "generated-images");
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir);
    }

    // Create sanitized filename from prompt
    const sanitizedPrompt = prompt.replace(/[^a-z0-9]/gi, "_").toLowerCase();
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const filename = `${sanitizedPrompt}_${timestamp}.png`;
    const outputPath = path.join(outputDir, filename);

    // Save the image
    const writer = fs.createWriteStream(outputPath);
    response.data.pipe(writer);

    return new Promise((resolve, reject) => {
      writer.on("finish", () => resolve(outputPath));
      writer.on("error", reject);
    });
  } catch (error) {
    console.error("Error downloading image:", error.message);
    return null;
  }
}

// Main function to run the script
async function main() {
  rl.question(
    "Enter a word or phrase to generate a hand-drawn image: ",
    async (prompt) => {
      if (prompt.trim() === "") {
        console.log("Please enter a valid prompt.");
        rl.close();
        return;
      }

      const imageUrl = await generateImage(prompt);

      if (imageUrl) {
        console.log("Image generated successfully!");
        console.log("Image URL:", imageUrl);

        const savedPath = await downloadImage(imageUrl, prompt);
        if (savedPath) {
          console.log(`Image downloaded and saved to: ${savedPath}`);
        }
      }

      rl.close();
    }
  );
}

// Check if API key is configured
if (OPENAI_API_KEY === "your-api-key-here") {
  console.log("Please set your OpenAI API key in the script before running.");
  process.exit(1);
}

// Run the script
main();
