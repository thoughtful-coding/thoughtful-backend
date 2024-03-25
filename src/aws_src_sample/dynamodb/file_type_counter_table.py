#!/usr/bin/env python3
import boto3

class FileTypeCounterTable:
    def __init__(self, table_name: str) -> None:
        self.client = boto3.client("dynamodb")
        self.table = self.client.Table(table_name)  


    
    def get_value(self, *, item_key:str) -> int:        
        
        
        response = self.table.get_item(Key={
            "file_type": item_key
        }).get("Item",{"count": 0})["count"]
        
        
        return response
    
    def set_value(self, *, item_key:str, item_value:str) -> None:
            
        self.table.put_item(
        Item={
            "file_type": item_key,  # Assuming 'id' is your primary key
            "count": item_value  # Assuming 'value' is an integer attribute you want to store
            }
        )
        
    def increment(self, *, item_key:str)->None:
        self.set_value(self,item_key=item_key,item_value=self.get_value(self,item_key=item_key)+1)
    
    
    