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

    def extract_noun_phrases(self, sentences):
        for s in sentences:
            i = 0
            # print(s.getText())
            word_root_index = -1
            while i < len(s.words):
                word = s.words[i]
                if word.head == 0:
                    word_root_index = i
                    break
                i += 1
            word_root = s.words[word_root_index]
            print(word_root.lemma, word_root.children)
            groups = {}
            self.np_recursive_extractor(word_root, s.words, groups, None)
            print(groups)

    def np_recursive_extractor(self, word, words, groups, head_id=None):
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

        # print("%s ----- %s ------ %s ----- %s" % (word.form, word.misc, word.upostag, word.deprel))
        if not (new_head_id is None):
            self.np_push_to_group(groups, new_head_id, token_id)
        while i < len(word.children):
            children_index = word.children[i]
            self.np_recursive_extractor(words[children_index], words, groups, new_head_id)
            i += 1

    @staticmethod
    def np_push_to_group(groups, head_id, token_id):

        # Create head group if it doesn't exist
        # print(head_id, groups)
        if not (head_id in groups):
            groups[head_id] = []
        groups[head_id].append(token_id)


