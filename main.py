from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import secrets
from flask_sqlalchemy import SQLAlchemy
from elasticsearch import Elasticsearch
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.secret_key = secrets.token_urlsafe(25)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mydatabase.db'
db = SQLAlchemy(app)
es = Elasticsearch()


class Users(db.Model):
    username = db.Column(db.String(100), primary_key=True)
    password = db.Column(db.String(100))
    api_key = db.Column(db.String(10), unique=True)

    def __init__(self, username, password, api_key):
        self.username = username
        self.password = password
        self.api_key = api_key

    def __int__(self):
        self.username = None
        self.password = None
        self.api_key = None


db.create_all()


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
    else:
        print("Sign Up")
        user = Users.query.get(request.form['username'])
        if user is not None:
            return render_template('signup.html', error="User Already exists")
        generated_key = secrets.token_urlsafe(10)
        user = Users(request.form['username'], request.form['password'], generated_key)
        db.session.add(user)
        session['username'] = user.username
        session['api_key'] = user.api_key
        if create_index(user.username):
            db.session.commit()
            return render_template('showApiKey.html', api_key=generated_key)
        else:
            db.session.close()
            return render_template('signup.html', error="something went wrong")


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == 'GET':
        return render_template('signup.html')
    else:
        print("login")
        user = Users.query.get(request.form['username'])
        if user is None:
            return render_template('signup.html', error="incorrect details")
        if user.password == request.form['password']:
            session['username'] = user.username
            session['api_key'] = user.api_key
            return redirect(url_for('home'))
        else:
            return render_template('signup.html', error="incorrect details")


@app.route('/showApiKey')
def show_api_key():
    return render_template('showApiKey.html', api_key=session['api_key'])


def create_index(index):
    result = es.indices.exists(index=index)
    if result:
        return False
    result = es.indices.create(index=index)

    print(result)
    return True


@app.route('/logout')
def logout():
    session.pop('username')
    session.pop('api_key')
    return redirect(url_for('home'))


@app.route("/search/<api_key>")
def search(api_key):
    q = db.session.query(Users)
    user = q.filter(Users.api_key == api_key).first()
    if user is None:
        return jsonify({"success": False})

    search_on = list(request.args.keys())[0]
    search_for = request.args[search_on]
    if search_for == "":
        return jsonify([])

    query_body = {
        "sort": "_score",
        "query": {
            "query_string": {
                "query": search_for + "*",
                "fields": [search_on]
            }
        }
    }

    result = es.search(index=user.username, body=query_body)
    matches = []
    for single in result['hits']['hits']:
        matches.append(single['_source']['title'])
    return jsonify(matches)


@app.route("/add/<api_key>", methods=['POST'])
def add_data(api_key):
    q = db.session.query(Users)
    user = q.filter(Users.api_key == api_key).first()
    if user is None:
        return jsonify({"success": False})
    json = request.json

    return es.index(index=user.username, body=json)


if __name__ == '__main__':
    app.run(debug=True)
