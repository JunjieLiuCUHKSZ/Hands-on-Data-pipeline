import csv
import sqlite3
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ORDER_FILE_PATTERN = "order*.txt"
CUSTOMER_FILE_PATTERN = "customer*.txt"
DATABASE_FILE = BASE_DIR / "clean_and_merge.db"

CURRENCY_TO_CNY = {
    "USD": Decimal("6.9"),
    "EUR": Decimal("7.5"),
    "CNY": Decimal("1.0"),
    "JPY": Decimal("0.05"),
}


def read_txt_csv(path):
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        reader.fieldnames = [field.strip() for field in reader.fieldnames or []]
        return [
            {
                key.strip() if key else key: value.strip() if value else value
                for key, value in row.items()
            }
            for row in reader
        ]


def read_txt_csv_files(pattern):
    rows = []
    for path in sorted(DATA_DIR.glob(pattern)):
        rows.extend(read_txt_csv(path))
    return rows


def remove_duplicates(rows, key):
    seen = set()
    unique_rows = []
    for row in rows:
        row_key = row.get(key)
        if row_key in seen:
            continue
        seen.add(row_key)
        unique_rows.append(row)
    return unique_rows


def add_amount_cny(orders):
    converted_orders = []
    for order in orders:
        currency = order["currency"].upper()
        if currency not in CURRENCY_TO_CNY:
            raise ValueError(f"Unsupported currency: {currency}")
        amount = Decimal(order["amount"])
        converted_order = dict(order)
        converted_order["amount_cny"] = (
            amount * CURRENCY_TO_CNY[currency]
        ).quantize(Decimal("0.01"))
        converted_orders.append(converted_order)
    return converted_orders


def merge_orders_with_customers(orders, customers):
    customers_by_id = {customer["customer_id"]: customer for customer in customers}
    merged_rows = []
    for order in orders:
        customer = customers_by_id.get(order["customer_id"])
        if customer is None:
            continue
        merged_rows.append(
            {
                "order_id": order["order_id"],
                "customer_id": order["customer_id"],
                "amount": order["amount"],
                "currency": order["currency"],
                "amount_cny": order["amount_cny"],
                "customer_name": customer["customer_name"],
                "region": customer["region"],
            }
        )
    return merged_rows


def write_database(merged_rows, database_path):
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP TABLE IF EXISTS merged_orders")
        connection.execute("DROP TABLE IF EXISTS region_summary")
        connection.execute(
            """
            CREATE TABLE merged_orders (
                order_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                amount_cny REAL NOT NULL,
                customer_name TEXT NOT NULL,
                region TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO merged_orders (
                order_id,
                customer_id,
                amount,
                currency,
                amount_cny,
                customer_name,
                region
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["order_id"],
                    row["customer_id"],
                    float(row["amount"]),
                    row["currency"],
                    float(row["amount_cny"]),
                    row["customer_name"],
                    row["region"],
                )
                for row in merged_rows
            ],
        )
        connection.execute(
            """
            CREATE TABLE region_summary AS
            SELECT
                region,
                AVG(amount_cny) AS average_amount_cny
            FROM merged_orders
            GROUP BY region
            ORDER BY region
            """
        )
        connection.commit()


def main():
    orders = read_txt_csv_files(ORDER_FILE_PATTERN)
    customers = read_txt_csv_files(CUSTOMER_FILE_PATTERN)

    print("Order files: " + ", ".join(path.name for path in sorted(DATA_DIR.glob(ORDER_FILE_PATTERN))))
    print("Customer files: " + ", ".join(path.name for path in sorted(DATA_DIR.glob(CUSTOMER_FILE_PATTERN))))

    orders = remove_duplicates(orders, "order_id")
    customers = remove_duplicates(customers, "customer_id")

    orders = add_amount_cny(orders)
    merged_rows = merge_orders_with_customers(orders, customers)

    write_database(merged_rows, DATABASE_FILE)
    print(f"Wrote {len(merged_rows)} merged rows to {DATABASE_FILE}")
    print("Created table 'region_summary' with average amount_cny by region.")


if __name__ == "__main__":
    main()
