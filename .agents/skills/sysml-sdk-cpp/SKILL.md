---
name: sysml-sdk-cpp
description: Writes C++17 code that reads, navigates and queries SysML v2 and KerML models with the header-only sysml SDK (namespace sysml, <sysml/classes.g.hpp>), through the OpenMBEE SysML Toolkit (a native binding library loaded at run time), the SysML v2 Pilot Implementation, or a full-form interchange JSON payload. Use when a task involves loading .sysml/.kerml files or SysML v2 JSON in C++, walking parts, features, states, connections or requirements, evaluating a model's expressions, or answering questions about a SysML v2 model with code.
---

# SysML v2 SDK for C++

The SDK is the OMG metamodel as C++ structs: every KerML and SysML metaclass, property and
operation, under its specification name, with the metaclass hierarchy as virtual inheritance over
one runtime `Element`. Header-only, C++17, JSON through the bundled nlohmann/json. A model comes from
one of three backends:

- **the SysML Toolkit**, through its native binding library, loaded at run time: reads SysML text,
  resolves names, computes derived properties and evaluates operations, and refuses what it cannot
  derive completely;
- **the SysML v2 Pilot Implementation**, run in a Java process (or in this process through JNI):
  reads the text too, and computes every property and operation with its own code;
- **a payload**: a full-form interchange JSON export from any SysML v2 tool.

Besides the specification's members, the structs have `find_` convenience members (`find_parts()`,
`find_part_defs()`, `find_value()`, ...) for what takes several steps in the specification.

The SDK never guesses. A member the SysML Toolkit does not answer throws
`not_implemented_in_toolkit` with the reason the SysML Toolkit gives; a reference that does not
resolve throws `unresolved_reference`. Never catch these to substitute a made-up value; read
around them as described below, or report them.

## Setup

```sh
g++ -std=c++17 -I sysml-sdk-cpp-0.2.0/include main.cpp -o main   # add -ldl on Linux, -static with MinGW
```

- The package `sysml-sdk-cpp-0.2.0.zip` has `include/` with `sysml/` and `nlohmann/`.
- For the SysML Toolkit, the archive's `lib/<target>/` holds the binding library for Windows x64,
  Linux x64, and macOS on Apple silicon and on Intel: copy the one for your platform beside your
  executable, where `ToolkitBackend::open` finds it. To load it from elsewhere, set `SYSMLV2_ABI` to
  it, or name it in code: pass `std::make_shared<ToolkitBackend::Library>(path)` as the last
  argument of `ToolkitBackend::open`.
- The archive's `sysml.library/` holds the standard library models: copy that directory beside your
  executable too, or name it in `SYSML_LIBRARY_DIR`.

**Initialize first: get the standard library.** Nearly every model refers to it (`ScalarValues::Real`,
`ISQ::mass`, and implicitly `Parts::parts`, `Items::items`, ...). Do this once, at the start of the
program, before loading any model:

```cpp
#include <sysml/library.hpp>

std::string library_dir = sysml::standard_library();         // sysml.library beside the executable, or SYSML_LIBRARY_DIR
std::string library_json = sysml::standard_library_json();   // the library as JSON, for a payload's PayloadLibrary
```

C++ downloads nothing: `standard_library_json()` is the file `SYSML_LIBRARY_JSON` names, else the
copy in the user cache that the other SDK languages download; otherwise it throws
`library_unavailable` with instructions (download the release's `sysml_library-0.2.0.zip` and set
`SYSML_LIBRARY_JSON` to its `sysml.library.full.json`). Call only the one the chosen backend needs.

Costs: `classes.g.hpp` is about 4 MB, so a translation unit that includes it takes tens of seconds
to compile: keep the SDK in one translation unit (or a precompiled header). Opening a model with the
standard library takes one to three seconds; the SysML Toolkit's JSON export of a model takes a few
seconds; parsing the 160 MB library JSON takes tens of seconds (parse it once). A model that does
not load, or a model file or library directory that does not exist, throws `sdk_error` with a
status; the SysML Toolkit's reason (the missing path, a parse error) is printed on stderr.

## Loading a model

`<sysml/classes.g.hpp>` includes the runtime (`<sysml/sdk.hpp>`, which alone has no
metaclasses): include it, `<sysml/library.hpp>` for the standard library helpers, and
`<sysml/toolkit.hpp>` for the SysML Toolkit.

Through the SysML Toolkit:

```cpp
#include <sysml/classes.g.hpp>   // the runtime and every metaclass (always include it)
#include <sysml/library.hpp>     // the standard library helpers
#include <sysml/toolkit.hpp>     // the SysML Toolkit backend
using namespace sysml;

int main() {
    Model model = Model::from_backend(ToolkitBackend::open(
        {"model.sysml"},           // your files
        {},                        // or in-memory sources: {{"m.sysml", text}}
        standard_library()));      // the standard library, from the initialization
    // ... your code here ...
}
```

From a payload (a JSON export you have):

```cpp
#include <fstream>
#include <sstream>
#include <sysml/classes.g.hpp>
#include <sysml/library.hpp>
using namespace sysml;

static std::string read_file(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    std::stringstream text;
    text << in.rdbuf();
    return text.str();
}

int main() {
    auto library = PayloadLibrary::parse(read_file(standard_library_json()));   // once; a shared_ptr to share
    Model model = Model::from_full_json(read_file("model.json"), library);
    // ... your code here ...
}
```

