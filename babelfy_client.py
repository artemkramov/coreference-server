from http_client import HttpClient


class Babelfy:

    def __init__(self):
        self.client = HttpClient()

    endpoint = "https://babelfy.io/v1/disambiguate"
    api_key = "24857588-e014-40b6-92e9-f993306255a9"
    lang = "uk"
    client = None

    def send_text(self, text):
        parameters = {
            "text": text,
            "lang": self.lang,
            "key": self.api_key
        }
        groups = []

        try:
            response = self.client.get(self.endpoint, parameters)

            if len(response) > 0:
                for entity_group in response:
                    token_fragment = entity_group['tokenFragment']
                    if token_fragment['end'] - token_fragment['start'] > 0:
                        groups.append(range(token_fragment['start'], token_fragment['end'] + 1))
        except Exception:
            return []

        return groups

    def set_client(self, _client):
        self.client = _client
