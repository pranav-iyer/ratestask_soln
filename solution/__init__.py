from flask import Flask

app = Flask(__name__)
app.config.from_object("solution.settings")

import solution.rates
