from __future__ import annotations

from unittest.mock import MagicMock

from gh_service import fetch_open_issue_claims


def test_fetch_open_issue_claims_pagination(monkeypatch):
    """첫 번째 페이지에서 hasNextPage=True일 때 두 번째 페이지까지

    정상적으로 연속 조회하고, endCursor가 다음 요청의 after 인자로
    정상 바인딩되는지 페이지네이션 흐름을 검증합니다.
    """
    call_count = 0
    captured_variables = []

    # 외부 API 호출을 차단하고 2개 페이지 응답 시뮬레이션을 위한 가상 훅 함수 정의
    def mock_execute(query, variable_values):
        nonlocal call_count
        call_count += 1
        captured_variables.append(variable_values)

        if call_count == 1:
            return {
                "repository": {
                    "issues": {
                        "pageInfo": {
                            "hasNextPage": True,
                            "endCursor": "token_for_page_2",
                        },
                        "nodes": [{"number": 1, "title": "1페이지 대량 이슈"}],
                    }
                }
            }
        elif call_count == 2:
            return {
                "repository": {
                    "issues": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [{"number": 2, "title": "2페이지 잔여 이슈"}],
                    }
                }
            }
        return {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [],
                }
            }
        }

    # gql Client 세션 객체 모킹 컨텍스트 빌드
    mock_session = MagicMock()
    mock_session.execute = mock_execute

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return mock_session

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    # gh_service 내부의 Client 생성을 MockClient로 몽키패치 처리
    monkeypatch.setattr("gh_service.Client", MockClient)

    # 100개 초과 조건 레이어 조회 함수 실행
    result = fetch_open_issue_claims("oss2026hnu/reposcore-py", "mock_github_token")

    # [인수 기준 검증 1] 여러 페이지의 열린 issue nodes 데이터가
    # 유실 없이 단일 목록으로 누적 병합 반환 확인
    assert len(result) == 2
    assert result[0]["title"] == "1페이지 대량 이슈"
    assert result[1]["title"] == "2페이지 잔여 이슈"

    # [인수 기준 검증 2] 첫 번째 요청의 after는 None,
    # 두 번째 요청의 after는 전 회차 endCursor 임을 확인
    assert captured_variables[0]["after"] is None
    assert captured_variables[1]["after"] == "token_for_page_2"


def test_fetch_open_issue_claims_single_page(monkeypatch):
    """열린 이슈가 100개 이하인 기존 단일 페이지 상황에서도

    반복 루프 없이 1회 요청 후 안전하게 종료 및 정상 동작을 유지하는지 검증합니다.
    """

    def mock_execute(query, variable_values):
        return {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [{"number": 42, "title": "소량의 단일 페이지 오픈 이슈"}],
                }
            }
        }

    mock_session = MagicMock()
    mock_session.execute = mock_execute

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return mock_session

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr("gh_service.Client", MockClient)

    result = fetch_open_issue_claims("oss2026hnu/reposcore-py", "mock_github_token")

    assert len(result) == 1
    assert result[0]["title"] == "소량의 단일 페이지 오픈 이슈"
