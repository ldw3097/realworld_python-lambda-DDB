import json
import boto3
import logging
import uuid
from datetime import datetime
from slugify import slugify
from boto3.dynamodb.conditions import Key, Attr
import src.user as user
from src.util import *

dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-2")
articles_table = dynamodb.Table("dev-articles")


def create_article(event, context):
    authenticatedUser = user.authenticate_and_get_user(event)
    if authenticatedUser is None:
        return envelop("Must be logged in", 422)

    body = json.loads(event["body"])
    if "article" not in body:
        return envelop("Article must be specified", 422)

    article_val = body["article"]
    for field in ["title", "description", "body"]:
        if field not in article_val:
            return envelop(f"{field} must be specified", 422)

    timestamp = int(datetime.utcnow().timestamp())
    timeformated = datetime.fromtimestamp(timestamp).isoformat() + ".000Z"
    slug = slugify(article_val["title"]) + "-" + str(uuid.uuid4())[:8]

    item = {
        "slug": slug,
        "title": article_val["title"],
        "description": article_val["description"],
        "body": article_val["body"],
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "author": authenticatedUser["username"],
        "dummy": "partition",
        "favoritesCount": 0,
    }

    if "tagList" in article_val:
        item["tagList"] = article_val["tagList"]

    articles_table.put_item(Item=item)

    del item["dummy"]
    item["tagList"] = article_val.get("tagList", [])
    item["createdAt"] = timeformated
    item["updatedAt"] = timeformated
    item["favorited"] = False
    item["favoritesCount"] = 0
    item["author"] = {
        "username": authenticatedUser["username"],
        "bio": authenticatedUser.get("bio", ""),
        "image": authenticatedUser.get("image", ""),
        "following": False,
    }

    return envelop({"article": item})


def get_article(event, context):
    if "slug" not in event["pathParameters"]:
        return envelop("Slug must be specified", 422)

    slug = event["pathParameters"]["slug"]
    result = articles_table.get_item(Key={"slug": slug})
    if "Item" not in result:
        return envelop(f"Article not found: {slug}", 422)

    article = result["Item"]
    authenticated_user = user.authenticate_and_get_user(event)
    return envelop(
        {"article": transform_retrieved_article(article, authenticated_user)}
    )


def get_article_by_slug(slug):
    result = articles_table.get_item(Key={"slug": slug})
    if "Item" not in result:
        return None
    return result["Item"]


def transform_retrieved_article(article, authenticated_user):
    del article["dummy"]
    article["tagList"] = article.get("tagList", [])
    article["favoritesCount"] = article.get("favoritesCount", 0)
    article["favorited"] = False
    article["createdAt"] = (
        datetime.fromtimestamp(article["createdAt"]).isoformat() + ".000Z"
    )
    article["updatedAt"] = (
        datetime.fromtimestamp(article["updatedAt"]).isoformat() + ".000Z"
    )
    if "favoritedBy" in article:
        if authenticated_user:
            article["favorited"] = (
                authenticated_user["username"] in article["favoritedBy"]
            )
        del article["favoritedBy"]
    article["author"] = user.get_profile_by_username(
        article["author"], authenticated_user
    )
    return article


def update_article(event, context):

    body = json.loads(event["body"])
    if "article" not in body:
        return envelop("Article must be specified", 422)
    article_mutation = body["article"]

    if all(item not in article_mutation for item in ["title", "description", "body"]):
        return envelop(
            "At least one field must be specified: [title, description, body].", 422
        )

    authenticated_user = user.authenticate_and_get_user(event)
    if authenticated_user is None:
        return envelop("Must be logged in", 422)

    slug = event["pathParameters"].get("slug")

    if slug is None:
        return envelop("Slug must be specified", 422)

    article = articles_table.get_item(Key={"slug": slug}).get("Item")
    if article is None:
        return envelop(f"Article not found: {slug}", 422)

    if article["author"] != authenticated_user["username"]:
        return envelop(
            f"Article can only be updated by author: {article['author']}", 422
        )

    for field in ["title", "description", "body"]:
        if field in article_mutation:
            article[field] = article_mutation[field]
    article["updatedAt"] = int(datetime.utcnow().timestamp())
    articles_table.put_item(Item=article)

    return envelop(
        {"article": transform_retrieved_article(article, authenticated_user)}
    )


def delete_article(event, context):
    authenticated_user = user.authenticate_and_get_user(event)
    if authenticated_user is None:
        return envelop("Must be logged in", 422)
    slug = event["pathParameters"].get("slug")
    if slug is None:
        return envelop("Slug must be specified", 422)

    article = articles_table.get_item(Key={"slug": slug}).get("Item")
    if article is None:
        return envelop(f"Article not found: {slug}", 422)
    if article["author"] != authenticated_user["username"]:
        return envelop(
            f"Article can only be deleted by author: {article['author']}", 422
        )
    articles_table.delete_item(Key={"slug": slug})
    return envelop({})


