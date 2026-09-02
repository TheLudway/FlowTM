import json
import os
import re
from pathlib import Path

import duckdb
import psycopg
from psycopg import sql

DATA_DIR = Path("/data")
DUCKDB_PATH = "/database/transport.duckdb"
POSTGRES_PATHS = (Path("infra_troncal"), Path("gtfs/gtfs_20260727"))


def sanitize_identifier(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_]+", "_", value.lower())
    return re.sub(r"_+", "_", value).strip("_")


def table_name(data_file: Path) -> str:
    relative = data_file.relative_to(DATA_DIR)
    parts = list(relative.parts)
    parts[-1] = Path(parts[-1]).stem
    return "__".join(sanitize_identifier(part) for part in parts)


def is_postgres_path(data_file: Path) -> bool:
    relative = data_file.relative_to(DATA_DIR)
    return any(relative == path or path in relative.parents for path in POSTGRES_PATHS)


def read_secret(name: str) -> str:
    path = Path(f"/run/secrets/{name}")
    if not path.exists():
        raise RuntimeError(f"Secret '{name}' was not found.")
    return path.read_text().strip()


def postgres_connection():
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=read_secret("postgres_password"),
    )


def postgres_type(dtype: str) -> str:
    dtype = dtype.upper()
    if "BIGINT" in dtype:
        return "BIGINT"
    if "INTEGER" in dtype or dtype == "INT":
        return "INTEGER"
    if "DOUBLE" in dtype:
        return "DOUBLE PRECISION"
    if "FLOAT" in dtype:
        return "REAL"
    if "BOOLEAN" in dtype:
        return "BOOLEAN"
    if "DATE" in dtype:
        return "DATE"
    if "TIMESTAMP" in dtype:
        return "TIMESTAMP"
    return "TEXT"


def duckdb_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def load_duckdb(con, parquet_file: Path, table: str):
    print(f"[DuckDB] {parquet_file} -> {table}")
    con.execute(
        f'CREATE OR REPLACE TABLE "{table}" AS '
        "SELECT * FROM read_parquet(?)",
        [parquet_file.as_posix()],
    )


def create_postgres_table(pg, table: str, columns):
    definitions = sql.SQL(", ").join(
        sql.SQL("{} {}").format(sql.Identifier(name), sql.SQL(dtype))
        for name, dtype in columns
    )
    with pg.cursor() as cur:
        cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table)))
        cur.execute(
            sql.SQL("CREATE TABLE {} ({})").format(sql.Identifier(table), definitions)
        )
    pg.commit()


def load_postgres_parquet(pg, parquet_file: Path, table: str):
    print(f"[PostGIS] {parquet_file} -> {table}")
    parquet_path = parquet_file.as_posix()
    duck = duckdb.connect()
    try:
        columns = duck.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)", [parquet_path]
        ).fetchall()
        create_postgres_table(
            pg, table, [(name, postgres_type(dtype)) for name, dtype, *_ in columns]
        )
        csv_path = f"/tmp/{table}.csv"
        duck.execute(
            f"COPY (SELECT * FROM read_parquet({duckdb_literal(parquet_path)})) "
            f"TO {duckdb_literal(csv_path)} (FORMAT CSV, HEADER, DELIMITER ',')",
        )
        with pg.cursor() as cur, open(csv_path, "rb") as source, cur.copy(
            sql.SQL("COPY {} FROM STDIN WITH (FORMAT csv, HEADER true)").format(
                sql.Identifier(table)
            )
        ) as copy:
            while data := source.read(1024 * 1024):
                copy.write(data)
        pg.commit()
        Path(csv_path).unlink(missing_ok=True)
    finally:
        duck.close()


def json_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def load_postgres_geojson(pg, geojson_file: Path, table: str):
    print(f"[PostGIS] {geojson_file} -> {table}")
    document = json.loads(geojson_file.read_text())
    features = document.get("features", [])
    property_names = sorted(
        {name for feature in features for name in feature.get("properties", {})}
        - {"geometry"}
    )
    columns = [(name, "TEXT") for name in property_names]
    # Infrastructure GeoJSON mixes 2D and 3D coordinates.
    columns.append(("geometry", "geometry"))
    create_postgres_table(pg, table, columns)

    identifiers = sql.SQL(", ").join(sql.Identifier(name) for name, _ in columns)
    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in property_names)
    placeholders = sql.SQL("{}, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)").format(
        placeholders
    )
    insert = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table), identifiers, placeholders
    )
    rows = [
        tuple(
            [json_value(feature.get("properties", {}).get(name)) for name in property_names]
            + [
                json.dumps(feature["geometry"])
                if feature.get("geometry") is not None
                else None
            ]
        )
        for feature in features
    ]
    with pg.cursor() as cur:
        cur.executemany(insert, rows)
    pg.commit()


def main():
    parquet_files = sorted(DATA_DIR.rglob("*.parquet"))
    duck = duckdb.connect(DUCKDB_PATH)
    pg = postgres_connection()
    try:
        for parquet_file in parquet_files:
            table = table_name(parquet_file)
            load_duckdb(duck, parquet_file, table)
            if is_postgres_path(parquet_file):
                load_postgres_parquet(pg, parquet_file, table)
        for geojson_file in sorted(DATA_DIR.joinpath("infra_troncal").glob("*.geojson")):
            load_postgres_geojson(pg, geojson_file, table_name(geojson_file))
    finally:
        duck.close()
        pg.close()


if __name__ == "__main__":
    main()
