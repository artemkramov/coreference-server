from flask import Flask, request
from flask_restful import Api
from flask_cors import CORS
from flask.json import jsonify
from mitie import *
import nlp

# Load API web-server
app = Flask(__name__)
CORS(app)
api = Api(app)

# Load NER model
print("Loading ner model...")
ner = named_entity_extractor('uk_model.dat')


# Set HTTP endpoints of API
# There are two methods for text parsing and saving of relation between tokens
@app.route('/extract', methods=['POST'])
def extractor():
    content = request.get_json()
    tagged_data = nlp.extract_entities(content['text'], ner)
    # Extract all tokens, entities and named entities together with tags from the text
    # try:
    #     tagged_data = nlp.extract_entities(content['text'], ner)
    #     return jsonify(tagged_data)
    # except Exception as e:
    #     return jsonify({"error": str(e)}), 400


@app.route('/save', methods=['POST'])
def save_clusters():
    content = request.get_json()
    # Save all tokens with corresponding tags and relations
    try:
        nlp.save_tokens(content)
        return jsonify({})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# Run HTTP web-server
app.run(host='0.0.0.0', port=8090)
