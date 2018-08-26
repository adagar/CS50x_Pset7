import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

"""
Custom content
"""
@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Allow user to deposit more cash"""
    if request.method != "POST":
        cash = db.execute("SELECT cash FROM users where id=:userID",
                                 userID=session["user_id"])[0]["cash"]
        return render_template("deposit.html", cash=cash)
    else:
        try:
            deposit = float(request.form.get("deposit"))
        except ValueError:
            return apology("Invalid deposit", 400)

        db.execute("UPDATE users SET cash = cash + :deposit WHERE id=:userID",
                           deposit=deposit, userID=session["user_id"])
        return redirect("/")

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # get username
    userInfo = db.execute("SELECT * FROM users WHERE id = :userID",
                          userID=session["user_id"])
    cash = int(userInfo[0]["cash"])
    # get all transactions for this user
    userTransactions = db.execute("SELECT * FROM transactions where userID = :userID",
                                  userID=session["user_id"])

    # turn transactions into clean portfolio
    portfolio = GetUserStocks()
    totalStockVal = 0.0

    if len(portfolio) != 0:
        for item in portfolio:
            totalStockVal += lookup(item)["price"] * portfolio[item][0]

    return render_template("index.html", portfolio=portfolio, cash=cash, totalStockVal=totalStockVal)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbolRequest = request.form.get("symbol")
        # print(request.form.get("shares"))
        try:
            quantity = float(request.form.get("shares"))
        except ValueError:
            return apology("Invalid quantity", 400)
        if quantity < 0 or quantity % 1 != 0:
            return apology("Invalid quantity", 400)

        stockInfo = lookup(symbolRequest)
        if stockInfo != None and len(stockInfo) != 0:
            cleanPrice = int(stockInfo["price"])
            cleanSymbol = stockInfo["symbol"]

            totalCost = cleanPrice * quantity
            # check if user can afford it
            # Look up user
            userData = db.execute("SELECT * FROM users WHERE id = :userID", userID=session["user_id"])
            # get their cash balance
            cashBalance = userData[0]["cash"]
            # print(cashBalance)
            # if they can afford
            if totalCost < cashBalance:
                # print(cashBalance - totalCost)
                # create a transaction
                db.execute("INSERT INTO transactions(userID, symbol, value, quantity) VALUES(:userID, :cleanSymbol, :cleanPrice, :quantity)",
                           userID=session["user_id"], cleanSymbol=cleanSymbol, cleanPrice=cleanPrice, quantity=quantity)
                # update user cash
                db.execute("UPDATE users SET cash = cash - :totalCost WHERE id=:userID",
                           totalCost=totalCost, userID=session["user_id"])

            else:
                return apology("you can't afford that", 403)
        else:
            return apology("Invalid stock choice", 400)

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    actions = db.execute("SELECT * FROM transactions where userID = :userID", userID=session["user_id"])
    return render_template("history.html", actions=actions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form render_template("display.html")
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        q = request.form.get("symbol")
        stockInfo = lookup(q)
        if stockInfo != None and len(stockInfo) != 0:
            return render_template("display.html", symbol=stockInfo)
        else:
            return apology("must provide valid symbol", 400)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()

    if request.method == "POST":
        # check for username
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # check for password field
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # check for matching password field
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password confirmation must match", 400)

        # username must be unique
        elif len(db.execute("SELECT * FROM users WHERE username = :username",
                            username=request.form.get("username"))) > 0:
            return apology("username is taken")

        # print("Form seems good!")
        # add username to database
        hash = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users(username, hash) VALUES(:username, :hash)",
                   username=request.form.get("username"), hash=hash)

        # query that new user
        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # remember that user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect to home page
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        # get user stocks
        portfolio = GetUserStocks()
        # turn them into a list
        # get quantity sold
        # confirm its an integer
        # sell
        symbolRequest = request.form.get("symbol")
        quantity = int(request.form.get("shares")) * -1

        # username = username['username']
        stockInfo = lookup(symbolRequest)
        cleanPrice = int(stockInfo["price"])
        cleanSymbol = stockInfo["symbol"]

        totalSalesPrice = cleanPrice * quantity
        # print(quantity)
        # check if user can afford it
        # Look up user
        ownedQuantityStock = db.execute("SELECT SUM(quantity) FROM transactions WHERE userID = :userID AND symbol = :symbol",
                                        userID=session["user_id"], symbol=cleanSymbol)[0]['SUM(quantity)']

        if abs(quantity) <= ownedQuantityStock:
            # create a transaction
            db.execute("INSERT INTO transactions(userID, symbol, value, quantity) VALUES(:userID, :cleanSymbol, :cleanPrice, :quantity)",
                       userID=session["user_id"], cleanSymbol=cleanSymbol, cleanPrice=cleanPrice, quantity=quantity)
            # update user cash
            db.execute("UPDATE users SET cash = cash - :totalSalesPrice WHERE id = :userID",
                       totalSalesPrice=totalSalesPrice, userID=session["user_id"])

        else:
            return apology("you don't have that many", 400)

        return redirect("/")
    else:
        portfolio = GetUserStocks()
        return render_template("sell.html", portfolio=portfolio)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


def GetUserStocks():
    userTransactions = db.execute("SELECT * FROM transactions where userID = :userID",
                                  userID=session["user_id"])

    # turn transactions into clean portfolio
    portfolio = {}

    for transaction in userTransactions:
        symbol = transaction["symbol"]
        if symbol in portfolio:
            portfolio[symbol][0] += transaction["quantity"]
            if portfolio[symbol][0] == 0:
                del portfolio[symbol]
        else:
            portfolio[symbol] = [transaction["quantity"], lookup(symbol)["price"]]

    return portfolio