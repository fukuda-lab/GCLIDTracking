from libs.dbProcess import get_db_conn, update_cfg
from psycopg2 import sql
import getpass


def load_sql(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def create_tables(conn):
    query = load_sql("libs/create_tables.sql")
    with conn.cursor() as cur:
        cur.execute(query)
        conn.commit()

def create_db(conn, DB_NAME):
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(DB_NAME)
        ))
        conn.commit()


DB_HOST = input("Postgres host (localhost [default] / IP): ")
DB_PORT = input("Port [default 5432]: ")
DB_USER = input("Postgres username: ")
DB_PASSWORD = getpass.getpass("Postgres password: ")

DB_NAME = input("Database name: ")

try:
    update_cfg(DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)

    print(f"Creating Database {DB_NAME} ...")
    try:
        with get_db_conn(default=True) as conn:
          create_db(conn, DB_NAME)

        print(f"Creating tables ...")
        try:
            with get_db_conn() as conn:
                create_tables(conn)
        except Exception as ex:
            print("Error creating tables: ", ex)
            raise

        print("Done!")

    except Exception as ex:
        print("Error creating db: ", ex)
    




except Exception as e:
    print(e)