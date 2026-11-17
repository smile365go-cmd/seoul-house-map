"""설정값 모음. API 키는 .env 파일에서 읽는다 (코드에 직접 쓰지 않는다)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SEOUL_API_KEY = os.getenv("SEOUL_API_KEY", "").strip()
VWORLD_API_KEY = os.getenv("VWORLD_API_KEY", "").strip()

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "realestate.db"
GEOJSON_PATH = DATA_DIR / "seoul_gu.geojson"

DATA_DIR.mkdir(exist_ok=True)

PYEONG_M2 = 3.3058  # 1평 = 3.3058㎡
