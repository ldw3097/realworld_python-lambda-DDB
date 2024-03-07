import boto3
from moto import mock_aws
import pytest

import sys, os

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from src import user


@pytest.fixture
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "ap-northeast-2"


@pytest.fixture
def dynamodb_client(aws_credentials):
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-2")
        yield dynamodb


@pytest.fixture
def users_table(dynamodb_client):
    table = dynamodb_client.create_table(
        TableName="dev-users",
        KeySchema=[{"AttributeName": "username", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "username", "AttributeType": "S"},
            {"AttributeName": "email", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        GlobalSecondaryIndexes=[
            {
                "IndexName": "email",
                "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 1,
                    "WriteCapacityUnits": 1,
                },
            }
        ],
    )
    yield table


@pytest.fixture
def articles_table(dynamodb_client):
    attribute_definitions = [
        {"AttributeName": "slug", "AttributeType": "S"},
        {"AttributeName": "dummy", "AttributeType": "S"},
        {"AttributeName": "updatedAt", "AttributeType": "N"},
    ]

    key_schema = [{"AttributeName": "slug", "KeyType": "HASH"}]

    global_secondary_indexes = [
        {
            "IndexName": "updatedAt",
            "KeySchema": [
                {"AttributeName": "dummy", "KeyType": "HASH"},
                {"AttributeName": "updatedAt", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
            "ProvisionedThroughput": {"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        }
    ]

    # Create the table
    table = dynamodb_client.create_table(
        TableName="dev-articles",
        AttributeDefinitions=attribute_definitions,
        KeySchema=key_schema,
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        GlobalSecondaryIndexes=global_secondary_indexes,
    )
    yield table
