from flask import Flask, request
from flask_restful import Api
from flask_cors import CORS
from flask.json import jsonify
from mitie import *
import nlp
import db
from word import Word

app = Flask(__name__)
CORS(app)
api = Api(app)

# Add test word to database
# w = Word()
# w.RawText = "asd"
# w.DocumentID = "435345"
# w.WordOrder = 4
# w.PartOfSpeech = "noun"
# w.Lemmatized = "asd"
# w.IsPlural = 0
# w.Gender = "m"
# w.RawTagString = "sdfdsf:dsfsdf/sdfsdf:sdfs"
# s = db.session()
# s.add(w)
# s.commit()

print("Loading ner model...")
ner = named_entity_extractor('uk_model.dat')


@app.route('/extract', methods=['POST'])
def extractor():
    content = request.get_json()
    tagged_data = nlp.extract_entities(content['text'], ner)
    return jsonify(tagged_data)


@app.route('/save', methods=['POST'])
def save_clusters():
    content = request.get_json()

    return jsonify({})


app.run(host='0.0.0.0', port=8090)
