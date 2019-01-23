import subprocess
import threading
import os
import re
import uuid
from word import Word
from babelfy_client import Babelfy
from universal_dependency_model import UniversalDependencyModel
import db
import csv
import string

# Encoding of the files
ENCODING = 'utf-8'

# Global variable which is used for handling of the buffer output
output = ""

# Database session marker
db_session = db.session()

# Load gazetteers
gazetteer = []
with open('gazetteers\\gazetteer.csv', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        gazetteer.append(row[0])
    # For test purpose cut size
    # gazetteer = gazetteer[:10]

# Set Babelfy client entity for working with remote API
babelfy = Babelfy()

# Load UD parser model
ud_model = UniversalDependencyModel('ukrainian-iu-ud-2.3-181115.udpipe')


# Apply gazetteer for text and try ro find named entities from it
def preprocess_text_with_gazetteer(text):
    # Array with terms which were found in the text
    gazetteer_entity_pointers = []

    # List with ranges of all found gazetteer entities
    gazetteer_entities = []

    # Loop through gazetteer terms and try to find matches
    for term in gazetteer:
        # Apply regular expression and generate list of tuples (start, end) with all occurrences
        term_occurrences = [(m.start(), m.start() + len(term)) for m in re.finditer(term, text)]
        if len(term_occurrences) > 0:
            # Parse term to form the tokens which will replace UUID
            tokens = []
            term_sentences = ud_model.tokenize(term)
            for s in term_sentences:
                i = 0
                while i < len(s.words):
                    # Omit <root> tag
                    if s.words[i].form != '<root>':
                        tokens.append(s.words[i].form)
                    i += 1

            # Add entity to gazetteer vocabulary
            gazetteer_entity_pointers.append({
                'term': term,
                'tokens': tokens
            })
    # Tokenize the whole text
    sentences = ud_model.tokenize(text)
    print("Sentence length: %d" % len(sentences))

    # Loop through each found gazetteer entity
    for gazetteer_entity_pointer in gazetteer_entity_pointers:
        window_size = len(gazetteer_entity_pointer['tokens'])
        sentence_offset = 0
        # Loop though all words of each sentence
        # and check if window is equal to current clique
        for s in sentences:
            i = 0

            # Slide window across all text
            while i < len(s.words) - window_size:
                # Set start and finish position of current clique
                j = i
                is_clique_entity = True
                clique_end = i + window_size

                # Loop through clique and compare its tokens with gazetteer entity tokens
                while j < clique_end:
                    if s.words[j].form != gazetteer_entity_pointer['tokens'][j - i]:
                        is_clique_entity = False
                        break
                    j += 1
                if is_clique_entity:
                    gazetteer_entities.append({
                        'items': range(i + sentence_offset, clique_end + sentence_offset),
                        'head_word': None
                    })
                i += 1
            sentence_offset += len(s.words)

    return gazetteer_entities


# Print output from CLI
def print_output(p):
    global output
    output = p.stdout.read().decode(ENCODING)


# Set tags for text words
def tag(in_txt):
    script_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'TagText.groovy')
    cmd = ['groovy', script_path, '-i', '-', '-o', '-', '-f']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    thread = threading.Thread(target=print_output, args=(p,))
    thread.start()
    p.stdin.write(in_txt.encode(ENCODING))
    p.stdin.close()
    thread.join()
    return output


