def add_authorizer_info(event: dict, user_id: str) -> None:
    assert "authorizer" not in event["requestContext"]
    event["requestContext"]["authorizer"] = {"jwt": {"claims": {"sub": user_id}}}
