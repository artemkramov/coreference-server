import subprocess
import threading
import os
import re
import uuid
from word import Word
import db

# Encoding of the files
ENCODING = 'utf-8'

# Global variable which is used for handling of the buffer output
output = ""

# Database session marker
db_session = db.session()


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
    text_tagged = tag(text)

    # Fetch all tokens with appropriate tags
    # Set regular expression and extract pairs word-tag
    tag_extractor = re.compile("([^\] ]+)\[(.*?)\]")
    matches = tag_extractor.findall(text_tagged)

    # Form set of tokens from extracted list of tuples
    tokens = []
    tagged_words = []
    for item in matches:
        word = item[0].strip()
        tokens.append(word)
        tagged_word = {
            'word': word,
            'tag': item[1],
            'isEntity': False,
            'groupID': None,
            'groupLength': None,
            'groupWord': None
        }
        tagged_words.append(tagged_word)

    # Apply NER model for searching of named entities
    named_entities = ner.extract_entities(tokens)

    # Form list of positions which are used in the named entity
    # It is used for ignoring of them further
    exclude_entities_index = []
    named_entities_range = []
    for idx, named_entity in enumerate(named_entities):

        # Convert range to list for JSON serialization
        named_entities_range.append(list(named_entity[0]))

        # Set common group ID for all words of the named entity
        group_id = idx

        group_word = " ".join(tagged_words[i]['word'] for i in named_entity[0])

        group_length = len(list(named_entity[0]))

        for i in named_entity[0]:
            exclude_entities_index.append(i)
            tagged_words[i]['isEntity'] = True
            tagged_words[i]['groupID'] = group_id
            tagged_words[i]['groupLength'] = group_length
            tagged_words[i]['groupWord'] = group_word
    entities = []
    for position, token in enumerate(tagged_words):

        # Detect noun or pronoun
        tag_string = token['tag']
        if tag_string.find("noun") > -1 or tag_string.find("&pron") > -1:

            # Check if word isn't a part of named entity
            if not (position in exclude_entities_index):
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
