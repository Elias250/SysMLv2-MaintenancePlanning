---
name: sysml-sdk-python
description: Writes Python code that reads, navigates and queries SysML v2 and KerML models with the SysML v2 SDK (import sysml), through the OpenMBEE SysML Toolkit, the SysML v2 Pilot Implementation, or a full-form interchange JSON payload. Use when a task involves loading .sysml/.kerml files or SysML v2 JSON in Python, walking parts, features, states, connections or requirements, evaluating a model's expressions, or answering questions about a SysML v2 model with code.
---

# SysML v2 SDK for Python

The SDK is the OMG metamodel as Python classes: every KerML and SysML metaclass, property and
operation, under its specification name. A model comes from one of three backends:

- **the SysML Toolkit**, through its native binding library: reads `.sysml`/`.kerml` text, resolves
  names, computes derived properties and evaluates operations, and refuses what it cannot derive
  completely;
- **the SysML v2 Pilot Implementation**, run in Java: reads the text too, and computes every property
  and operation with its own code;
- **a payload**: a full-form interchange JSON export from any SysML v2 tool, read with no native code.

Besides the specification's members, the classes have `find_` convenience members (`find_parts()`,
`find_part_defs()`, `find_value()`, ...) for what takes several steps in the specification.

The SDK never guesses. A member the SysML Toolkit does not answer raises `NotImplementedInToolkit`
with the reason the SysML Toolkit gives; a reference that does not resolve raises
`UnresolvedReference`. Never catch these to substitute a made-up value; read around them as
described below, or report them.

## Setup

```sh
pip install sysml   # the wheel carries the binding library and the standard library models
```

`SYSMLV2_ABI` makes the SDK use another build of the binding library than the wheel's. On a platform
without a wheel, pip installs the source distribution, which reads payloads only.

**Initialize first: get the standard library.** Nearly every model refers to it (`ScalarValues::Real`,
`ISQ::mass`, and implicitly `Parts::parts`, `Items::items`, ...). Do this once, at the start of the
program, before loading any model:

```python
from sysml import standard_library, standard_library_json

library_dir = standard_library()          # the models the wheel carries: library_dir of the SysML Toolkit
library_json = standard_library_json()    # the library as JSON, for a payload's PayloadLibrary
```

`standard_library_json()` downloads the JSON from the SDK's GitHub release on its first call (checked
against the SHA-256 GitHub states, kept in the user cache; later calls read the cache) and raises
`LibraryUnavailable` with instructions when it cannot. Offline, `SYSML_LIBRARY_JSON` names a copy
(the `sysml.library.full.json` of the release's `sysml_library-0.2.0.zip`). Call only the one the
chosen backend needs.

Costs: opening a model with the standard library takes one to three seconds; the library JSON is
about 160 MB and takes a few seconds to read (read it once); the SysML Toolkit's JSON export of a
model takes a few seconds. A model file or library directory that does not exist raises
`FileNotFoundError`; a model that does not load raises `ToolkitError` with a status, and the
SysML Toolkit's reason (a parse error) is printed on stderr.

## Loading a model

Through the SysML Toolkit (pick one of the three calls):

```python
from sysml import Model, NotImplementedInToolkit, UnresolvedReference
from sysml.classes import *      # every metaclass: PartUsage, Definition, FeatureTyping, ...

model = Model.from_toolkit("model.sysml", library_dir=library_dir)     # a file + standard library
model = Model.from_toolkit("a.sysml", "b.sysml", library_dir=library_dir)   # several files
model = Model.from_toolkit(sources={"model.sysml": text}, library_dir=library_dir)  # in-memory text
```

From a payload (a JSON export you have):

```python
import json
from sysml import Model, PayloadLibrary, UnresolvedReference
from sysml.classes import *

library = PayloadLibrary(json.load(open(library_json, encoding="utf-8")))  # once, share it
model = Model.from_full_json(json.load(open("model.json", encoding="utf-8")), library=library)
```

- Load the standard library whenever the model uses it, which nearly every model does
  (`ScalarValues::Real`, `ISQ::mass`, and implicitly `Parts::parts`, `Items::items`, ...). Without it
  such references stay unresolved: harmless until you read one, then `UnresolvedReference`.
- Paths are strings or `pathlib.Path`s; relative ones are relative to the current directory.
  Element ids depend on the file name given; load by file name when ids must be stable. With
  sources given, paths are ignored.
- A payload refers to the standard library's elements without containing them; pass the library
  JSON and those references resolve. Library elements are not the model's (`all()`, `roots`,
  `elements_of_type` skip them); a qualified name is looked up in the payload first. The library
  JSON lists each library element's own members only, not what it inherits.

