from datetime import datetime, timedelta

import psycopg2
import pytest

from solution import app
from solution.rates import RatesEndpoint, ValidationError, get_connection


# ---------------------------------------Fixtures------------------------------------------------
@pytest.fixture()
def test_client():
    with app.test_client() as client:
        yield client


@pytest.fixture()
def rates_url():
    return "/rates"


@pytest.fixture()
def rates_endpoint():
    conn = get_connection(app)
    with conn:
        with conn.cursor() as cur:
            yield RatesEndpoint(cur)
    conn.close()


@pytest.fixture()
def test_params():
    return {
        "date_from": "2016-01-01",
        "date_to": "2016-01-10",
        "origin": "CNSGH",
        "destination": "north_europe_main",
    }


# ------------------------------Unit Tests----------------------------------------------


@pytest.mark.parametrize(
    "blank_field", ["date_from", "date_to", "origin", "destination"]
)
def test_validation_empty_params(
    blank_field: str, test_params: dict[str, str], rates_endpoint: RatesEndpoint
):
    test_params[blank_field] = ""
    with pytest.raises(ValidationError, match=r"blank"):
        new_params = rates_endpoint.normalize_params(test_params)


def test_validation_date_to_wrong_format(
    test_params: dict[str, str], rates_endpoint: RatesEndpoint
):
    test_params["date_to"] = "01/10/2016"
    with pytest.raises(ValidationError, match=r"YYYY-mm-dd"):
        new_params = rates_endpoint.normalize_params(test_params)


def test_validation_date_from_wrong_format(
    test_params: dict[str, str], rates_endpoint: RatesEndpoint
):
    test_params["date_from"] = "01/01/2016"
    with pytest.raises(ValidationError, match=r"YYYY-mm-dd"):
        new_params = rates_endpoint.normalize_params(test_params)


def test_validation_date_to_before_date_from(
    test_params: dict[str, str], rates_endpoint: RatesEndpoint
):
    test_params["date_to"] = "2015-12-31"
    with pytest.raises(ValidationError, match=r"cannot be before"):
        new_params = rates_endpoint.normalize_params(test_params)


@pytest.mark.test_data
def test_granchild_regions_are_found(rates_endpoint):
    """
    In the test data, 'norway_south_east' is a grand-child region of 'northern_europe'.
    Make sure it gets picked up.
    """
    children = rates_endpoint.get_all_regions_within("northern_europe")
    assert "norway_south_east" in children


# --------------------------------------Integration Tests-----------------------------------------


def test_failed_validation_returns_400(test_params, test_client, rates_url, mocker):
    mocker.patch(
        "solution.rates.RatesEndpoint.normalize_params",
        side_effect=ValidationError("key", "value"),
    )
    response = test_client.get(rates_url, query_string=test_params)
    data = response.json
    assert response.status_code == 400
    assert data["key"] == "value"


def test_cant_connect_to_db_returns_503(test_client, rates_url, mocker, test_params):
    mocker.patch("psycopg2.connect", side_effect=psycopg2.OperationalError("error"))

    response = test_client.get(rates_url, query_string=test_params)
    assert response.status_code == 503


def test_all_dates_in_range_are_present(test_params, test_client, rates_url):
    response = test_client.get(rates_url, query_string=test_params)
    data = response.json

    assert response.status_code == 200
    assert isinstance(data, list)
    assert len(data) == 10

    start_date = datetime.strptime(test_params["date_from"], "%Y-%m-%d")
    for i in range(len(data)):
        assert data[i]["day"] == (start_date + timedelta(days=i)).strftime("%Y-%m-%d")


def test_correct_key_names_in_result(test_params, test_client, rates_url):
    response = test_client.get(rates_url, query_string=test_params)
    data = response.json

    assert response.status_code == 200
    assert isinstance(data, list)
    assert set(data[0].keys()) == {"day", "average_price"}


@pytest.mark.test_data
def test_jan_01_price_is_1112(test_params, test_client, rates_url):
    """In the test data, Jan. 4, 2016 has only one price for the test route,
    so it should return NULL for average_price."""
    response = test_client.get(rates_url, query_string=test_params)
    data = response.json

    assert response.status_code == 200
    assert isinstance(data, list)
    assert data[0]["average_price"] == 1112


@pytest.mark.test_data
def test_jan_02_price_is_1112(test_params, test_client, rates_url):
    """In the test data, Jan. 4, 2016 has only one price for the test route,
    so it should return NULL for average_price."""
    response = test_client.get(rates_url, query_string=test_params)
    data = response.json

    assert response.status_code == 200
    assert isinstance(data, list)
    assert data[1]["average_price"] == 1112


@pytest.mark.test_data
def test_jan_03_price_is_null(test_params, test_client, rates_url):
    """In the test data, Jan. 3, 2016 has no rates, so it should return NULL."""
    response = test_client.get(rates_url, query_string=test_params)
    data = response.json

    assert response.status_code == 200
    assert isinstance(data, list)
    assert data[2]["average_price"] == None


@pytest.mark.test_data
def test_jan_04_price_is_null(test_params, test_client, rates_url):
    """In the test data, Jan. 4, 2016 has only one price for the test route,
    so it should return NULL for average_price."""
    response = test_client.get(rates_url, query_string=test_params)
    data = response.json

    assert response.status_code == 200
    assert isinstance(data, list)
    assert data[3]["average_price"] == None
