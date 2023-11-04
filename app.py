from flask import Flask, redirect, url_for, render_template, request, session, flash
from datetime import timedelta
import pyrebase
import requests
import json
import re
import stripe

stripe.api_key = 'sk_test_51NvUfwDjldMXbWwWCMm6iC9uxDC88N9mvMhrZwuEd1OtAAyhionlezyws1H3D92ALwqIZkll4qzqmotaeYkwvqlm00yzB1PQkc'


app = Flask(__name__)
app.secret_key = "hello"
app.permanent_session_lifetime = timedelta(minutes=5)

firebaseConfig = dict(apiKey="AIzaSyDyt_QkHxhpgLxKHppnI_pjhZQDZV9dGZA",
                      authDomain="smart-parking-d841d.firebaseapp.com", projectId="smart-parking-d841d",
                      storageBucket="smart-parking-d841d.appspot.com", messagingSenderId="189936042589",
                      appId="1:189936042589:web:772ac9d4e09cf11d8043b4", measurementId="G-5PCDRVSEVK",
                      databaseURL="https://smart-parking-d841d-default-rtdb.firebaseio.com/")

firebase = pyrebase.initialize_app(firebaseConfig)

db = firebase.database()
auth = firebase.auth()


# storage = firebase.storage()


@app.route('/',  methods=['POST', 'GET'])
def home():
    if request.method == "GET":
        if "username" in session:
            user_name = session["username"]
            try:
                user_license_num = db.child("accounts").child(user_name).child("license_num").get().val()
            except:
                user_license_num = "None"

            stripe_customer_id = db.child("accounts").child(user_name).child("stripe_customer_id").get().val()
            cards = []

            # If there is a Stripe customer ID, fetch the cards
            if stripe_customer_id:
                cards = stripe.PaymentMethod.list(
                    customer=stripe_customer_id,
                    type="card",
                )

            tag_ID = db.child("accounts").child(user_name).child("tag_ID").get().val()
            if tag_ID == "":
                tag_ID = "No assigned RF tag"
            
            return render_template("home.html", user=user_name, license=user_license_num, cards=cards.data, tag_ID=tag_ID)
        else:
            return redirect(url_for('login'))



@app.route('/login', methods=['POST', 'GET'])
def login():
    if "username" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        # session.permanent = True
        user_email = request.form["email"]
        user_password = request.form["password"]
        try:
            auth.sign_in_with_email_and_password(email=user_email, password=user_password)

            accounts = db.child("accounts").get().val()
            username = ""
            for name, account_info in accounts.items():
                if account_info['email'] == user_email:
                    username = name
                    # print(f"the email: {account_info['email']}")
                    # print(f"the username: {name}")

            session["username"] = username
            return redirect(url_for("home"))
        except Exception as e:
            print("something broke")
            print(f"execption is: {e}")
            flash("Incorrect Username or Password", "error")
            return redirect(url_for("login"))
    return render_template("login.html", button_label="Sign Up")


# @app.route('/user')
# def user():
#     if "user" in session:
#         user = session["user"]
#         return redirect()
#     else:
#         return redirect(url_for("login"))


@app.route('/logout')
def logout():
    # session.permanent = False
    session.pop("username", None)
    session.clear()
    return redirect(url_for("login"))


@app.route('/signup', methods=["POST", "GET"])
def signup():

    if request.method == "POST":
        username = request.form["username"]
        user_email = request.form["email"]
        user_password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        valid = True

        if user_password != confirm_password:
            flash("Passwords do not match, please try again.")
            valid = False
            # return redirect(url_for('signup'))

        if username in list(db.child("accounts").shallow().get().val()):
            flash("There is already an account associated with this username.")
            valid = False
            # return redirect(url_for('signup'))

        if not re.match(r'^[a-zA-Z0-9]+$', username):
            flash("Username can only contain letters and numbers")
            valid = False
            # return redirect(url_for('signup'))

        # return redirect(url_for('signup'))

        if valid:
            try:
                auth.create_user_with_email_and_password(user_email, user_password)
            except requests.exceptions.HTTPError as error:
                error_json = error.args[1]
                error_dict = json.loads(error_json)["error"]
                error_message = error_dict["message"]

                if "EMAIL_EXISTS" in error_message:
                    flash("There is already an account associated with this email.")

                if "WEAK_PASSWORD" in error_message:
                    flash("Password should be at least 6 characters.")

                # else:
                #     flash("An unknown error occurred please try again.")

                return redirect(url_for("signup"))

            db.child("accounts").child(username).set({"email": user_email, "username": username})
            flash(f"{username}, your account has been created!")
            return redirect(url_for("login"))
        else:
            return redirect(url_for("signup"))

    else:
        return render_template("signup.html")

@app.route('/addLicense', methods=["POST", "GET"])
def addLicense():
    if request.method == "POST":
        user_license_num = request.form["addLicense"]
        session["user_license_num"] = user_license_num
        db.child("accounts").child(session["username"]).update({"license_num": user_license_num})
        return redirect(url_for("home"))
    else:
        return render_template("add_license.html")

# @app.route('/modify_cars')
# def modify_cars():
#     if "username" in session:
#         return render_template("add_license.html")
#     else:
#         flash("Username no longer in session.")
#         return redirect(url_for('login'))


@app.route('/modify_payment', methods=["POST", "GET"])
def modify_payment():
    if "username" in session:
        stripe_customer_id = db.child("accounts").child(session["username"]).child("stripe_customer_id").get().val()

        # If the customer does not exist on Stripe, create them
        if not stripe_customer_id:
            user_email = db.child("accounts").child(session["username"]).child("email").get().val()
            customer = stripe.Customer.create(email=user_email)

            db.child("accounts").child(session["username"]).update({"stripe_customer_id": customer.id})
            stripe_customer_id = customer.id

        customer = stripe.Customer.retrieve(stripe_customer_id)

        # Get all cards
        cards = stripe.PaymentMethod.list(
        customer=stripe_customer_id,
        type="card",
    )


        return render_template("modify_payment.html", cards=cards)
    else:
        flash("Username no longer in session.")
        return redirect(url_for('login'))
    

@app.route('/add_card', methods=["POST"])
def add_card():
    if "username" in session:
        stripe_customer_id = db.child("accounts").child(session["username"]).child("stripe_customer_id").get().val()
        token = request.form['stripeToken']

        if stripe_customer_id:
            payment_method = stripe.PaymentMethod.create(
                type='card',
                card={
                    "token": token
                }
            )

            stripe.PaymentMethod.attach(
                payment_method.id,
                customer=stripe_customer_id,
            )
        else:
            flash("Something went wrong.")
            return redirect(url_for('login'))


        flash("Card added successfully!", "success")
        return redirect(url_for('modify_payment'))
    else:
        flash("Username no longer in session.")
        return redirect(url_for('login'))




if __name__ == '__main__':
    app.run(debug=True)
