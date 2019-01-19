import requests
import json


class HttpClient:

    host_url = ""

    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:45.0) Gecko/20100101 Firefox/45.0',
            'Accept-Encoding': 'gzip'
        })

    def set_host_url(self, _host_url):
        self.host_url = _host_url

    def get(self, url, parameters):
        request = self.s.get(url, params=parameters)
        return json.loads(request.text)