# Extract all named entities and nouns/pronouns from text
def extract_entities(text, ner):
    tokens = []
    tagged_words = []

    # Apply gazetteer for the text and tokenize text
    gazetteer_entities = preprocess_text_with_gazetteer(text)

    # Parse text with UD
    sentences = ud_model.tokenize(text)

    for s in sentences:
        ud_model.tag(s)
        ud_model.parse(s)

        i = 0
        while i < len(s.words):
            word = s.words[i]
            raw_word = word.form.strip()
            tokens.append(raw_word)
            word_tag = word.feats
            if i == len(s.words) - 1 and raw_word == '.':
                word_tag = './SENT_END'

            tagged_word = {
                'word': raw_word,
                'tag': word_tag,
                'isEntity': False,
                'groupID': None,
                'groupLength': None,
                'groupWord': None,
                'pos': word.upostag
            }
            tagged_words.append(tagged_word)
            # print(word.feats)
            i += 1

    # Apply NER model for searching of named entities
    named_entities_models = ner.extract_entities(tokens)

    # Add named entities that were found
    # But check if their does'nt intersect with gazetteer data
    named_entities = gazetteer_entities[:]
    for named_entities_model in named_entities_models:
        is_entity_new = True
        for gazetteer_entity in gazetteer_entities:
            if len(set(gazetteer_entity['items']).intersection(named_entities_model[0])) > 0:
                is_entity_new = False
                break
        if is_entity_new and named_entities_model[2] > 0.4:
            named_entities.append({
                'items': named_entities_model[0],
                'head_word': None
            })
    named_entities_indexes = [entity['items'] for entity in named_entities]

    # Extract noun phrases from text but with excluding of the named entities
    ud_groups = ud_model.extract_noun_phrases(sentences, named_entities_indexes)
    for ud_group in ud_groups:
        named_entities.append({
            'items': ud_group['items'],
            'head_word': ud_group['head_word']
        })

    # Form list of positions which are used in the named entity
    # It is used for ignoring of them further
    exclude_entities_index = []
    named_entities_range = []
    for idx, named_entity in enumerate(named_entities):

        # Set common group ID for all words of the named entity
        group_id = idx
        named_entities_index = []

        for i in named_entity['items']:

            # Check if entity group doesn't contain dot symbol
            # which represents the end of the sentence
            token = tagged_words[i]
            if token['tag'] == './SENT_END':
                if i == 0:
                    continue
                else:
                    break
            named_entities_index.append(i)
            exclude_entities_index.append(i)
            tagged_words[i]['isEntity'] = True
            tagged_words[i]['groupID'] = group_id
            if i == named_entity['head_word'] and (not (named_entity['head_word'] is None)):
                tagged_words[i]['isHeadWord'] = True

        group_word = " ".join(tagged_words[i]['word'] for i in named_entities_index)
        group_length = len(named_entities_index)
        tagged_words[named_entities_index[0]]['groupLength'] = group_length
        tagged_words[named_entities_index[0]]['groupWord'] = group_word
        # Convert range to list for JSON serialization
        named_entities_range.append(named_entities_index)
    entities = []
    for position, token in enumerate(tagged_words):
        # Check if word isn't a part of named entity
        if not (position in exclude_entities_index):

            # Tag string for the detection of the part of speech and its attributes
            tag_string = token['tag']

            # Check if the entity is personal pronoun
            is_personal_pronoun = False
            if token['pos'] == 'PRON' and tag_string.find("PronType=Prs") > -1:
                is_personal_pronoun = True

            if is_personal_pronoun or token['pos'] == 'PROPN' or token['pos'] == 'X':
                entities.append(position)
                tagged_words[position]['isEntity'] = True

    summary = {
        "tokens": tagged_words,
        "named_entities": named_entities_range,
        "entities": entities
    }
    return summary


# Parse tag string (like столиця/noun:inanim:p:v_rod - https://github.com/brown-uk/dict_uk/blob/master/doc/tags.txt)
def parse_tag(tag_string):
    # Split by slash to divide lemma and morphological attributes
    common_parts = tag_string.split('/')

    # Set initial data
    part_of_speech = None
    is_plural = False
    gender = None
    lemma = ""

    # If the splitting operation is correct
    if len(common_parts) > 1:

        # Get lemmatized word
        lemma = common_parts[0]

        # Split second part to get separate
        morphology_attributes = common_parts[1].split(':')
        part_of_speech = morphology_attributes[0]
        morphology_attributes = morphology_attributes[1:]
        for morphology_attribute in morphology_attributes:
            # Extract gender
            if morphology_attribute in ['m', 'n', 'f']:
                gender = morphology_attribute

            # Extract plurality
            if morphology_attribute == 'p':
                is_plural = True

    return part_of_speech, is_plural, gender, lemma


# Save token with the given parameters
def save_token(word, tag_string, word_order, entity_id, coreference_group_id, document_id, is_proper_name):
    token = Word()
    token.RawText = word
    token.DocumentID = document_id
    token.WordOrder = word_order
    part_of_speech, is_plural, gender, lemma = parse_tag(tag_string)
    token.PartOfSpeech = part_of_speech
    token.Lemmatized = lemma
    token.IsPlural = is_plural
    token.IsProperName = is_proper_name
    token.Gender = gender
    token.EntityID = entity_id
    token.CoreferenceGroupID = coreference_group_id
    token.RawTagString = tag_string
    db_session.add(token)
    db_session.commit()


# Save all tokens with corresponding groups
def save_tokens(entities):
    # Word order in the document
    word_order = 0

    # Dictionary of cluster groups
    cluster_groups = {}

    # Generate unique document ID
    document_id = uuid.uuid4()

    # Loop through collection of entities
    for entity in entities:
        entity_id = None
        cluster_id = None
        is_proper_name = False

        if not (entity['groupID'] is None):
            is_proper_name = True

        # Check if entity is located inside some cluster
        if not (entity['clusterID'] is None):
            # Create new cluster group inside dictionary if it doesn't exist
            if not (entity['clusterID'] in cluster_groups):
                cluster_groups[entity['clusterID']] = uuid.uuid4()
            cluster_id = cluster_groups[entity['clusterID']]

        # Check if entity contains few words
        if len(entity['groupWords']) > 0:

            # Generate common entity ID for all words of the entity
            # and save each inner word
            entity_id = uuid.uuid4()
            for token in entity['groupWords']:
                save_token(token['word'], token['tag'], word_order, entity_id, cluster_id, document_id, is_proper_name)
                word_order += 1
        else:
            # Generate unique ID if the input token is entity (noun or pronoun)
            # and save it
            if entity['isEntity']:
                entity_id = uuid.uuid4()
            save_token(entity['word'], entity['tag'], word_order, entity_id, cluster_id, document_id, is_proper_name)
            word_order += 1
