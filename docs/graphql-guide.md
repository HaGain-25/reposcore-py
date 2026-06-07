# GitHub GraphQL API 기본 사용 가이드

이 문서는 `reposcore-py` 프로젝트에서 GitHub GraphQL API를 Python으로 사용하는 기본 방법을 정리합니다.

---

## 목차

- [GitHub GraphQL API를 사용하는 목적](#github-graphql-api를-사용하는-목적)
- [REST API와 GraphQL API의 차이](#rest-api와-graphql-api의-차이)
- [gql 라이브러리 기본 구조](#gql-라이브러리-기본-구조)
- [GITHUB_TOKEN 환경 변수 설정](#github_token-환경-변수-설정)
- [RequestsHTTPTransport 설정](#requestshttptransport-설정)
- [저장소 기본 정보 조회 예시](#저장소-기본-정보-조회-예시)
- [Issue / PR 개수 조회 예시](#issue--pr-개수-조회-예시)
- [GraphQL 응답 데이터 처리에 Pydantic 활용하기](#graphql-응답-데이터-처리에-pydantic-활용하기)
- [GraphQL 쿼리 작성 시 주의사항](#graphql-쿼리-작성-시-주의사항)

---

## GitHub GraphQL API를 사용하는 목적

`reposcore-py`는 GitHub 저장소의 기여자별 활동 데이터를 수집하고 점수화하는 프로젝트입니다.
이를 위해 저장소의 Issue, PR, 커밋 등 다양한 데이터를 GitHub API로부터 가져와야 합니다.

GitHub GraphQL API를 사용하면 다음과 같은 이점이 있습니다:

- **필요한 데이터만 선택적으로 요청**할 수 있어 불필요한 네트워크 트래픽을 줄일 수 있습니다.
- **단일 요청으로 여러 리소스**의 데이터를 한꺼번에 가져올 수 있습니다.
- REST API보다 **API 요청 횟수를 줄여** rate limit 소진을 방지할 수 있습니다.

---

## REST API와 GraphQL API의 차이

| 항목 | REST API | GraphQL API |
|------|----------|-------------|
| 엔드포인트 | 리소스마다 별도 URL | 단일 URL (`/graphql`) |
| 응답 데이터 | 서버가 고정된 구조로 반환 | 클라이언트가 필요한 필드만 지정 |
| 요청 횟수 | 여러 리소스 조회 시 다수 요청 필요 | 단일 요청으로 여러 데이터 조회 가능 |
| 과다 데이터 | Over-fetching 발생 가능 | 필요한 데이터만 수신 |

**예시 비교:**

- REST: PR 목록과 각 PR의 리뷰 수를 얻으려면 `/pulls` 호출 후, 각 PR마다 `/pulls/{id}/reviews` 반복 호출
- GraphQL: 단일 쿼리로 PR 목록과 리뷰 수를 한 번에 조회 가능

---

## gql 라이브러리 기본 구조

`gql`은 Python에서 GraphQL 쿼리를 쉽게 작성하고 실행할 수 있는 라이브러리입니다.

**설치:**

```bash
pip install gql[requests]
```

**기본 사용 구조:**

```python
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

# 1. Transport 설정 (인증 포함)
transport = RequestsHTTPTransport(
    url="https://api.github.com/graphql",
    headers={"Authorization": f"Bearer {token}"},
)

# 2. Client 생성
client = Client(transport=transport, fetch_schema_from_transport=True)

# 3. 쿼리 작성
query = gql("""
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    nameWithOwner
    description
  }
}
""")

# 4. 쿼리 실행
result = client.execute(query, variable_values={"owner": "owner", "name": "repo"})
print(result)
```

---

## GITHUB_TOKEN 환경 변수 설정

GitHub GraphQL API는 인증된 요청만 허용합니다. Personal Access Token을 환경 변수로 관리하는 것을 권장합니다.

**환경 변수 설정 (Linux/macOS):**

```bash
export GITHUB_TOKEN=your_personal_access_token
```

**`.env` 파일 사용 (선택):**

```
GITHUB_TOKEN=your_personal_access_token
```

**Python 코드에서 불러오기:**

```python
import os

token = os.environ.get("GITHUB_TOKEN")
if not token:
    raise ValueError("GITHUB_TOKEN 환경 변수가 설정되지 않았습니다.")
```

> ⚠️ 토큰을 코드에 직접 작성하거나 Git에 커밋하지 마세요. `.gitignore`에 `.env`를 추가하세요.

---

## RequestsHTTPTransport 설정

`RequestsHTTPTransport`는 HTTP 기반으로 GraphQL 요청을 전송하는 전송 계층입니다.

```python
from gql.transport.requests import RequestsHTTPTransport
import os

token = os.environ.get("GITHUB_TOKEN")

transport = RequestsHTTPTransport(
    url="https://api.github.com/graphql",
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    },
    verify=True,   # SSL 검증 (기본값 True, 변경 비권장)
    retries=3,     # 실패 시 재시도 횟수
)
```

---

## 저장소 기본 정보 조회 예시

```python
import os
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

token = os.environ.get("GITHUB_TOKEN")

transport = RequestsHTTPTransport(
    url="https://api.github.com/graphql",
    headers={"Authorization": f"Bearer {token}"},
)

client = Client(transport=transport, fetch_schema_from_transport=True)

query = gql("""
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    nameWithOwner
    description
    stargazerCount
    forkCount
    createdAt
  }
}
""")

result = client.execute(query, variable_values={
    "owner": "oss2026hnu",
    "name": "reposcore-py"
})

print(result["repository"]["nameWithOwner"])
print(result["repository"]["stargazerCount"])
```

---

## Issue / PR 개수 조회 예시

```python
query = gql("""
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    issues(states: OPEN) {
      totalCount
    }
    closedIssues: issues(states: CLOSED) {
      totalCount
    }
    pullRequests(states: OPEN) {
      totalCount
    }
    mergedPRs: pullRequests(states: MERGED) {
      totalCount
    }
  }
}
""")

result = client.execute(query, variable_values={
    "owner": "oss2026hnu",
    "name": "reposcore-py"
})

repo = result["repository"]
print(f"열린 Issue: {repo['issues']['totalCount']}")
print(f"닫힌 Issue: {repo['closedIssues']['totalCount']}")
print(f"열린 PR:    {repo['pullRequests']['totalCount']}")
print(f"Merged PR:  {repo['mergedPRs']['totalCount']}")
```

---

## GraphQL 응답 데이터 처리에 Pydantic 활용하기

### dict 구조 그대로 사용할 때의 한계
GitHub GraphQL API의 응답은 기본적으로 중첩된 `dict` 형태로 다루게 됩니다. 하지만 응답 구조가 복잡해질수록 다음과 같은 문제가 발생할 수 있습니다.
- **오타 및 타입 혼동:** 필드 이름을 잘못 입력하거나(`issuse` 등), 데이터 타입을 잘못 파악해 런타임 에러가 발생하기 쉽습니다. IDE의 자동 완성 지원도 받을 수 없습니다.
- **가독성 저하:** `result["repository"]["issues"]["totalCount"]` 처럼 딕셔너리 키 체이닝이 길어져 코드 유지보수가 어려워집니다.

### Pydantic 모델을 통한 구조화 및 검증
Pydantic을 활용하면 데이터 구조를 명확한 Python 객체로 정의하여 타입을 보장받고 데이터 검증을 수행할 수 있습니다.

#### 설치
```bash
pip install pydantic
```

### 예시
```python
from pydantic import BaseModel

class IssueCount(BaseModel):
    totalCount: int

class PullRequestCount(BaseModel):
    totalCount: int

class RepositoryCounts(BaseModel):
    nameWithOwner: str
    issues: IssueCount
    pullRequests: PullRequestCount

repository_data = result["repository"]
repository = RepositoryCounts.model_validate(repository_data)

print(repository.nameWithOwner)
print(repository.issues.totalCount)
print(repository.pullRequests.totalCount)
```

---

## GraphQL 쿼리 작성 시 주의사항

### 페이지네이션

GraphQL은 기본적으로 한 번에 반환하는 항목 수에 제한이 있습니다. `first` / `after` 인자로 페이지네이션을 구현하세요.

```python
query = gql("""
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(first: 100, after: $cursor, states: CLOSED) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        title
        author { login }
      }
    }
  }
}
""")
```

### Rate Limit 확인

쿼리에 `rateLimit` 필드를 추가하면 현재 남은 요청 횟수를 확인할 수 있습니다.

```python
query = gql("""
query {
  rateLimit {
    limit
    remaining
    resetAt
  }
}
""")
```

### 그 외 주의사항

- **변수(variable)를 적극 활용**하세요. 쿼리 문자열에 값을 직접 삽입하면 유지보수가 어렵고 인젝션 위험이 있습니다.
- **`fetch_schema_from_transport=True`** 옵션은 편리하지만 매 실행 시 스키마를 가져오므로, 운영 환경에서는 `False`로 설정하는 것을 고려하세요.
- GitHub GraphQL API의 최대 복잡도(complexity)를 초과하면 요청이 거부됩니다. 중첩 쿼리 깊이를 적절히 제한하세요.
- 응답 필드명에 **alias**를 사용하면 같은 타입을 다른 조건으로 여러 번 조회할 수 있습니다 (예: `closedIssues: issues(states: CLOSED)`).
- **Pydantic Alias 주의:** GraphQL 쿼리에서 `closedIssues: issues`와 같이 Alias를 적용한 필드가 있다면, Pydantic 모델을 작성할 때도 해당 이름과 매핑되도록 필드명을 일치시켜 주어야 구조화 시 에러가 나지 않습니다.
