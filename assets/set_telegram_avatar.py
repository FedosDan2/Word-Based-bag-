import json
import urllib.error
import urllib.request
from pathlib import Path


root = Path(__file__).resolve().parents[1]
env_path = root / ".env"
token = None
for line in env_path.read_text(encoding="utf-8").splitlines():
    if line.startswith("TELEGRAM_BOT_TOKEN="):
        token = line.partition("=")[2].strip().strip("\"'")
        break
if not token:
    raise SystemExit("TELEGRAM_BOT_TOKEN is missing from .env")

boundary = "----BugizslovAvatarBoundary7MA4YWxkTrZu0gW"
photo_json = json.dumps({"type": "static", "photo": "attach://avatar"}).encode()
photo_bytes = (root / "assets" / "bugizslov-avatar.jpg").read_bytes()
parts = [
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"\r\nContent-Type: application/json\r\n\r\n".encode(),
    photo_json,
    f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"avatar\"; filename=\"bugizslov-avatar.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".encode(),
    photo_bytes,
    f"\r\n--{boundary}--\r\n".encode(),
]
request = urllib.request.Request(
    f"https://api.telegram.org/bot{token}/setMyProfilePhoto",
    data=b"".join(parts),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read())
except urllib.error.HTTPError as error:
    result = json.loads(error.read())
if not result.get("ok"):
    raise SystemExit(f"Telegram rejected the profile photo: {result.get('description', 'unknown error')}")
print("Telegram bot profile photo updated.")
