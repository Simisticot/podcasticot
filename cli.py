import argparse
import sqlite3

import uvicorn

from endpoints import refresh_all_feeds, scheduler
from persistence.migration import migrate

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="podcasticot",
        description="rss podcast aggregation web server",
    )
    parser.add_argument("command")
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    match args.command:
        case "serve":
            scheduler.add_job(func=refresh_all_feeds, trigger="interval", minutes=10)
            uvicorn.run(
                "endpoints:app", host=args.host, port=args.port, reload=args.reload
            )
        case "migrate":
            connection = sqlite3.connect("./db/poddb.db")
            migrate(connection)
            connection.close()
            print("Applied migrations")
        case _:
            parser.print_help()
