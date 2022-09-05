import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Get the required data for the current user
    owns = db.execute('SELECT * FROM owned WHERE user_id = ?', session['user_id'])

    cash = db.execute('SELECT cash FROM users WHERE id = ?', session['user_id'])[0]['cash']
    spent = db.execute('SELECT spent FROM users WHERE id = ?', session['user_id'])[0]['spent']

    total = cash + spent

    return render_template("index.html", owns=owns, o_cash=usd(cash), o_total=usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide a symbol", 400)

        # Use lookup to get info about submitted symbol
        info = lookup(request.form.get("symbol"))

        # Ensure valid symbol was submitted
        if info == None:
            return apology("must provide a valid symbol", 400)

        # Store info variables
        name = info['name']
        price = info['price']
        symbol = info['symbol']

        # Ensure a number of shares were submitted
        if not request.form.get("shares"):
            return apology("must provide a number of shares", 400)

        # Get the number of submitted shares
        val = request.form.get("shares")

        # Ensure number of shares is not negative
        try:
            num = int(val)
            if num <= 0:
                return apology("must provide a positive number of shares", 400)
        except ValueError:
            return apology("must provide a valid number of shares", 400)

        # Get the user's current cash
        cash = db.execute('SELECT cash FROM users WHERE id = ?', session['user_id'])[0]['cash']

        # Get the user's current spent money
        spent = db.execute('SELECT spent FROM users WHERE id = ?', session['user_id'])[0]['spent']

        # Check if the user has the required cash
        if cash < num * price:
            return apology("you don't have enough cash", 400)

        # datetime object containing current date and time
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

        # Make the transaction

        # Modify user's cash according to the made transaction
        db.execute('UPDATE users SET cash = ? WHERE id = ?', (cash - num * price), session['user_id'])
        db.execute('UPDATE users SET spent = ? WHERE id = ?', (spent + num * price), session['user_id'])

        # Add the made transactions (will be useful in history funtion)
        db.execute('INSERT INTO transactions (user_id, symbol, shares, price, tdate) VALUES(?, ?, ?, ?, ?)',
                   session['user_id'], symbol, num, usd(price), dt_string)

        # Check if the user already has shares of the same company
        own = db.execute('SELECT * FROM owned WHERE user_id = ? AND symbol = ?', session['user_id'], symbol)

        # Increase user's number of shares if he already has some
        if len(own) != 0:
            db.execute('UPDATE owned SET shares = ?, total = ? WHERE user_id = ? AND symbol = ?',
                       (own[0]['shares'] + num), usd((own[0]['shares'] + num) * price), session['user_id'], symbol)

        # Add the shares to user's owned shares if those are his first
        else:
            db.execute('INSERT INTO owned (user_id, symbol, name, shares, price, total) VALUES(?, ?, ?, ?, ?, ?)',
                       session['user_id'], symbol, name, num, usd(price), usd(num * price))

        # Redirect the user to te login page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Get the current user transactions
    transactions = db.execute('SELECT * FROM transactions WHERE user_id = ?', session['user_id'])

    return render_template("history.html", transactions=transactions)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide a symbol", 400)

        # Use lookup to get info about submitted symbol
        info = lookup(request.form.get("symbol"))

        # Ensure valid symbol was submitted
        if info == None:
            return apology("must provide a valid symbol", 400)

        # Get all the required values
        name = info['name']
        price = usd(info['price'])
        symbol = info['symbol']

        # Redirect the user to the quoted page
        return render_template("quoted.html", name=name, price=price, symbol=symbol)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username dosen't exist already
        if len(rows) > 0:
            return apology("username already exists", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide password confirmation", 400)

        # Ensure confirmation matches password
        elif not request.form.get("confirmation") == request.form.get("password"):
            return apology("password and confirmation don't match", 400)

        # Add the user data to users table
        else:
            hash_pswd = generate_password_hash(request.form.get("password"))
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", request.form.get("username"), hash_pswd)

        # Redirect the user to te login page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # Get all of the current user's shares
    dumb = db.execute('SELECT * FROM owned WHERE user_id = ?', session['user_id'])

    # Get all the symbols the user needed
    symbols = []
    for i in dumb:
        symbols.append(i['symbol'])

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide a symbol", 400)

        # Get the number of owned shares of the submitted symbol
        shares = db.execute('SELECT shares FROM owned WHERE user_id = ? AND symbol = ?',
                            session['user_id'], request.form.get("symbol"))

        # Ensure user owns shares of the submitted symbol
        if shares[0]['shares'] == 0:
            return apology("you don't have any shares of this symbol", 400)

        # Use lookup to get info about submitted symbol
        info = lookup(request.form.get("symbol"))

        # Ensure valid symbol was submitted
        if info == None:
            return apology("must provide a valid symbol", 400)

        # Store info variables
        name = info['name']
        price = info['price']
        symbol = info['symbol']

        # Ensure a number of shares were submitted
        if not request.form.get("shares"):
            return apology("must provide a number of shares", 400)

        # Get the number of submitted shares
        val = request.form.get("shares")

        # Ensure number of shares is not negative
        try:
            num = int(val)
            if num <= 0:
                return apology("must provide a positive number of shares", 400)
        except ValueError:
            return apology("must provide a valid number of shares", 400)

        # Ensure the user owns that number of shares
        if shares[0]['shares'] < num:
            return apology("you don't have this much shares!", 400)

        # datetime object containing current date and time
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

        # Get the user's current cash
        cash = db.execute('SELECT cash FROM users WHERE id = ?', session['user_id'])[0]['cash']

        # Get the user's current spent money
        spent = db.execute('SELECT spent FROM users WHERE id = ?', session['user_id'])[0]['spent']

        # Make the transaction

        # Modify user's cash according to the made transaction
        db.execute('UPDATE users SET cash = ? WHERE id = ?', (cash + num * price), session['user_id'])
        db.execute('UPDATE users SET spent = ? WHERE id = ?', (spent - num * price), session['user_id'])

        # Add the made transactions (will be useful in history funtion)
        db.execute('INSERT INTO transactions (user_id, symbol, shares, price, tdate) VALUES(?, ?, ?, ?, ?)',
                   session['user_id'], symbol, -num, usd(price), dt_string)

        # Drop the whole row if the user sold all his shares
        if shares[0]['shares'] == num:
            db.execute('DELETE FROM owned WHERE user_id = ? AND symbol = ?', session['user_id'], symbol)

        # Modify the number of owned shares if not
        else:
            db.execute('UPDATE owned SET shares = ?, total = ? WHERE user_id = ? AND symbol = ?',
                       (shares[0]['shares'] - num), usd((shares[0]['shares'] - num) * price), session['user_id'], symbol)

        # Redirect the user to te login page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html", symbols=symbols)
