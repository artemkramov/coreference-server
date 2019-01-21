import ufal.udpipe


class UniversalDependencyModel:

    # udpipe compiled model
    model = None

    np_simple_tags = ['ADJ', 'DET', 'NUM', 'PRON', 'PROPN', 'PUNCT', 'SCONJ', 'SYM']
    np_noun_tag = 'NOUN'

    np_relation_nmod = 'nmod'
    np_relation_case = 'case'
    np_relation_obl = 'obl'

    def __init__(self, path):
        # Load model by the given path
        self.model = ufal.udpipe.Model.load(path)
        if not self.model:
            raise Exception("Cannot load model by the given path: %s" % path)

    def parse(self, sentence):
        self.model.parse(sentence, self.model.DEFAULT)

    def tokenize(self, text):
        """Tokenize the text and return list of ufal.udpipe.Sentence-s."""
        tokenizer = self.model.newTokenizer(self.model.DEFAULT)
        if not tokenizer:
            raise Exception("The model does not have a tokenizer")
        return self._read(text, tokenizer)

    def read(self, text, in_format):
        """Load text in the given format (conllu|horizontal|vertical) and return list of ufal.udpipe.Sentence-s."""
        input_format = ufal.udpipe.InputFormat.newInputFormat(in_format)
        if not input_format:
            raise Exception("Cannot create input format '%s'" % in_format)
        return self._read(text, input_format)

    def _read(self, text, input_format):
        input_format.setText(text)
        error = ufal.udpipe.ProcessingError()
        sentences = []

        sentence = ufal.udpipe.Sentence()
        while input_format.nextSentence(sentence, error):
            sentences.append(sentence)
            sentence = ufal.udpipe.Sentence()
        if error.occurred():
            raise Exception(error.message)

        return sentences

    def tag(self, sentence):
        """Tag the given ufal.udpipe.Sentence (inplace)."""
        self.model.tag(sentence, self.model.DEFAULT)

    def write(self, sentences, out_format):
        """Write given ufal.udpipe.Sentence-s in the required format (conllu|horizontal|vertical)."""

        output_format = ufal.udpipe.OutputFormat.newOutputFormat(out_format)
        output = ''
        for sentence in sentences:
            output += output_format.writeSentence(sentence)
        output += output_format.finishDocument()

        return output

    def extract_noun_phrases(self, sentences, named_entities):
        sentences_groups = []
        token_offset = 0
        named_entities_indexes = []
        for r in named_entities:
            named_entities_indexes.extend(list(r))

        # Loop through the sentences
        for s in sentences:
            i = 0
            word_root_index = -1

            # Loop through words of the sentence and find out root word
            while i < len(s.words):
                word = s.words[i]

                # Check if the head links to the <root> element
                # and set index
                if word.head == 0:
                    word_root_index = i
                    break
                i += 1

            # Retrieve root word
            word_root = s.words[word_root_index]

            # Find groups with head nouns and corresponding tokens
            groups = {}
            self.np_recursive_extractor(word_root, s.words, groups, named_entities_indexes, token_offset, None)

            # Fix token sequence inside each NP group
            # It is necessary to remove all spaces inside the group
            np_indexes = list(groups.keys())
            np_indexes.sort()

            sentence_group = []
            for np_index in np_indexes:

                # Get all token list of NP and sort it in ascending order
                group = groups[np_index]
                group.sort()

                # Find index of head token
                np_group_idx = group.index(np_index)

                # Init corrected group
                group_aligned = [np_index]

                # Loop till the end of list from the head word
                # and check if all numbers is located near each other
                i = np_group_idx + 1
                while i < len(group):
                    if group[i] == group[i - 1] + 1:
                        group_aligned.append(group[i])
                    else:
                        break
                    i += 1

                # Loop till the start of list from the head word
                # and check if all numbers is located near each other
                i = np_group_idx - 1
                while i >= 0:
                    if group[i] + 1 == group[i + 1]:
                        group_aligned.append(group[i])
                    else:
                        break
                    i -= 1

                # Sort aligned group
                group_aligned.sort()
                # Append group as range
                sentence_group.append({
                    'head_word_idx': np_index + token_offset,
                    'items': range(group_aligned[0] + token_offset, group_aligned[-1] + token_offset + 1)
                })

            # Append all groups of the sentence to the general collection
            sentences_groups.extend(sentence_group)
            token_offset += len(s.words)
        return sentences_groups

    def np_recursive_extractor(self, word, words, groups, named_entity_indexes, offset, head_id=None):
        if groups is None:
            groups = {}
        i = 0
        new_head_id = None
        token_id = word.id

        # Part of speech - NOUN, ADJ, VERB etc. - https://universaldependencies.org/u/pos/index.html
        u_pos_tag = word.upostag

        # Dependency relation to the head (amod, nmod) - https://universaldependencies.org/u/dep/index.html
        deprel = word.deprel

        # Check if the parent id is passed and POS tag is allowed
        if (not (head_id is None)) and u_pos_tag in self.np_simple_tags:
            new_head_id = head_id

        if u_pos_tag == self.np_noun_tag:
            new_head_id = token_id
            if not (head_id is None):
                # Check if we can add current noun to another NP
                # Firstly check if the type of the relation is nmod
                if deprel == self.np_relation_nmod and words[head_id].deprel != 'obl':

                    # Also check if current word contains case relation
                    j = 0
                    is_containing_case = False
                    while j < len(word.children):
                        children = words[word.children[j]]
                        if children.deprel == self.np_relation_case:
                            is_containing_case = True
                            break
                        j += 1
                    if not is_containing_case:
                        new_head_id = head_id

        # If the head word is set than add current token to its group
        if not (new_head_id is None):
            # Check if head_id and token_id aren't already inside named entities
            if (not (token_id + offset in named_entity_indexes)) and (not (new_head_id + offset in named_entity_indexes)):
                self.np_push_to_group(groups, new_head_id, token_id)

        # Loop through child words and call function in recursive manner
        while i < len(word.children):
            children_index = word.children[i]
            self.np_recursive_extractor(words[children_index], words, groups, named_entity_indexes, offset, new_head_id)
            i += 1

    @staticmethod
    def np_push_to_group(groups, head_id, token_id):
        # Create head group if it doesn't exist
        if not (head_id in groups):
            groups[head_id] = []
        groups[head_id].append(token_id)


