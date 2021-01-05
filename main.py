from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import secrets
from flask_sqlalchemy import SQLAlchemy
from elasticsearch import Elasticsearch
from flask_cors import CORS
import pandas as pd

app = Flask(__name__)
CORS(app)
app.secret_key = secrets.token_urlsafe(25)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///myDatabase.db'
db = SQLAlchemy(app)

credentials_file_location = "/home/user/Downloads/credentials-a3e5f1-2021-Jan-05--14_26_59.csv"
credentials = pd.read_csv(credentials_file_location)

es_username = credentials.loc[0]['username'].strip()
es_password = credentials.loc[0]['password ']
hosts = "https://" + es_username + ":" + es_password + "@"
hosts += "05ba4a32533549bb802525a08a612fff.ap-south-1.aws.elastic-cloud.com:9243"

es = Elasticsearch()


class User(db.Model):
    username = db.Column(db.String(100), primary_key=True)
    password = db.Column(db.String(100))
    api_key = db.Column(db.String(10), unique=True)
    indexes = db.relationship('Index', backref='user', lazy=True)

    def __init__(self, username, password, api_key):
        self.username = username
        self.password = password
        self.api_key = api_key


class Index(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), db.ForeignKey('user.username'), nullable=False)

    def __init__(self, index_id, name, username):
        self.username = username
        self.name = name
        self.id = index_id


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
        user = User.query.get(request.form['username'])
        if user is not None:
            return render_template('signup.html', error="User Already exists")
        generated_key = secrets.token_urlsafe(10)
        user = User(request.form['username'], request.form['password'], generated_key)
        print(user.username + " " + user.password)
        db.session.add(user)
        session['username'] = user.username
        session['api_key'] = user.api_key
        db.session.commit()
        return render_template('showApiKey.html', api_key=generated_key)


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == 'GET':
        return render_template('signup.html')
    else:
        print("login")
        user = User.query.get(request.form['username'])
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


@app.route('/addIndex', methods=['GET', 'POST'])
def add_index():
    if request.method == 'GET':
        return render_template('addIndex.html')
    else:
        username = session['username']
        index_name = request.form['Index_name']
        user = User.query.get(session['username'])
        for index in user.indexes:
            if index.name == index_name:
                return render_template('addIndex.html', error="Index Already exists")
        index = Index(None, index_name, username)
        db.session.add(index)

        if create_index(index_name):
            db.session.commit()
            user = User.query.get(session['username'])
            return render_template('showIndex.html', data=user.indexes)
        else:
            db.session.close()
            return render_template('addIndex.html', error="something went wrong")


@app.route('/showIndex')
def show_index():
    user = User.query.get(session['username'])
    print(user.indexes)
    return render_template('showIndex.html', data=user.indexes)


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


@app.route("/search/<api_key>/<index>")
def search(api_key, index):
    q = db.session.query(User)
    user = q.filter(User.api_key == api_key).first()
    if user is None:
        return jsonify({"error": "Wrong Api Key"})

    params = list(request.args.keys())
    if len(params) == 0:
        return jsonify({"error": "No parameter"})
    search_on = params[0]
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

    result = es.search(index=index, body=query_body)
    matches = []
    for single in result['hits']['hits']:
        matches.append(single['_source']['title'])
    return jsonify(matches)


@app.route("/add/<api_key>/<index>", methods=['GET', 'POST'])
def add_data(api_key, index):
    if request.method == 'GET':
        return render_template('addData.html')
    else:
        q = db.session.query(User)
        user = q.filter(User.api_key == api_key).first()
        if user is None:
            return jsonify({"error": "Wrong Api Key"})
        for user_index in user.indexes:
            if user_index.name == index:
                if len(request.form) == 0:
                    json = request.json
                    data = json
                else:
                    data = request.form['data']
                try:
                    return es.index(index=index, body=data)
                except:
                    return jsonify({"error": "Input Format incorrect"})

        return jsonify({"error": "index doesn't exist"})


if __name__ == '__main__':
    app.run(debug=True)
