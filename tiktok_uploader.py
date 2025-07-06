import os
import sys
import time
import json
import requests
import pickle
import hashlib
import base64
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode, parse_qs, urlparse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import socket


class TikTokUploader:
    def __init__(self, client_key=None, client_secret=None, redirect_uri=None, config_file="tiktok_config.json"):
        """
        Initialize TikTok uploader with OAuth credentials.
        
        Args:
            client_key (str): Your TikTok app's client key (optional if using config file)
            client_secret (str): Your TikTok app's client secret (optional if using config file)
            redirect_uri (str): Redirect URI for OAuth flow (optional, will use config file value)
            config_file (str): Path to configuration file (default: "tiktok_config.json")
        """
        # Load configuration from file if it exists
        self.config = self.load_config(config_file)
        
        # Use provided credentials or fall back to config file (from 'tiktok' section)
        tiktok_config = self.config.get('tiktok', {})
        self.client_key = client_key or tiktok_config.get('client_key')
        self.client_secret = client_secret or tiktok_config.get('client_secret')
        self.redirect_uri = redirect_uri or tiktok_config.get('redirect_uri')
        
        if not self.client_key or not self.client_secret:
            raise ValueError("TikTok client_key and client_secret must be provided either as parameters or in config file")
        
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self.open_id = None
        
        # TikTok API endpoints
        self.auth_url = "https://www.tiktok.com/v2/auth/authorize/"
        self.token_url = "https://open.tiktokapis.com/v2/oauth/token/"
        self.creator_info_url = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
        self.video_init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
        self.status_url = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
        
        # Load existing tokens if available
        self.token_file = self.config.get('token_file', "tiktok_tokens.json")
        self.load_tokens()
        
        # PKCE parameters
        self.code_verifier = None
        self.code_challenge = None
    
    def generate_pkce_params(self):
        """Generate PKCE code verifier and challenge for OAuth 2.0."""
        # Generate code verifier (random string)
        self.code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        
        # Generate code challenge (SHA256 hash of verifier)
        challenge_bytes = hashlib.sha256(self.code_verifier.encode('utf-8')).digest()
        self.code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')
        
        print(f"Generated PKCE parameters")
        print(f"Code verifier: {self.code_verifier[:20]}...")
        print(f"Code challenge: {self.code_challenge[:20]}...")
    
    def load_config(self, config_file):
        """Load configuration from JSON file."""
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                print(f"Configuration loaded from {config_file}")
                return config
            except Exception as e:
                print(f"Error loading config file: {e}")
        return {}
    
    def save_tokens(self):
        """Save access tokens to file for persistence."""
        token_data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None,
            "open_id": self.open_id
        }
        with open(self.token_file, 'w') as f:
            json.dump(token_data, f)
        print("Tokens saved successfully.")
    
    def load_tokens(self):
        """Load access tokens from file if they exist."""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                self.access_token = token_data.get("access_token")
                self.refresh_token = token_data.get("refresh_token")
                self.open_id = token_data.get("open_id")
                if token_data.get("token_expires_at"):
                    self.token_expires_at = datetime.fromisoformat(token_data["token_expires_at"])
                print("Tokens loaded successfully.")
            except Exception as e:
                print(f"Error loading tokens: {e}")
    
    def get_auth_url(self, scopes=None):
        """
        Generate the authorization URL for TikTok OAuth with PKCE.
        
        Args:
            scopes (list): List of permission scopes. Default includes video.publish
            
        Returns:
            str: Authorization URL
        """
        if scopes is None:
            scopes = ["user.info.basic", "video.publish"]
        
        # Generate PKCE parameters
        self.generate_pkce_params()
        
        params = {
            "client_key": self.client_key,
            "scope": ",".join(scopes),
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": f"tiktok_auth_{int(time.time())}",
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256"
        }
        
        return f"{self.auth_url}?{urlencode(params)}"
    
    def start_oauth_flow(self, scopes=None):
        """
        Start the OAuth authorization flow using the configured redirect_uri only.
        Prompts the user to visit the auth URL, then paste the redirect URL after authorization.
        """
        auth_url = self.get_auth_url(scopes)
        print("Please visit the following URL in your browser to authorize:")
        print(auth_url)
        print("\nAfter authorizing, you will be redirected to a URL like:")
        print(f"{self.redirect_uri}?code=AUTH_CODE&state=...")
        print("Copy the entire URL from your browser's address bar and paste it below.")
        redirect_url = input("Paste the full redirect URL here: ").strip()

        # Extract the code from the URL
        try:
            parsed_url = urlparse(redirect_url)
            params = parse_qs(parsed_url.query)
            if 'code' in params:
                return params['code'][0]
            else:
                raise Exception("No authorization code found in the URL.")
        except Exception as e:
            raise Exception(f"Failed to extract authorization code: {e}")
    
    def exchange_code_for_token(self, auth_code):
        """
        Exchange authorization code for access token using PKCE.
        
        Args:
            auth_code (str): Authorization code from TikTok
            
        Returns:
            dict: Token response from TikTok
        """
        if not self.code_verifier:
            raise Exception("PKCE code verifier not found. Must call get_auth_url first.")
        
        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
            "code_verifier": self.code_verifier
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache"
        }
        
        print("Exchanging authorization code for access token...")
        print(f"Using code verifier: {self.code_verifier[:20]}...")
        
        response = requests.post(self.token_url, data=data, headers=headers)
        
        if response.status_code != 200:
            print(f"Token exchange failed with status {response.status_code}")
            print(f"Response: {response.text}")
            response.raise_for_status()
        
        token_data = response.json()
        
        if 'error' in token_data:
            print(f"Token exchange error: {token_data}")
            raise Exception(f"Token exchange failed: {token_data.get('error_description', token_data.get('error'))}")
        
        # Store tokens
        self.access_token = token_data["access_token"]
        self.refresh_token = token_data["refresh_token"]
        self.open_id = token_data["open_id"]
        self.token_expires_at = datetime.now() + timedelta(seconds=token_data["expires_in"])
        
        self.save_tokens()
        print("Access token obtained and saved successfully!")
        return token_data
    
    def refresh_access_token(self):
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            raise Exception("No refresh token available")
        
        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache"
        }
        
        response = requests.post(self.token_url, data=data, headers=headers)
        response.raise_for_status()
        
        token_data = response.json()
        
        # Update tokens
        self.access_token = token_data["access_token"]
        self.refresh_token = token_data["refresh_token"]
        self.token_expires_at = datetime.now() + timedelta(seconds=token_data["expires_in"])
        
        self.save_tokens()
        return token_data
    
    def validate_token_and_permissions(self):
        """Validate the current access token and check app permissions."""
        if not self.access_token:
            print("No access token available. Need to authenticate first.")
            return False
        
        print("Validating access token and checking permissions...")
        
        # Test the token by calling creator info endpoint
        try:
            creator_info = self.get_creator_info()
            print("✓ Access token is valid")
            print(f"✓ Creator info retrieved successfully")
            print(f"Response structure: {json.dumps(creator_info, indent=2)}")
            
            # Check if we have the required permissions - handle different response structures
            if 'data' in creator_info:
                if 'creator_info' in creator_info['data']:
                    creator_data = creator_info['data']['creator_info']
                    print(f"✓ Creator ID: {creator_data.get('creator_id', 'N/A')}")
                    print(f"✓ Creator Name: {creator_data.get('creator_name', 'N/A')}")
                    return True
                elif 'error' in creator_info['data']:
                    error = creator_info['data']['error']
                    print(f"✗ API Error: {error.get('code', 'Unknown')} - {error.get('message', 'No message')}")
                    return False
                else:
                    print("⚠ Warning: Unexpected response structure")
                    print("Response contains 'data' but no 'creator_info' or 'error'")
                    # If we got a successful response without creator_info, the token is still valid
                    return True
            else:
                print("⚠ Warning: Response does not contain 'data' field")
                print("This might indicate a different API response format")
                # If we got a response without an error, the token is probably valid
                return True
                
        except Exception as e:
            print(f"✗ Token validation failed: {e}")
            if "401" in str(e) or "unauthorized" in str(e).lower():
                print("Access token is invalid or expired. Need to re-authenticate.")
                return False
            elif "403" in str(e) or "forbidden" in str(e).lower():
                print("Access token is valid but lacks required permissions.")
                print("Please ensure your TikTok app has 'video.publish' scope enabled.")
                return False
            else:
                print("Unknown error during token validation.")
                return False
    
    def ensure_valid_token(self):
        """Ensure we have a valid access token, refreshing if necessary."""
        if not self.access_token:
            print("No access token found. Starting OAuth flow...")
            auth_code = self.start_oauth_flow()
            self.exchange_code_for_token(auth_code)
            return
        
        # Check if token is expired or will expire soon (within 5 minutes)
        if self.token_expires_at and self.token_expires_at <= datetime.now() + timedelta(minutes=5):
            print("Access token expired or expiring soon. Refreshing...")
            try:
                self.refresh_access_token()
            except Exception as e:
                print(f"Failed to refresh token: {e}")
                print("Starting new OAuth flow...")
                auth_code = self.start_oauth_flow()
                self.exchange_code_for_token(auth_code)
    
    def get_creator_info(self):
        """Get creator information for the authenticated user."""
        self.ensure_valid_token()
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        
        response = requests.post(self.creator_info_url, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    def upload_video(self, video_path, title=None, description=None, privacy_level=None, 
                    disable_duet=None, disable_comment=None, disable_stitch=None):
        """
        Upload a video to TikTok.
        
        Args:
            video_path (str): Path to the video file
            title (str): Video title/caption (optional, uses config default)
            description (str): Video description (optional)
            privacy_level (str): Privacy level (optional, uses config default)
            disable_duet (bool): Whether to disable duets (optional, uses config default)
            disable_comment (bool): Whether to disable comments (optional, uses config default)
            disable_stitch (bool): Whether to disable stitches (optional, uses config default)
            
        Returns:
            dict: Upload response containing publish_id and status
        """
        # Validate token and permissions before attempting upload
        if not self.validate_token_and_permissions():
            print("Token validation failed. Attempting to refresh...")
            self.ensure_valid_token()
            if not self.validate_token_and_permissions():
                raise Exception("Failed to obtain valid access token with required permissions")
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # Get file size
        video_size = os.path.getsize(video_path)
        
        # Use config defaults if not provided
        tiktok_config = self.config.get('tiktok', {})
        video_config = self.config.get('video_settings', {})
        
        privacy_level = privacy_level or tiktok_config.get('default_privacy', 'SELF_ONLY')
        disable_duet = disable_duet if disable_duet is not None else video_config.get('disable_duet', False)
        disable_comment = disable_comment if disable_comment is not None else video_config.get('disable_comment', False)
        disable_stitch = disable_stitch if disable_stitch is not None else video_config.get('disable_stitch', False)
        
        # Prepare post info
        post_info = {
            "privacy_level": privacy_level,
            "disable_duet": disable_duet,
            "disable_comment": disable_comment,
            "disable_stitch": disable_stitch
        }
        
        # Generate title from template if not provided
        if title:
            post_info["title"] = title
        elif description:
            post_info["title"] = description
        else:
            # Use template from config
            title_template = tiktok_config.get('default_title_template', 'AI Pictionary Chain Game #{hashtag}')
            hashtags = tiktok_config.get('hashtags', ['AI', 'Pictionary', 'Comedy'])
            hashtag_str = ' '.join(f'#{tag}' for tag in hashtags[:3])  # Use first 3 hashtags
            post_info["title"] = title_template.replace('{hashtag}', hashtag_str)
        
        # For videos larger than 64MB, we need chunking
        chunk_size = min(video_size, 64 * 1024 * 1024)  # 64MB max chunk size
        total_chunk_count = (video_size + chunk_size - 1) // chunk_size
        
        # Initialize upload
        init_data = {
            "post_info": post_info,
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunk_count
            }
        }
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        
        print("Initializing video upload...")
        print(f"Using access token: {self.access_token[:20]}...")
        print(f"Post info: {json.dumps(post_info, indent=2)}")
        print(f"Video size: {video_size} bytes ({video_size / (1024*1024):.2f} MB)")
        
        try:
            response = requests.post(self.video_init_url, json=init_data, headers=headers)
            
            # Detailed error handling for 403 and other errors
            if response.status_code == 403:
                print(f"403 Forbidden Error Details:")
                print(f"Response Headers: {dict(response.headers)}")
                print(f"Response Body: {response.text}")
                
                # Try to get more specific error information
                try:
                    error_data = response.json()
                    error_code = error_data.get('error', {}).get('code')
                    error_message = error_data.get('error', {}).get('message')
                    print(f"Error Code: {error_code}")
                    print(f"Error Message: {error_message}")
                    
                    # Common 403 error codes and solutions
                    if error_code == 'access_token_expired':
                        print("Access token expired. Refreshing...")
                        self.refresh_access_token()
                        # Retry with new token
                        headers["Authorization"] = f"Bearer {self.access_token}"
                        response = requests.post(self.video_init_url, json=init_data, headers=headers)
                        response.raise_for_status()
                    elif error_code == 'insufficient_permissions':
                        print("Insufficient permissions. Please check your TikTok app settings:")
                        print("1. Ensure 'video.publish' scope is enabled")
                        print("2. Ensure your app is approved for video publishing")
                        print("3. Check if your app is in the correct environment (sandbox/production)")
                        raise Exception(f"TikTok API Error: {error_message}")
                    elif error_code == 'rate_limit_exceeded':
                        print("Rate limit exceeded. Please wait before retrying.")
                        raise Exception(f"TikTok API Error: Rate limit exceeded")
                    else:
                        raise Exception(f"TikTok API Error: {error_message or 'Unknown 403 error'}")
                        
                except json.JSONDecodeError:
                    print("Could not parse error response as JSON")
                    raise Exception("TikTok API Error: 403 Forbidden - Unable to parse error details")
                    
            elif response.status_code != 200:
                print(f"HTTP Error {response.status_code}:")
                print(f"Response Headers: {dict(response.headers)}")
                print(f"Response Body: {response.text}")
                response.raise_for_status()
            
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
            raise
        
        init_response = response.json()
        publish_id = init_response["data"]["publish_id"]
        upload_url = init_response["data"]["upload_url"]
        
        print(f"Upload initialized. Publish ID: {publish_id}")
        
        # Upload video file
        print("Uploading video file...")
        with open(video_path, 'rb') as video_file:
            if total_chunk_count == 1:
                # Single chunk upload
                video_data = video_file.read()
                upload_headers = {
                    "Content-Range": f"bytes 0-{video_size-1}/{video_size}",
                    "Content-Length": str(video_size),
                    "Content-Type": "video/mp4"
                }
                
                upload_response = requests.put(upload_url, data=video_data, headers=upload_headers)
                upload_response.raise_for_status()
            else:
                # Multi-chunk upload
                for chunk_index in range(total_chunk_count):
                    start_byte = chunk_index * chunk_size
                    end_byte = min(start_byte + chunk_size - 1, video_size - 1)
                    chunk_data = video_file.read(end_byte - start_byte + 1)
                    
                    upload_headers = {
                        "Content-Range": f"bytes {start_byte}-{end_byte}/{video_size}",
                        "Content-Length": str(len(chunk_data)),
                        "Content-Type": "video/mp4"
                    }
                    
                    print(f"Uploading chunk {chunk_index + 1}/{total_chunk_count}")
                    upload_response = requests.put(upload_url, data=chunk_data, headers=upload_headers)
                    upload_response.raise_for_status()
        
        print("Video uploaded successfully!")
        
        # Check upload status
        return self.check_upload_status(publish_id)
    
    def check_upload_status(self, publish_id, max_wait_time=300):
        """
        Check the status of a video upload.
        
        Args:
            publish_id (str): The publish ID returned from upload
            max_wait_time (int): Maximum time to wait for processing (seconds)
            
        Returns:
            dict: Status response from TikTok
        """
        self.ensure_valid_token()
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        
        data = {"publish_id": publish_id}
        
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            response = requests.post(self.status_url, json=data, headers=headers)
            response.raise_for_status()
            
            status_response = response.json()
            status = status_response["data"]["status"]
            
            print(f"Upload status: {status}")
            
            if status == "PUBLISH_COMPLETE":
                post_id = status_response["data"].get("publicaly_available_post_id", [])
                if post_id:
                    print(f"Video published successfully! Post ID: {post_id[0]}")
                else:
                    print("Video published successfully!")
                return status_response
            elif status == "FAILED":
                fail_reason = status_response["data"].get("fail_reason", "Unknown error")
                raise Exception(f"Upload failed: {fail_reason}")
            elif status in ["PROCESSING_DOWNLOAD", "PROCESSING_UPLOAD", "PROCESSING_VIDEO"]:
                print("Video is still processing...")
                time.sleep(10)  # Wait 10 seconds before checking again
            else:
                print(f"Unknown status: {status}")
                time.sleep(5)
        
        raise Exception(f"Upload timed out after {max_wait_time} seconds")


