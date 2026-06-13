from dataclasses import dataclass


@dataclass
class DB:
    host: str
    port: int


@dataclass
class Settings:
    db: DB
