import boto3
from moto import mock_aws
import pytest

import sys, os

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from src import user, article


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
        {"AttributeName": "createdAt", "AttributeType": "N"},
        {"AttributeName": "author", "AttributeType": "S"},
    ]

    key_schema = [{"AttributeName": "slug", "KeyType": "HASH"}]

    global_secondary_indexes = [
        {
            "IndexName": "createdAt",
            "KeySchema": [
                {"AttributeName": "dummy", "KeyType": "HASH"},
                {"AttributeName": "createdAt", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
            "ProvisionedThroughput": {"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        },
        {
            "IndexName": "author",
            "KeySchema": [
                {"AttributeName": "author", "KeyType": "HASH"},
                {"AttributeName": "createdAt", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
            "ProvisionedThroughput": {"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        },
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


@pytest.fixture
def comments_table(dynamodb_client):
    table = dynamodb_client.create_table(
        TableName="dev-comments",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "slug", "AttributeType": "S"},
            {"AttributeName": "createdAt", "AttributeType": "N"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        GlobalSecondaryIndexes=[
            {
                "IndexName": "article",
                "KeySchema": [
                    {"AttributeName": "slug", "KeyType": "HASH"},
                    {"AttributeName": "createdAt", "KeyType": "RANGE"},
                ],
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
def user1Token(users_table):
    user1 = {
        "username": "john doe",
        "email": "johndoe@gmail.com",
        "password": "password123",
    }
    eventbody = {"user": user1}
    event = {"body": eventbody}
    ret = user.create_user(event, {})
    return ret["body"]["user"]["token"]


@pytest.fixture
def user2Token(users_table):
    user1 = {
        "username": "jane doe",
        "email": "janedoe@gmail.com",
        "password": "password111",
    }
    eventbody = {"user": user1}
    event = {"body": eventbody}
    ret = user.create_user(event, {})
    return ret["body"]["user"]["token"]


@pytest.fixture
def article1():
    return {
        "title": "title1",
        "description": "description1",
        "body": "body1",
    }


@pytest.fixture
def article2():
    return {
        "title": "title2",
        "description": "description2",
        "body": "body2",
    }


@pytest.fixture
def article3():
    return {
        "title": "title3",
        "description": "description3",
        "body": "body3",
        "tagList": ["tag1", "tag2"],
    }


@pytest.fixture
def article1Slug(articles_table, article1, user1Token):
    eventbody = {"article": article1}
    headers = {"Authorization": f"Token {user1Token}"}
    event = {"headers": headers, "body": eventbody}
    ret = article.create_article(event, {})
    return ret["body"]["article"]["slug"]
