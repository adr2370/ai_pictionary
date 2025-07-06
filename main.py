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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_name = f"pictionary_chain_{timestamp}_part{part_number}.mp4" if part_number else f"pictionary_chain_{timestamp}.mp4"
    output_path = os.path.join(game_dir, output_name)
    cmd = [
        sys.executable, VIDEO_SCRIPT,
        '--game-dir', game_dir,
        '--output', output_name
    ]
    if part_number:
        cmd += ['--part', str(part_number)]
    subprocess.run(cmd, check=True)
    print(f"Video generated: {output_path}")
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


def main():
    parser = argparse.ArgumentParser(description="Orchestrate AI Pictionary game, video generation, and social media uploads.")
    parser.add_argument('--dry-run', action='store_true', help='Run everything except the upload steps.')
    parser.add_argument('--count', type=int, default=1, help='Number of videos to create in a row (default: 1)')
    parser.add_argument('--start-part', type=int, default=1, help='Part number to start on (default: 1)')
    parser.add_argument('--wait-minutes', type=int, default=60, help='Minutes to wait between uploads and retries (default: 60)')
    parser.add_argument('--max-retries', type=int, default=50, help='Maximum number of retries for upload limit errors (default: 50)')
    parser.add_argument('--chain-games', action='store_true', help='Use the last guess from each game as the starting word for the next game (creates a continuous chain)')
    
    # YouTube options
    parser.add_argument('--skip-youtube', action='store_true', help='Skip YouTube upload')
    
    # TikTok options
    parser.add_argument('--skip-tiktok', action='store_true', help='Skip TikTok upload')
    parser.add_argument('--tiktok-config', default='tiktok_config.json', help='TikTok configuration file (default: tiktok_config.json)')
    parser.add_argument('--tiktok-client-key', help='TikTok app client key (overrides config file)')
    parser.add_argument('--tiktok-client-secret', help='TikTok app client secret (overrides config file)')
    parser.add_argument('--tiktok-privacy', choices=['PUBLIC_TO_EVERYONE', 'MUTUAL_FOLLOW_FRIENDS', 'SELF_ONLY'], 
                       help='TikTok video privacy level (overrides config file)')
    
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
    
    if not args.skip_tiktok and TIKTOK_AVAILABLE:
        if not tiktok_client_key or not tiktok_client_secret:
            print("Warning: TikTok credentials not found. TikTok uploads will be skipped.")
            print("Configure credentials in one of these ways:")
            print(f"  1. Create {args.tiktok_config} with client_key and client_secret")
            print("  2. Use --tiktok-client-key and --tiktok-client-secret arguments")
            print("  3. Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET environment variables")
            args.skip_tiktok = True

    try:
        previous_game_dir = None
        for i in range(args.count):
            part_number = args.start_part + i
            print(f"\n=== Starting video creation for Part {part_number} ===")
            
            # For the first game, use no start word (random). For subsequent games, use the last guess from the previous game if chaining is enabled.
            start_word = None
            if args.chain_games and i > 0 and previous_game_dir:
                start_word = extract_last_guess_from_game(previous_game_dir)
                if start_word:
                    print(f"Using last guess from previous game as starting word: '{start_word}'")
                else:
                    print("Could not extract last guess from previous game, using random word")
            elif args.chain_games and i == 0:
                print("First game in chain - using random starting word")
            elif not args.chain_games:
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
                
                # Upload to YouTube
                if not args.skip_youtube:
                    try:
                        youtube_result = upload_to_youtube(
                            video_path, 
                            part_number=part_number, 
                            max_retries=args.max_retries, 
                            wait_minutes=args.wait_minutes
                        )
                    except Exception as e:
                        print(f"YouTube upload failed: {e}")
                
                # Upload to TikTok
                if not args.skip_tiktok and TIKTOK_AVAILABLE and tiktok_client_key and tiktok_client_secret:
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
                
                # Summary
                print(f"\n=== Upload Summary for Part {part_number} ===")
                if youtube_result:
                    print(f"✓ YouTube: https://youtube.com/shorts/{youtube_result['id']}")
                else:
                    print("✗ YouTube: Upload failed or skipped")
                
                if tiktok_result:
                    post_ids = tiktok_result.get('data', {}).get('publicaly_available_post_id', [])
                    if post_ids:
                        print(f"✓ TikTok: Post ID {post_ids[0]}")
                    else:
                        print("✓ TikTok: Upload successful (processing)")
                else:
                    print("✗ TikTok: Upload failed or skipped")
            
            print(f"All steps completed for Part {part_number}.")
            
            # Wait between uploads (except for the last one)
            if i < args.count - 1:  # Don't wait after the last upload
                wait_seconds = args.wait_minutes * 60
                current_time = datetime.now()
                next_upload_time = current_time + timedelta(seconds=wait_seconds)
                print(f"\nWaiting {args.wait_minutes} minutes before next upload to avoid throttling...")
                print(f"Next upload will start at: {next_upload_time.strftime('%H:%M:%S')}")
                time.sleep(wait_seconds)
                print(f"Resuming at: {datetime.now().strftime('%H:%M:%S')}")
                
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()