Through the SysML v2 Pilot Implementation, which runs in this process through JPype when it is
installed (`pip install "sysml[pilot]"`), else in a Java process:

```python
from sysml import BackendError, Model
from sysml.classes import *

model = Model.from_pilot("model.sysml")                     # files; or sources={"model.sysml": text}
```

- It needs a Java 21 or newer runtime (`JAVA_HOME`, or `java` on the path). The first use downloads
  the Pilot (about 130 MB) into the user cache; `SYSML_PILOT_HOME` names a Pilot already at hand.
  Opening takes seconds even for a small model.
- It reads with its own standard library: pass no library.
- It answers rather than refuses: the derived reads the SysML Toolkit refuses (`type`,
  `inheritedFeature`, `connectorEnd`, ...) and the operations it does not evaluate are answered, so
  the workarounds below are not needed. Its answers are the Pilot's own; where they differ from the
  SysML Toolkit's, say which backend produced the result.
- The model it reads is elaborated: it holds the implied relationships and implicit elements too
  (more elements in `all()` than the text declares).
- A failure inside the Pilot, an operation it lacks, or a Pilot that cannot be found or started
  raises `BackendError`.

## The shape of the API

- **Find:** `model.resolve("Pkg::Part::feature")` (a qualified name, or `None`), `model.all()`,
  `model.elements_of_type(PartUsage)` (a class or its name; subclasses included; `exact=True` for
  that metaclass only), `model.roots` (top-level namespaces; the packages are their `ownedMember`).
  `model.resolve` is the SysML Toolkit's own name lookup: it also finds inherited members and
  members of a feature's type (`"EBikes::CargoEBike::wheels"` is `Bike::wheels`,
  `"EBikes::CargoEBike::battery::mass"` is `Battery::mass`), and it answers where the
  specification's `resolve` operation is refused.
- **Properties** are attributes under the specification name: `el.qualifiedName`, `el.ownedFeature`,
  `part.isComposite`. **Operations** are methods: `el.effectiveName()`, `ns.resolve("Name")`. An
  operation sharing a property's name takes a suffix: `instantiatedType_op()`.
- **Metaclass tests** are real subclassing: `isinstance(el, PartUsage)`. `ConnectionUsage`,
  `InterfaceUsage` and `AllocationUsage` are `PartUsage`s too (`FlowUsage` is not); every connector,
  connections, flows, successions and bindings alike, is a `ConnectorAsUsage`. A definition's
  `ownedPart` therefore lists its connections too. `el.metaclass_name` is the concrete metaclass.
- **Every element** has the members of `Element`: `name`, `declaredName`, `qualifiedName`, `owner`,
  `owningNamespace`, `documentation`, `isLibraryElement`, `elementId`, `effectiveName()`.
- **Values:** a multi-valued property is a list (`[]` when absent), a single-valued one is a value or
  `None`. Integers are `int`, reals `float`, enumeration values lowercase strings
  (`'requirement'`, `'in'`). An unnamed element has `name` `None` (a `connect` without a name).
