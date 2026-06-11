.PHONY: synopsis docs

# 최상위 README.md Synopsis 갱신
synopsis: README-template.md main.py
  python tools/update-synopsis.py

# docs/README.md 문서 목록 갱신 (스크립트 추가 시 활성화)
# docs-readme: docs/
# 	python tools/update-docs-readme.py

# 전체 문서 갱신
docs: synopsis