def favorite_article(event, context):
    authenticated_user = user.authenticate_and_get_user(event)
    if authenticated_user is None:
        return envelop("Must be logged in", 422)
    slug = event["pathParameters"].get("slug")
    if slug is None:
        return envelop("Slug must be specified", 422)

    article = articles_table.get_item(Key={"slug": slug}).get("Item")
    if article is None:
        return envelop(f"Article not found: {slug}", 422)

    shouldFavorite = event["httpMethod"] != "DELETE"
    if shouldFavorite:
        article.setdefault("favoritedBy", [])
        if authenticated_user["username"] not in article["favoritedBy"]:
            article["favoritedBy"].append(authenticated_user["username"])
            article["favoritesCount"] += 1
    elif (
        "favoritedBy" in article
        and authenticated_user["username"] in article["favoritedBy"]
    ):
        article["favoritedBy"].remove(authenticated_user["username"])
        article["favoritesCount"] -= 1
        if len(article["favoritedBy"]) == 0:
            del article["favoritedBy"]
            article["favoritesCount"] = 0

    articles_table.put_item(Item=article)

    return envelop(
        {"article": transform_retrieved_article(article, authenticated_user)}
    )


def list_articles(event, context):
    authenticated_user = user.authenticate_and_get_user(event)
    params = event.get("queryStringParameters", {})
    if params == None:
        params = {}
    limit = params.get("limit", 20)
    if type(limit) != int:
        limit = 20
    limit = int(limit)
    offset = params.get("offset", 0)
    if type(offset) != int:
        offset = 0
    offset = int(offset)
    if sum(item in params for item in ["tag", "author", "favorited"]) > 1:
        return envelop("Use only one of tag, author, or favorited", 422)
    queryParams = {
        "KeyConditionExpression": Key("dummy").eq("partition"),
        "ScanIndexForward": False,
        "IndexName": "createdAt",
    }
    if "tag" in params:
        queryParams["FilterExpression"] = "contains(tagList, :tag)"
        queryParams["ExpressionAttributeValues"] = {":tag": params["tag"]}
    elif "author" in params:
        queryParams["FilterExpression"] = "author = :author"
        queryParams["ExpressionAttributeValues"] = {":author": params["author"]}
    elif "favorited" in params:
        queryParams["FilterExpression"] = "contains(favoritedBy, :favorited)"
        queryParams["ExpressionAttributeValues"] = {":favorited": params["favorited"]}

    return envelop(
        {
            "articles": queryEnoughArticles(
                queryParams, authenticated_user, limit, offset
            )
        }
    )


def get_article_by_author(author):
    queryParams = {
        "ScanIndexForward": False,
        "IndexName": "author",
        "KeyConditionExpression": Key("author").eq(author),
    }
    queryResult = articles_table.query(**queryParams)
    return queryResult.get("Items", [])


def get_feed(event, context):
    authenticated_user = user.authenticate_and_get_user(event)
    if authenticated_user is None:
        return envelop("Must be logged in", 422)
    params = event.get("queryStringParameters", {})
    if params is None:
        params = {}
    limit = int(params.get("limit", 20))
    offset = int(params.get("offset", 0))
    follow_list = user.get_followed_users(authenticated_user["username"])
    articles_ret = []
    for username in follow_list:
        articles_ret.extend(get_article_by_author(username))
    articles_ret.sort(key=lambda x: x["createdAt"], reverse=True)
    articles_ret = list(
        map(
            lambda x: transform_retrieved_article(x, authenticated_user),
            articles_ret[offset : offset + limit],
        )
    )
    return envelop({"articles": articles_ret})


def get_tags(event, context):
    uniqTags = set()
    scanParam = {
        "AttributesToGet": ["tagList"],
    }
    while True:
        scanResult = articles_table.scan(**scanParam)
        for item in scanResult["Items"]:
            if "tagList" in item:
                uniqTags.update(item["tagList"])
        if "LastEvaluatedKey" not in scanResult:
            break
        scanParam["ExclusiveStartKey"] = scanResult["LastEvaluatedKey"]
    return envelop({"tags": list(uniqTags)})


def queryEnoughArticles(queryParams, authenticatedUser, limit, offset):
    queryResultItems = []
    while len(queryResultItems) < limit + offset:
        print(queryParams)
        queryResult = articles_table.query(**queryParams)
        queryResultItems.extend(queryResult["Items"])
        if "LastEvaluatedKey" not in queryResult:
            break
        else:
            queryParams["ExclusiveStartKey"] = queryResult["LastEvaluatedKey"]
    articleRet = []
    for article in queryResultItems[offset : offset + limit]:
        articleRet.append(transform_retrieved_article(article, authenticatedUser))
    return articleRet
