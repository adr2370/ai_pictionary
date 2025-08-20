import subprocess
import os
import sys
import argparse
import glob
import time
import re
import json
from datetime import datetime, timedelta
import pickle
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

# Import TikTok uploader
try:
    from tiktok_uploader import upload_to_tiktok
    TIKTOK_AVAILABLE = True
except ImportError:
    print("Warning: TikTok uploader not available. Install tiktok_uploader.py to enable TikTok uploads.")
    TIKTOK_AVAILABLE = False

# Import GitHub uploader
try:
    import requests
    GITHUB_AVAILABLE = True
except ImportError:
    print("Warning: requests not available. Install requests to enable GitHub uploads.")
    GITHUB_AVAILABLE = False


GAMES_DIR = os.path.join(os.path.dirname(__file__), 'games')
VIDEO_SCRIPT = os.path.join(os.path.dirname(__file__), 'pictionary-python-generator.py')
NODE_GAME_SCRIPT = os.path.join(os.path.dirname(__file__), 'pictionary-chain-local.js')


def extract_last_guess_from_game(game_dir):
    """Extract the last guess from a game directory by reading the final round's summary file."""
    try:
        # Find all round summary files
        summary_files = glob.glob(os.path.join(game_dir, 'round_*_summary.txt'))
        if not summary_files:
            print(f"No summary files found in {game_dir}")
            return None
        
        # Sort by round number to find the last one
        def extract_round_number(filename):
            match = re.search(r'round_(\d+)_summary\.txt', os.path.basename(filename))
            return int(match.group(1)) if match else 0
        
        summary_files.sort(key=extract_round_number)
        last_summary_file = summary_files[-1]
        
        # Read the last summary file
        with open(last_summary_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract the AI's guess from the summary
        guess_match = re.search(r"AI's Guess: (.+)", content)
        if guess_match:
            last_guess = guess_match.group(1).strip()
            print(f"Extracted last guess from previous game: '{last_guess}'")
            return last_guess
        else:
            print(f"Could not find AI's guess in {last_summary_file}")
            return None
            
    except Exception as e:
        print(f"Error extracting last guess from {game_dir}: {e}")
        return None


def run_js_game(start_word=None):
    print("[1/4] Running Pictionary game (Node.js)...")
    cmd = ['node', NODE_GAME_SCRIPT]
    if start_word:
        cmd.append(start_word)
        print(f"Starting with word: '{start_word}'")
    result = subprocess.run(cmd, check=True)
    print("Game finished.")


def find_latest_game_dir():
    print("[2/4] Locating latest game directory...")
    game_dirs = [d for d in glob.glob(os.path.join(GAMES_DIR, 'pictionary_game_*')) if os.path.isdir(d)]
    if not game_dirs:
        raise FileNotFoundError("No game directories found.")
    latest = max(game_dirs, key=os.path.getmtime)
    print(f"Latest game directory: {latest}")
    return latest


def generate_video(game_dir, part_number=None):
    print(f"[3/4] Generating video from game session (Part {part_number})...")
    
    # Create videos directory within the project folder if it doesn't exist
    videos_dir = os.path.join(os.path.dirname(__file__), 'videos')
    os.makedirs(videos_dir, exist_ok=True)
    
    # Generate filename like "the_worlds_longest_game_of_pictionary_part_1.mp4", etc.
    if part_number:
        output_name = f"the_worlds_longest_game_of_pictionary_part_{part_number}.mp4"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"pictionary_chain_{timestamp}.mp4"
    
    output_path = os.path.join(videos_dir, output_name)
    
    cmd = [
        sys.executable, VIDEO_SCRIPT,
        '--game-dir', game_dir,
        '--output', output_name
    ]
    if part_number:
        cmd += ['--part', str(part_number)]
    subprocess.run(cmd, check=True)
    
    # Move the generated video to videos directory
    temp_video_path = os.path.join(game_dir, output_name)
    if os.path.exists(temp_video_path):
        import shutil
        shutil.move(temp_video_path, output_path)
        print(f"Video saved to: {output_path}")
    else:
        print(f"Warning: Expected video file not found at {temp_video_path}")
    
    return output_path


def upload_to_youtube(video_path, part_number=None, max_retries=50, wait_minutes=60):
    print(f"[4a/5] Uploading video to YouTube (Part {part_number})...")
    # Check for client_secrets.json
    if not os.path.exists('client_secrets.json'):
        raise FileNotFoundError("client_secrets.json not found. Please download your OAuth 2.0 credentials and place them in the project directory.")
    
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    
    def get_youtube_client():
        """Create a fresh YouTube API client with valid credentials."""
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        return build('youtube', 'v3', credentials=creds)
    
    for attempt in range(max_retries):
        try:
            # Create a fresh YouTube client for each attempt to avoid stale connections
            youtube = get_youtube_client()
            
            request = youtube.videos().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": f"The World's Longest Game of Pictionary Part {part_number}" if part_number else "AI Pictionary Chain Game",
                        "description": "This is the future. We're doomed.",
                        "tags": ["AI", "Pictionary", "Game", "AI Fails", "Comedy", "Funny", "AI Art", "Drawing", "Shorts", "Viral", "Tech Comedy", "AI Generated", "Chain Game", "Automation", "Entertainment"]
                    },
                    "status": {
                        "privacyStatus": "unlisted",
                        "selfDeclaredMadeForKids": False
                    }
                },
                media_body=MediaFileUpload(video_path)
            )
            response = request.execute()
            print(f"Video uploaded to YouTube: https://youtube.com/shorts/{response['id']}")
            return response  # Success, exit the retry loop
            
        except HttpError as e:
            error_details = e.error_details[0] if e.error_details else {}
            reason = error_details.get('reason', '')
            
            if reason == 'uploadLimitExceeded':
                if attempt < max_retries - 1:  # Not the last attempt
                    wait_time = wait_minutes * 60  # Convert minutes to seconds
                    print(f"Upload limit exceeded. Waiting {wait_minutes} minutes before retry {attempt + 2}/{max_retries}...")
                    current_time = datetime.now()
                    next_retry_datetime = current_time + timedelta(seconds=wait_time)
                    print(f"Next retry will be at: {next_retry_datetime.strftime('%H:%M:%S')}")
                    time.sleep(wait_time)
                    print(f"Retrying upload at: {datetime.now().strftime('%H:%M:%S')}")
                    continue
                else:
                    print(f"Upload limit exceeded after {max_retries} attempts. Giving up.")
                    raise
            else:
                # For other HTTP errors, don't retry
                print(f"HTTP Error occurred: {e}")
                raise
        except Exception as e:
            # For non-HTTP errors, don't retry
            print(f"Error during upload: {e}")
            raise


