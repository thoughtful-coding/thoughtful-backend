import boto3


class PongScoreTable:
    def __init__(self, table_name: str) -> None:
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)

    def get_value(self, *, item_key: str) -> str:

        response = self.table.get_item(Key={"user": item_key}).get("Item", {"score": -1})["score"]

        return response

    def set_value(self, *, item_key: str, item_value: int) -> None:
        self.table.put_item(
            Item={
                "user": item_key,  # Assuming 'id' is your primary key
                "score": item_value,  # Assuming 'value' is an integer attribute you want to store
            }
        )

    def get_top_five(self) -> dict:
        response = self.table.scan()
        items = response["Items"]

        # Sort items by score in descending order
        sorted_items = sorted(items, key=lambda x: x["score"], reverse=True)

        # Select top 5 items
        top_scores = sorted_items[:5]

        # Format the result as a dictionary
        return {item["user"]: item["score"] for item in top_scores}