def upload_to_tiktok(video_path, client_key=None, client_secret=None, title=None, description=None, 
                    privacy_level=None, max_retries=None, wait_minutes=None, config_file="tiktok_config.json"):
    """
    Convenience function to upload a video to TikTok with retry logic.
    
    Args:
        video_path (str): Path to video file
        client_key (str): TikTok app client key (optional if using config file)
        client_secret (str): TikTok app client secret (optional if using config file)
        title (str): Video title/caption (optional, uses config default)
        description (str): Video description (optional)
        privacy_level (str): Privacy level for the video (optional, uses config default)
        max_retries (int): Maximum number of retry attempts (optional, uses config default)
        wait_minutes (int): Minutes to wait between retries (optional, uses config default)
        config_file (str): Path to configuration file
        
    Returns:
        dict: Upload result
    """
    uploader = TikTokUploader(client_key, client_secret, config_file=config_file)
    
    # Get retry settings from config if not provided
    upload_config = uploader.config.get('upload_settings', {})
    max_retries = max_retries or upload_config.get('max_retries', 3)
    wait_minutes = wait_minutes or upload_config.get('wait_minutes_between_retries', 60)
    
    for attempt in range(max_retries):
        try:
            print(f"TikTok upload attempt {attempt + 1}/{max_retries}")
            result = uploader.upload_video(
                video_path=video_path,
                title=title,
                description=description,
                privacy_level=privacy_level
            )
            print("TikTok upload successful!")
            return result
            
        except Exception as e:
            print(f"TikTok upload failed: {e}")
            if attempt < max_retries - 1:
                wait_time = wait_minutes * 60
                print(f"Waiting {wait_minutes} minutes before retry...")
                time.sleep(wait_time)
            else:
                print(f"TikTok upload failed after {max_retries} attempts")
                raise


if __name__ == "__main__":
    # Example usage
    if len(sys.argv) < 2:
        print("Usage: python tiktok_uploader.py <video_path> [title] [--config CONFIG_FILE]")
        print("Example: python tiktok_uploader.py video.mp4 'My Video Title'")
        print("Example: python tiktok_uploader.py video.mp4 --config my_config.json")
        sys.exit(1)
    
    video_path = sys.argv[1]
    title = None
    config_file = "tiktok_config.json"
    
    # Parse arguments
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--config':
            i += 1
            if i < len(sys.argv):
                config_file = sys.argv[i]
        else:
            title = sys.argv[i]
        i += 1
    
    try:
        result = upload_to_tiktok(video_path, title=title, config_file=config_file)
        print("Upload completed successfully!")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Upload failed: {e}")
        sys.exit(1)