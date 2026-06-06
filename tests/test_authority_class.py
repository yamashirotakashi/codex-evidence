from codex_evidence.core.authority import AuthorityClass, authority_rank


def test_authority_class_ordering_is_explicit():
    assert [item.value for item in AuthorityClass] == [
        "canonical",
        "runtime",
        "derived",
        "archive",
    ]
    assert authority_rank(AuthorityClass.CANONICAL) > authority_rank(
        AuthorityClass.RUNTIME
    )
    assert authority_rank(AuthorityClass.RUNTIME) > authority_rank(
        AuthorityClass.DERIVED
    )
    assert authority_rank(AuthorityClass.DERIVED) > authority_rank(
        AuthorityClass.ARCHIVE
    )
