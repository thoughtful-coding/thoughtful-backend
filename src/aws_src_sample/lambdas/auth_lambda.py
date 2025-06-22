import json
import logging
import typing

from aws_src_sample.utils.apig_utils import format_lambda_response, get_method, get_path

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class AuthApiHandler:
    def __init__(self) -> None:
        # Dependencies like the DAL for the refresh token table will be added later
        pass

    def handle(self, event: dict) -> dict:
        path = get_path(event)
        method = get_method(event)
        _LOGGER.info(f"Auth handler received request: {method} {path}")

        # Routing logic for /login, /refresh, /logout will be added in a future step

        return format_lambda_response(501, {"message": f"Path {path} not implemented yet."})


def auth_lambda_handler(event: dict, context: typing.Any) -> dict:
    """
    Main handler for all authentication-related API requests.
    """
    _LOGGER.info("Auth lambda handler invoked.")

    try:
        handler = AuthApiHandler()
        return handler.handle(event)
    except Exception as e:
        _LOGGER.error(f"Critical error in auth_lambda_handler: {e}", exc_info=True)
        return format_lambda_response(500, {"message": "Internal Server Error in Auth Handler"})