- **Identity:** the elements of one model compare and hash by element id (`el.element_id`), so they
  work in sets and as dict keys. The same element read through two models (the SysML Toolkit's and
  its export's) is two unequal objects: compare their `element_id`s. Runtime members all contain an
  underscore (`element_id`, `metaclass_name`, `get_raw`); specification names never do.
- **Errors:** `NotImplementedInToolkit`, `UnresolvedReference`, `Gone` (from `sysml`, base
  `SdkError`). An operation argument that must be an element and is `None` raises `TypeError`.
- **Operations** need the SysML Toolkit (a payload raises for every one) and take the
  specification's parameters in order; `sysml/classes.pyi` in the wheel has every signature
  (`inheritedMemberships(excludedNamespaces, excludedTypes, excludeImplied)`). The SysML Toolkit has
  a body for about a third of them and answers a call only where its evidence for the model is
  complete. Answered on a typical model: `effectiveName()` (not on every unnamed feature),
  `effectiveShortName()`, `resolveGlobal`, `supertypes(True)` (the argument is `excludeImplied`),
  `evaluate(target)` (target: the element to evaluate in, such as the part usage, never `None`; it
  returns elements, such as the literal a feature is bound to), `modelLevelEvaluable`. Refused
  there: `resolve`, `resolveLocal`, `resolveVisible`, `visibleMemberships`, `namesOf`,
  `inheritedMemberships`, `supertypes(False)`. No body at all: `isCompatibleWith`, `specializes`,
  `allSupertypes`, `directionOf`, ... Catch the refusal.
- `el.get_raw("prop")` is the backend's raw value (unresolved spellings included), for diagnosis.

## Convenience members

Besides the specification's members, the classes have `find_` members (312), each defined by the SDK
over the specification's properties and operations; `sysml/classes.pyi` in the wheel has every
signature with its definition. Use one wherever it answers: one call instead of a walk.

```python
from sysml import NotAnswered, Refused, Scope, VisibilityFilter

d.find_parts()                       # the part usages d owns (a connection is a part too)
d.find_parts_exact()                 # exactly PartUsage; d.find_part("engine"): by name, or None
d.find_parts(Scope.ALL)              # owned, then inherited; Scope.INHERITED: inherited only
d.find_parts_semantic()              # the features typed by a part definition
pkg.find_part_defs()                 # the part definitions a namespace owns; find_part_def(name)
pkg.find_part_defs_by_name()         # {name: definition}, every name and short name
pkg.find_part_defs().find_ports()    # a list carries its elements' members: calls chain
feature.find_declared_types()        # the types as written; t.find_declared_supertypes()
feature.find_redefinition_root()     # the feature its written redefinitions start from
feature.find_value()                 # the value expression (=, :=, default), or None
expr.find_literal()                  # an int, float, bool or str (math.inf for *), a sign folded
t.find_lower_bound(), t.find_upper_bound()   # t's own multiplicity; None without one
```

- The feature kinds (27): `find_attributes`, `find_ports`, `find_items`, `find_actions`,
  `find_states`, `find_connections`, `find_requirements`, `find_constraints`, ... Every list takes
  `scope`, `visibility` (`VisibilityFilter.PUBLIC`, `PROTECTED`; `ANY` by default) and `library`
  (`True` keeps what the standard library's types contribute, left out by default). On a namespace:
  `find_<kind>_defs()`, `find_<kind>_def(name)`, `find_<kind>_defs_by_name()`, and the usages it has
  through any membership, `find_member_<kinds>()`.
- Also: `find_subsetted_features()`, `find_redefined_features()`, `find_referenced_feature()`,
  `find_effective_feature(f)`, `find_unit()` (`1500 [kg]`: `SI::kilogram`), `find_parameters()`,
  `find_inputs()`, `find_outputs()`, `find_initial_states()`, `find_accepted_types()`,
  `find_is_accepted_type(t)`, `find_result_expression()`, `find_path()`, `find_applied_metadata()`,
  `find_doc_text()`.
- `Refused` (a `NotAnswered`): the member's definition gives no answer for this element
  (`find_literal()` of `2 * x`, or of a value with a unit). `NotAnswered`: the backend cannot answer
  something the member reads, named in the message (`NotImplementedInToolkit` from the SysML
  Toolkit).
- **On the Pilot Implementation** every member answers.
- **On the SysML Toolkit**, the members answer: every list, lookup and exact list in the owned scope;
  the definition lists and name maps of a package; the types, supertypes, subsettings and
  redefinitions as written; values, unsigned literals and own bounds; paths, metadata and
  documentation. They are refused, with the reason: the inherited scope and `Scope.ALL` of feature
  and member lists and the semantic lists (`specializes()`), `find_effective_feature`, the implied
  supertypes, `find_parameters`, `find_inputs` and `find_outputs` (`directionOf()`), the accepted
  types (`payloadParameter`), `find_initial_states`, `find_result_expression`, and a literal with a
  sign or a unit (`argument`). For those, use the helpers below: `features_with_inherited`,
  `accepted_types`, `initial_states`, `number`.
- `find_lower_bound()`/`find_upper_bound()` read the type's own multiplicity only; for SysML's
  default and the multiplicity a usage takes from what it redefines, use `multiplicity_of` below.
- Outside the owned scope, a member or definition list is in the backend's order: the specification
  does not define the order of a namespace's memberships.

## When the SysML Toolkit refuses a read (read this before writing queries)

The SysML Toolkit's checked reader answers a property only where it can derive it completely. In
this release it answers most reads (all but 3.6 % on the specification's Annex A model), refuses a
few properties wherever they apply, and refuses some on particular elements, so plan for it:

- **refused wherever they apply (on the Annex A model):** `featuringType`, `parameter`,
  `isModelLevelEvaluable`, `individualDefinition`, `defaultFeaturingType`, `actionDefinition`,
  `stateDefinition`, `calculationDefinition`, `flowDefinition`, `enumerationDefinition`, a metadata
  usage's `metadataDefinition` and `metaclass`, `actorParameter`, `stakeholderParameter`,
  `framedConcern`, `objectiveRequirement`, `step`, `expression`, `calculation`, `interaction`,
  `flowEnd`, `sourceOutputFeature` and `targetInputFeature`;
- **refused on some elements:** `type`, `definition` and `behavior` on action, perform action,
  state, exhibit state, transition, flow, accept, send, allocation and use case usages and on
  enumeration values, and `type` on some parameters and reference usages (use `types_of` below
  there); the inherited and imported member lists (`feature`, `inheritedFeature`,
  `featureMembership`, `inheritedMembership`, `member`, `membership`, `importedMembership`, `input`,
  `output` and `endFeature`) on a definition with a `public import` in its body, or one that
  specializes it; on expressions (operator, invocation, feature reference and feature chain
  expressions, literals) their owned lists (`ownedMember`, `ownedFeature`, `ownedMembership` and
  `ownedElement`), `directedFeature` and a literal's `result`; `result` on some requirement,
  constraint and case usages and on calculation, requirement and case definitions;
  `isImpliedIncluded`; an end feature's `isConstant`; a connector's `association`; `argument` on a
  type test (`istype`, `@`);
- **answered:** everything else, among it the inherited and imported member lists and `type` on most
  elements, a connector's ends (`sourceFeature`, `targetFeature`, `connectorEnd` and
  `relatedFeature`), `payloadParameter`, `payloadType`, `subjectParameter`, `requirementDefinition`
  and `satisfyingFeature`, and what the model states itself: `ownedMember`, `ownedFeature`,
  `ownedMembership`, the owned lists (`ownedUsage`, `ownedPart`, `nestedUsage`, `nestedPart`,
  `nestedAttribute`, `nestedState`, `nestedTransition`, ...; owned members only, so an empty
  `nestedPart` does not mean a usage has no parts), `owner`, `owningNamespace`, `owningType`,
  `name`, `declaredName`, `qualifiedName`, `documentation`, `multiplicity`, `direction`,
  `isComposite`, `isEnd`, `isImplied`, `entryAction`, `isParallel`, `triggerAction`, a transition's
  `source` and `target`, `satisfiedRequirement`, `chainingFeature`, and the specific owned
  relationships with their ends: `ownedTyping` (`type`), `ownedSubclassification`
  (`superclassifier`), `ownedSpecialization` (`general`), `ownedSubsetting` (`subsettedFeature`; it
  holds the redefinitions too), `ownedRedefinition` (`redefinedFeature`), `ownedReferenceSubsetting`
  (`referencedFeature`), and a port definition's `conjugatedPortDefinition` /
  `originalPortDefinition`.

The refusal's message names the member and the SysML Toolkit's reason (`property has an incomplete
derivation`, `Type features are incomplete: IncompleteProvider`, `incomplete operation evidence`):
the SysML Toolkit lacks complete evidence for that element, which says nothing about whether the
model is right. Whether a read is refused depends on the property and the element; try one element
first (`try: el.type; except NotImplementedInToolkit as e: print(e)`) rather than assume. Where it
is refused, in this order:

**1. Read what the model states.** The helpers below derive what the common refused properties
give, from the owned relationships (verified through the SysML Toolkit and through the export alike;
copy them as they are). `isImplied` marks the relationships the SysML Toolkit adds from the library,
which the model does not write.

```python
def types_of(feature):
    """A feature's types: `type` where the SysML Toolkit answers it; else its own typings; else
    those of the features it redefines or subsets as the model writes them
    (`part :>> battery[2];`)."""
    try:
        return list(feature.type)
    except NotImplementedInToolkit:
        pass
    own = [t.type for t in feature.ownedTyping]
    if own:
        return own
    for general in written_generals(feature):
        if found := types_of(general):
            return found
    return []


def written_generals(feature):
    """The features a feature redefines or subsets as the model writes them (ownedSubsetting holds
    the redefinitions too; `isImplied` marks what the SysML Toolkit adds from the library)."""
    return [s.subsettedFeature for s in feature.ownedSubsetting if not s.isImplied]


def written_supertypes(definition):
    """A definition's supertypes as the model writes them, without the library ones the
    SysML Toolkit implies (Parts::Part for a part definition)."""
    return [s.superclassifier for s in definition.ownedSubclassification if not s.isImplied]


def features_with_inherited(t, _seen=None):
    """t's own features, then those it inherits along what the model writes (a definition's
    supertypes; a usage's types and the usages it redefines or subsets), without the ones redefined
    on the way. The model's own features, not the library's; not the specification's full
    derivation (no visibility, no imports)."""
    _seen = set() if _seen is None else _seen
    if t in _seen:
        return []
    _seen.add(t)
    own = list(t.ownedFeature)
    redefined = {r.redefinedFeature for f in own for r in f.ownedRedefinition}
    bases = written_supertypes(t) if isinstance(t, Classifier) else types_of(t) + written_generals(t)
    for base in bases:
        for f in features_with_inherited(base, _seen):
            if f not in redefined and f not in own:
                own.append(f)
    return own


def feature_in(context, feature):
    """The feature that stands for `feature` in `context`: `feature` itself where the context
    inherits it, or the nearest one that redefines it, directly or through other redefinitions;
    None where the context has neither (pass the declaration, `Component::mass`, not a
    redefinition in some other definition)."""
    def redefines(f, target, seen):
        for r in f.ownedRedefinition:
            g = r.redefinedFeature
            if g == target or (g not in seen and redefines(g, target, seen | {g})):
                return True
        return False
    for f in features_with_inherited(context):
        if f == feature or redefines(f, feature, {f}):
            return f
    return None


def bound_value(context, feature):
    """The expression that gives `feature` its value in `context` (`attribute :>> mass = 2.5;` in
    the context's definition or body), or None. Initial values (`:=`) and defaults (`default =`)
    count too; the FeatureValue's `isInitial` / `isDefault` tell them apart."""
    f = feature_in(context, feature)
    if f is None:
        return None
    return next((m.value for m in f.ownedMembership if isinstance(m, FeatureValue)), None)


def declaration_of(feature):
    """The feature a chain of written redefinitions starts from (`Frame::mass` -> `Unit::mass`): the
    declaration to pass to bound_value and feature_in."""
    seen = {feature}
    while True:
        written = [r.redefinedFeature for r in feature.ownedRedefinition if not r.isImplied]
        if not written or written[0] in seen:
            return feature
        feature = written[0]
        seen.add(feature)


def bounds(multiplicity):
    """(lower, upper) of a MultiplicityRange with literal bounds; upper None for `*`. `[4]` has only
    an upper bound: lower = upper then. A bound that is an expression (`[rotorCount]`) raises."""
    def value(e):
        if isinstance(e, LiteralInfinity):
            return None
        if isinstance(e, LiteralInteger):
            return e.value
        raise ValueError(f"a bound to evaluate in context: {e.metaclass_name}")
    upper = value(multiplicity.upperBound)
    return (upper if multiplicity.lowerBound is None else value(multiplicity.lowerBound)), upper


def multiplicity_of(usage):
    """(lower, upper) of the multiplicity that applies to a usage: its own; else, nearest first,
    that of the features it redefines or subsets as written; else (1, 1) where SysML gives the
    default (an attribute, item, part or port usage, not a connection, owned by a definition or
    usage); else (0, None), unconstrained."""
    seen, todo = {usage}, [usage]
    while todo:
        u = todo.pop(0)
        # A multiplicity without bounds is the default member SysML implies (`Base::exactlyOne`):
        # the rule below gives it.
        if isinstance(u.multiplicity, MultiplicityRange):
            return bounds(u.multiplicity)
        generals = written_generals(u)
        if not generals:
            # a PartUsage is an ItemUsage
            default = (isinstance(u, (AttributeUsage, ItemUsage, PortUsage)) and not isinstance(u, ConnectionUsage)
                       and isinstance(u.owningType, (Definition, Usage)))
            return (1, 1) if default else (0, None)
        for g in generals:
            if g not in seen:
                seen.add(g)
                todo.append(g)
    return (0, None)


def ends(connector):
    """A connector's ends in order, the source first: the features or feature chains it connects.
    For connections, flows, successions and bindings alike."""
    try:
        return [connector.sourceFeature, *connector.targetFeature]
    except NotImplementedInToolkit:
        return [e.ownedReferenceSubsetting.referencedFeature
                for e in connector.ownedFeature if e.isEnd and e.ownedReferenceSubsetting]


def path(feature):
    """A feature chain as its features ([battery, powerOut] for battery.powerOut); else [feature]."""
    return list(feature.chainingFeature) or [feature]


def accepted_types(accept):
    """What an accept action accepts (a transition's triggerAction[0]): its payload's types."""
    try:
        return list(accept.payloadParameter.type)
    except NotImplementedInToolkit:
        payload = next(m.ownedMemberParameter for m in accept.ownedMembership if isinstance(m, ParameterMembership))
        return types_of(payload)


def satisfying_feature(satisfy):
    """What satisfies the requirement in `satisfy r by x;`: x."""
    try:
        return satisfy.satisfyingFeature
    except NotImplementedInToolkit:
        subject = next(m.ownedSubjectParameter for m in satisfy.ownedMembership if isinstance(m, SubjectMembership))
        value = next(m.value for m in subject.ownedMembership if isinstance(m, FeatureValue))
        return value.referent                               # a FeatureReferenceExpression


def subject_of(requirement):
    """The subject parameter of a requirement or requirement definition: its own `subject`; else,
    nearest first, that of its definitions or of what it specializes as written; else None."""
    try:
        return requirement.subjectParameter
    except NotImplementedInToolkit:
        pass
    own = next((m.ownedSubjectParameter for m in requirement.ownedMembership if isinstance(m, SubjectMembership)), None)
    if own is not None:
        return own
    bases = (written_supertypes(requirement) if isinstance(requirement, Classifier)
             else types_of(requirement) + written_generals(requirement))
    for base in bases:
        if (found := subject_of(base)) is not None:
            return found
    return None


def initial_states(machine):
    """The states a state machine (a state usage or definition) starts in, as find_initial_states
    defines them: the targets of its successions from the library's `start` (`first start then
    off;`), and only where there are none, from its entry action (`entry; then off;`)."""
    entry, from_start, from_entry = machine.entryAction, [], []
    for f in machine.ownedFeature:
        if isinstance(f, SuccessionAsUsage):
            e = ends(f)
            if len(e) == 2 and isinstance(e[1], StateUsage):
                if e[0].isLibraryElement and e[0].name == "start":
                    from_start.append(e[1])
                elif entry is not None and e[0] == entry:
                    from_entry.append(e[1])
    return from_start or from_entry


def reachable_states(machine):
    """The states of a state machine reachable from its initial states along its own transitions,
    in the order found (guards and triggers not considered; the transitions inside composite states
    not followed)."""
    next_of = {}
    for t in machine.ownedFeature:
        if isinstance(t, TransitionUsage):
            next_of.setdefault(t.source, []).append(t.target)
    reached = initial_states(machine)
    i = 0
    while i < len(reached):
        for n in next_of.get(reached[i], []):
            if isinstance(n, StateUsage) and n not in reached:
                reached.append(n)
        i += 1
    return reached


def number(expr):
    """The number an expression stands for when it is a literal, or a sign applied to one (`-40.0`
    is an OperatorExpression `-` whose operand is the literal 40.0). Anything else raises: evaluate
    it in context (the SysML Toolkit's `evaluate` refuses operator expressions)."""
    if isinstance(expr, (LiteralInteger, LiteralRational)):
        return expr.value
    if isinstance(expr, OperatorExpression) and expr.operator in ("-", "+"):
        # The operands' parameters through the owned relationships: the SysML Toolkit refuses an
        # operator expression's ownedFeature in this release.
        params = [p for r in expr.ownedRelationship if isinstance(r, ParameterMembership) for p in r.ownedRelatedElement]
        operands = [m.value for f in params for m in f.ownedMembership if isinstance(m, FeatureValue)]
        if len(operands) == 1:
            return -number(operands[0]) if expr.operator == "-" else number(operands[0])
    raise ValueError(f"not a literal number: {expr.metaclass_name}")
```

**2. Query the SysML Toolkit's export as a payload** when a question needs the specification's full
derivation across a whole model (inherited members with visibility and imports, connector ends of
library connections). The export is written by the SysML Toolkit's compatibility path: it carries a
value for every property, including the ones the checked reader refuses, which the SysML Toolkit
does not vouch for. Say so in your answer when the result depends on them.

```python
import json
from sysml import Model, PayloadLibrary, standard_library, standard_library_json
from sysml.toolkit import ToolkitBackend

backend = ToolkitBackend.open(["model.sysml"], library_dir=standard_library())   # paths: str or Path
library = PayloadLibrary(json.load(open(standard_library_json(), encoding="utf-8")))  # once
payload = Model.from_full_json(json.loads(backend.full_json()), library=library)   # same element ids
toolkit = Model(backend)         # the same session, for operations and checked reads
```

**3. Never** substitute an empty list, a guess or a default for a refused read.

## Navigation recipes

With the helpers above; each works through the SysML Toolkit and on a payload.

```python
# d, part, port, usage, flow, machine and constraint stand for elements you have at hand (d: a
# definition or usage); model is the Model.

# Parts of a definition or usage, owned and inherited, not connections; the model's own, not the
# library's (start, done, subparts, ...)
parts = [f for f in features_with_inherited(d) if isinstance(f, PartUsage) and not isinstance(f, ConnectionUsage)]

# What a usage is typed by (its definitions)
types_of(part)                               # [PartDefinition, ...]

# The value a feature has in a context (`attribute :>> mass = 2.5;` in the part's definition or body)
mass = model.resolve("Pkg::Component::mass")   # the declaration; declaration_of(f) finds it from a redefinition
expr = bound_value(part, mass)               # an Expression, or None
number(expr)                                 # its number: a literal, or a sign applied to one (-40.0)

# How many instances a usage stands for, when its bounds are literals
lower, upper = multiplicity_of(usage)        # (2, 2) for [2]; (1, 1) by default; upper None for *
text = f"[{lower}]" if lower == upper else f"[{lower}..{'*' if upper is None else upper}]"

# Roll-up: an attribute summed over a definition's direct parts (mass, cost, power); for a deeper
# tree, apply it to each part that has parts of its own (features_with_inherited(p))
total, missing = 0.0, []
for p in parts:
    expr, (lower, upper) = bound_value(p, mass), multiplicity_of(p)
    if expr is None or lower != upper:         # no value, or a range ([4..6], *): report, never guess
        missing.append(p.name)
    else:
        total += number(expr) * lower

# Ports: the definition, and whether it is conjugated (`port p : ~PowerPort;`). `portDefinition`
# (a list) is refused; `port.isConjugated` is False on a `~` port: the conjugation is its type, the
# ConjugatedPortDefinition that PowerPort owns (name `~PowerPort`, qualified name
# `Pkg::PowerPort::'~PowerPort'`, quotes included)
for t in types_of(port):
    print(("~" + t.originalPortDefinition.qualifiedName) if isinstance(t, ConjugatedPortDefinition)
          else t.qualifiedName)

# Connections (ConnectionUsage: connect, interfaces, allocations): the ends, the source first. The
# ends of an inherited connection are the supertype's features (Drone::rotors, not a redefining
# `part :>> rotors[8];`): feature_in(d, path(end)[0]) is the one that stands for it in d
for c in features_with_inherited(d):
    if isinstance(c, ConnectionUsage):
        print(" -> ".join(".".join(f.name for f in path(end)) for end in ends(c)))   # battery.powerOut -> ...
        port_types = [types_of(path(end)[-1]) for end in ends(c)]   # per end: [PortDefinition or ConjugatedPortDefinition]
# Flows (FlowUsage), bindings (BindingConnectorAsUsage) and successions are ConnectorAsUsage too,
# with the same ends()
flow.payloadType                             # [the flowing item's definition]

# States
machine = model.resolve("Pkg::Controller::modes")   # an ExhibitStateUsage or StateUsage
states = machine.nestedState                 # its own states
machine.isParallel, machine.entryAction
initial = initial_states(machine)            # `first start then off;`, else `entry; then off;`
reachable = reachable_states(machine)        # from the initial states along the transitions
for t in machine.nestedTransition:           # t.source, t.target: the states it leaves and enters;
    # a transition from the entry action leaves an action, not a state
    signals = accepted_types(t.triggerAction[0]) if t.triggerAction else []   # [ItemDefinition, ...]
    t.guardExpression                        # [Expression]
    if t.triggerAction:
        t.triggerAction[0].payloadArgument   # TriggerInvocationExpression for `accept at`/`when` (.kind)

# Requirements
for s in model.elements_of_type(SatisfyRequirementUsage):
    req = s.satisfiedRequirement             # the requirement usage
    by = satisfying_feature(s)               # the part that satisfies it
    definition = types_of(req)               # [RequirementDefinition]
    subject = subject_of(req)                # its subject parameter, or None; often the definition's
                                             # (`subject bike : Bike;` in MassLimit: MassLimit::bike)
    limit_f = next(f for t in types_of(req) for f in features_with_inherited(t) if f.name == "maxMass")
    limit = bound_value(req, limit_f)        # the requirement's value for its definition's maxMass
    s.isNegated
    constraints = [m.ownedConstraint for m in req.ownedMembership        # its own constraints
                   if isinstance(m, RequirementConstraintMembership) and m.kind == "requirement"]
res = next(m for m in constraint.ownedMembership if isinstance(m, ResultExpressionMembership))
res.ownedResultExpression                    # a constraint's expression
```

## Multiplicity

`multiplicity` is only what the usage itself declares; `multiplicity_of` above applies SysML's rule:
a usage without one takes the multiplicity of the features it redefines or subsets as written
(nearest first; `part :>> battery[2];` declares its own), and one that redefines or subsets nothing
is `[1..1]` if it is an attribute, item, part or port usage owned by a definition or usage, and
unconstrained (`[0..*]`) otherwise. Implied subsettings (`s.isImplied`, such as every part's
subsetting of the library's `parts`) do not count. A bound may be an expression to evaluate in
context (`Rotor[rotorCount]`); `bounds` raises for it.

## Evaluating the model's expressions

Expressions are elements: `OperatorExpression` (`operator` such as `'<='`, `'and'`, `'not'`;
`argument`), `FeatureReferenceExpression` (`referent`), `FeatureChainExpression` (`a.b`:
`argument[0]` is `a`, `targetFeature` is `b`; it is a subclass of OperatorExpression, so test it
first), literals with `.value` (`LiteralInteger`, `LiteralRational`, `LiteralBoolean`,
`LiteralString`, `LiteralInfinity` for `*`), `TriggerInvocationExpression` (`kind`: `at`, `after`,
`when`). An enumeration literal (`IgnitionOnOff::on`) is an `EnumerationUsage` whose
`owningNamespace` is the `EnumerationDefinition`; its `owningType` is `None`, by the specification.
Through the SysML Toolkit, `argument` is refused: an expression's operands are its `ownedFeature`s,
each bound by a `FeatureValue` in its `ownedMembership`.

The SysML Toolkit's `evaluate(target)` operation evaluates some expressions (it returns elements);
beyond that, the SDK does not evaluate. The SDK's source repository
(https://github.com/Open-MBEE/sysml-sdk, not the release packages) has, in
`examples/queries/python/queries.py`, a small evaluator in three-valued logic and complete queries
built on it: reachable states with shortest trigger sequences, bill of materials, attribute roll-up,
connectivity, requirement checks. Where it is at hand, start from it for such questions; the recipes
above cover the simple cases.

## Other differences from the specification

- **With the library loaded**, `usage`/`feature` (in a payload) include library features (`self`,
  `start`, `subparts`, ...): filter with `isLibraryElement`. A flow's `connectorEnd` also lists the
  library flow's ends; use `ends`.
- The second operand of `and`/`or`/`implies` is the operand expression itself; the specification
  makes it a `FeatureReferenceExpression` to it. Accept both.
- An unnamed `satisfy` has no `name`, but a qualified-name lookup may still find it under the name
  of the requirement it satisfies. A feature named only through what it redefines has `name` from it
  and `declaredName` `None` (a satisfy's subject parameter is named `subj`, although it redefines
  the subject of the requirement's definition). Use `name` to display, `declaredName` to know what
  was written.
- `mayTimeVary`, `isVariable` and `isConstant` on usages raise `NotImplementedInToolkit`.
- In the SysML Toolkit's export, an alias (`alias ax for x;`) hides the membership of the feature it
  names from what specializations inherit, and a conjugated port's `portDefinition` is the
  `ConjugatedPortDefinition` (`~PowerPort`), as the specification says.
- A payload answers what its writer wrote: stand-ins where the writer had no value (null, `false`,
  `[]`), and `UnresolvedReference` for references into the standard
  library unless it was given the library JSON.

## Verify

- Run the same query through the SysML Toolkit (with the helpers) and on its export as a payload
  (the plain derived properties), matching elements by `element_id`; differences point at the
  SysML Toolkit, the export, or your code.
- Work out a few answers by hand from the model and assert them.
- For more examples: the Python guide and runnable tutorial (`examples/python/`) and the query
  examples (`examples/queries/python/`) in the SDK repository.
