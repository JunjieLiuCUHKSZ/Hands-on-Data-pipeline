import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "clean_and_merge.db"

app = Flask(__name__)


def database_version():
    if not DB_PATH.exists():
        return "missing"

    stat = DB_PATH.stat()
    return f"{stat.st_mtime_ns}-{stat.st_size}"


def fetch_dashboard_data():
    data = {
        "version": database_version(),
        "orders": [],
        "summary": [],
        "error": None,
    }

    if not DB_PATH.exists():
        data["error"] = "Database not found. Run clean_and_merge.py first."
        return data

    try:
        connection = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row

        existing_tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        required_tables = {"merged_orders", "region_summary"}
        missing_tables = required_tables - existing_tables
        if missing_tables:
            data["error"] = (
                "Missing table(s): " + ", ".join(sorted(missing_tables))
            )
            return data

        data["orders"] = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    order_id,
                    customer_id,
                    amount,
                    currency,
                    amount_cny,
                    customer_name,
                    region
                FROM merged_orders
                ORDER BY order_id
                """
            )
        ]

        data["summary"] = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    region,
                    average_amount_cny
                FROM region_summary
                ORDER BY region
                """
            )
        ]

        return data
    except sqlite3.Error as error:
        data["error"] = f"SQLite error: {error}"
        return data
    finally:
        if "connection" in locals():
            connection.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/dashboard")
def dashboard_api():
    response = jsonify(fetch_dashboard_data())
    response.headers["Cache-Control"] = "no-store"
    return response


if __name__ == "__main__":
    app.run(debug=True)
