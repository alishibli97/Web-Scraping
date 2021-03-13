import tabulate

from configuration import MongoConfig
from utils import setup_mongo

exit()


mongoconfig = MongoConfig()
mongoclient, collection = setup_mongo(mongoconfig)

# region Counts by predicate and engine
cursor = collection.aggregate(
    [
        {
            "$group": {
                "_id": {
                    "predicate": "$predicate",
                    "engine": "$engine",
                },
                "count": {"$sum": 1},
            },
        }
    ]
)
print(
    tabulate.tabulate(
        [(d["_id"]["engine"], d["_id"]["predicate"], d["count"]) for d in cursor],
        headers=["engine", "predicate", "count"],
    )
)
# endregion

# region Find by predicate and engine
cursor = collection.find({"engine": "yahoo", "predicate": "on"})
print(
    tabulate.tabulate(
        [(d["query"], d["result_index"], d["caption"]) for d in cursor],
        headers=["engine", "predicate", "count"],
    )
)
# endregion

# region Find and remove duplicates by (predicate, query, engine, result_index)
cursor = collection.aggregate(
    [
        {
            "$group": {
                "_id": {
                    "predicate": "$predicate",
                    "query": "$query",
                    "engine": "$engine",
                    "result_index": "$result_index",
                },
                "count": {"$sum": 1},
                "unique_ids": {"$addToSet": "$_id"},
            }
        },
        {"$match": {"count": {"$gt": 1}}},
        # {"$project": {"name": "$_id", "_id": 0}},
    ]
)
cursor = list(cursor)
print(
    tabulate.tabulate(
        [
            (
                d["_id"]["predicate"],
                d["_id"]["query"],
                d["_id"]["engine"],
                d["_id"]["result_index"],
                d["count"],
            )
            for d in cursor
        ],
        headers=["predicate", "query", "engine", "result_index", "count"],
    )
)
for d in cursor:
    collection.delete_many({"_id": {"$in": d["unique_ids"][1:]}})
# endregion
