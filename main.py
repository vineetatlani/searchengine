from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import secrets
from flask_sqlalchemy import SQLAlchemy
from elasticsearch import Elasticsearch
from flask_cors import CORS
import pandas as pd
import json


app = Flask(__name__)
CORS(app)
app.secret_key = secrets.token_urlsafe(25)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///myDatabase.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

credentials_file_location = "/home/user/Downloads/credentials-a3e5f1-2021-Jan-05--14_26_59.csv"
credentials = pd.read_csv(credentials_file_location)

es_username = credentials.loc[0]['username'].strip()
es_password = credentials.loc[0]['password ']
host = "https://" + es_username + ":" + es_password + "@"
host += "05ba4a32533549bb802525a08a612fff.ap-south-1.aws.elastic-cloud.com:9243"

es = Elasticsearch(hosts=host)


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
    if 'username' not in session:
        return redirect(url_for('home'))
    return render_template('showApiKey.html', api_key=session['api_key'])


@app.route('/addIndex', methods=['GET', 'POST'])
def add_index():
    if 'username' not in session:
        return redirect(url_for('home'))
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

        if create_index(username + "_" + index_name):
            db.session.commit()
            user = User.query.get(session['username'])
            return render_template('showIndex.html', data=user.indexes)
        else:
            db.session.close()
            return render_template('addIndex.html', error="something went wrong")


@app.route('/showIndex')
def show_index():
    if 'username' not in session:
        return redirect(url_for('home'))
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
    if 'username' not in session:
        return redirect(url_for('home'))
    session.pop('username')
    session.pop('api_key')
    return redirect(url_for('home'))


@app.route("/search/<api_key>/<index>")
def search(api_key, index):
    q = db.session.query(User)
    user = q.filter(User.api_key == api_key).first()
    if user is None:
        return jsonify({"error": "Wrong Api Key"})
    found = False
    for user_index in user.indexes:
        if user_index.name == index:
            found = True
            break
    if not found:
        return jsonify({"error": "Wrong Index"})
    index = user.username + "_" + index
    params = list(request.args.keys())
    if len(params) == 0:
        return jsonify({"error": "No parameters"})
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
    return jsonify(result['hits']['hits'])


@app.route("/add/<api_key>/<index>", methods=['GET', 'POST'])
def add_data(api_key, index):
    if request.method == 'GET':
        return render_template('addData.html')

    q = db.session.query(User)
    user = q.filter(User.api_key == api_key).first()
    if user is None:
        return jsonify({"error": "Wrong Api Key"})
    found = False
    for user_index in user.indexes:
        if user_index.name == index:
            found = True
            break
    if not found:
        return jsonify({"error": "Wrong Index"})
    index = user.username + "_" + index
    if len(request.form) == 0:
        data_json = request.json
        data = data_json
    else:
        try:
            data = json.loads(request.form['data'])
        except:
            return jsonify({"error": "Data format invalid, should be json"})
    data_id = None
    if '_id' in data:
        data_id = data['_id']
        data.pop('_id')
    return es.index(index=index, body=data, id=data_id)


@app.route('/delete/<api_key>/<index>', methods=['GET', 'DELETE'])
def delete_data(api_key, index):
    if request.method == "GET":
        return render_template('deleteData.html')
    q = db.session.query(User)
    user = q.filter(User.api_key == api_key).first()
    if user is None:
        return jsonify({"error": "Wrong Api Key"})
    found = False
    for user_index in user.indexes:
        if user_index.name == index:
            found = True
            break
    if not found:
        return jsonify({"error": "Wrong Index"})
    index = user.username + "_" + index

    if '_id' in request.args:
        delete_id = request.args['_id']
        try:
            return es.delete(index=index, id=delete_id)
        except:
            return jsonify({"acknowledgement": False})
    else:
        return jsonify({"error": "_id is required as arguments for deleting"})


if __name__ == '__main__':
    app.run(host='0.0.0.0')
