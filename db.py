from strawberry.types import Info

DB_NAME = "iris"

def get_db( info: Info, collection: str ):
    return info.context.db[DB_NAME][collection]