def upload_to_tiktok_with_retry(video_path, client_key, client_secret, part_number=None, max_retries=50, wait_minutes=60):
    """Upload video to TikTok with retry logic."""
    print(f"[4b/5] Uploading video to TikTok (Part {part_number})...")
    
    if not TIKTOK_AVAILABLE:
        print("TikTok uploader not available. Skipping TikTok upload.")
        return None
    
    if not client_key or not client_secret:
        print("TikTok credentials not provided. Skipping TikTok upload.")
        return None
    
    # Generate title for TikTok
    title = f"The World's Longest Game of Pictionary Part {part_number} #AI #Pictionary #Comedy #ArtificialIntelligence #GameShow" if part_number else "AI Pictionary Chain Game #AI #Pictionary #Comedy"
    
    for attempt in range(max_retries):
        try:
            result = upload_to_tiktok(
                video_path=video_path,
                client_key=client_key,
                client_secret=client_secret,
                title=title,
                privacy_level="PUBLIC_TO_EVERYONE",  # Change to SELF_ONLY for testing
                max_retries=1,  # Don't double-retry inside the function
                wait_minutes=0
            )
            print("Video uploaded to TikTok successfully!")
            return result
            
        except Exception as e:
            print(f"TikTok upload failed: {e}")
            if attempt < max_retries - 1:
                wait_time = wait_minutes * 60
                print(f"Waiting {wait_minutes} minutes before retry {attempt + 2}/{max_retries}...")
                current_time = datetime.now()
                next_retry_datetime = current_time + timedelta(seconds=wait_time)
                print(f"Next retry will be at: {next_retry_datetime.strftime('%H:%M:%S')}")
                time.sleep(wait_time)
                print(f"Retrying TikTok upload at: {datetime.now().strftime('%H:%M:%S')}")
                continue
            else:
                print(f"TikTok upload failed after {max_retries} attempts. Continuing without TikTok upload.")
                return None