Load the standard library whenever the model uses it, which nearly every model does
(`ScalarValues::Real`, `ISQ::mass`, and implicitly `Parts::parts`). Without it, references into the
library stay unresolved: harmless until you read one, then `unresolved_reference`.
(`ToolkitBackend::open({"a.sysml"})` and `ToolkitBackend::open_sources({{"m.sysml", text}})` open
without it.) Relative paths are relative to the working directory. Element ids depend on the file
names given. With sources given, paths are ignored. Elements keep their model alive; copy them
freely. The SDK takes JSON as text, not paths.

A payload refers to the standard library's elements without containing them; pass the library JSON
and those references resolve. Library elements are not the model's (`all()`, `roots()`,
`elements_of_type<T>()` skip them); a qualified name is looked up in the payload first. The library
JSON lists each library element's own members only, not what it inherits.

Through the SysML v2 Pilot Implementation, which runs in a Java process, or in this process through
JNI when compiled with `SYSML_PILOT_JNI` and the JDK's include directories:

```cpp
#include <sysml/pilot.hpp>   // and copy sysml-pilot-server.jar beside the program

Model model = Model::from_backend(PilotBackend::open({"model.sysml"}));   // or PilotBackend::open_sources({...})
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
  raises `backend_error`.

## The shape of the API

- **Find:** `model.resolve("Pkg::Part::feature")` returns `std::optional<Element>`; convert with
  `.value().as<PartDefinition>()`. `model.elements_of_type<PartUsage>()` (subclasses included),
  `model.all()`, `model.roots()` (top-level namespaces; the packages are their
  `getOwnedMember()`). `model.resolve` is the SysML Toolkit's own name lookup: it also finds
  inherited members and members of a feature's type (`"EBikes::CargoEBike::wheels"` is
  `Bike::wheels`), and it answers where the specification's `resolve` operation is refused.
- **Properties** are getters, `get` + the specification name: `getQualifiedName()`,
  `getOwnedFeature()`, `getIsComposite()`. **Operations** keep their names: `effectiveName()`,
  `resolve("Name")` on a `Namespace`.
- **Results:** a multi-valued property is `std::vector<T>` (empty when absent); a single-valued one
  `std::optional<T>`: `std::optional<std::string>`, `std::optional<bool>`,
  `std::optional<std::int64_t>` for Integer, `std::optional<double>` for Real, enumeration values as
  lowercase strings (`"requirement"`). `getSourceFeature()` is one optional feature,
  `getTargetFeature()` a vector. An unnamed element's `getName()` is `std::nullopt` (`entry;`, a
  `connect` without a name). An operation without a declared type returns `Value`.
- **Metaclass tests:** `el.is_a<PartUsage>()`; convert with `el.as<PartUsage>()`, which throws
  `wrong_kind` if it is not one. Never `static_cast` or `dynamic_cast` between the structs.
  `ConnectionUsage`, `InterfaceUsage` and `AllocationUsage` are `PartUsage`s too (`FlowUsage` is
  not); every connector, connections, flows, successions and bindings alike, is a
  `ConnectorAsUsage`. A definition's `getOwnedPart()` therefore lists its connections too.
  `el.metaclass_name()` is the concrete metaclass.
- **Every element** has the members of `Element`: `getName()`, `getDeclaredName()`,
  `getQualifiedName()`, `getOwner()`, `getOwningNamespace()`, `getDocumentation()`,
  `getIsLibraryElement()`, `effectiveName()`.
- **Identity:** within one model, `==` compares element ids, and `std::hash<Element>` hashes them,
  so `std::unordered_set<Element>` works (store `Element`, convert with `as<T>()` when reading). The
  same element read through two models (the SysML Toolkit's and its export's) is not `==`: compare
  their `element_id()`s.
  Runtime members are snake_case with an underscore: `element_id()`, `backend_handle()`,
  `metaclass_name()`, `get_raw(prop)`, `is_a`, `as`.
- **Errors** (all `sdk_error`, a `std::runtime_error`): `not_implemented_in_toolkit`,
  `unresolved_reference`, `gone`, `wrong_kind`. An operation argument that must be an element and is
  empty throws `std::invalid_argument`.
- **Operations** need the SysML Toolkit (a payload throws for every one) and take the
  specification's parameters in order, as `classes.g.hpp` declares them
  (`inheritedMemberships(excludedNamespaces, excludedTypes, excludeImplied)`). The SysML Toolkit has
  a body for about a third of them and answers a call only where its evidence for the model is
  complete. Answered on a typical model: `effectiveName()` (not on every unnamed feature),
  `effectiveShortName()`, `resolveGlobal`, `supertypes(true)` (the argument is `excludeImplied`),
  `evaluate(target)` (target: the element to evaluate in, such as the part usage; it returns
  elements, such as the literal a feature is bound to), `modelLevelEvaluable`. Refused there:
  `resolve`, `resolveLocal`, `resolveVisible`, `visibleMemberships`, `namesOf`,
  `inheritedMemberships`, `supertypes(false)`. No body at all: `isCompatibleWith`, `specializes`,
  `allSupertypes`, `directionOf`, ... Catch the refusal.

## Convenience members

Besides the specification's members, the structs have `find_` members (312), each defined by the SDK
over the specification's properties and operations; every one has its definition in its Doxygen
comment in `classes.g.hpp`. Use one wherever it answers: one call instead of a walk.

```cpp
d.find_parts();                      // ElementList<PartUsage>: the part usages d owns (connections too)
d.find_parts_exact();                // exactly PartUsage; d.find_part("engine"): std::optional
d.find_parts(Scope::All);            // owned, then inherited; Scope::Inherited: inherited only
d.find_parts_semantic();             // the features typed by a part definition
pkg.find_part_defs();                // the part definitions a namespace owns; find_part_def(name)
pkg.find_part_defs_by_name();        // NameMap<PartDefinition>: pairs of a name and a definition, find(name)
pkg.find_part_defs().find_ports();   // an ElementList carries its elements' members: calls chain
feature.find_declared_types();       // the types as written; t.find_declared_supertypes()
feature.find_redefinition_root();    // the feature its written redefinitions start from
feature.find_value();                // std::optional<Expression>: the value expression (=, :=, default)
expr.find_literal();                 // a Literal: std::variant<std::int64_t, double, bool,
                                     //   std::string, Unbounded>; read it with std::get or std::visit
