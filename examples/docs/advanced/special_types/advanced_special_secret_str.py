"""SecretStr — masks secret values in str/repr."""

from dataclasses import dataclass

from dature.fields.secret_str import SecretStr

secret = SecretStr("my-database-password")


@dataclass
class Config:
    db_password: SecretStr


config = Config(db_password=secret)

print(config.db_password)  # **********
print(repr(config.db_password))  # SecretStr('**********')
print(config.db_password.get_secret_value())  # my-database-password
print(len(config.db_password))  # 20
