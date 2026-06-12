from dature.type_aliases import FieldRef
from dature.validators.predicate import Predicate

type FieldValidators = dict[FieldRef, Predicate | tuple[Predicate, ...]]