t.find_lower_bound(); t.find_upper_bound();   // std::optional<Literal>: t's own multiplicity
```

- The feature kinds (27): `find_attributes`, `find_ports`, `find_items`, `find_actions`,
  `find_states`, `find_connections`, `find_requirements`, `find_constraints`, ... Every list takes
  `scope`, `visibility` (`VisibilityFilter::Public`, `Protected`; `Any` by default) and `library`
  (`true` keeps what the standard library's types contribute, left out by default). On a namespace:
  `find_<kind>_defs()`, `find_<kind>_def(name)`, `find_<kind>_defs_by_name()`, and the usages it has
  through any membership, `find_member_<kinds>()`.
- Also: `find_subsetted_features()`, `find_redefined_features()`, `find_referenced_feature()`,
  `find_effective_feature(f)`, `find_unit()` (`1500 [kg]`: `SI::kilogram`), `find_parameters()`,
  `find_inputs()`, `find_outputs()`, `find_initial_states()`, `find_accepted_types()`,
  `find_is_accepted_type(t)`, `find_result_expression()`, `find_path()`, `find_applied_metadata()`,
  `find_doc_text()`.
- `refused` (a `not_answered`): the member's definition gives no answer for this element
  (`find_literal()` of `2 * x`, or of a value with a unit). `not_answered`: the backend cannot answer
  something the member reads, named in `what()` (`not_implemented_in_toolkit` from the SysML
  Toolkit).
- **On the Pilot Implementation** every member answers.
- **On the SysML Toolkit**, the members answer: every list, lookup and exact list in the owned scope;
  the definition lists and name maps of a package; the types, supertypes, subsettings and
  redefinitions as written; values, unsigned literals and own bounds; paths, metadata and
  documentation. They are refused, with the reason: the inherited scope and `Scope::All` of feature
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

- **refused wherever they apply (on the Annex A model):** `getFeaturingType()`, `getParameter()`,
  `getIsModelLevelEvaluable()`, `getIndividualDefinition()`, `getDefaultFeaturingType()`,
  `getActionDefinition()`, `getStateDefinition()`, `getCalculationDefinition()`,
  `getFlowDefinition()`, `getEnumerationDefinition()`, a metadata usage's `getMetadataDefinition()`
  and `getMetaclass()`, `getActorParameter()`, `getStakeholderParameter()`, `getFramedConcern()`,
  `getObjectiveRequirement()`, `getStep()`, `getExpression()`, `getCalculation()`,
  `getInteraction()`, `getFlowEnd()`, `getSourceOutputFeature()` and `getTargetInputFeature()`;
- **refused on some elements:** `getType()`, `getDefinition()` and `getBehavior()` on action,
  perform action, state, exhibit state, transition, flow, accept, send, allocation and use case
  usages and on enumeration values, and `getType()` on some parameters and reference usages (use
  `types_of` below there); the inherited and imported member lists (`getFeature()`,
  `getInheritedFeature()`, `getFeatureMembership()`, `getInheritedMembership()`, `getMember()`,
  `getMembership()`, `getImportedMembership()`, `getInput()`, `getOutput()` and `getEndFeature()`)
  on a definition with a `public import` in its body, or one that specializes it; on expressions
  (operator, invocation, feature reference and feature chain expressions, literals) their owned
  lists (`getOwnedMember()`, `getOwnedFeature()`, `getOwnedMembership()` and `getOwnedElement()`),
  `getDirectedFeature()` and a literal's `getResult()`; `getResult()` on some requirement,
  constraint and case usages and on calculation, requirement and case definitions;
  `getIsImpliedIncluded()`; an end feature's `getIsConstant()`; a connector's `getAssociation()`;
  `getArgument()` on a type test (`istype`, `@`);
- **answered:** everything else, among it the inherited and imported member lists and `getType()` on
  most elements, a connector's ends (`getSourceFeature()`, `getTargetFeature()`, `getConnectorEnd()`
  and `getRelatedFeature()`), `getPayloadParameter()`, `getPayloadType()`, `getSubjectParameter()`,
  `getRequirementDefinition()` and `getSatisfyingFeature()`, and what the model states itself:
  `getOwnedMember()`, `getOwnedFeature()`, `getOwnedMembership()`, the owned lists
  (`getOwnedUsage()`, `getOwnedPart()`, `getNestedUsage()`, `getNestedPart()`,
  `getNestedAttribute()`, `getNestedState()`, `getNestedTransition()`, ...; owned members only, so
  an empty `getNestedPart()` does not mean a usage has no parts), `getOwner()`,
  `getOwningNamespace()`, `getOwningType()`, `getName()`, `getDeclaredName()`, `getQualifiedName()`,
  `getDocumentation()`, `getMultiplicity()`, `getDirection()`, `getIsComposite()`, `getIsEnd()`,
  `getIsImplied()`, `getEntryAction()`, `getIsParallel()`, `getTriggerAction()`, a transition's
  `getSource()` and `getTarget()`, `getSatisfiedRequirement()`, `getChainingFeature()`, and the
  specific owned relationships with their ends: `getOwnedTyping()` (`getType()`),
  `getOwnedSubclassification()` (`getSuperclassifier()`), `getOwnedSpecialization()`
  (`getGeneral()`), `getOwnedSubsetting()` (`getSubsettedFeature()`; it holds the redefinitions
  too), `getOwnedRedefinition()` (`getRedefinedFeature()`), `getOwnedReferenceSubsetting()`
  (`getReferencedFeature()`), and a port definition's `getConjugatedPortDefinition()` /
  `getOriginalPortDefinition()`.

The refusal's message names the member and the SysML Toolkit's reason (`property has an incomplete
derivation`, `Type features are incomplete: IncompleteProvider`, `incomplete operation evidence`):
the SysML Toolkit lacks complete evidence for that element, which says nothing about whether the
model is right. Whether a read is refused depends on the property and the element; try one element
first rather than assume. Where it is refused, in this order:

**1. Read what the model states.** The helpers below derive what the common refused properties
give, from the owned relationships (verified through the SysML Toolkit and through the export alike;
copy them as they are, after the SDK's includes and `using namespace sysml;`). `getIsImplied()`
marks the relationships the SysML Toolkit adds from the library, which the model does not write.

```cpp
#include <algorithm>
#include <cstdint>
#include <deque>
#include <optional>
#include <stdexcept>
#include <unordered_set>
#include <utility>
#include <vector>

