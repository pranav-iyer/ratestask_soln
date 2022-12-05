from datetime import datetime
from typing import Any

import psycopg2
from flask import jsonify, request

from solution import app


def get_connection(app):
    """
    Gets the connection, using the connection parameters
    in the app's config.
    """
    return psycopg2.connect(
        host=app.config["PG_HOST"],
        port=app.config["PG_PORT"],
        dbname=app.config["PG_DBNAME"],
        user=app.config["PG_USER"],
        password=app.config["PG_PASSWD"],
    )


class ValidationError(Exception):
    """
    Error class to be raised when parameters are not correctly validated.
    The first argument will be the name of the field which cause the error,
    and the second will be a description of the error.
    """

    pass


class RatesEndpoint:
    """
    Handles queries to the Rates API endpoint. Should be initialized
    with a database cursor. The main method to call is `get_data`, which
    takes in a dictionary of parameters, and returns the fetched data
    from the database.
    """

    def __init__(self, cur):
        self.cur = cur

    def get_data(self, params: dict[str, str]) -> list[dict]:
        """
        Given the URL parameters, normalizes them and then fetches the
        correct data from the database.
        """
        new_params = self.normalize_params(params)
        sql = self.construct_rates_sql(new_params)

        # execute the constructed SQL query
        self.cur.execute(sql, new_params)
        colnames = [desc[0] for desc in self.cur.description]
        results = self.cur.fetchall()

        # this makes each row a dictionary where the key is the column name
        # and the value is the value in that column.
        return [dict(zip(colnames, row)) for row in results]

    def get_region_children(self, region_slug: str) -> list[str]:
        """
        Returns a list of all immediate children regions of the supplied region.
        """
        self.cur.execute(
            "SELECT slug FROM regions WHERE parent_slug=%s", (region_slug,)
        )
        return [row[0] for row in self.cur.fetchall()]

    def get_all_regions_within(self, region_slug: str) -> list[str]:
        """
        Returns a list of all the regions which are contained within the specified region,
        including that region itself.
        """
        regions = [region_slug]
        next_to_check = 0
        while next_to_check < len(regions):
            regions.extend(self.get_region_children(regions[next_to_check]))
            next_to_check += 1

        return regions

    def is_region(self, region_slug: str) -> bool:
        """Checks if the supplied region_slug is valid (if it is present in the regions table)."""
        self.cur.execute("SELECT * FROM regions WHERE LOWER(slug)=%s", (region_slug,))
        return self.cur.fetchone() is not None

    def is_port_code(self, code: str) -> bool:
        """Checks if the supplied port code is valid (if it is present in the ports table.)"""
        self.cur.execute("SELECT * FROM ports WHERE LOWER(code)=%s", (code,))
        return self.cur.fetchone() is not None

    def normalize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Normalizes the parameters passed in. This includes validating parameters,
        lowercasing strings, checking whether origin and destination parameters
        are port codes or region slugs.

        If parameters does not pass validation, this method will raise `ValidationError`,
        with info about the failing field.
        """
        # lowercase all fields
        for key in params:
            params[key] = params[key].lower()

        # all fields in params must be non-empty
        for key in params:
            if params[key] == "":
                raise ValidationError(key, "This field cannot be blank.")

        # make sure dates are in valid format
        for key in ["date_from", "date_to"]:
            try:
                params[key] = datetime.strptime(params[key], "%Y-%m-%d")
            except ValueError as e:
                raise ValidationError(
                    key, f"{params[key]!r} is not a valid date in YYYY-mm-dd format."
                )

        # make sure dates are in the right order
        if params["date_to"] < params["date_from"]:
            raise ValidationError("date_to", "date_to cannot be before date_from.")

        # check if origin is a region slug, port code, or invalid
        for key in ["origin", "destination"]:
            is_region = self.is_region(params[key])
            params[key + "_is_region"] = is_region

            if not is_region and not self.is_port_code(params[key]):
                raise ValidationError(
                    key, f"{params[key]!r} is not a valid region slug or port code."
                )

        # if origin is a region, instead of the given code, we will pass a list of
        # all child regions to check against the ports table
        if params["origin_is_region"]:
            params["origin_parents"] = tuple(
                self.get_all_regions_within(params["origin"])
            )

        # same for destination
        if params["destination_is_region"]:
            params["destination_parents"] = tuple(
                self.get_all_regions_within(params["destination"])
            )

        return params

    def construct_rates_sql(self, params: dict[str, Any]) -> str:
        """
        Contructs the SQL query to be run based on the parameters supplied. The
        only dynamic part depends on the origin and destination being either
        port codes or regions. If they are codes, we filter to match that code,
        but if they are regions, we filter to match the parent_slug inside
        that region.
        """
        if params["origin_is_region"]:
            origin_clause = "orig_port.parent_slug IN %(origin_parents)s"
        else:
            origin_clause = "LOWER(orig_code) = %(origin)s"

        if params["destination_is_region"]:
            destination_clause = "dest_port.parent_slug IN %(destination_parents)s"
        else:
            destination_clause = "LOWER(dest_code) = %(destination)s"

        sql = f"""
        SELECT
            TO_CHAR(d.day, 'YYYY-mm-dd') AS day,
            CASE
                WHEN COUNT(pric.day) < 3 THEN NULL
                ELSE CAST(AVG(pric.price) AS int)
            END AS average_price
        FROM alldates d
            LEFT OUTER JOIN (
                SELECT *
                FROM prices p
                    LEFT OUTER JOIN ports orig_port ON p.orig_code=orig_port.code
                    LEFT OUTER JOIN ports dest_port ON p.dest_code=dest_port.code
                WHERE (
                    {origin_clause} AND {destination_clause}
                )
            ) pric ON pric.day = d.day
        WHERE
            d.day >= %(date_from)s AND
            d.day <= %(date_to)s
        GROUP BY d.day
        ORDER BY d.day
        """
        return sql


@app.route("/rates", methods=["GET"])
def get_rates():
    try:
        conn = get_connection(app)
    except psycopg2.OperationalError as e:
        return jsonify({"message": "Database is currently unavailable."}), 503

    with conn:
        with conn.cursor() as cur:
            endpoint = RatesEndpoint(cur)

            try:
                data = endpoint.get_data(
                    {
                        "date_from": request.args.get("date_from", ""),
                        "date_to": request.args.get("date_to", ""),
                        "origin": request.args.get("origin", ""),
                        "destination": request.args.get("destination", ""),
                    }
                )
            except ValidationError as e:
                return jsonify({e.args[0]: e.args[1]}), 400

    conn.close()

    return jsonify(data), 200
