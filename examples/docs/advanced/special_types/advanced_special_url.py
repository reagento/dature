"""URL — parsed into urllib.parse.ParseResult."""

from dataclasses import dataclass
from urllib.parse import urlparse

from dature.types import URL


@dataclass
class Config:
    api_url: URL


config = Config(api_url=urlparse("https://api.example.com:8080/v1?key=abc#section"))

print(config.api_url.scheme)  # https
print(config.api_url.netloc)  # api.example.com:8080
print(config.api_url.hostname)  # api.example.com
print(config.api_url.port)  # 8080
print(config.api_url.path)  # /v1
print(config.api_url.query)  # key=abc
print(config.api_url.fragment)  # section
print(config.api_url.geturl())  # https://api.example.com:8080/v1?key=abc#section
