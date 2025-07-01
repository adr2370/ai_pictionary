import torch

print("=" * 50)
print("🔧 PyTorch CUDA Test")
print("=" * 50)

print(f"PyTorch version: {torch.__version__}")
print(f"CUDA compiled version: {torch.version.cuda}")
print(f"CUDA available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
    print(f"✅ VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    
    # Quick GPU test
    try:
        x = torch.rand(1000, 1000).cuda()
        y = x @ x.T  # Matrix multiplication on GPU
        print("✅ GPU computation test: PASSED")
        print("🎉 Ready for LoRA training!")
    except Exception as e:
        print(f"❌ GPU test failed: {e}")
else:
    print("❌ PyTorch can't access CUDA")