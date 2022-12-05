from dotenv import dotenv_values

env_vals = dotenv_values()

PG_PASSWD = env_vals["POSTGRES_PASSWORD"]
PG_USER = env_vals["POSTGRES_USER"]
PG_DBNAME = env_vals["POSTGRES_DBNAME"]
PG_HOST = env_vals["POSTGRES_HOST"]
PG_PORT = env_vals["POSTGRES_PORT"]