// The features a feature redefines or subsets as the model writes them (getOwnedSubsetting() holds
// the redefinitions too; getIsImplied() marks what the SysML Toolkit adds from the library).
inline std::vector<Feature> written_generals(const Feature& feature) {
    std::vector<Feature> out;
    for (const Subsetting& s : feature.getOwnedSubsetting())
        if (s.getIsImplied() != true) out.push_back(s.getSubsettedFeature().value());
    return out;
}

// A definition's supertypes as the model writes them, without the library ones the SysML Toolkit
// implies (Parts::Part for a part definition).
inline std::vector<Classifier> written_supertypes(const Classifier& definition) {
    std::vector<Classifier> out;
    for (const Subclassification& s : definition.getOwnedSubclassification())
        if (s.getIsImplied() != true) out.push_back(s.getSuperclassifier().value());
    return out;
}

// A feature's types: getType() where the SysML Toolkit answers it; else its own typings; else those
// of the features it redefines or subsets as written (`part :>> battery[2];`).
inline std::vector<Type> types_of(const Feature& feature) {
    try { return feature.getType(); } catch (const not_implemented_in_toolkit&) { /* read around it */ }
    std::vector<Type> own;
    for (const FeatureTyping& t : feature.getOwnedTyping()) own.push_back(t.getType().value());
    if (!own.empty()) return own;
    for (const Feature& general : written_generals(feature)) {
        std::vector<Type> found = types_of(general);
        if (!found.empty()) return found;
    }
    return {};
}

// t's own features, then those it inherits along what the model writes (a definition's
// supertypes; a usage's types and the usages it redefines or subsets), without the ones redefined
// on the way. The model's own features, not the library's; not the specification's full
// derivation (no visibility, no imports).
inline std::vector<Feature> features_with_inherited(const Type& t, std::unordered_set<Element>& seen) {
    if (!seen.insert(t).second) return {};
    std::vector<Feature> own = t.getOwnedFeature();
    std::unordered_set<Element> redefined;
    for (const Feature& f : own)
        for (const Redefinition& r : f.getOwnedRedefinition()) redefined.insert(r.getRedefinedFeature().value());
    std::vector<Type> bases;
    if (t.is_a<Classifier>()) {
        for (const Classifier& c : written_supertypes(t.as<Classifier>())) bases.push_back(c.as<Type>());
    } else if (t.is_a<Feature>()) {
        for (const Type& x : types_of(t.as<Feature>())) bases.push_back(x);
        for (const Feature& g : written_generals(t.as<Feature>())) bases.push_back(g.as<Type>());
    }
    for (const Type& base : bases)
        for (const Feature& f : features_with_inherited(base, seen))
            if (!redefined.count(f) && std::find(own.begin(), own.end(), f) == own.end()) own.push_back(f);
    return own;
}

inline std::vector<Feature> features_with_inherited(const Type& t) {
    std::unordered_set<Element> seen;
    return features_with_inherited(t, seen);
}

inline bool redefines(const Feature& f, const Feature& target, std::unordered_set<Element>& seen) {
    for (const Redefinition& r : f.getOwnedRedefinition()) {
        Feature g = r.getRedefinedFeature().value();
        if (g == target || (seen.insert(g).second && redefines(g, target, seen))) return true;
    }
    return false;
}

