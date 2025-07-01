#!/usr/bin/env python3
"""
Complete QuickDraw LoRA Dataset Preprocessor
Downloads, processes, and organizes QuickDraw data for LoRA training in ComfyUI
"""

import os
import json
import random
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import shutil
from typing import List, Dict, Tuple

class QuickDrawLoRAPreprocessor:
    def __init__(self, 
                 base_output_dir: str = "quickdraw_lora_training",
                 image_size: int = 512,
                 images_per_category: int = 50):
        """
        Initialize the preprocessor
        
        Args:
            base_output_dir: Main directory for all output
            image_size: Size of generated images (512 recommended for LoRA)
            images_per_category: Number of images to process per category
        """
        self.base_output_dir = base_output_dir
        self.image_size = image_size
        self.images_per_category = images_per_category
        
        # Create directory structure
        self.raw_data_dir = os.path.join(base_output_dir, "01_raw_ndjson")
        self.processed_dir = os.path.join(base_output_dir, "02_processed_images")
        self.training_dir = os.path.join(base_output_dir, "03_training_data", "quickdraw_sketches", "25_sketch drawings")
        
        for directory in [self.raw_data_dir, self.processed_dir, self.training_dir]:
            os.makedirs(directory, exist_ok=True)
        
        # Base URL for QuickDraw dataset
        self.base_url = "https://storage.googleapis.com/quickdraw_dataset/full/simplified/"
        
        # Caption templates for variety
        self.caption_templates = [
            "a hand-drawn sketch of {category}",
            "simple line drawing of {category}",
            "black and white sketch of {category}",
            "pencil drawing of {category}",
            "minimalist drawing of {category}",
            "doodle of {category}",
            "quick sketch of {category}",
            "line art of {category}"
        ]
        
        print(f"🎯 QuickDraw LoRA Preprocessor initialized")
        print(f"📁 Output directory: {self.base_output_dir}")
        print(f"🖼️  Image size: {self.image_size}x{self.image_size}")
        print(f"📊 Images per category: {self.images_per_category}")
    
    def get_popular_categories(self) -> List[str]:
        """Return a comprehensive list of popular/recognizable categories"""
        return [
            # Animals
            "cat", "dog", "bird", "fish", "horse", "cow", "pig", "sheep", "rabbit", "elephant", 
            "lion", "bear", "monkey", "snake", "frog", "butterfly", "bee", "spider",
            
            # Nature
            "tree", "flower", "grass", "apple", "banana", "strawberry", "mushroom", "leaf",
            "sun", "moon", "star", "cloud", "mountain", "ocean", "rain", "lightning",
            
            # Objects
            "house", "car", "bicycle", "airplane", "boat", "train", "bus", "truck",
            "chair", "table", "bed", "book", "cup", "phone", "computer", "television",
            
            # Shapes & Body
            "circle", "square", "triangle", "heart", "smiley face", "eye", "nose", 
            "mouth", "hand", "foot", "face", "person",
            
            # Food
            "pizza", "hamburger", "cake", "ice cream", "donut", "bread", "cheese",
            
            # Tools & Items
            "scissors", "umbrella", "key", "clock", "camera", "guitar", "piano"
        ]
    
    def download_category(self, category_name: str) -> str:
        """
        Download a specific category from QuickDraw dataset
        
        Args:
            category_name: Name of the category to download
            
        Returns:
            Path to downloaded file or None if failed
        """
        # Replace spaces with %20 for URL
        url_category = category_name.replace(" ", "%20")
        file_url = f"{self.base_url}{url_category}.ndjson"
        file_path = os.path.join(self.raw_data_dir, f"{category_name.replace(' ', '_')}.ndjson")
        
        print(f"⬇️  Downloading {category_name}...")
        
        try:
            response = requests.get(file_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Download with progress indication
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\r   Progress: {percent:.1f}%", end="", flush=True)
            
            print(f"\n✅ Downloaded {category_name}")
            return file_path
            
        except requests.exceptions.RequestException as e:
            print(f"\n❌ Failed to download {category_name}: {e}")
            return None
    
    def convert_strokes_to_image(self, drawing_data: List[List[List[int]]], 
                               image_size: int = None) -> Image.Image:
        """
        Convert QuickDraw stroke data to PIL Image
        
        Args:
            drawing_data: QuickDraw stroke data
            image_size: Size of output image
            
        Returns:
            PIL Image object
        """
        if image_size is None:
            image_size = self.image_size
            
        # Create white background image
        image = Image.new("RGB", (image_size, image_size), "white")
        draw = ImageDraw.Draw(image)
        
        # Process each stroke
        for stroke in drawing_data:
            if len(stroke) >= 2 and len(stroke[0]) > 1:
                x_coords = stroke[0]
                y_coords = stroke[1]
                
                # Scale coordinates to image size
                points = []
                for x, y in zip(x_coords, y_coords):
                    # QuickDraw coordinates are 0-255, scale to image size
                    scaled_x = int((x / 255.0) * (image_size - 1))
                    scaled_y = int((y / 255.0) * (image_size - 1))
                    points.append((scaled_x, scaled_y))
                
                # Draw stroke with appropriate line width
                if len(points) > 1:
                    draw.line(points, fill="black", width=3)
                elif len(points) == 1:
                    # Draw single point as small circle
                    x, y = points[0]
                    draw.ellipse([x-1, y-1, x+1, y+1], fill="black")
        
        # Apply slight smoothing to reduce pixelation
        image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
        
        return image
    
    def generate_caption(self, category_name: str) -> str:
        """Generate a random caption for the category"""
        template = random.choice(self.caption_templates)
        return template.format(category=category_name)
    
    def process_category_file(self, ndjson_path: str, category_name: str) -> List[Dict]:
        """
        Process a downloaded NDJSON file into images and captions
        
        Args:
            ndjson_path: Path to the NDJSON file
            category_name: Name of the category
            
        Returns:
            List of processed items with paths and metadata
        """
        if not os.path.exists(ndjson_path):
            print(f"❌ File not found: {ndjson_path}")
            return []
        
        print(f"🔄 Processing {category_name}...")
        
        # Read and filter drawings
        recognized_drawings = []
        line_count = 0
        
        try:
            with open(ndjson_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line_count += 1
                    if line_count % 10000 == 0:
                        print(f"   Read {line_count} drawings...", end='\r')
                    
                    try:
                        data = json.loads(line.strip())
                        # Only use recognized drawings with reasonable stroke count
                        if (data.get('recognized', True) and 
                            len(data.get('drawing', [])) > 0 and 
                            len(data.get('drawing', [])) < 20):  # Filter overly complex drawings
                            recognized_drawings.append(data)
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            print(f"\n❌ Error reading file: {e}")
            return []
        
        print(f"\n   Found {len(recognized_drawings)} good drawings")
        
        # Sample the requested number of drawings
        if len(recognized_drawings) > self.images_per_category:
            selected_drawings = random.sample(recognized_drawings, self.images_per_category)
        else:
            selected_drawings = recognized_drawings
            print(f"   ⚠️  Only {len(selected_drawings)} drawings available")
        
        # Process each selected drawing
        processed_items = []
        category_safe = category_name.replace(" ", "_").replace("/", "_")
        
        for i, drawing_data in enumerate(selected_drawings):
            try:
                # Convert to image
                image = self.convert_strokes_to_image(drawing_data['drawing'])
                
                # Generate filenames
                base_filename = f"{category_safe}_{i:04d}"
                image_filename = f"{base_filename}.png"
                caption_filename = f"{base_filename}.txt"
                
                # Save to processed directory
                image_path = os.path.join(self.processed_dir, image_filename)
                caption_path = os.path.join(self.processed_dir, caption_filename)
                
                # Save image
                image.save(image_path, "PNG", quality=95)
                
                # Generate and save caption
                caption = self.generate_caption(category_name)
                with open(caption_path, 'w', encoding='utf-8') as f:
                    f.write(caption)
                
                processed_items.append({
                    'image_path': image_path,
                    'caption_path': caption_path,
                    'category': category_name,
                    'caption': caption,
                    'base_filename': base_filename
                })
                
                # Progress indicator
                if (i + 1) % 10 == 0:
                    print(f"   Processed {i + 1}/{len(selected_drawings)} images", end='\r')
                    
            except Exception as e:
                print(f"\n   ⚠️  Error processing drawing {i}: {e}")
                continue
        
        print(f"\n✅ Processed {len(processed_items)} images for {category_name}")
        return processed_items
    
    def organize_for_training(self, all_processed_items: List[Dict]) -> None:
        """
        Organize processed images into Kohya-compatible training structure
        
        Args:
            all_processed_items: List of all processed items from all categories
        """
        print(f"📁 Organizing {len(all_processed_items)} files for training...")
        
        # Copy files to training directory
        for item in all_processed_items:
            src_image = item['image_path']
            src_caption = item['caption_path']
            
            # Destination paths in training directory
            dst_image = os.path.join(self.training_dir, os.path.basename(src_image))
            dst_caption = os.path.join(self.training_dir, os.path.basename(src_caption))
            
            # Copy files
            try:
                shutil.copy2(src_image, dst_image)
                shutil.copy2(src_caption, dst_caption)
            except Exception as e:
                print(f"⚠️  Error copying {os.path.basename(src_image)}: {e}")
        
        print(f"✅ Training data organized in: {self.training_dir}")
    
    def create_dataset_info(self, categories: List[str], 
                          all_processed_items: List[Dict]) -> None:
        """Create a summary file with dataset information"""
        info = {
            "dataset_info": {
                "total_images": len(all_processed_items),
                "categories": categories,
                "images_per_category": {cat: len([item for item in all_processed_items 
                                               if item['category'] == cat]) 
                                       for cat in categories},
                "image_size": self.image_size,
                "training_directory": self.training_dir
            },
            "usage_instructions": {
                "kohya_ss": "Use the path: " + self.training_dir,
                "comfyui_lora_training": "Point to the quickdraw_sketches folder",
                "recommended_settings": {
                    "resolution": self.image_size,
                    "network_dim": 64,
                    "network_alpha": 32,
                    "learning_rate": "1e-4",
                    "batch_size": 2
                }
            }
        }
        
        info_path = os.path.join(self.base_output_dir, "dataset_info.json")
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2)
        
        print(f"📋 Dataset info saved to: {info_path}")
    
    def process_categories(self, categories: List[str]) -> None:
        """
        Main processing function - downloads and processes multiple categories
        
        Args:
            categories: List of category names to process
        """
        print(f"🚀 Starting processing of {len(categories)} categories")
        print(f"Categories: {', '.join(categories)}")
        print("-" * 60)
        
        all_processed_items = []
        successful_categories = []
        
        for category in categories:
            try:
                # Download category
                ndjson_path = self.download_category(category)
                if ndjson_path is None:
                    print(f"⏭️  Skipping {category} due to download failure")
                    continue
                
                # Process category
                processed_items = self.process_category_file(ndjson_path, category)
                if processed_items:
                    all_processed_items.extend(processed_items)
                    successful_categories.append(category)
                else:
                    print(f"⏭️  Skipping {category} due to processing failure")
                
                print("-" * 40)
                
            except Exception as e:
                print(f"❌ Error processing {category}: {e}")
                continue
        
        if all_processed_items:
            # Organize for training
            self.organize_for_training(all_processed_items)
            
            # Create dataset info
            self.create_dataset_info(successful_categories, all_processed_items)
            
            # Final summary
            print("\n" + "=" * 60)
            print("🎉 PROCESSING COMPLETE!")
            print(f"✅ Successfully processed {len(successful_categories)} categories")
            print(f"📊 Total images: {len(all_processed_items)}")
            print(f"📁 Training data location: {self.training_dir}")
            print(f"💡 Next step: Use this path in your LoRA training tool")
            print("=" * 60)
        else:
            print("\n❌ No data was successfully processed!")

def get_all_quickdraw_categories():
    """Get the complete list of all 345 QuickDraw categories"""
    # This is the complete list from the QuickDraw dataset
    all_categories = [
        "aircraft carrier", "airplane", "alarm clock", "ambulance", "angel", "animal migration", 
        "ant", "anvil", "apple", "arm", "asparagus", "axe", "backpack", "banana", "bandage", 
        "barn", "baseball", "baseball bat", "basket", "basketball", "bat", "bathtub", "beach", 
        "bear", "beard", "bed", "bee", "belt", "bench", "bicycle", "binoculars", "bird", 
        "birthday cake", "blackberry", "blueberry", "book", "boomerang", "bottlecap", "bowtie", 
        "bracelet", "brain", "bread", "bridge", "broccoli", "broom", "bucket", "bulldozer", 
        "bus", "bush", "butterfly", "cactus", "cake", "calculator", "calendar", "camel", 
        "camera", "camouflage", "campfire", "candle", "cannon", "canoe", "car", "carrot", 
        "castle", "cat", "ceiling fan", "cello", "cell phone", "chair", "chandelier", "church", 
        "circle", "clarinet", "clock", "cloud", "coffee cup", "compass", "computer", "cookie", 
        "cooler", "couch", "cow", "crab", "crayon", "crocodile", "crown", "cruise ship", 
        "cup", "diamond", "dishwasher", "diving board", "dog", "dolphin", "donut", "door", 
        "dragon", "dresser", "drill", "drums", "duck", "dumbbell", "ear", "elbow", "elephant", 
        "envelope", "eraser", "eye", "eyeglasses", "face", "fan", "feather", "fence", "finger", 
        "fire hydrant", "fireplace", "firetruck", "fish", "flamingo", "flashlight", "flip flops", 
        "floor lamp", "flower", "flying saucer", "foot", "fork", "frog", "frying pan", 
        "garden", "garden hose", "giraffe", "goatee", "golf club", "grapes", "grass", "guitar", 
        "hamburger", "hammer", "hand", "harp", "hat", "headphones", "hedgehog", "helicopter", 
        "helmet", "hexagon", "hockey puck", "hockey stick", "horse", "hospital", "hot air balloon", 
        "hot dog", "hot tub", "hourglass", "house", "house plant", "hurricane", "ice cream", 
        "jacket", "jail", "kangaroo", "key", "keyboard", "knee", "knife", "ladder", "lantern", 
        "laptop", "leaf", "leg", "light bulb", "lighter", "lighthouse", "lightning", "line", 
        "lion", "lipstick", "lobster", "lollipop", "mailbox", "map", "marker", "matches", 
        "megaphone", "mermaid", "microphone", "microwave", "monkey", "moon", "mosquito", 
        "motorbike", "mountain", "mouse", "moustache", "mouth", "mug", "mushroom", "nail", 
        "necklace", "nose", "ocean", "octagon", "octopus", "onion", "oven", "owl", "paintbrush", 
        "paint can", "palm tree", "panda", "pants", "paper clip", "parachute", "parrot", 
        "passport", "peanut", "pear", "peas", "pencil", "penguin", "piano", "pickup truck", 
        "picture frame", "pig", "pillow", "pineapple", "pizza", "pliers", "police car", "pond", 
        "pool", "popsicle", "postcard", "potato", "power outlet", "purse", "rabbit", "raccoon", 
        "radio", "rain", "rainbow", "rake", "remote control", "rhinoceros", "rifle", "river", 
        "roller coaster", "rollerskates", "sailboat", "sandwich", "saw", "saxophone", "school bus", 
        "scissors", "scorpion", "screwdriver", "sea turtle", "see saw", "shark", "sheep", 
        "shoe", "shorts", "shovel", "sink", "skateboard", "skull", "skyscraper", "sleeping bag", 
        "smiley face", "snail", "snake", "snorkel", "snowflake", "snowman", "soccer ball", 
        "sock", "speedboat", "spider", "spoon", "spreadsheet", "square", "squiggle", "squirrel", 
        "stairs", "star", "steak", "stereo", "stethoscope", "stitches", "stop sign", "stove", 
        "strawberry", "streetlight", "string bean", "submarine", "suitcase", "sun", "swan", 
        "sweater", "swing set", "sword", "syringe", "table", "teapot", "teddy-bear", "telephone", 
        "television", "tennis racquet", "tent", "The Eiffel Tower", "The Great Wall of China", 
        "The Mona Lisa", "tiger", "toaster", "toe", "toilet", "tooth", "toothbrush", "toothpaste", 
        "tornado", "tractor", "traffic light", "train", "tree", "triangle", "trombone", "truck", 
        "trumpet", "t-shirt", "umbrella", "underwear", "van", "vase", "violin", "washing machine", 
        "watermelon", "waterslide", "whale", "wheel", "windmill", "wine bottle", "wine glass", 
        "wristwatch", "yoga", "zebra", "zigzag"
    ]
    return all_categories

def main():
    """Main function with user-friendly interface"""
    print("🎨 QuickDraw LoRA Dataset Preprocessor")
    print("=" * 50)
    
    print("\n🎯 Choose your dataset size:")
    print("1. Small test (6 categories, ~300 images) - Quick test")
    print("2. Medium (50 categories, ~2500 images) - Good balance") 
    print("3. Large (100 categories, ~5000 images) - High quality")
    print("4. ALL CATEGORIES (345 categories, ~17,250 images) - Maximum quality")
    
    choice = input("\nEnter your choice (1-4) [default: 2]: ").strip() or "2"
    
    # Initialize preprocessor with appropriate settings
    if choice == "1":
        preprocessor = QuickDrawLoRAPreprocessor(images_per_category=50)
        popular_categories = preprocessor.get_popular_categories()
        selected_categories = popular_categories[:6]
        print(f"\n🚀 Processing {len(selected_categories)} categories (small test)")
        
    elif choice == "2":
        preprocessor = QuickDrawLoRAPreprocessor(images_per_category=50)
        popular_categories = preprocessor.get_popular_categories()
        selected_categories = popular_categories[:50]
        print(f"\n🚀 Processing {len(selected_categories)} categories (medium dataset)")
        
    elif choice == "3":
        preprocessor = QuickDrawLoRAPreprocessor(images_per_category=50)
        all_categories = get_all_quickdraw_categories()
        selected_categories = all_categories[:100]
        print(f"\n🚀 Processing {len(selected_categories)} categories (large dataset)")
        
    elif choice == "4":
        print("\n📊 How many images per category?")
        print("1. Conservative (50 images) - 17,250 total")
        print("2. Balanced (100 images) - 34,500 total") 
        print("3. High Quality (200 images) - 69,000 total")
        print("4. Maximum (500 images) - 172,500 total")
        
        img_choice = input("Enter choice (1-4) [default: 2]: ").strip() or "2"
        
        if img_choice == "1":
            images_per_cat = 50
        elif img_choice == "2": 
            images_per_cat = 100
        elif img_choice == "3":
            images_per_cat = 200
        elif img_choice == "4":
            images_per_cat = 500
        else:
            images_per_cat = 100
            
        preprocessor = QuickDrawLoRAPreprocessor(images_per_category=images_per_cat)
        selected_categories = get_all_quickdraw_categories()
        total_images = len(selected_categories) * images_per_cat
        
        print(f"\n🚀 Processing ALL {len(selected_categories)} categories!")
        print(f"📊 Total images: {total_images:,}")
        print(f"⏱️  Estimated processing time: {total_images // 1000} hours")
        print(f"💾 Estimated dataset size: ~{total_images * 0.5 // 1000} GB")
        
        confirm = input("Continue? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return
    else:
        print("Invalid choice, using medium dataset")
        preprocessor = QuickDrawLoRAPreprocessor(images_per_category=50)
        popular_categories = preprocessor.get_popular_categories()
        selected_categories = popular_categories[:50]
    
    print(f"\n📊 Total images: {len(selected_categories) * preprocessor.images_per_category}")
    print(f"💾 Estimated size: {len(selected_categories) * 50 * 512 * 512 * 3 / 1e9:.1f} GB")
    
    # Start processing
    preprocessor.process_categories(selected_categories)

if __name__ == "__main__":
    main()