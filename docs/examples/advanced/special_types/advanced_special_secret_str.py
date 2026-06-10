# --8<-- [start:setup]
from dataclasses import dataclass

from dature.fields.secret_str import SecretStr

secret = SecretStr("my-database-password")


@dataclass
class Config:
    db_password: SecretStr


config = Config(db_password=secret)

# --8<-- [end:setup]

# --8<-- [start:example]
assert str(config.db_password) == "**********"
assert repr(config.db_password) == "SecretStr('**********')"
assert config.db_password.get_secret_value() == "my-database-password"
assert len(config.db_password) == 20

# --8<-- [end:example]
