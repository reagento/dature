from dataclasses import dataclass

import dature


@dataclass
class Config:
    name: str

field_mapping = {dature.F[Config].name: ("fullName", "userName")}
