# reposcore-py

A CLI for scoring student participation in an open-source class repo, implemented in Python using GraphQL.

## Quick Start

처음 도구를 사용하는 분들을 위한 구체적인 실행 예시입니다. 아래 명령어들을 복사하여 터미널에서 바로 테스트해 볼 수 있습니다.

### 1. 단일 저장소 조회
가장 기본적인 형태로, 하나의 저장소에 대한 기여자 점수를 조회합니다.
```bash
reposcore oss2026hnu/reposcore-py
```

### 2. 여러 저장소 조회
공백으로 구분하여 여러 저장소 경로를 입력하면, 각 저장소의 결과를 한 번에 조회할 수 있습니다.
```bash
reposcore oss2026hnu/reposcore-py oss2026hnu/reposcore-cs oss2026hnu/reposcore-ts
```

### 3. `--format` 옵션을 사용한 출력 형식 지정
`-f` 또는 `--format` 옵션을 사용하여 출력 포맷을 지정합니다. (기본값: txt)
```bash
# CSV 형식으로 출력
reposcore oss2026hnu/reposcore-py --format csv

# HTML 형식으로 출력
reposcore oss2026hnu/reposcore-py --format html
```

### 4. `--output` 옵션을 사용한 파일 저장 위치 지정
`-o` 또는 `--output` 옵션을 사용해 결과를 터미널에 출력하는 대신 지정한 디렉터리 경로에 파일로 저장합니다.
```bash
reposcore oss2026hnu/reposcore-py --format html --output ./result
```

### 5. `--aggregate` 옵션을 사용한 다중 저장소 점수 합산
여러 저장소를 조회할 때, 기본값은 저장소별로 점수를 각각 출력합니다.
`--aggregate` 옵션을 붙이면 여러 저장소의 기여를 사용자 단위로 합산하여 전체 점수를 출력합니다.
```bash
# 저장소별 점수를 각각 출력 (기본 동작)
reposcore oss2026hnu/reposcore-py oss2026hnu/reposcore-cs

# 두 저장소의 기여를 합산한 전체 점수 출력
reposcore oss2026hnu/reposcore-py oss2026hnu/reposcore-cs --aggregate
```

## Synopsis

```text
Usage: reposcore [OPTIONS] REPOS...

 Fetch basic repository counts from GitHub GraphQL API.

Arguments
  *    repos      REPOS...  조회할 GitHub 저장소 경로입니다. 예: owner/repo1 owner/repo2
                            [required]

Options
  --version             -v                                 현재 버전을 출력하고 종료합니다.
  --format              -f      [csv|txt|html]             출력 파일 형식을 지정합니다. (csv | tx…
                                                           | html)
                                                           [default: txt]
  --output              -o      TEXT                       결과를 저장할 출력 디렉터리 경로입니다…
                                                           생략하면 파일로 저장하지 않고 stdout에
                                                           출력합니다. 예: ./result
  --token               -t      TEXT                       GitHub Personal Access Token. 미제공  …
                                                           GITHUB_TOKEN 환경 변수를 사용합니다.
  --aggregate                                              여러 저장소의 결과를 하나로 합산하여
                                                           전체 기여 점수를 출력합니다.
  --no-cache                                               캐시를 사용하지 않고 GitHub API에서
                                                           최신 데이터를 다시 조회합니다.
  --since                       TEXT                       이 날짜 이후의 기여만 점수 계산에
                                                           포함합니다. 예: 2026-06-01 (YYYY-MM-DD)
  --until                       TEXT                       이 날짜까지의 기여만 점수 계산에
                                                           포함합니다. 예: 2026-06-10 (YYYY-MM-DD)
  --page-size                   INTEGER RANGE [1<=x<=100]  GraphQL 페이지네이션의 페이지
                                                           크기입니다. (1~100)
                                                           [env var: REPOSCORE_PAGE_SIZE]
                                                           [default: 100]
  --install-completion                                     Install completion for the current
                                                           shell.
  --show-completion                                        Show completion for the current shell,
                                                           to copy it or customize the
                                                           installation.
  --help                                                   Show this message and exit.
```
