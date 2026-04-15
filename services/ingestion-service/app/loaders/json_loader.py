import json
from pathlib import Path
from app.utils.parser import (
    parse_business,
    parse_review,
    parse_user,
    parse_tip,
    parse_checkin,
)


def _iter_file(data_path: str, filename: str, parser):
    file_path = Path(data_path) / filename
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield parser(json.loads(line))


def load_businesses(data_path: str):
    return _iter_file(data_path, "yelp_academic_dataset_business.json", parse_business)


def load_reviews(data_path: str):
    return _iter_file(data_path, "yelp_academic_dataset_review.json", parse_review)


def load_users(data_path: str):
    return _iter_file(data_path, "yelp_academic_dataset_user.json", parse_user)


def load_tips(data_path: str):
    return _iter_file(data_path, "yelp_academic_dataset_tip.json", parse_tip)


def load_checkins(data_path: str):
    return _iter_file(data_path, "yelp_academic_dataset_checkin.json", parse_checkin)