// The feature that stands for `feature` in `context`: `feature` itself where the context inherits
// it, or the nearest one that redefines it, directly or through other redefinitions; empty where the
// context has neither (pass the declaration, `Component::mass`, not a redefinition in some other
// definition).
inline std::optional<Feature> feature_in(const Type& context, const Feature& feature) {
    for (const Feature& f : features_with_inherited(context)) {
        std::unordered_set<Element> seen{f};
        if (f == feature || redefines(f, feature, seen)) return f;
    }
    return std::nullopt;
}

// The expression that gives `feature` its value in `context` (`attribute :>> mass = 2.5;` in the
// context's definition or body), or empty. Initial values (`:=`) and defaults (`default =`) count
// too; the FeatureValue's getIsInitial() / getIsDefault() tell them apart.
inline std::optional<Expression> bound_value(const Type& context, const Feature& feature) {
    std::optional<Feature> f = feature_in(context, feature);
    if (!f) return std::nullopt;
    for (const Membership& m : f->getOwnedMembership())
        if (m.is_a<FeatureValue>()) return m.as<FeatureValue>().getValue();
    return std::nullopt;
}

// The feature a chain of written redefinitions starts from (`Frame::mass` -> `Unit::mass`): the
// declaration to pass to bound_value and feature_in.
inline Feature declaration_of(Feature feature) {
    std::unordered_set<Element> seen{feature};
    for (;;) {
        std::optional<Feature> next;
        for (const Redefinition& r : feature.getOwnedRedefinition())
            if (r.getIsImplied() != true) { next = r.getRedefinedFeature(); break; }
        if (!next || !seen.insert(*next).second) return feature;
        feature = *next;
    }
}

using Bounds = std::pair<std::optional<std::int64_t>, std::optional<std::int64_t>>;   // upper empty for `*`

// {lower, upper} of a MultiplicityRange with literal bounds. `[4]` has only an upper bound:
// lower = upper then. A bound that is an expression (`[rotorCount]`) throws.
inline Bounds bounds(const MultiplicityRange& range) {
    auto literal = [](const std::optional<Expression>& e) -> std::optional<std::int64_t> {
        if (e && e->is_a<LiteralInfinity>()) return std::nullopt;
        if (e && e->is_a<LiteralInteger>()) return e->as<LiteralInteger>().getValue();
        throw std::invalid_argument("a bound to evaluate in context: " + (e ? e->metaclass_name() : std::string("none")));
    };
    std::optional<std::int64_t> upper = literal(range.getUpperBound());
    return {range.getLowerBound() ? literal(range.getLowerBound()) : upper, upper};
}

// {lower, upper} of the multiplicity that applies to a usage: its own; else, nearest first, that of
// the features it redefines or subsets as written; else {1, 1} where SysML gives the default (an
// attribute, item, part or port usage, not a connection, owned by a definition or usage); else
// {0, empty}, unconstrained.
inline Bounds multiplicity_of(const Feature& usage) {
    std::unordered_set<Element> seen{usage};
    std::deque<Feature> todo{usage};
    while (!todo.empty()) {
        Feature u = todo.front();
        todo.pop_front();
        std::optional<Multiplicity> m = u.getMultiplicity();
        if (m && m->is_a<MultiplicityRange>()) return bounds(m->as<MultiplicityRange>());
        std::vector<Feature> generals = written_generals(u);
        if (generals.empty()) {
            bool kind = (u.is_a<AttributeUsage>() || u.is_a<ItemUsage>() || u.is_a<PortUsage>()) && !u.is_a<ConnectionUsage>();   // a PartUsage is an ItemUsage
            std::optional<Type> owner = u.getOwningType();
            bool owned = owner && (owner->is_a<Definition>() || owner->is_a<Usage>());
            if (kind && owned) return {1, 1};
            return {0, std::nullopt};
        }
        for (const Feature& g : generals)
            if (seen.insert(g).second) todo.push_back(g);
    }
    return {0, std::nullopt};
}

// A connector's ends in order, the source first: the features or feature chains it connects. For
// connections, flows, successions and bindings alike.
inline std::vector<Feature> ends(const Connector& connector) {
    try {
        std::vector<Feature> out;
        if (std::optional<Feature> s = connector.getSourceFeature()) out.push_back(*s);
        for (const Feature& t : connector.getTargetFeature()) out.push_back(t);
        return out;
    } catch (const not_implemented_in_toolkit&) { /* read around it */ }
    std::vector<Feature> out;
    for (const Feature& e : connector.getOwnedFeature())
        if (e.getIsEnd() == true && e.getOwnedReferenceSubsetting())
            out.push_back(e.getOwnedReferenceSubsetting()->getReferencedFeature().value());
    return out;
}

// A feature chain as its features ([battery, powerOut] for battery.powerOut); else [feature].
inline std::vector<Feature> path(const Feature& feature) {
    std::vector<Feature> chain = feature.getChainingFeature();
    return chain.empty() ? std::vector<Feature>{feature} : chain;
}

// What an accept action accepts (a transition's getTriggerAction().at(0)): its payload's types.
inline std::vector<Type> accepted_types(const AcceptActionUsage& accept) {
    try { return accept.getPayloadParameter().value().getType(); } catch (const not_implemented_in_toolkit&) { /* read around it */ }
    for (const Membership& m : accept.getOwnedMembership())
        if (m.is_a<ParameterMembership>()) return types_of(m.as<ParameterMembership>().getOwnedMemberParameter().value());
    return {};
}

