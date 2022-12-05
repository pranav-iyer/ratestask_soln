# Rates Task Solution

## Notes

- I have appended two extra SQL statements to rates.sql from the original version. These statements select all dates from 1900 through 2099 into a new table called 'alldates'.
They also create an index on the new table by date, so that range queries (which is what is done here) will run faster.
Since the table will not be modified after creation, there is no cost to creating the index.
- My solution is implemented using Flask. The Flask app is created in `solution/__init__.py`, and then all other
application code is in `solution/rates.py`. Configuration is stored in `solution/settings.py`. Tests are
in `solution/test_rates.py`.
- Configuration variables are stored in the `.env` file, which is then read in by `solution/settings.py`. Normally, this `.env` file would not be kept in version control, but I have included it here for ease of running.

## Instructions

### 1. Database setup
Run the following steps to start the Postgres database image:

To build the container image:

```
docker build -t ratestask .
```

To start the container:
```
docker run -p 0.0.0.0:5432:5432 --name ratestask ratestask
```

### 2. Virtual Environment
Create a new virtual environment however you like. Then, run:
```
pip install -r requirements.txt
```
This is required to start the Flask server or run the test suite.

### 3. Running the development server
With the Postgres server running, run the following commands to start the development Flask server:
```
flask --app solution run
```

## Testing
Tests are located in the `test_rates.py` file. To run all tests, ensure you have the Postgres instance running, then run:
```
pytest
```

Certain tests rely on exactly the test data which is populated into the Docker container from `rates.sql`.
These are marked with `@pytest.mark.test_data`. They may fail if the database is modified after initial load.