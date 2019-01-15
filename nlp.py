import subprocess
import threading
import os
import re

ENCODING = 'utf-8'

output = ""


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