// What satisfies the requirement in `satisfy r by x;`: x.
inline std::optional<Feature> satisfying_feature(const SatisfyRequirementUsage& satisfy) {
    try { return satisfy.getSatisfyingFeature(); } catch (const not_implemented_in_toolkit&) { /* read around it */ }
    for (const Membership& m : satisfy.getOwnedMembership())
        if (m.is_a<SubjectMembership>())
            for (const Membership& v : m.as<SubjectMembership>().getOwnedSubjectParameter().value().getOwnedMembership())
                if (v.is_a<FeatureValue>()) {
                    std::optional<Expression> e = v.as<FeatureValue>().getValue();
                    if (e && e->is_a<FeatureReferenceExpression>()) return e->as<FeatureReferenceExpression>().getReferent();
                }
    return std::nullopt;
}

// The subject parameter of a requirement or requirement definition: its own `subject`; else,
// nearest first, that of its definitions or of what it specializes as written; else empty.
inline std::optional<Usage> subject_of(const Type& requirement) {
    try {
        if (requirement.is_a<RequirementUsage>()) return requirement.as<RequirementUsage>().getSubjectParameter();
        if (requirement.is_a<RequirementDefinition>()) return requirement.as<RequirementDefinition>().getSubjectParameter();
    } catch (const not_implemented_in_toolkit&) { /* read around it */ }
    for (const Membership& m : requirement.getOwnedMembership())
        if (m.is_a<SubjectMembership>()) return m.as<SubjectMembership>().getOwnedSubjectParameter();
    std::vector<Type> bases;
    if (requirement.is_a<Classifier>()) {
        for (const Classifier& c : written_supertypes(requirement.as<Classifier>())) bases.push_back(c.as<Type>());
    } else if (requirement.is_a<Feature>()) {
        for (const Type& x : types_of(requirement.as<Feature>())) bases.push_back(x);
        for (const Feature& g : written_generals(requirement.as<Feature>())) bases.push_back(g.as<Type>());
    }
    for (const Type& base : bases)
        if (std::optional<Usage> found = subject_of(base)) return found;
    return std::nullopt;
}

// The states a state machine (a StateUsage or StateDefinition) starts in, as find_initial_states
// defines them: the targets of its successions from the library's `start` (`first start then
// off;`), and only where there are none, from its entry action (`entry; then off;`).
inline std::vector<StateUsage> initial_states(const Type& machine) {
    std::optional<ActionUsage> entry;
    if (machine.is_a<StateUsage>()) entry = machine.as<StateUsage>().getEntryAction();
    else if (machine.is_a<StateDefinition>()) entry = machine.as<StateDefinition>().getEntryAction();
    std::vector<StateUsage> from_start, from_entry;
    for (const Feature& f : machine.getOwnedFeature()) {
        if (!f.is_a<SuccessionAsUsage>()) continue;
        std::vector<Feature> e = ends(f.as<SuccessionAsUsage>());
        if (e.size() != 2 || !e[1].is_a<StateUsage>()) continue;
        if (e[0].getIsLibraryElement() == true && e[0].getName() == std::optional<std::string>("start"))
            from_start.push_back(e[1].as<StateUsage>());
        else if (entry && e[0] == *entry)
            from_entry.push_back(e[1].as<StateUsage>());
    }
    return from_start.empty() ? from_entry : from_start;
}

// The states of a state machine reachable from its initial states along its own transitions, in the
// order found (guards and triggers not considered; the transitions inside composite states not
// followed).
inline std::vector<StateUsage> reachable_states(const Type& machine) {
    std::vector<std::pair<Element, Element>> edges;
    for (const Feature& f : machine.getOwnedFeature())
        if (f.is_a<TransitionUsage>()) {
            TransitionUsage t = f.as<TransitionUsage>();
            std::optional<ActionUsage> source = t.getSource(), target = t.getTarget();
            if (source && target) edges.emplace_back(*source, *target);
        }
    std::vector<StateUsage> reached = initial_states(machine);
    for (std::size_t i = 0; i < reached.size(); ++i)
        for (const auto& [from, to] : edges)
            if (from == reached[i] && to.is_a<StateUsage>() && std::find(reached.begin(), reached.end(), to) == reached.end())
                reached.push_back(to.as<StateUsage>());
    return reached;
}

