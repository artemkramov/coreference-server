from flask import Flask, request
from flask_restful import Api
from flask_cors import CORS
from json import dumps
from flask.json import jsonify
from mitie import *
import nlp

app = Flask(__name__)
CORS(app)
api = Api(app)

print("Loading ner model...")
ner = named_entity_extractor('uk_model.dat')


@app.route('/extract', methods=['POST'])
def extractor():
    content = request.get_json()
    tagged_data = nlp.extract_entities(content['text'], ner)
    return jsonify(tagged_data)


app.run(host='0.0.0.0', port=8090)
