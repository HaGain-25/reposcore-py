from __future__ import annotations

from collections.abc import Iterable
from pydantic import BaseModel


SCORE_PR_FEATURE_BUG = 3
SCORE_PR_DOC = 2
SCORE_PR_TYPO = 1
SCORE_ISSUE_FEATURE_BUG = 2
SCORE_ISSUE_DOC = 1


class UserContributionCounts(BaseModel):
    """사용자별 PR/이슈 기여 개수를 담는 점수 계산 입력 모델입니다."""

    user: str
    feature_bug_pr_count: int = 0
    doc_pr_count: int = 0
    typo_pr_count: int = 0
    feature_bug_issue_count: int = 0
    doc_issue_count: int = 0


class UserScore(BaseModel):
    """사용자별 기여 개수와 최종 계산 점수를 함께 담는 점수 계산 결과 모델입니다."""

    contribution: UserContributionCounts
    score: int


def calculate_final_score(
    feature_bug_pr_count: int,
    doc_pr_count: int,
    typo_pr_count: int,
    feature_bug_issue_count: int,
    doc_issue_count: int,
) -> int:
    max_additional_pr_count = 3 * max(feature_bug_pr_count, 1)
    valid_pr_count = feature_bug_pr_count + min(
        doc_pr_count + typo_pr_count,
        max_additional_pr_count,
    )

    valid_issue_count = min(
        feature_bug_issue_count + doc_issue_count,
        4 * valid_pr_count,
    )

    optimized_feature_bug_pr_count = min(feature_bug_pr_count, valid_pr_count)
    remaining_pr_slots = valid_pr_count - optimized_feature_bug_pr_count

    optimized_doc_pr_count = min(doc_pr_count, remaining_pr_slots)
    optimized_typo_pr_count = (
        valid_pr_count
        - optimized_feature_bug_pr_count
        - optimized_doc_pr_count
    )

    optimized_feature_bug_issue_count = min(
        feature_bug_issue_count,
        valid_issue_count,
    )
    optimized_doc_issue_count = (
        valid_issue_count - optimized_feature_bug_issue_count
    )

    return (
        optimized_feature_bug_pr_count * SCORE_PR_FEATURE_BUG
        + optimized_doc_pr_count * SCORE_PR_DOC
        + optimized_typo_pr_count * SCORE_PR_TYPO
        + optimized_feature_bug_issue_count * SCORE_ISSUE_FEATURE_BUG
        + optimized_doc_issue_count * SCORE_ISSUE_DOC
    )


def calculate_user_score(contribution: UserContributionCounts) -> UserScore:
    score = calculate_final_score(
        contribution.feature_bug_pr_count,
        contribution.doc_pr_count,
        contribution.typo_pr_count,
        contribution.feature_bug_issue_count,
        contribution.doc_issue_count,
    )

    return UserScore(
        contribution=contribution,
        score=score,
    )


def calculate_repository_scores(
    contributions: Iterable[UserContributionCounts],
) -> list[UserScore]:
    scores = [calculate_user_score(contribution) for contribution in contributions]

    return sorted(scores, key=lambda user_score: (-user_score.score, user_score.contribution.user))


def merge_repository_contributions(
    repositories: Iterable[Iterable[UserContributionCounts]],
) -> list[UserContributionCounts]:
    merged: dict[str, UserContributionCounts] = {}

    for repository in repositories:
        for contribution in repository:
            if contribution.user not in merged:
                merged[contribution.user] = UserContributionCounts(user=contribution.user)

            current = merged[contribution.user]
            current.feature_bug_pr_count += contribution.feature_bug_pr_count
            current.doc_pr_count += contribution.doc_pr_count
            current.typo_pr_count += contribution.typo_pr_count
            current.feature_bug_issue_count += contribution.feature_bug_issue_count
            current.doc_issue_count += contribution.doc_issue_count

    return list(merged.values())


def calculate_total_scores(
    repositories: Iterable[Iterable[UserContributionCounts]],
) -> list[UserScore]:
    merged_contributions = merge_repository_contributions(repositories)

    return calculate_repository_scores(merged_contributions)
