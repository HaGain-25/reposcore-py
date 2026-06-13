import sys
from pathlib import Path

# 프로젝트 루트 경로를 추가하여 로컬 모듈(gh_service 등)을 찾을 수 있게 합니다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
