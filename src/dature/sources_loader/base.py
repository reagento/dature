import abc
import json
import logging
from dataclasses import fields, is_dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Annotated, ClassVar, TypeVar, cast, get_args, get_origin, get_type_hints

from adaptix import NameStyle as AdaptixNameStyle
from adaptix import Retort, loader, name_mapping
from adaptix.provider import Provider

from dature.expansion.alias_provider import AliasProvider, resolve_nested_owner
from dature.expansion.env_expand import expand_env_vars
from dature.field_path import FieldPath
from dature.fields.byte_size import ByteSize
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr
from dature.path_finders.base import PathFinder
from dature.protocols import DataclassInstance, LoaderProtocol, ValidatorProtocol
from dature.skip_field_provider import ModelToDictProvider, SkipFieldProvider
from dature.sources_loader.loaders.base import (
    base64url_bytes_from_string,
    base64url_str_from_string,
    byte_size_from_string,
    bytes_from_string,
    complex_from_string,
    payment_card_number_from_string,
    secret_str_from_string,
    timedelta_from_string,
    url_from_string,
)
from dature.types import (
    URL,
    Base64UrlBytes,
    Base64UrlStr,
    DotSeparatedPath,
    ExpandEnvVarsMode,
    FieldMapping,
    FieldValidators,
    FileOrStream,
    JSONValue,
    NameStyle,
    TypeAnnotation,
)
from dature.validators.base import (
    create_metadata_validator_providers,
    create_root_validator_providers,
    create_validator_providers,
    extract_validators_from_type,
)

if TYPE_CHECKING:
    from dature.metadata import TypeLoader

T = TypeVar("T")

logger = logging.getLogger("dature")


