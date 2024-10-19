import dataclasses as dc
from typing import (
    Any,
    Optional,
    List,
)

from awscore import AwsServiceSession


AWSDbCon = Any


def parse_data(data: dict):
    try:
        key, val = next(iter(data.items()))
        if key == "S":
            return val
        if key == "N":
            return float(val)
        if key == "L":
            return [parse_data(r) for r in val]
        if key == "M":
            return parse_row(val)
        if key == "BOOL":
            return val
        # I guess this is like a 'null' marker?
        if key == "NULL":
            return val
        else:
            print("UNKNOWN KEY:", key, "WITH VAL:", val, data)
    except Exception as e:
        print("caught error:", e)
    return


def parse_row(row: dict):
    return {k: parse_data(data) for k, data in row.items()}


@dc.dataclass
class TableCon:
    dbcon: AWSDbCon
    table_name: str

    def get_item(self, key_exp: dict):
        r = self.dbcon.get_item(
            TableName=self.table_name,
            Key=key_exp,
        )
        return r.get("Item", None)

    def get_items(self, key_exprs: List[dict]):
        res = self.dbcon.batch_get_item(
            RequestItems={
                self.table_name: {
                    "Keys": key_exprs,
                }
            }
        )
        if res.get("UnprocessedKeys"):
            # TODO: handle this by simply re-fetching the unprocessed keys
            raise Exception("failed to fetch all items from DynamoDB")
        return res["Responses"][self.table_name]

    def query(
        self,
        key_expr: str,
        values: dict,
        exp_attr_names: Optional[dict] = None,
        index_name: str | None = None,
        auto_parse: bool = True,
    ):
        req = {
            "TableName": self.table_name,
            "KeyConditionExpression": key_expr,
            "ExpressionAttributeValues": values,
        }
        if index_name is not None:
            req["IndexName"] = index_name
        if exp_attr_names is not None:
            req["ExpressionAttributeNames"] = exp_attr_names
        res = self.dbcon.query(**req)
        items = res["Items"]
        last_evaluated_key = res.get("LastEvaluatedKey")
        while last_evaluated_key:
            print("another page...")
            res = self.dbcon.query(
                **req,
                **{
                    "ExclusiveStartKey": last_evaluated_key,
                },
            )
            last_evaluated_key = res.get("LastEvaluatedKey")
            items.extend(res.get("Items", []))
            pass
        if auto_parse:
            return [parse_row(r) for r in items]
        return items

    def put_item(self, item: dict):
        """Write an item to a table."""
        return self.dbcon.put_item(
            TableName=self.table_name,
            Item=item,
            ReturnValues="ALL_OLD",
        )

    def delete_item(self, key: dict):
        """Delete an item."""
        return self.dbcon.delete_item(
            TableName=self.table_name,
            Key=key,
        )

    def describe_table(self):
        return self.dbcon.describe_table(TableName=self.table_name)

    def scan(self, page_size=40):
        desc = self.describe_table()
        item_count = desc["Table"]["ItemCount"]
        if not item_count:
            return []
        notify_progress = (page_size / item_count) < 0.1
        last_p_notify = 0
        if notify_progress:
            print("fetching", item_count, "records")
        rows = []
        res = self.dbcon.scan(
            TableName=self.table_name,
            Limit=page_size,
        )
        rows.extend(res["Items"])
        try:
            while res.get("LastEvaluatedKey"):
                res = self.dbcon.scan(
                    TableName=self.table_name,
                    ExclusiveStartKey=res["LastEvaluatedKey"],
                    Limit=page_size,
                )
                rows.extend(res["Items"])
                p_done = len(rows) * 100 / item_count
                p_done_to_tenth = int(10 * p_done) // 10
                if notify_progress:
                    if p_done_to_tenth > last_p_notify:
                        print(f"{p_done_to_tenth}% done")
                        last_p_notify = p_done_to_tenth
        except KeyboardInterrupt:
            print("exiting early...")
            return rows
        return rows


class AWSDynamoCon:
    """
    An interface into dynamodb.
    """

    def __init__(self):
        """Set up AWS and dynamo connection."""
        self.dbcon = AwsServiceSession("dynamodb").service
        self.all_tables = []
        return

    def get_table_name(self, name: str, suffix: str):
        if not self.all_tables:
            self.all_tables = self.list_tables()
        matches = [t for t in self.all_tables if f"{name}-" in t and f"-{suffix}" in t]
        if matches:
            return matches[0]
        return

    def list_tables(self):
        tables = []
        kwargs = {}
        while True:
            res = self.dbcon.list_tables(**kwargs)
            tables.extend(res["TableNames"])
            if "LastEvaluatedTableName" in res:
                kwargs["ExclusiveStartTableName"] = res["LastEvaluatedTableName"]
            else:
                return tables
        return

    def connect_table(self, table_name: str):
        return TableCon(self.dbcon, table_name)
