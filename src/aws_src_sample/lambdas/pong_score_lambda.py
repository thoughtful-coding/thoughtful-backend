class PongScoreHandler:
    def __init__(self) -> None:
        pass

    def handle(self, event: dict) -> dict:
        return {}


# placehold


def pong_score_lambda_handler(event: dict, context) -> dict:
    lh = PongScoreHandler(
        # whatever
    )
    return lh.handle(event)
