from dature.types import FieldRef
from dature.validators.predicate import Predicate

type FieldValidators = dict[FieldRef, Predicate | tuple[Predicate, ...]]