class BaseLoader(LoaderProtocol, abc.ABC):
    display_name: ClassVar[str]
    path_finder_class: type[PathFinder] | None = None

    def __init__(  # noqa: PLR0913
        self,
        *,
        prefix: DotSeparatedPath | None = None,
        name_style: NameStyle | None = None,
        field_mapping: FieldMapping | None = None,
        root_validators: tuple[ValidatorProtocol, ...] | None = None,
        validators: FieldValidators | None = None,
        expand_env_vars: ExpandEnvVarsMode = "default",
        type_loaders: "tuple[TypeLoader, ...]" = (),
    ) -> None:
        self._prefix = prefix
        self._name_style = name_style
        self._field_mapping = field_mapping
        self._root_validators = root_validators or ()
        self._validators = validators or {}
        self._expand_env_vars_mode = expand_env_vars
        self._type_loaders = type_loaders
        self.retorts: dict[type, Retort] = {}

    def _additional_loaders(self) -> list[Provider]:
        return []

    def _get_adaptix_name_style(self) -> AdaptixNameStyle | None:
        if self._name_style is None:
            return None

        name_style_map = {
            "lower_snake": AdaptixNameStyle.LOWER_SNAKE,
            "upper_snake": AdaptixNameStyle.UPPER_SNAKE,
            "lower_camel": AdaptixNameStyle.CAMEL,
            "upper_camel": AdaptixNameStyle.PASCAL,
            "lower_kebab": AdaptixNameStyle.LOWER_KEBAB,
            "upper_kebab": AdaptixNameStyle.UPPER_KEBAB,
        }
        return name_style_map.get(self._name_style)

    def _get_name_mapping_provider(self) -> list[Provider]:
        providers: list[Provider] = []

        adaptix_name_style = self._get_adaptix_name_style()
        if adaptix_name_style is not None:
            providers.append(name_mapping(name_style=adaptix_name_style))

        if self._field_mapping:
            owner_fields: dict[type[DataclassInstance] | str, dict[str, str]] = {}
            for field_path_key in self._field_mapping:
                if not isinstance(field_path_key, FieldPath):
                    continue
                owner: type[DataclassInstance] | str = field_path_key.owner
                if len(field_path_key.parts) > 1 and not isinstance(field_path_key.owner, str):
                    owner = resolve_nested_owner(field_path_key.owner, field_path_key.parts[:-1])
                field_name = field_path_key.parts[-1]
                if owner not in owner_fields:
                    owner_fields[owner] = {}
                owner_fields[owner][field_name] = field_name

            for owner, identity_map in owner_fields.items():
                if isinstance(owner, str):
                    providers.append(name_mapping(map=identity_map))
                else:
                    providers.append(name_mapping(owner, map=identity_map))

            providers.append(AliasProvider(self._field_mapping))

        return providers

    def _get_validator_providers(self, dataclass_: type[T]) -> list[Provider]:
        providers: list[Provider] = []
        type_hints = get_type_hints(dataclass_, include_extras=True)

        for field in fields(cast("type[DataclassInstance]", dataclass_)):
            if field.name not in type_hints:
                continue

            field_type = type_hints[field.name]
            validators = extract_validators_from_type(field_type)

            if validators:
                field_providers = create_validator_providers(dataclass_, field.name, validators)
                providers.extend(field_providers)

            for nested_dc in self._find_nested_dataclasses(field_type):
                nested_providers = self._get_validator_providers(nested_dc)
                providers.extend(nested_providers)

        return providers

    @staticmethod
    def _find_nested_dataclasses(
        field_type: TypeAnnotation,
    ) -> list[type[DataclassInstance]]:
        result: list[type[DataclassInstance]] = []
        queue: list[TypeAnnotation] = [field_type]

        while queue:
            current = queue.pop()

            if is_dataclass(current):
                result.append(current)
                continue

            origin = get_origin(current)
            if origin is Annotated:
                queue.append(get_args(current)[0])
            elif origin is not None:
                queue.extend(get_args(current))

        return result

    @staticmethod
    def _infer_type(value: str) -> JSONValue:
        if value == "":
            return value

        try:
            return cast("JSONValue", json.loads(value))
        except (json.JSONDecodeError, ValueError):
            return value

    @classmethod
    def _parse_string_values(cls, data: JSONValue, *, infer_scalars: bool = False) -> JSONValue:
        if not isinstance(data, dict):
            return data

        result: dict[str, JSONValue] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = cls._parse_string_values(value, infer_scalars=True)
            elif isinstance(value, str) and (infer_scalars or value.startswith(("[", "{"))):
                result[key] = cls._infer_type(value)
            else:
                result[key] = value
        return result

    def _base_recipe(self) -> list[Provider]:
        user_loaders: list[Provider] = [loader(tl.type_, tl.func) for tl in self._type_loaders]
        default_loaders: list[Provider] = [
            loader(bytes, bytes_from_string),
            loader(complex, complex_from_string),
            loader(timedelta, timedelta_from_string),
            loader(URL, url_from_string),
            loader(Base64UrlBytes, base64url_bytes_from_string),
            loader(Base64UrlStr, base64url_str_from_string),
            loader(SecretStr, secret_str_from_string),
            loader(PaymentCardNumber, payment_card_number_from_string),
            loader(ByteSize, byte_size_from_string),
        ]
        return [
            *user_loaders,
            *default_loaders,
            *self._additional_loaders(),
            *self._get_name_mapping_provider(),
        ]

    def create_retort(self) -> Retort:
        return Retort(
            strict_coercion=False,
            recipe=self._base_recipe(),
        )

    def create_probe_retort(self) -> Retort:
        return Retort(
            strict_coercion=False,
            recipe=[*self._base_recipe(), SkipFieldProvider(), ModelToDictProvider()],
        )

    def create_validating_retort(self, dataclass_: type[T]) -> Retort:
        root_validator_providers = create_root_validator_providers(
            dataclass_,
            self._root_validators,
        )
        metadata_validator_providers = create_metadata_validator_providers(
            self._validators,
        )
        return Retort(
            strict_coercion=False,
            recipe=[
                *self._base_recipe(),
                *self._get_validator_providers(dataclass_),
                *metadata_validator_providers,
                *root_validator_providers,
            ],
        )

    @abc.abstractmethod
    def _load(self, path: FileOrStream) -> JSONValue: ...

    def _apply_prefix(self, data: JSONValue) -> JSONValue:
        if not self._prefix:
            return data

        for key in self._prefix.split("."):
            if not isinstance(data, dict):
                return {}
            if key not in data:
                return {}
            data = data[key]

        return data

    def _pre_processing(self, data: JSONValue) -> JSONValue:
        prefixed = self._apply_prefix(data)
        return expand_env_vars(prefixed, mode=self._expand_env_vars_mode)

    def transform_to_dataclass(self, data: JSONValue, dataclass_: type[T]) -> T:
        if dataclass_ not in self.retorts:
            self.retorts[dataclass_] = self.create_retort()
        return self.retorts[dataclass_].load(data, dataclass_)

    def load_raw(self, path: FileOrStream) -> JSONValue:
        data = self._load(path)
        processed = self._pre_processing(data)
        logger.debug(
            "[%s] load_raw: path=%s, raw_keys=%s, after_preprocessing_keys=%s",
            type(self).__name__,
            path,
            sorted(data.keys()) if isinstance(data, dict) else "<non-dict>",
            sorted(processed.keys()) if isinstance(processed, dict) else "<non-dict>",
        )
        return processed
