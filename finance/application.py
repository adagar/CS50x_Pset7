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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    #get username
    rows = db.execute("SELECT * FROM users WHERE id = :userID",
                          userID=session["user_id"])
    username = rows[0]["username"]
    cash = int(rows[0]["cash"])
    #get all transactions for this user
    rows = db.execute("SELECT * FROM users WHERE id = :userID",
                          userID=session["user_id"])
    userTransactions = db.execute("SELECT * FROM transactions where purchasing_user = :username", username=username)

    #turn transactions into clean portfolio
    portfolio = {}
    totalStockVal = 0

    for transaction in userTransactions:
        symbol = transaction["symbol"]
        if symbol in portfolio:
            portfolio[symbol][0] += transaction["quantity"]
        else:
            portfolio[symbol] = [transaction["quantity"], lookup(symbol)["price"]]
        totalStockVal += lookup(symbol)["price"] * transaction["quantity"]


    return render_template("index.html", portfolio=portfolio, cash=cash, totalStockVal=totalStockVal)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbolRequest = request.form.get("symbol")
        quantity = int(request.form.get("quantity"))

        stockInfo = lookup(symbolRequest)
        cleanPrice = int(stockInfo["price"])
        cleanSymbol = stockInfo["symbol"]

        totalCost = cleanPrice * quantity
        #check if user can afford it
        #Look up user
        rows = db.execute("SELECT * FROM users WHERE id = :userID",
                          userID=session["user_id"])
        #get their cash balance
        cashBalance = rows[0]["cash"]
        username = rows[0]["username"]
        #print(cashBalance)
            #if they can afford
        if totalCost < cashBalance:
            print(cashBalance - totalCost)
            #create a transaction
            db.execute("INSERT INTO transactions(purchasing_user, symbol, value, quantity) VALUES(:username, :cleanSymbol, :cleanPrice, :quantity)", username=username, cleanSymbol=cleanSymbol, cleanPrice=cleanPrice, quantity=quantity)
            #update user cash
            db.execute("UPDATE users SET cash = cash - :totalCost WHERE id = :userID", totalCost = totalCost, userID = session["user_id"])

        else:
            return apology("you can't afford that", 403)

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

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
    q = request.args.get("symbol")
    print(q)
    if request.method == "GET" and q:
        stockInfo = lookup(q)
        return render_template("display.html", symbol=stockInfo)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()

    if request.method == "POST":
        #check for username
        if not request.form.get("username"):
            return apology("must provide username", 403)

        #check for password field
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        #check for matching password field
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password confirmation must match", 403)

        #username must be unique
        elif len(db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))) > 0:
            return apology("username is taken")

        print("Form seems good!")
        #add username to database
        hash = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users(username, hash) VALUES(:username, :hash)", username = request.form.get("username"), hash=hash)

        #query that new user
        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        #remember that user has logged in
        session["user_id"] = rows[0]["id"]

        #redirect to home page
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbolRequest = request.form.get("symbol")
        quantity = int(request.form.get("quantity")) * -1

        username = db.execute("SELECT username FROM users WHERE id=:userID", userID=session["user_id"])[0]['username']
        #username = username['username']
        stockInfo = lookup(symbolRequest)
        cleanPrice = int(stockInfo["price"])
        cleanSymbol = stockInfo["symbol"]

        totalSalesPrice = cleanPrice * quantity
        print(quantity)
        #check if user can afford it
        #Look up user
        print(f"{username} wants to sell {quantity} of {cleanSymbol} for {totalSalesPrice}")
        ownedQuantityStock = db.execute("SELECT SUM(quantity) FROM transactions WHERE purchasing_user = :username AND symbol = :symbol", username=username, symbol=cleanSymbol)[0]['SUM(quantity)']

        if abs(quantity) <= ownedQuantityStock:
            #create a transaction
            db.execute("INSERT INTO transactions(purchasing_user, symbol, value, quantity) VALUES(:username, :cleanSymbol, :cleanPrice, :quantity)", username=username, cleanSymbol=cleanSymbol, cleanPrice=cleanPrice, quantity=quantity)
            #update user cash
            db.execute("UPDATE users SET cash = cash - :totalSalesPrice WHERE id = :userID", totalSalesPrice = totalSalesPrice, userID = session["user_id"])

        else:
            return apology("you don't have that many", 403)

        return redirect("/")
    else:
        return render_template("sell.html")



def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