def get_github_config():
    if not os.path.exists('github_config.json'):
        raise FileNotFoundError("github_config.json not found. Please create it with your GitHub token and repo.")
    with open('github_config.json', 'r') as f:
        config = json.load(f)
    token = config.get('token')
    repo = config.get('repo')
    if not token or not repo:
        raise ValueError("github_config.json must contain 'token' and 'repo'.")
    return token, repo


def upload_to_github_release(video_path, part_number=None):
    """Upload a video to GitHub Releases and return the direct .mp4 URL."""
    print(f"[4c/5] Uploading video to GitHub Releases (Part {part_number})...")
    if not GITHUB_AVAILABLE:
        print("GitHub uploader not available. Skipping GitHub upload.")
        return None
    import time
    import requests
    from requests.exceptions import Timeout, ConnectionError
    try:
        token, repo = get_github_config()
        video_name = os.path.basename(video_path)
        tag = "pictionary-videos"
        release_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        REQUEST_TIMEOUT = (10, 300)  # (connect, read) in seconds
        r = requests.get(release_url, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code == 404:
            create_url = f"https://api.github.com/repos/{repo}/releases"
            data = {
                'tag_name': tag,
                'name': 'AI Pictionary Videos',
                'body': 'Batch upload of AI Pictionary videos',
                'draft': False,
                'prerelease': False
            }
            r = requests.post(create_url, headers=headers, json=data, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            release = r.json()
        else:
            release = r.json()
        upload_url = release['upload_url'].split('{')[0]
        assets_url = release['assets_url']
        # Paginate through all assets
        all_assets = []
        page = 1
        while True:
            paged_url = assets_url + f'?per_page=100&page={page}'
            resp = requests.get(paged_url, headers=headers, timeout=REQUEST_TIMEOUT)
            assets = resp.json()
            if not isinstance(assets, list) or not assets:
                break
            all_assets.extend(assets)
            if len(assets) < 100:
                break
            page += 1
        deleted_any = False
        for asset in all_assets:
            if asset['name'] == video_name:
                print(f"⚠️ Asset {video_name} already exists. Deleting before upload...")
                delete_url = asset['url']
                try:
                    del_resp = requests.delete(delete_url, headers=headers, timeout=REQUEST_TIMEOUT)
                except (Timeout, ConnectionError) as e:
                    print(f"❌ Timeout or connection error during asset deletion: {e}")
                    continue
                if del_resp.status_code == 204:
                    print(f"✅ Deleted existing asset: {video_name}")
                    deleted_any = True
                else:
                    print(f"❌ Failed to delete existing asset: {video_name}. Status: {del_resp.status_code}, Response: {del_resp.text}")
                    raise Exception(f"Failed to delete existing asset: {video_name}")
        if deleted_any:
            time.sleep(2)
            # Re-fetch asset list for debug
            resp = requests.get(assets_url + '?per_page=100', headers=headers, timeout=REQUEST_TIMEOUT)
        # Upload asset with robust retry logic
        max_upload_retries = 1000
        max_backoff = 600  # 10 minutes
        for attempt in range(max_upload_retries):
            try:
                with open(video_path, 'rb') as f:
                    upload_headers = headers.copy()
                    upload_headers['Content-Type'] = 'video/mp4'
                    params = {'name': video_name}
                    upload_resp = requests.post(
                        upload_url,
                        headers=upload_headers,
                        params=params,
                        data=f,
                        timeout=REQUEST_TIMEOUT
                    )
                if upload_resp.status_code >= 500 or upload_resp.status_code == 429:
                    # Server error or rate limit, retry
                    raise requests.exceptions.HTTPError(f"Server error or rate limit: {upload_resp.status_code}")
                if upload_resp.status_code >= 400 and upload_resp.status_code not in (422, 429):
                    # Unrecoverable client error (auth, bad request, etc.)
                    print(f"❌ Unrecoverable error: {upload_resp.status_code} {upload_resp.text}")
                    return None
                upload_resp.raise_for_status()
                asset = upload_resp.json()
                print(f"✅ Uploaded to GitHub Releases: {asset['browser_download_url']}")
                return {
                    'name': video_name,
                    'download_url': asset['browser_download_url']
                }
            except (Timeout, ConnectionError) as e:
                wait_time = min(2 ** attempt, max_backoff)
                print(f"GitHub upload attempt {attempt+1} failed due to timeout/connection error: {e}")
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            except requests.exceptions.HTTPError as e:
                if upload_resp.status_code in (429, 500, 502, 503, 504):
                    wait_time = min(2 ** attempt, max_backoff)
                    print(f"GitHub upload attempt {attempt+1} failed due to HTTP error: {e}")
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                elif upload_resp.status_code == 422:
                    print(f"GitHub upload failed: {e}")
                    print(f"GitHub response: {upload_resp.text}")
                    print("❌ 422 Unprocessable Entity: This usually means the asset already exists, the file is too large, or the upload parameters are invalid.")
                    return None
                else:
                    print(f"❌ Unrecoverable HTTP error: {upload_resp.status_code} {upload_resp.text}")
                    return None
            except Exception as e:
                print(f"GitHub upload failed: {e}")
                wait_time = min(2 ** attempt, max_backoff)
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
        print(f"❌ GitHub upload failed after {max_upload_retries} attempts.")
        return None
    except Exception as e:
        print(f"GitHub upload failed: {e}")
        return None


def upload_image_to_github_release(image_path, part_number=None):
    """Upload a PNG image to GitHub Releases and return the direct .png URL."""
    print(f"[4d/5] Uploading thumbnail to GitHub Releases (Part {part_number})...")
    if not GITHUB_AVAILABLE:
        print("GitHub uploader not available. Skipping GitHub upload.")
        return None
    import time
    import requests
    from requests.exceptions import Timeout, ConnectionError
    try:
        token, repo = get_github_config()
        image_name = os.path.basename(image_path)
        tag = "pictionary-videos"
        release_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        REQUEST_TIMEOUT = (10, 300)
        r = requests.get(release_url, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code == 404:
            create_url = f"https://api.github.com/repos/{repo}/releases"
            data = {
                'tag_name': tag,
                'name': 'AI Pictionary Videos',
                'body': 'Batch upload of AI Pictionary videos',
                'draft': False,
                'prerelease': False
            }
            r = requests.post(create_url, headers=headers, json=data, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            release = r.json()
        else:
            release = r.json()
        upload_url = release['upload_url'].split('{')[0]
        assets_url = release['assets_url']
        # Paginate through all assets
        all_assets = []
        page = 1
        while True:
            paged_url = assets_url + f'?per_page=100&page={page}'
            resp = requests.get(paged_url, headers=headers, timeout=REQUEST_TIMEOUT)
            assets = resp.json()
            if not isinstance(assets, list) or not assets:
                break
            all_assets.extend(assets)
            if len(assets) < 100:
                break
            page += 1
        deleted_any = False
        for asset in all_assets:
            if asset['name'] == image_name:
                print(f"⚠️ Thumbnail {image_name} already exists. Deleting before upload...")
                delete_url = asset['url']
                try:
                    del_resp = requests.delete(delete_url, headers=headers, timeout=REQUEST_TIMEOUT)
                except (Timeout, ConnectionError) as e:
                    print(f"❌ Timeout or connection error during thumbnail deletion: {e}")
                    continue
                if del_resp.status_code == 204:
                    print(f"✅ Deleted existing thumbnail: {image_name}")
                    deleted_any = True
                else:
                    print(f"❌ Failed to delete existing thumbnail: {image_name}. Status: {del_resp.status_code}, Response: {del_resp.text}")
                    raise Exception(f"Failed to delete existing thumbnail: {image_name}")
        if deleted_any:
            time.sleep(2)
            # Re-fetch asset list for debug
            resp = requests.get(assets_url + '?per_page=100', headers=headers, timeout=REQUEST_TIMEOUT)
        # Upload asset with robust retry logic
        max_upload_retries = 1000
        max_backoff = 600  # 10 minutes
        for attempt in range(max_upload_retries):
            try:
                with open(image_path, 'rb') as f:
                    upload_headers = headers.copy()
                    upload_headers['Content-Type'] = 'image/png'
                    params = {'name': image_name}
                    upload_resp = requests.post(
                        upload_url,
                        headers=upload_headers,
                        params=params,
                        data=f,
                        timeout=REQUEST_TIMEOUT
                    )
                if upload_resp.status_code >= 500 or upload_resp.status_code == 429:
                    # Server error or rate limit, retry
                    raise requests.exceptions.HTTPError(f"Server error or rate limit: {upload_resp.status_code}")
                if upload_resp.status_code >= 400 and upload_resp.status_code not in (422, 429):
                    # Unrecoverable client error (auth, bad request, etc.)
                    print(f"❌ Unrecoverable error: {upload_resp.status_code} {upload_resp.text}")
                    return None
                upload_resp.raise_for_status()
                asset = upload_resp.json()
                print(f"✅ Uploaded thumbnail to GitHub Releases: {asset['browser_download_url']}")
                return {
                    'name': image_name,
                    'download_url': asset['browser_download_url']
                }
            except (Timeout, ConnectionError) as e:
                wait_time = min(2 ** attempt, max_backoff)
                print(f"GitHub thumbnail upload attempt {attempt+1} failed due to timeout/connection error: {e}")
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            except requests.exceptions.HTTPError as e:
                if upload_resp.status_code in (429, 500, 502, 503, 504):
                    wait_time = min(2 ** attempt, max_backoff)
                    print(f"GitHub thumbnail upload attempt {attempt+1} failed due to HTTP error: {e}")
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                elif upload_resp.status_code == 422:
                    print(f"GitHub thumbnail upload failed: {e}")
                    print(f"GitHub response: {upload_resp.text}")
                    print("❌ 422 Unprocessable Entity: This usually means the asset already exists, the file is too large, or the upload parameters are invalid.")
                    return None
                else:
                    print(f"❌ Unrecoverable HTTP error: {upload_resp.status_code} {upload_resp.text}")
                    return None
            except Exception as e:
                print(f"GitHub thumbnail upload failed: {e}")
                wait_time = min(2 ** attempt, max_backoff)
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
        print(f"❌ GitHub thumbnail upload failed after {max_upload_retries} attempts.")
        return None
    except Exception as e:
        print(f"GitHub thumbnail upload failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Orchestrate AI Pictionary game, video generation, and social media uploads.")
    parser.add_argument('--dry-run', action='store_true', help='Run everything except the upload steps.')
    parser.add_argument('--count', type=int, default=1, help='Number of videos to create in a row (default: 1)')
    parser.add_argument('--start-part', type=int, default=1, help='Part number to start on (default: 1)')
    parser.add_argument('--wait-minutes', type=int, default=60, help='Minutes to wait between uploads and retries (default: 60)')
    parser.add_argument('--max-retries', type=int, default=50, help='Maximum number of retries for upload limit errors (default: 50)')
    parser.add_argument('--no-chain-games', action='store_true', help='Disable chaining - each game starts with a random word instead of using the last guess from the previous game')
    
    # YouTube options
    parser.add_argument('--upload-youtube', action='store_true', help='Upload to YouTube (disabled by default)')
    
    # TikTok options
    parser.add_argument('--upload-tiktok', action='store_true', help='Upload to TikTok (disabled by default)')
    parser.add_argument('--tiktok-config', default='tiktok_config.json', help='TikTok configuration file (default: tiktok_config.json)')
    parser.add_argument('--tiktok-client-key', help='TikTok app client key (overrides config file)')
    parser.add_argument('--tiktok-client-secret', help='TikTok app client secret (overrides config file)')
    parser.add_argument('--tiktok-privacy', choices=['PUBLIC_TO_EVERYONE', 'MUTUAL_FOLLOW_FRIENDS', 'SELF_ONLY'], 
                       help='TikTok video privacy level (overrides config file)')
    
    # CSV scheduling options
    parser.add_argument('--hours-ahead', type=int, default=3, help='Hours ahead of now to schedule the first video (default: 3)')
    parser.add_argument('--start-time', help='Exact start time for first video (format: YYYY-MM-DD HH:MM, timezone: PST)')
    parser.add_argument('--posts-per-day', type=int, default=8, help='Number of posts per day for bulk upload scheduling (default: 8)')
    parser.add_argument('--start-word', type=str, help='Specify the starting word for the first game (overrides random/chain for first game only)')
    
    args = parser.parse_args()

    # Load TikTok configuration
    tiktok_config = {}
    if os.path.exists(args.tiktok_config):
        try:
            with open(args.tiktok_config, 'r') as f:
                config_data = json.load(f)
            tiktok_config = config_data.get('tiktok', {})
            print(f"TikTok configuration loaded from {args.tiktok_config}")
        except Exception as e:
            print(f"Warning: Could not load TikTok config: {e}")

    # Get TikTok credentials from args, config file, or environment (in order of preference)
    tiktok_client_key = (args.tiktok_client_key or 
                        tiktok_config.get('client_key') or 
                        os.getenv('TIKTOK_CLIENT_KEY'))
    tiktok_client_secret = (args.tiktok_client_secret or 
                           tiktok_config.get('client_secret') or 
                           os.getenv('TIKTOK_CLIENT_SECRET'))
    tiktok_privacy_level = (args.tiktok_privacy or 
                           tiktok_config.get('default_privacy', 'SELF_ONLY'))
    
    if args.upload_tiktok and TIKTOK_AVAILABLE:
        if not tiktok_client_key or not tiktok_client_secret:
            print("Warning: TikTok credentials not found. TikTok uploads will be skipped.")
            print("Configure credentials in one of these ways:")
            print(f"  1. Create {args.tiktok_config} with client_key and client_secret")
            print("  2. Use --tiktok-client-key and --tiktok-client-secret arguments")
            print("  3. Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET environment variables")
            args.upload_tiktok = False

    try:
        # Calculate interval based on posts per day
        posts_per_day = args.posts_per_day
        interval_hours = 24 / posts_per_day
        print(f"🕒 Scheduling {posts_per_day} posts per day, every {interval_hours:.2f} hours.")
        
        previous_game_dir = None
        for i in range(args.count):
            part_number = args.start_part + i
            print(f"\n=== Starting video creation for Part {part_number} ===")
            
            # For the first game, use --start-word if provided, else use chain/random logic
            start_word = None
            if i == 0 and args.start_word:
                start_word = args.start_word
                print(f"First game - using user-specified starting word: '{start_word}'")
            elif not args.no_chain_games and i > 0 and previous_game_dir:
                start_word = extract_last_guess_from_game(previous_game_dir)
                if start_word:
                    print(f"Using last guess from previous game as starting word: '{start_word}'")
                else:
                    print("Could not extract last guess from previous game, using random word")
            elif not args.no_chain_games and i == 0:
                print("First game in chain - using random starting word")
            elif args.no_chain_games:
                print("Chain mode disabled - each game starts with a random word")
            
            run_js_game(start_word)
            game_dir = find_latest_game_dir()
            previous_game_dir = game_dir  # Store for next iteration
            video_path = generate_video(game_dir, part_number=part_number)
            
            if args.dry_run:
                print("[DRY RUN] Skipping all uploads.")
            else:
                # Track upload results
                youtube_result = None
                tiktok_result = None
                github_result = None
                
                # Upload to YouTube (only if explicitly requested)
                if args.upload_youtube:
                    try:
                        youtube_result = upload_to_youtube(
                            video_path, 
                            part_number=part_number, 
                            max_retries=args.max_retries, 
                            wait_minutes=args.wait_minutes
                        )
                    except Exception as e:
                        print(f"YouTube upload failed: {e}")
                else:
                    print("YouTube upload skipped (use --upload-youtube to enable)")
                
                # Upload to TikTok (only if explicitly requested)
                if args.upload_tiktok and TIKTOK_AVAILABLE and tiktok_client_key and tiktok_client_secret:
                    try:
                        # Generate title from config template if available
                        title_template = tiktok_config.get('default_title_template', 
                                                         'The World\'s Longest Game of Pictionary Part {part} #{hashtags}')
                        hashtags = ' '.join(f'#{tag}' for tag in tiktok_config.get('hashtags', ['AI', 'Pictionary', 'Comedy'])[:3])
                        title = title_template.replace('{part}', str(part_number)).replace('{hashtags}', hashtags)
                        
                        tiktok_result = upload_to_tiktok(
                            video_path=video_path,
                            client_key=tiktok_client_key,
                            client_secret=tiktok_client_secret,
                            title=title,
                            privacy_level=tiktok_privacy_level,
                            config_file=args.tiktok_config
                        )
                        print("TikTok upload completed successfully!")
                        
                    except Exception as e:
                        print(f"TikTok upload failed: {e}")
                else:
                    print("TikTok upload skipped (use --upload-tiktok to enable)")
                
                # Upload to GitHub Releases (enabled by default)
                try:
                    github_result = upload_to_github_release(video_path, part_number=part_number)
                except Exception as e:
                    print(f"GitHub upload failed: {e}")
                    github_result = None
                if not github_result or not github_result.get('download_url'):
                    print("❌ GitHub video upload failed. Stopping script. No CSV row will be written for this video.")
                    sys.exit(2)
                # Upload thumbnail to GitHub Releases
                thumbnail_url = ''
                try:
                    videos_dir = os.path.join(os.path.dirname(__file__), 'videos')
                    thumbnail_name = f"the_worlds_longest_game_of_pictionary_part_{part_number}_thumbnail.png"
                    thumbnail_path = os.path.join(videos_dir, thumbnail_name)
                    if os.path.exists(thumbnail_path):
                        thumbnail_result = upload_image_to_github_release(thumbnail_path, part_number=part_number)
                        if thumbnail_result and thumbnail_result.get('download_url'):
                            thumbnail_url = thumbnail_result['download_url']
                    else:
                        print(f"Thumbnail not found at {thumbnail_path}, skipping upload.")
                except Exception as e:
                    print(f"GitHub thumbnail upload failed: {e}")
                    thumbnail_url = ''
                
                if github_result and github_result.get('download_url'):
                    print(f"✓ GitHub: {github_result['download_url']}")
                    # CSV logic (same as before, but use github_result['download_url'])
                    import csv
                    from datetime import datetime, timedelta
                    import pytz
                    pst = pytz.timezone('US/Pacific')
                    csv_folder = 'bulk_upload_csvs'
                    os.makedirs(csv_folder, exist_ok=True)
                    if 'csv_start_time' not in locals():
                        if args.start_time:
                            try:
                                csv_start_time = datetime.strptime(args.start_time, '%Y-%m-%d %H:%M')
                                csv_start_time = pst.localize(csv_start_time)
                                print(f"📅 Using custom start time: {csv_start_time.strftime('%Y-%m-%d %H:%M %Z')}")
                            except ValueError:
                                print(f"❌ Invalid start time format: {args.start_time}. Use YYYY-MM-DD HH:MM")
                                print(f"📅 Falling back to {args.hours_ahead} hours ahead")
                                csv_start_time = datetime.now(pst) + timedelta(hours=args.hours_ahead)
                                csv_start_time = csv_start_time.replace(minute=0, second=0, microsecond=0)
                        else:
                            csv_start_time = datetime.now(pst) + timedelta(hours=args.hours_ahead)
                            csv_start_time = csv_start_time.replace(minute=0, second=0, microsecond=0)
                            print(f"📅 Scheduling first video {args.hours_ahead} hours ahead: {csv_start_time.strftime('%Y-%m-%d %H:%M %Z')}")
                        csv_filename = f'ai_pictionary_bulk_upload_{csv_start_time.strftime("%Y%m%d_%H%M%S")}.csv'
                        csv_filepath = os.path.join(csv_folder, csv_filename)
                        headers = [
                            'Labels', 'Text', 'Year', 'Month (1 to 12)', 'Date', 'Hour (From 0 to 23)',
                            'Minutes', 'Queue Schedule', 'Post Type', 'Video Title', 'Video URL',
                            'Thumbnail URL', 'Subtitles URL', 'Subtitles Language', 'Subtitles Auto-Sync',
                            'Privacy Status', 'Category', 'Playlist', 'Tags', 'License', 'Embeddable',
                            'Notify Subscribers', 'Made For Kids'
                        ]
                        with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
                            writer = csv.DictWriter(csvfile, fieldnames=headers)
                            writer.writeheader()
                    video_time = csv_start_time + timedelta(hours=(part_number - args.start_part) * interval_hours)
                    row = {
                        'Labels': f'Part {part_number}',
                        'Text': f"The World's Longest Game of Pictionary Part {part_number}. This is the future. We're doomed. #AI #Pictionary #Comedy #ArtificialIntelligence",
                        'Year': video_time.year,
                        'Month (1 to 12)': video_time.month,
                        'Date': video_time.day,
                        'Hour (From 0 to 23)': video_time.hour,
                        'Minutes': video_time.minute,
                        'Queue Schedule': '',
                        'Post Type': 'SHORTS',
                        'Video Title': f"The World's Longest Game of Pictionary Part {part_number}",
                        'Video URL': github_result['download_url'],
                        'Thumbnail URL': thumbnail_url,
                        'Subtitles URL': '',
                        'Subtitles Language': '',
                        'Subtitles Auto-Sync': '',
                        'Privacy Status': 'PUBLIC',
                        'Category': 'Comedy',
                        'Playlist': '',
                        'Tags': 'AI,Pictionary,Comedy,ArtificialIntelligence,Game,AI Fails,Funny',
                        'License': 'YOUTUBE',
                        'Embeddable': 'YES',
                        'Notify Subscribers': 'NO',
                        'Made For Kids': 'NO'
                    }
                    with open(csv_filepath, 'a', newline='', encoding='utf-8') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=headers)
                        writer.writerow(row)
                    print(f"💾 Added to CSV: {csv_filepath}")
                else:
                    print("✗ GitHub: Upload failed or no download URL returned. Skipping CSV row for this video.")
            
            print(f"All steps completed for Part {part_number}.")
            
            # Wait between uploads (except for the last one, and only if uploading to platforms with rate limits)
            if i < args.count - 1 and (args.upload_youtube or args.upload_tiktok):
                wait_seconds = args.wait_minutes * 60
                current_time = datetime.now()
                next_upload_time = current_time + timedelta(seconds=wait_seconds)
                print(f"\nWaiting {args.wait_minutes} minutes before next upload to avoid throttling...")
                print(f"Next upload will start at: {next_upload_time.strftime('%H:%M:%S')}")
                time.sleep(wait_seconds)
                print(f"Resuming at: {datetime.now().strftime('%H:%M:%S')}")
            elif i < args.count - 1:
                print(f"\nProceeding to next video immediately (no uploads enabled)")
                
        # Final CSV summary
        if 'csv_filepath' in locals():
            print(f"\n✅ Final CSV Summary:")
            print(f"📁 CSV file: {csv_filepath}")
            print(f"📊 Total videos in CSV: {part_number - args.start_part + 1}")
            print(f"📅 Start time: {csv_start_time.strftime('%Y-%m-%d %H:%M %Z')}")
            print(f"📅 End time: {(csv_start_time + timedelta(hours=(part_number - args.start_part) * interval_hours)).strftime('%Y-%m-%d %H:%M %Z')}")
            print(f"⏰ Schedule: {posts_per_day} videos per day, every {interval_hours:.2f} hours")
            print(f"📁 CSV saved in: bulk_upload_csvs/")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()