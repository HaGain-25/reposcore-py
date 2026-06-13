from calc_score import (
    UserContributionCounts,
    calculate_final_score,
    calculate_repository_scores,
    calculate_total_scores,
    calculate_user_score,
    merge_repository_contributions,
)


def test_calculate_final_score_applies_basic_weights():
    assert (
        calculate_final_score(
            feature_bug_pr_count=1,
            doc_pr_count=1,
            typo_pr_count=1,
            feature_bug_issue_count=1,
            doc_issue_count=1,
        )
        == 9
    )


def test_doc_typo_pr_limit_when_feature_bug_pr_is_zero():
    assert (
        calculate_final_score(
            feature_bug_pr_count=0,
            doc_pr_count=10,
            typo_pr_count=10,
            feature_bug_issue_count=0,
            doc_issue_count=0,
        )
        == 6
    )


def test_doc_typo_pr_limit_when_feature_bug_pr_is_one():
    assert (
        calculate_final_score(
            feature_bug_pr_count=1,
            doc_pr_count=10,
            typo_pr_count=10,
            feature_bug_issue_count=0,
            doc_issue_count=0,
        )
        == 9
    )


def test_doc_typo_pr_limit_when_feature_bug_pr_is_two():
    assert (
        calculate_final_score(
            feature_bug_pr_count=2,
            doc_pr_count=10,
            typo_pr_count=10,
            feature_bug_issue_count=0,
            doc_issue_count=0,
        )
        == 18
    )


def test_issue_limit_when_valid_pr_count_is_one():
    assert (
        calculate_final_score(
            feature_bug_pr_count=1,
            doc_pr_count=0,
            typo_pr_count=0,
            feature_bug_issue_count=10,
            doc_issue_count=10,
        )
        == 11
    )


def test_issue_limit_when_valid_pr_count_is_two():
    assert (
        calculate_final_score(
            feature_bug_pr_count=2,
            doc_pr_count=0,
            typo_pr_count=0,
            feature_bug_issue_count=10,
            doc_issue_count=10,
        )
        == 22
    )


def test_issue_over_limit_is_not_counted():
    limited_score = calculate_final_score(
        feature_bug_pr_count=1,
        doc_pr_count=0,
        typo_pr_count=0,
        feature_bug_issue_count=4,
        doc_issue_count=0,
    )

    excessive_score = calculate_final_score(
        feature_bug_pr_count=1,
        doc_pr_count=0,
        typo_pr_count=0,
        feature_bug_issue_count=100,
        doc_issue_count=0,
    )

    assert limited_score == excessive_score


def test_calculate_user_score():
    contribution = UserContributionCounts(
        user="alice",
        feature_bug_pr_count=1,
        doc_pr_count=1,
        typo_pr_count=1,
        feature_bug_issue_count=1,
        doc_issue_count=1,
    )

    result = calculate_user_score(contribution)

    assert result.contribution == contribution
    assert result.score == calculate_final_score(
        1,
        1,
        1,
        1,
        1,
    )


def test_calculate_repository_scores_sorts_by_score_desc():
    contributions = [
        UserContributionCounts(user="alice", typo_pr_count=3),
        UserContributionCounts(user="bob", feature_bug_pr_count=1),
        UserContributionCounts(
            user="charlie",
            feature_bug_pr_count=1,
            doc_pr_count=1,
        ),
    ]

    scores = calculate_repository_scores(contributions)

    assert [score.contribution.user for score in scores] == [
        "charlie",
        "alice",
        "bob",
    ]


def test_calculate_repository_scores_sorts_user_id_when_scores_equal():
    contributions = [
        UserContributionCounts(user="charlie", feature_bug_pr_count=1),
        UserContributionCounts(user="alice", feature_bug_pr_count=1),
        UserContributionCounts(user="bob", feature_bug_pr_count=1),
    ]

    scores = calculate_repository_scores(contributions)

    assert [score.contribution.user for score in scores] == [
        "alice",
        "bob",
        "charlie",
    ]


def test_merge_repository_contributions():
    repositories = [
        [
            UserContributionCounts(
                user="alice",
                feature_bug_pr_count=1,
                doc_pr_count=2,
                typo_pr_count=3,
                feature_bug_issue_count=4,
                doc_issue_count=5,
            ),
            UserContributionCounts(
                user="bob",
                feature_bug_pr_count=1,
            ),
        ],
        [
            UserContributionCounts(
                user="alice",
                feature_bug_pr_count=2,
                doc_pr_count=3,
                typo_pr_count=4,
                feature_bug_issue_count=5,
                doc_issue_count=6,
            ),
        ],
    ]

    merged = merge_repository_contributions(repositories)
    merged_by_user = {item.user: item for item in merged}

    assert merged_by_user["alice"].feature_bug_pr_count == 3
    assert merged_by_user["alice"].doc_pr_count == 5
    assert merged_by_user["alice"].typo_pr_count == 7
    assert merged_by_user["alice"].feature_bug_issue_count == 9
    assert merged_by_user["alice"].doc_issue_count == 11

    assert merged_by_user["bob"].feature_bug_pr_count == 1


def test_calculate_total_scores():
    repositories = [
        [
            UserContributionCounts(
                user="bob",
                feature_bug_pr_count=1,
            ),
            UserContributionCounts(
                user="alice",
                typo_pr_count=3,
            ),
        ],
        [
            UserContributionCounts(
                user="bob",
                doc_pr_count=1,
            ),
            UserContributionCounts(
                user="charlie",
                feature_bug_pr_count=1,
                doc_pr_count=1,
            ),
        ],
    ]

    scores = calculate_total_scores(repositories)

    assert [score.contribution.user for score in scores] == [
        "bob",
        "charlie",
        "alice",
    ]

    assert [score.score for score in scores] == [
        5,
        5,
        3,
    ]
