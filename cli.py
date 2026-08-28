import argparse
import sqlite3
from getpass import getpass

import uvicorn

from endpoints import get_settings, refresh_all_feeds, scheduler, user_service
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
                "endpoints:app",
                host=args.host,
                port=args.port,
                reload=args.reload,
                # before incrementing worker count consider impacts on :
                # - sqlite connection reuse
                workers=1,
            )
        case "migrate":
            connection = sqlite3.connect(get_settings().db_connection_string)
            migrate(connection)
            connection.close()
            print("Applied migrations")
        case "setpass":
            email = input("user email:")
            password = getpass("new password:")
            service = user_service()
            service.set_user_password(user_email=email, new_password=password)
        case _:
            parser.print_help()
