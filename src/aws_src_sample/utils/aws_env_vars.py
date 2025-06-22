import os


def get_output_bucket_name() -> str:
    return os.environ["OUTPUT_BUCKET_NAME"]


def get_file_type_counter_table_name() -> str:
    return os.environ["FILE_TYPE_COUNTER_TABLE_NAME"]


def get_region() -> str:
    return os.environ["REGION"]


def _get_resource_by_env_var(env_var: str) -> str:
    table_name = os.environ.get(env_var)
    if not table_name:
        raise ValueError(f"Missing environment variable: {env_var}")
    return table_name


def get_pong_score_table_name() -> str:
    return _get_resource_by_env_var("PONG_SCORE_TABLE_NAME")


def get_progress_table_name() -> str:
    return _get_resource_by_env_var("PROGRESS_TABLE_NAME")


def get_learning_entries_table_name() -> str:
    return _get_resource_by_env_var("LEARNING_ENTRIES_TABLE_NAME")


def get_primm_submissions_table_name() -> str:
    return _get_resource_by_env_var("PRIMM_SUBMISSIONS_TABLE_NAME")


def get_throttle_table_name() -> str:
    return _get_resource_by_env_var("THROTTLING_TABLE_NAME")


def get_refresh_token_table_name() -> str:
    return _get_resource_by_env_var("REFRESH_TOKEN_TABLE_NAME")


def get_user_permissions_table_name() -> str:
    return _get_resource_by_env_var("USER_PERMISSIONS_TABLE_NAME")


def get_chatbot_api_key_secrets_arn() -> str:
    """
    Gets the AWS Secrets Manager secret name/ARN that stores the ChatBot API key.
    """
    return _get_resource_by_env_var("CHATBOT_API_KEY_SECRETS_ARN")