// The number an expression stands for when it is a literal, or a sign applied to one (`-40.0` is an
// OperatorExpression `-` whose operand is the literal 40.0). Anything else throws: evaluate it in
// context (the SysML Toolkit's evaluate refuses operator expressions).
inline double number(const Expression& expr) {
    if (expr.is_a<LiteralInteger>()) return static_cast<double>(expr.as<LiteralInteger>().getValue().value());
    if (expr.is_a<LiteralRational>()) return expr.as<LiteralRational>().getValue().value();
    if (expr.is_a<OperatorExpression>()) {
        std::optional<std::string> op = expr.as<OperatorExpression>().getOperator();
        if (op == std::optional<std::string>("-") || op == std::optional<std::string>("+")) {
            // The operands' parameters through the owned relationships: the SysML Toolkit refuses an
            // operator expression's ownedFeature in this release.
            std::vector<Expression> operands;
            for (const Relationship& r : expr.getOwnedRelationship())
                if (r.is_a<ParameterMembership>())
                    for (const Element& p : r.getOwnedRelatedElement())
                        if (p.is_a<Feature>())
                            for (const Membership& m : p.as<Feature>().getOwnedMembership())
                                if (m.is_a<FeatureValue>()) operands.push_back(m.as<FeatureValue>().getValue().value());
            if (operands.size() == 1) return *op == "-" ? -number(operands[0]) : number(operands[0]);
        }
    }
    throw std::invalid_argument("not a literal number: " + expr.metaclass_name());
}
```

**2. Query the SysML Toolkit's export as a payload** when a question needs the specification's full
derivation across a whole model (inherited members with visibility and imports, connector ends of
library connections). The export is written by the SysML Toolkit's compatibility path: it carries a
value for every property, including the ones the checked reader refuses, which the SysML Toolkit
does not vouch for. Say so in your answer when the result depends on them. `full_json` belongs to
the backend, so take it before handing the backend to a model:

```cpp
auto library = PayloadLibrary::parse(read_file(standard_library_json()));   // once; read_file as above
auto backend = ToolkitBackend::open({"model.sysml"}, {}, standard_library());
Model exported = Model::from_full_json(backend->full_json(), library);   // same element ids as the SysML Toolkit's
Model model = Model::from_backend(std::move(backend));                    // the same session
```

**3. Never** substitute an empty vector, a guess or a default for a refused read.

## Navigation recipes

With the helpers above; each works through the SysML Toolkit and on a payload.

```cpp
// d, part, port, usage, flow, machine and constraint stand for elements you have at hand (d: a
// definition or usage, as a Type); model is the Model.

// Parts of a definition or usage, owned and inherited, not connections; the model's own, not the
// library's (start, done, subparts, ...)
std::vector<PartUsage> parts;
for (const Feature& f : features_with_inherited(d))
    if (f.is_a<PartUsage>() && !f.is_a<ConnectionUsage>()) parts.push_back(f.as<PartUsage>());

std::vector<Type> definitions = types_of(part);      // what a usage is typed by

// The value a feature has in a context (`attribute :>> mass = 2.5;` in the part's definition or body)
Feature mass_f = model.resolve("Pkg::Component::mass").value().as<Feature>();   // the declaration; declaration_of(f) finds it from a redefinition
std::optional<Expression> expr = bound_value(part, mass_f);
double mass = number(expr.value());                  // a literal, or a sign applied to one (-40.0)

Bounds b = multiplicity_of(usage);                   // {2, 2} for [2]; {1, 1} by default; upper empty for *
std::string text = b.first == b.second ? "[" + std::to_string(*b.first) + "]"
    : "[" + std::to_string(b.first.value_or(0)) + ".." + (b.second ? std::to_string(*b.second) : "*") + "]";

// Roll-up: an attribute summed over a definition's direct parts (mass, cost, power); for a deeper
// tree, apply it to each part that has parts of its own (features_with_inherited(p))
double total = 0;
std::vector<std::string> missing;
for (const PartUsage& p : parts) {
    std::optional<Expression> e = bound_value(p, mass_f);
    Bounds n = multiplicity_of(p);
    if (!e || !n.second || n.first != n.second) missing.push_back(p.getName().value_or("?"));   // no value, or a range ([4..6], *): report, never guess
    else total += number(*e) * static_cast<double>(*n.second);
}

// Ports: the definition, and whether it is conjugated (`port p : ~PowerPort;`). getPortDefinition()
// (a vector) is refused; getIsConjugated() is false on a `~` port: the conjugation is its type, the
// ConjugatedPortDefinition that PowerPort owns (name "~PowerPort", qualified name
// "Pkg::PowerPort::'~PowerPort'", quotes included)
for (const Type& t : types_of(port))
    std::cout << (t.is_a<ConjugatedPortDefinition>()
        ? "~" + t.as<ConjugatedPortDefinition>().getOriginalPortDefinition().value().getQualifiedName().value_or("")
        : t.getQualifiedName().value_or("")) << "\n";

// Connections (ConnectionUsage: connect, interfaces, allocations): the ends, the source first. The
// ends of an inherited connection are the supertype's features (Drone::rotors, not a redefining
// `part :>> rotors[8];`): feature_in(d, chain.front()) is the one that stands for it in d
for (const Feature& f : features_with_inherited(d))
    if (f.is_a<ConnectionUsage>())
        for (const Feature& end : ends(f.as<ConnectionUsage>())) {
            std::vector<Feature> chain = path(end);          // [battery, powerOut], then the target
            std::vector<Type> port_types = types_of(chain.back());   // [PortDefinition or ConjugatedPortDefinition]
        }
// Flows (FlowUsage), bindings (BindingConnectorAsUsage) and successions are ConnectorAsUsage too,
// with the same ends()
std::vector<Classifier> items = flow.as<FlowUsage>().getPayloadType();   // the flowing item's definition

// States
StateUsage machine = model.resolve("Pkg::Controller::modes").value().as<StateUsage>();   // e.g. an ExhibitStateUsage
std::vector<StateUsage> states = machine.getNestedState();   // its own states
std::vector<StateUsage> initial = initial_states(machine);   // `first start then off;`, else `entry; then off;`
std::vector<StateUsage> reachable = reachable_states(machine);   // from the initial states along the transitions
for (const TransitionUsage& t : machine.getNestedTransition()) {
    ActionUsage from = t.getSource().value();   // getSource(), getTarget(): std::optional<ActionUsage>; the
    ActionUsage to = t.getTarget().value();     // states (as<StateUsage>()); a transition
    // from the entry action leaves an action, not a state: no as<StateUsage>() then
    std::vector<Type> signals = t.getTriggerAction().empty() ? std::vector<Type>{} : accepted_types(t.getTriggerAction().at(0));
}

