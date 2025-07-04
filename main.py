import subprocess
import os
import sys
import argparse
import glob
import time
from datetime import datetime
import pickle
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError


GAMES_DIR = os.path.join(os.path.dirname(__file__), 'games')
VIDEO_SCRIPT = os.path.join(os.path.dirname(__file__), 'pictionary-python-generator.py')
NODE_GAME_SCRIPT = os.path.join(os.path.dirname(__file__), 'pictionary-chain-local.js')


def run_js_game():
    print("[1/4] Running Pictionary game (Node.js)...")
    result = subprocess.run(['node', NODE_GAME_SCRIPT], check=True)
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


def upload_to_youtube(video_path, part_number=None, max_retries=50):
    print(f"[4/4] Uploading video to YouTube (Part {part_number})...")
    # Check for client_secrets.json
    if not os.path.exists('client_secrets.json'):
        raise FileNotFoundError("client_secrets.json not found. Please download your OAuth 2.0 credentials and place them in the project directory.")
    
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
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
    
    youtube = build('youtube', 'v3', credentials=creds)
    
    for attempt in range(max_retries):
        try:
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
            print(f"Video uploaded: https://youtube.com/shorts/{response['id']}")
            return  # Success, exit the retry loop
            
        except HttpError as e:
            error_details = e.error_details[0] if e.error_details else {}
            reason = error_details.get('reason', '')
            
            if reason == 'uploadLimitExceeded':
                if attempt < max_retries - 1:  # Not the last attempt
                    wait_time = 3600  # 1 hour in seconds
                    print(f"Upload limit exceeded. Waiting {wait_time//60} minutes before retry {attempt + 2}/{max_retries}...")
                    next_retry_time = datetime.now().timestamp() + wait_time
                    next_retry_datetime = datetime.fromtimestamp(next_retry_time)
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


def main():
    parser = argparse.ArgumentParser(description="Orchestrate AI Pictionary game, video generation, and YouTube upload.")
    parser.add_argument('--dry-run', action='store_true', help='Run everything except the YouTube upload step.')
    parser.add_argument('--count', type=int, default=1, help='Number of videos to create in a row (default: 1)')
    parser.add_argument('--start-part', type=int, default=1, help='Part number to start on (default: 1)')
    parser.add_argument('--wait-minutes', type=int, default=60, help='Minutes to wait between uploads (default: 60)')
    parser.add_argument('--max-retries', type=int, default=50, help='Maximum number of retries for upload limit errors (default: 50)')
    args = parser.parse_args()

    try:
        for i in range(args.count):
            part_number = args.start_part + i
            print(f"\n=== Starting video creation for Part {part_number} ===")
            run_js_game()
            game_dir = find_latest_game_dir()
            video_path = generate_video(game_dir, part_number=part_number)
            if args.dry_run:
                print("[DRY RUN] Skipping YouTube upload.")
            else:
                upload_to_youtube(video_path, part_number=part_number, max_retries=args.max_retries)
            print(f"All steps completed for Part {part_number}.")
            
            # Wait between uploads (except for the last one)
            if i < args.count - 1:  # Don't wait after the last upload
                wait_seconds = args.wait_minutes * 60
                print(f"\nWaiting {args.wait_minutes} minutes before next upload to avoid throttling...")
                print(f"Next upload will start at: {datetime.now().strftime('%H:%M:%S')}")
                time.sleep(wait_seconds)
                print(f"Resuming at: {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 