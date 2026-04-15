def parse_business(data: dict) -> dict:
    return {
        "id": data.get("business_id"),
        "name": data.get("name"),
        "address": data.get("address"),
        "city": data.get("city"),
        "state": data.get("state"),
        "postal_code": data.get("postal_code"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "stars": data.get("stars"),
        "review_count": data.get("review_count"),
        "is_open": bool(data.get("is_open", 0)),
        "categories": data.get("categories"),
    }


def parse_review(data: dict) -> dict:
    return {
        "review_id": data.get("review_id"),
        "user_id": data.get("user_id"),
        "business_id": data.get("business_id"),
        "stars": data.get("stars"),
        "useful": data.get("useful", 0),
        "funny": data.get("funny", 0),
        "cool": data.get("cool", 0),
        "text": data.get("text"),
        "date": data.get("date"),
    }


def parse_user(data: dict) -> dict:
    return {
        "user_id": data.get("user_id"),
        "name": data.get("name"),
        "review_count": data.get("review_count", 0),
        "yelping_since": data.get("yelping_since"),
        "useful": data.get("useful", 0),
        "funny": data.get("funny", 0),
        "cool": data.get("cool", 0),
        "fans": data.get("fans", 0),
        "average_stars": data.get("average_stars"),
        "elite": data.get("elite"),
    }


def parse_tip(data: dict) -> dict:
    return {
        "user_id": data.get("user_id"),
        "business_id": data.get("business_id"),
        "text": data.get("text"),
        "date": data.get("date"),
        "compliment_count": data.get("compliment_count", 0),
    }


def parse_checkin(data: dict) -> dict:
    return {
        "business_id": data.get("business_id"),
        "date": data.get("date"),
    }