// Requirements
for (const SatisfyRequirementUsage& s : model.elements_of_type<SatisfyRequirementUsage>()) {
    RequirementUsage req = s.getSatisfiedRequirement().value();
    std::optional<Feature> by = satisfying_feature(s);            // the part that satisfies it
    std::vector<Type> definition = types_of(req);                 // [RequirementDefinition]
    std::optional<Usage> subject = subject_of(req);               // its subject parameter; often the definition's
                                                                  // (`subject bike : Bike;` in MassLimit: MassLimit::bike)
    std::optional<Feature> limit_f;                               // the definition's maxMass
    for (const Type& t : types_of(req))
        for (const Feature& f : features_with_inherited(t))
            if (f.getName() == std::optional<std::string>("maxMass")) limit_f = f;
    std::optional<Expression> limit = bound_value(req, limit_f.value());   // the requirement's value for it
    std::vector<ConstraintUsage> constraints;                     // its own constraints
    for (const Membership& m : req.getOwnedMembership())
        if (m.is_a<RequirementConstraintMembership>()
            && m.as<RequirementConstraintMembership>().getKind() == std::optional<std::string>("requirement"))
            constraints.push_back(m.as<RequirementConstraintMembership>().getOwnedConstraint().value());
}
```

## Multiplicity

`getMultiplicity()` is only what the usage itself declares; `multiplicity_of` above applies SysML's
rule: a usage without one takes the multiplicity of the features it redefines or subsets as written
(nearest first; `part :>> battery[2];` declares its own), and one that redefines or subsets nothing
is `[1..1]` if it is an attribute, item, part or port usage owned by a definition or usage, and
unconstrained (`[0..*]`) otherwise. Implied subsettings (`getIsImplied()`, such as every part's
subsetting of the library's `parts`) do not count. A bound may be an expression to evaluate in
context (`Rotor[rotorCount]`); `bounds` throws for it.

## Evaluating the model's expressions

Expressions are elements: `OperatorExpression` (`getOperator()` such as `"<="`, `"and"`, `"not"`;
`getArgument()`), `FeatureReferenceExpression` (`getReferent()`), `FeatureChainExpression` (`a.b`:
argument 0 is `a`, `getTargetFeature()` is `b`; it is an OperatorExpression too, so test it first),
literals with `getValue()` (`LiteralInteger`, `LiteralRational`, `LiteralBoolean`, `LiteralString`,
`LiteralInfinity` for `*`), `TriggerInvocationExpression` (`getKind()`: `at`, `after`, `when`). An
enumeration literal is an `EnumerationUsage` whose `getOwningNamespace()` is the
`EnumerationDefinition` (its owning type is empty, by the specification). Through the SysML Toolkit,
`getArgument()` is refused: an expression's operands are its `getOwnedFeature()`s, each bound by a
`FeatureValue` in its `getOwnedMembership()`.

The SysML Toolkit's `evaluate(target)` operation evaluates some expressions (it returns elements);
beyond that, the SDK does not evaluate. The SDK's source repository
(https://github.com/Open-MBEE/sysml-sdk, not the release packages) has, in
`examples/queries/cpp/queries.hpp`, an evaluator in three-valued logic (values as
`std::variant<Unknown, bool, double, std::string, Element>`) and complete queries: reachable states
with shortest trigger sequences, bill of materials, attribute roll-up, connectivity, requirement
checks. Where it is at hand, start from it for such questions; the recipes above cover the simple
cases. In C++17 a `std::variant` holding both `bool` and `std::string` takes a string literal as
`bool`: construct strings explicitly.

## Other differences from the specification

- **With the library loaded**, `getUsage()`/`getFeature()` (in a payload) include library features:
  filter with `getIsLibraryElement()`. A flow's `getConnectorEnd()` also lists the library flow's
  ends; use `ends`.
- The second operand of `and`/`or`/`implies` is the operand expression itself, not the
  `FeatureReferenceExpression` to it that the specification builds. Accept both.
- An unnamed `satisfy` has no name, but a qualified-name lookup may still find it under the name of
  the requirement it satisfies. A feature named only through what it redefines has `getName()` from
  it and `getDeclaredName()` `std::nullopt` (a satisfy's subject parameter is named `subj`, although
  it redefines the subject of the requirement's definition).
- `getMayTimeVary()`, `getIsVariable()` and `getIsConstant()` on usages throw
  `not_implemented_in_toolkit`.
- In the SysML Toolkit's export, an alias (`alias ax for x;`) hides the membership of the feature it
  names from what specializations inherit, and a conjugated port's `getPortDefinition()` is the
  `ConjugatedPortDefinition` (`~PowerPort`), as the specification says.
- A payload answers what its writer wrote: stand-ins where the writer had no value (empty, `false`,
  an empty vector), and `unresolved_reference` for references into the
  standard library unless it was given the library JSON.

## Verify

- Run the same query through the SysML Toolkit (with the helpers) and on its export as a payload
  (the plain derived properties), matching elements by `element_id()`; differences point at the
  SysML Toolkit, the export, or your code.
- Format numbers with `snprintf` in the C locale; `std::to_chars` for floating point is missing on
  older macOS deployment targets.
- For more examples: the guide and runnable tutorial (`examples/cpp/`) and the query examples
  (`examples/queries/cpp/`) in the SDK repository.
