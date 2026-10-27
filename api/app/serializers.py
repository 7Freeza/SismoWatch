from datetime import date, datetime
from decimal import Decimal


def clean_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [clean_value(item) for item in value]
    if isinstance(value, dict):
        return {key: clean_value(item) for key, item in value.items()}
    return value


def row_to_dict(row):
    return {key: clean_value(value) for key, value in row.items()}
