#!/usr/bin/env python3
"""
TikTok Authentication Test Script

This script helps diagnose TikTok API authentication and permission issues.
Run this before attempting video uploads to identify problems.
"""

import json
import os
from tiktok_uploader import TikTokUploader

def test_tiktok_auth():
    """Test TikTok authentication and permissions."""
    print("=== TikTok Authentication Test ===\n")
    
    # Check if config file exists
    config_file = "tiktok_config.json"
    if not os.path.exists(config_file):
        print("❌ tiktok_config.json not found!")
        print("Please create this file with your TikTok app credentials.")
        return False
    
    print("✓ Configuration file found")
    
    # Load configuration
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        tiktok_config = config.get('tiktok', {})
        print("✓ Configuration loaded successfully")
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        return False
    
    # Check required fields
    client_key = tiktok_config.get('client_key')
    client_secret = tiktok_config.get('client_secret')
    redirect_uri = tiktok_config.get('redirect_uri')
    
    if not client_key:
        print("❌ client_key not found in configuration")
        return False
    if not client_secret:
        print("❌ client_secret not found in configuration")
        return False
    if not redirect_uri:
        print("❌ redirect_uri not found in configuration")
        return False
    
    print("✓ All required configuration fields present")
    print(f"  Client Key: {client_key[:10]}...")
    print(f"  Redirect URI: {redirect_uri}")
    
    # Initialize uploader
    try:
        uploader = TikTokUploader(config_file=config_file)
        print("✓ TikTokUploader initialized successfully")
    except Exception as e:
        print(f"❌ Error initializing TikTokUploader: {e}")
        return False
    
    # Check if tokens exist
    token_file = uploader.token_file
    if os.path.exists(token_file):
        print("✓ Token file found")
        try:
            with open(token_file, 'r') as f:
                token_data = json.load(f)
            print("✓ Token file is valid JSON")
            
            # Check token fields
            if 'access_token' in token_data:
                print(f"✓ Access token present: {token_data['access_token'][:20]}...")
            else:
                print("❌ Access token missing from token file")
                return False
                
            if 'refresh_token' in token_data:
                print("✓ Refresh token present")
            else:
                print("❌ Refresh token missing from token file")
                return False
                
            if 'open_id' in token_data:
                print(f"✓ Open ID present: {token_data['open_id']}")
            else:
                print("❌ Open ID missing from token file")
                return False
                
        except Exception as e:
            print(f"❌ Error reading token file: {e}")
            return False
    else:
        print("⚠ Token file not found - will need to authenticate")
    
    # Test token validation
    print("\n=== Testing Token Validation ===")
    if uploader.access_token:
        try:
            is_valid = uploader.validate_token_and_permissions()
            if is_valid:
                print("✓ Token validation successful")
                print("✓ App has required permissions")
                return True
            else:
                print("❌ Token validation failed")
                return False
        except Exception as e:
            print(f"❌ Error during token validation: {e}")
            return False
    else:
        print("⚠ No access token available - need to authenticate")
        print("Run the authentication flow to get a token")
        return False

def main():
    """Main function."""
    try:
        success = test_tiktok_auth()
        if success:
            print("\n✅ All tests passed! TikTok authentication is working correctly.")
            print("You should be able to upload videos successfully.")
        else:
            print("\n❌ Tests failed. Please fix the issues above before attempting uploads.")
            print("\nCommon solutions:")
            print("1. Check your TikTok app settings in the TikTok Developer Console")
            print("2. Ensure 'video.publish' scope is enabled")
            print("3. Make sure your app is approved for video publishing")
            print("4. Verify your app is in the correct environment (sandbox/production)")
            print("5. Re-authenticate if tokens are expired")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    main() 