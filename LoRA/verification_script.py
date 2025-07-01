import os
import torch

def verify_setup():
    print("🔍 Verifying LoRA training setup...")
    
    # Check CUDA
    if torch.cuda.is_available():
        print(f"✅ CUDA available: {torch.cuda.get_device_name(0)}")
        print(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    else:
        print("❌ CUDA not available")
        return False
    
    # Check dataset
    dataset_path = "quickdraw_lora_training/03_training_data/quickdraw_sketches/25_sketch drawings"
    if os.path.exists(dataset_path):
        files = os.listdir(dataset_path)
        png_files = [f for f in files if f.endswith('.png')]
        txt_files = [f for f in files if f.endswith('.txt')]
        print(f"✅ Dataset ready: {len(png_files)} images, {len(txt_files)} captions")
    else:
        print("❌ Dataset not found")
        return False
    
    # Check base model (if using ComfyUI path)
    model_path = "../ComfyUI/models/checkpoints/DreamShaper_8_pruned.safetensors"
    if os.path.exists(model_path):
        size_gb = os.path.getsize(model_path) / 1e9
        print(f"✅ Base model ready: {size_gb:.1f} GB")
    else:
        print(f"⚠️  Base model not found at: {model_path}")
        print("   Download it before training")
    
    print("\n🎯 Ready for Phase 3: Training Configuration!")
    return True

verify_setup()