import os


def _get_resource_by_env_var(env_var: str) -> str:
    table_name = os.environ.get(env_var)
    if not table_name:
        raise ValueError(f"Missing environment variable: {env_var}")
    return table_name


def get_aws_region() -> str:
    return _get_resource_by_env_var("AWS_REGION")


def get_user_progress_table_name() -> str:
    return _get_resource_by_env_var("USER_PROGRESS_TABLE_NAME")


def get_learning_entries_table_name() -> str:
    return _get_resource_by_env_var("LEARNING_ENTRIES_TABLE_NAME")


def get_primm_submissions_table_name() -> str:
    return _get_resource_by_env_var("PRIMM_SUBMISSIONS_TABLE_NAME")


def get_throttle_table_name() -> str:
    return _get_resource_by_env_var("THROTTLE_TABLE_NAME")


def get_refresh_token_table_name() -> str:
    return _get_resource_by_env_var("REFRESH_TOKEN_TABLE_NAME")


def get_user_permissions_table_name() -> str:
    return _get_resource_by_env_var("USER_PERMISSIONS_TABLE_NAME")


def get_first_solutions_table_name() -> str:
    return _get_resource_by_env_var("FIRST_SOLUTIONS_TABLE_NAME")


def get_user_profile_table_name() -> str:
    return _get_resource_by_env_var("USER_PROFILE_TABLE_NAME")


def get_secrets_table_name() -> str:
    return _get_resource_by_env_var("SECRETS_TABLE_NAME")


def get_google_client_id() -> str:
    return _get_resource_by_env_var("GOOGLE_CLIENT_ID")


def is_demo_permissions_enabled() -> bool:
    """
    Checks if demo permissions should be automatically granted to new users.
    Defaults to False if not set or invalid value.
    """
    value = os.environ.get("ENABLE_DEMO_PERMISSIONS", "false").lower()
    return value in ("true", "1", "yes")
