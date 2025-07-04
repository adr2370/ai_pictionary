/**
 * Prompt templates for the Pictionary Chain Game
 */

/**
 * Returns the formatted prompt for generating pictionary-style images
 * @param {string} prompt - The base word to create an image for
 * @returns {string} - The formatted prompt for the image generation model
 */
function getPictionaryPrompt(prompt) {
  return `(${prompt}:1.3), simple line drawing, minimalist sketch, clean black lines only, (white background:1.2), monochrome, black and white only`;
}

module.exports = {
  getPictionaryPrompt,
};
