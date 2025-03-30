/**
 * Prompt templates for the Pictionary Chain Game
 */

/**
 * Returns the formatted prompt for generating pictionary-style images
 * @param {string} prompt - The base word to create an image for
 * @returns {string} - The formatted prompt for the image generation model
 */
function getPictionaryPrompt(prompt) {
  return `A minimalist vector-style line drawing of a ${prompt}, as if drawn using basic computer drawing software. Only black outlines on white background, no shading, no texture, extremely simple like a pictionary game. Use as few straight lines as possible, like a stick figure version.`;
}

module.exports = {
  getPictionaryPrompt,
};
