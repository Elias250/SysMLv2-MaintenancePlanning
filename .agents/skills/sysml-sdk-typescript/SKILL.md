---
name: sysml-sdk-typescript
description: Writes JavaScript or TypeScript code (Node or browser) that reads, navigates and queries SysML v2 and KerML models with the sysml package, through the OpenMBEE SysML Toolkit compiled to WebAssembly, the SysML v2 Pilot Implementation, or a full-form interchange JSON payload. Use when a task involves loading .sysml/.kerml text or SysML v2 JSON in JS/TS, walking parts, features, states, connections or requirements, evaluating a model's expressions, or answering questions about a SysML v2 model with code.
---

# SysML v2 SDK for JavaScript and TypeScript

The SDK is the OMG metamodel as typed element objects: every KerML and SysML metaclass, property and
operation, under its specification name. A model comes from one of three backends:

- **the SysML Toolkit**, compiled to WebAssembly (the same module in Node and browsers): reads SysML
  text, resolves names, computes derived properties and evaluates operations, and refuses what it
  cannot derive completely;
- **the SysML v2 Pilot Implementation**, run in a Java process (Node): reads the text too, and
  computes every property and operation with its own code;
- **a payload**: a full-form interchange JSON export from any SysML v2 tool.

Besides the specification's members, the classes have `find` convenience members (`findParts()`,
`findPartDefs()`, `findValue()`, ...) for what takes several steps in the specification.

The SDK never guesses. A member the SysML Toolkit does not answer throws `NotImplementedInToolkit`
with the reason the SysML Toolkit gives; a reference that does not resolve throws
`UnresolvedReference`. Never catch these to substitute a made-up value; read around them as
described below, or report them.

## Setup

```sh
npm install ./sysml-0.2.0.tgz    # carries the WebAssembly module and the standard library models
```

ES modules only: name files `.mjs`, or set `"type": "module"` in `package.json`. Node 20+.
`SYSMLV2_ABI_WASM` makes the SDK use another build of the module than the package's; in a browser,
pass `library: await ToolkitLibrary.load(await fetch(url))` to `ToolkitBackend.open`.

**Initialize first: get the standard library.** Nearly every model refers to it (`ScalarValues::Real`,
`ISQ::mass`, and implicitly `Parts::parts`, `Items::items`, ...). Do this once, at the start of the
program, before loading any model (Node):

```js
import { standardLibrary, standardLibraryJson } from "sysml";

const libraryDir = await standardLibrary();        // the models the package carries: libraryDir of the SysML Toolkit
const libraryJson = await standardLibraryJson();   // the library as JSON, for a payload's PayloadLibrary
```

`standardLibraryJson()` downloads the JSON from the SDK's GitHub release on its first call (checked
against the SHA-256 GitHub states, kept in the user cache; later calls read the cache) and throws
`LibraryUnavailable` with instructions when it cannot. Offline, `SYSML_LIBRARY_JSON` names a copy
(the `sysml.library.full.json` of the release's `sysml_library-0.2.0.zip`). Call only the one the
chosen backend needs. In a browser neither works (no file system): fetch the library's files for
`librarySources`, and a library JSON you host.

Costs: opening a model with the standard library takes two to three seconds; the SysML Toolkit's
JSON export (`fullJson()`) takes ten to thirty seconds under WebAssembly even for a small model, and
much longer once the 160 MB library JSON is parsed into the same process: export first, then read
the library JSON, and read it once. Node's default heap holds both.

## Loading a model

Through the SysML Toolkit:

```js
import { readFileSync } from "node:fs";
import { ToolkitBackend, Model, NotImplementedInToolkit, UnresolvedReference, elementsOfType, is }
  from "sysml";

const files = ["model.sysml"];                                   // your files
const sources = Object.fromEntries(files.map((f) => [f, readFileSync(f, "utf8")]));   // file name -> text
const toolkit = await ToolkitBackend.open({ sources, libraryDir });  // Node; libraryDir from the initialization
const model = new Model(toolkit);                                // toolkit.close() when done
// In a browser: ToolkitBackend.open({ sources, librarySources }), librarySources being the library's
// .sysml/.kerml files as { "<file name, without directories>": text } (fetch each file; the
// SysML Toolkit names library files so, and the library JSON's ids depend on it).
```

From a payload (a JSON export you have):

```js
import { readFileSync } from "node:fs";
import { Model, PayloadLibrary, UnresolvedReference, elementsOfType, is } from "sysml";

const library = new PayloadLibrary(JSON.parse(readFileSync(libraryJson, "utf8")));  // once, share it
const model = Model.fromFullJson(JSON.parse(readFileSync("model.json", "utf8")), { library });
```

- The SysML Toolkit compiled to WebAssembly reads no files itself: pass the model's units as
  `sources` (file name to text). Load the standard library whenever the model uses it, which nearly
  every model does (`ScalarValues::Real`, `ISQ::mass`, and implicitly `Parts::parts`): `libraryDir`
  in Node, or its files as `librarySources`. It loads as a library: its elements are not in
  `model.all()` or `elementsOfType`, and report `isLibraryElement`. Do not put library files into
  `sources`; they would count as the model's. Without it, references into the library stay
  unresolved: harmless until you read one, then `UnresolvedReference`.
- Element ids depend on the file names given; keep them stable when ids must be.
- A payload refers to the standard library's elements without containing them; pass the library
  JSON and those references resolve. Library elements are not the model's (`all()`, `roots()`,
  `elementsOfType` skip them); a qualified name is looked up in the payload first. The library JSON
  lists each library element's own members only, not what it inherits.

Through the SysML v2 Pilot Implementation, which runs in a Java process (Node only):

```js
import { BackendError, Model, PilotBackend } from "sysml";

const pilot = await PilotBackend.open({ paths: ["model.sysml"] });   // or sources: { "model.sysml": text }
const model = new Model(pilot);
// ...
pilot.close();
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

- **Find:** `model.resolve("Pkg::Part::feature")` (or `null`), `elementsOfType(model, "PartUsage")`
  (subclasses included), `model.all()` (an iterator), `model.roots()` (top-level namespaces; the
  packages are their `ownedMember`). `model.resolve` is the SysML Toolkit's own name lookup: it also
  finds inherited members and members of a feature's type (`"EBikes::CargoEBike::wheels"` is
  `Bike::wheels`), and it answers where the specification's `resolve` operation is refused.
- **Properties** read as properties under the specification name: `el.qualifiedName`,
  `el.ownedFeature`. **Operations** are methods: `el.effectiveName()`, `ns.resolve("Name")`.
  Suffixed where JavaScript or a property takes the name: `valueOfOp()`, `instantiatedTypeOp()`.
- **Metaclass tests:** `is(el, "PartUsage")` (metaclass or any ancestor; in TypeScript it narrows
  the type). `ConnectionUsage`, `InterfaceUsage` and `AllocationUsage` are `PartUsage`s too
  (`FlowUsage` is not); every connector, connections, flows, successions and bindings alike, is a
  `ConnectorAsUsage`. A definition's `ownedPart` therefore lists its connections too.
  `el.$metaclass` is the concrete metaclass name. There is no `instanceof` for metaclasses.
- **Every element** has the members of `Element`: `name`, `declaredName`, `qualifiedName`, `owner`,
  `owningNamespace`, `documentation`, `isLibraryElement`, `effectiveName()`.
- **Values:** a multi-valued property is an array (`[]` when absent), a single-valued one a value or
  `null` (`sourceFeature` is one feature or `null`, `targetFeature` an array). Numbers are
  `number`; enumeration values lowercase strings (`"requirement"`). An unnamed element has `name`
  `null` (a `connect` without a name).
- **Identity:** a model hands out one object per element, so `===` is element identity and elements
  can key a `Map` or `Set` (within one model). The same element read through two models (the
  SysML Toolkit's and its export's) is two objects: compare their `$id`s. Runtime members start with
  `$`: `$id` (element id), `$handle`, `$metaclass`, `$raw(prop)`.
- **Errors:** `NotImplementedInToolkit`, `UnresolvedReference`, `Gone`, `ToolkitError`. Elements are
  read-only; assignment throws `TypeError`. An operation argument that must be an element and is
  not throws `TypeError`. Reading a name that is not a member of the element's metaclass (a
  misspelling such as `ownedParts`, or a member of another metaclass) gives `undefined`, not an
  error: check names against `classes.d.ts`, or write TypeScript. `"name" in el` tells whether the
  metaclass has a member of that name.
- **Operations** need the SysML Toolkit (a payload throws for every one) and take the
  specification's parameters in order; `classes.d.ts` in the package has every signature
  (`inheritedMemberships(excludedNamespaces, excludedTypes, excludeImplied)`). The SysML Toolkit has
  a body for about a third of them and answers a call only where its evidence for the model is
  complete. Answered on a typical model: `effectiveName()` (not on every unnamed feature),
  `effectiveShortName()`, `resolveGlobal`, `supertypes(true)` (the argument is `excludeImplied`),
  `evaluate(target)` (target: the element to evaluate in, such as the part usage, never null; it
  returns elements, such as the literal a feature is bound to), `modelLevelEvaluable`. Refused
  there: `resolve`, `resolveLocal`, `resolveVisible`, `visibleMemberships`, `namesOf`,
  `inheritedMemberships`, `supertypes(false)`. No body at all: `isCompatibleWith`, `specializes`,
  `allSupertypes`, `directionOf`, ... Catch the refusal.
- TypeScript: `index.d.ts` and `classes.d.ts` type every metaclass; `AnyElement` is any element,
  `TypeMap` maps metaclass names to interfaces. `resolve` returns `AnyElement | null`: narrow it
  with `is(...)` before use.

## Convenience members

Besides the specification's members, the classes have `find` members (312), each defined by the SDK
over the specification's properties and operations; `classes.d.ts` has every signature with its
definition. Use one wherever it answers: one call instead of a walk.

```js
import { NotAnswered, Refused, Scope, VisibilityFilter } from "sysml";

d.findParts();                       // the part usages d owns (a connection is a part too)
d.findPartsExact();                  // exactly PartUsage; d.findPart("engine"): by name, or null
d.findParts(Scope.ALL);              // owned, then inherited; Scope.INHERITED: inherited only
d.findPartsSemantic();               // the features typed by a part definition
pkg.findPartDefs();                  // the part definitions a namespace owns; findPartDef(name)
pkg.findPartDefsByName();            // a Map from every name and short name to its definition
pkg.findPartDefs().findPorts();      // a list carries its elements' members: calls chain
feature.findDeclaredTypes();         // the types as written; t.findDeclaredSupertypes()
feature.findRedefinitionRoot();      // the feature its written redefinitions start from
feature.findValue();                 // the value expression (=, :=, default), or null
expr.findLiteral();                  // a number, boolean or string (Infinity for *), a sign folded
t.findLowerBound(); t.findUpperBound();   // t's own multiplicity; null without one
```

- The feature kinds (27): `findAttributes`, `findPorts`, `findItems`, `findActions`, `findStates`,
  `findConnections`, `findRequirements`, `findConstraints`, ... Every list takes `scope`,
  `visibility` (`VisibilityFilter.PUBLIC`, `PROTECTED`; `ANY` by default) and `library` (`true`
  keeps what the standard library's types contribute, left out by default). On a namespace:
  `find<Kind>Defs()`, `find<Kind>Def(name)`, `find<Kind>DefsByName()`, and the usages it has through
  any membership, `findMember<Kinds>()`.
- Also: `findSubsettedFeatures()`, `findRedefinedFeatures()`, `findReferencedFeature()`,
  `findEffectiveFeature(f)`, `findUnit()` (`1500 [kg]`: `SI::kilogram`), `findParameters()`,
  `findInputs()`, `findOutputs()`, `findInitialStates()`, `findAcceptedTypes()`,
  `findIsAcceptedType(t)`, `findResultExpression()`, `findPath()`, `findAppliedMetadata()`,
  `findDocText()`.
- `Refused` (a `NotAnswered`): the member's definition gives no answer for this element
  (`findLiteral()` of `2 * x`, or of a value with a unit). `NotAnswered`: the backend cannot answer
  something the member reads, named in the message (`NotImplementedInToolkit` from the SysML
  Toolkit).
- **On the Pilot Implementation** every member answers.
- **On the SysML Toolkit**, the members answer: every list, lookup and exact list in the owned scope;
  the definition lists and name maps of a package; the types, supertypes, subsettings and
  redefinitions as written; values, unsigned literals and own bounds; paths, metadata and
  documentation. They are refused, with the reason: the inherited scope and `Scope.ALL` of feature
  and member lists and the semantic lists (`specializes()`), `findEffectiveFeature`, the implied
  supertypes, `findParameters`, `findInputs` and `findOutputs` (`directionOf()`), the accepted types
  (`payloadParameter`), `findInitialStates`, `findResultExpression`, and a literal with a sign or a
  unit (`argument`). For those, use the helpers below: `featuresWithInherited`, `acceptedTypes`,
  `initialStates`, `number`.
- `findLowerBound()`/`findUpperBound()` read the type's own multiplicity only; for SysML's default
  and the multiplicity a usage takes from what it redefines, use `multiplicityOf` below.
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
  enumeration values, and `type` on some parameters and reference usages (use `typesOf` below
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
first rather than assume. Where it is refused, in this order:

**1. Read what the model states.** The helpers below derive what the common refused properties
give, from the owned relationships (verified through the SysML Toolkit and through the export alike;
copy them as they are). `isImplied` marks the relationships the SysML Toolkit adds from the library,
which the model does not write.

```js
const refused = (e) => { if (!(e instanceof NotImplementedInToolkit)) throw e; };

// The features a feature redefines or subsets as the model writes them (ownedSubsetting holds the
// redefinitions too; isImplied marks what the SysML Toolkit adds from the library).
const writtenGenerals = (feature) =>
  feature.ownedSubsetting.filter((s) => !s.isImplied).map((s) => s.subsettedFeature);

// A definition's supertypes as the model writes them, without the library ones the SysML Toolkit
// implies (Parts::Part for a part definition).
const writtenSupertypes = (definition) =>
  definition.ownedSubclassification.filter((s) => !s.isImplied).map((s) => s.superclassifier);

// A feature's types: `type` where the SysML Toolkit answers it; else its own typings; else those of
// the features it redefines or subsets as written (`part :>> battery[2];`).
function typesOf(feature) {
  try { return feature.type; } catch (e) { refused(e); }
  const own = feature.ownedTyping.map((t) => t.type);
  if (own.length) return own;
  for (const general of writtenGenerals(feature)) {
    const found = typesOf(general);
    if (found.length) return found;
  }
  return [];
}

// t's own features, then those it inherits along what the model writes (a definition's
// supertypes; a usage's types and the usages it redefines or subsets), without the ones redefined
// on the way. The model's own features, not the library's; not the specification's full
// derivation (no visibility, no imports).
function featuresWithInherited(t, seen = new Set()) {
  if (seen.has(t)) return [];
  seen.add(t);
  const own = [...t.ownedFeature];
  const redefined = new Set(own.flatMap((f) => f.ownedRedefinition.map((r) => r.redefinedFeature)));
  const bases = is(t, "Classifier") ? writtenSupertypes(t) : [...typesOf(t), ...writtenGenerals(t)];
  for (const base of bases) {
    for (const f of featuresWithInherited(base, seen)) if (!redefined.has(f) && !own.includes(f)) own.push(f);
  }
  return own;
}

// The feature that stands for `feature` in `context`: `feature` itself where the context inherits
// it, or the nearest one that redefines it, directly or through other redefinitions; null where the
// context has neither (pass the declaration, `Component::mass`, not a redefinition in some other
// definition).
function featureIn(context, feature) {
  const redefines = (f, target, seen) => f.ownedRedefinition.some((r) => {
    const g = r.redefinedFeature;
    return g === target || (!seen.has(g) && redefines(g, target, new Set([...seen, g])));
  });
  return featuresWithInherited(context).find((f) => f === feature || redefines(f, feature, new Set([f]))) ?? null;
}

// The expression that gives `feature` its value in `context` (`attribute :>> mass = 2.5;` in the
// context's definition or body), or null. Initial values (`:=`) and defaults (`default =`) count
// too; the FeatureValue's isInitial / isDefault tell them apart.
const boundValue = (context, feature) =>
  featureIn(context, feature)?.ownedMembership.find((m) => is(m, "FeatureValue"))?.value ?? null;

// The feature a chain of written redefinitions starts from (`Frame::mass` -> `Unit::mass`): the
// declaration to pass to boundValue and featureIn.
function declarationOf(feature) {
  const seen = new Set([feature]);
  for (;;) {
    const written = feature.ownedRedefinition.filter((r) => !r.isImplied).map((r) => r.redefinedFeature);
    if (!written.length || seen.has(written[0])) return feature;
    feature = written[0];
    seen.add(feature);
  }
}

// [lower, upper] of a MultiplicityRange with literal bounds; upper null for `*`. `[4]` has only an
// upper bound: lower = upper then. A bound that is an expression (`[rotorCount]`) throws.
function bounds(multiplicity) {
  const value = (e) => {
    if (is(e, "LiteralInfinity")) return null;
    if (is(e, "LiteralInteger")) return e.value;
    throw new Error(`a bound to evaluate in context: ${e.$metaclass}`);
  };
  const upper = value(multiplicity.upperBound);
  return [multiplicity.lowerBound == null ? upper : value(multiplicity.lowerBound), upper];
}

// [lower, upper] of the multiplicity that applies to a usage: its own; else, nearest first, that
// of the features it redefines or subsets as written; else [1, 1] where SysML gives the default (an
// attribute, item, part or port usage, not a connection, owned by a definition or usage); else
// [0, null], unconstrained.
function multiplicityOf(usage) {
  const seen = new Set([usage]);
  const todo = [usage];
  while (todo.length) {
    const u = todo.shift();
    // A multiplicity without bounds is the default member SysML implies (`Base::exactlyOne`): the rule below gives it.
    if (u.multiplicity != null && is(u.multiplicity, "MultiplicityRange")) return bounds(u.multiplicity);
    const generals = writtenGenerals(u);
    if (!generals.length) {
      const kind = ["AttributeUsage", "ItemUsage", "PortUsage"].some((k) => is(u, k)) && !is(u, "ConnectionUsage");   // a PartUsage is an ItemUsage
      const owner = u.owningType;
      return kind && owner && (is(owner, "Definition") || is(owner, "Usage")) ? [1, 1] : [0, null];
    }
    for (const g of generals) if (!seen.has(g)) { seen.add(g); todo.push(g); }
  }
  return [0, null];
}

// A connector's ends in order, the source first: the features or feature chains it connects. For
// connections, flows, successions and bindings alike.
function ends(connector) {
  try { return [connector.sourceFeature, ...connector.targetFeature]; } catch (e) { refused(e); }
  return connector.ownedFeature.filter((e) => e.isEnd && e.ownedReferenceSubsetting)
    .map((e) => e.ownedReferenceSubsetting.referencedFeature);
}

// A feature chain as its features ([battery, powerOut] for battery.powerOut); else [feature].
const path = (feature) => (feature.chainingFeature.length ? feature.chainingFeature : [feature]);

// What an accept action accepts (a transition's triggerAction[0]): its payload's types.
function acceptedTypes(accept) {
  try { return accept.payloadParameter.type; } catch (e) { refused(e); }
  const payload = accept.ownedMembership.find((m) => is(m, "ParameterMembership")).ownedMemberParameter;
  return typesOf(payload);
}

// What satisfies the requirement in `satisfy r by x;`: x.
function satisfyingFeature(satisfy) {
  try { return satisfy.satisfyingFeature; } catch (e) { refused(e); }
  const subject = satisfy.ownedMembership.find((m) => is(m, "SubjectMembership")).ownedSubjectParameter;
  return subject.ownedMembership.find((m) => is(m, "FeatureValue")).value.referent;   // a FeatureReferenceExpression
}

// The subject parameter of a requirement or requirement definition: its own `subject`; else,
// nearest first, that of its definitions or of what it specializes as written; else null.
function subjectOf(requirement) {
  try { return requirement.subjectParameter; } catch (e) { refused(e); }
  const own = requirement.ownedMembership.find((m) => is(m, "SubjectMembership"));
  if (own) return own.ownedSubjectParameter;
  const bases = is(requirement, "Classifier") ? writtenSupertypes(requirement)
    : [...typesOf(requirement), ...writtenGenerals(requirement)];
  for (const base of bases) {
    const found = subjectOf(base);
    if (found) return found;
  }
  return null;
}

// The states a state machine (a state usage or definition) starts in, as findInitialStates defines
// them: the targets of its successions from the library's `start` (`first start then off;`), and
// only where there are none, from its entry action (`entry; then off;`).
function initialStates(machine) {
  const entry = machine.entryAction, fromStart = [], fromEntry = [];
  for (const f of machine.ownedFeature) {
    if (!is(f, "SuccessionAsUsage")) continue;
    const e = ends(f);
    if (e.length !== 2 || !is(e[1], "StateUsage")) continue;
    if (e[0].isLibraryElement && e[0].name === "start") fromStart.push(e[1]);
    else if (entry && e[0] === entry) fromEntry.push(e[1]);
  }
  return fromStart.length ? fromStart : fromEntry;
}

// The states of a state machine reachable from its initial states along its own transitions, in the
// order found (guards and triggers not considered; the transitions inside composite states not
// followed).
function reachableStates(machine) {
  const next = new Map();
  for (const t of machine.ownedFeature.filter((f) => is(f, "TransitionUsage"))) {
    if (!next.has(t.source)) next.set(t.source, []);
    next.get(t.source).push(t.target);
  }
  const reached = initialStates(machine);
  for (let i = 0; i < reached.length; i++)
    for (const n of next.get(reached[i]) ?? []) if (is(n, "StateUsage") && !reached.includes(n)) reached.push(n);
  return reached;
}

// The number an expression stands for when it is a literal, or a sign applied to one (`-40.0` is an
// OperatorExpression `-` whose operand is the literal 40.0). Anything else throws: evaluate it in
// context (the SysML Toolkit's evaluate refuses operator expressions).
function number(expr) {
  if (is(expr, "LiteralInteger") || is(expr, "LiteralRational")) return expr.value;
  if (is(expr, "OperatorExpression") && (expr.operator === "-" || expr.operator === "+")) {
    // The operands' parameters through the owned relationships: the SysML Toolkit refuses an operator
    // expression's ownedFeature in this release.
    const params = expr.ownedRelationship.filter((r) => is(r, "ParameterMembership")).flatMap((r) => r.ownedRelatedElement);
    const operands = params.flatMap((f) => f.ownedMembership.filter((m) => is(m, "FeatureValue")).map((m) => m.value));
    if (operands.length === 1) return expr.operator === "-" ? -number(operands[0]) : number(operands[0]);
  }
  throw new Error(`not a literal number: ${expr.$metaclass}`);
}
```

**2. Query the SysML Toolkit's export as a payload** when a question needs the specification's full
derivation across a whole model (inherited members with visibility and imports, connector ends of
library connections). The export is written by the SysML Toolkit's compatibility path: it carries a
value for every property, including the ones the checked reader refuses, which the SysML Toolkit
does not vouch for. Say so in your answer when the result depends on them.

```js
import { PayloadLibrary, standardLibraryJson } from "sysml";   // besides the SysML Toolkit block's imports

const exportText = toolkit.fullJson();              // first: slow once the library JSON is in memory
const library = new PayloadLibrary(JSON.parse(readFileSync(await standardLibraryJson(), "utf8")));
const exported = Model.fromFullJson(JSON.parse(exportText), { library });   // same element ids
```

**3. Never** substitute an empty array, a guess or a default for a refused read.

## Navigation recipes

With the helpers above; each works through the SysML Toolkit and on a payload.

```js
// d, part, port, usage, flow, machine and constraint stand for elements you have at hand (d: a
// definition or usage); model is the Model.

// Parts of a definition or usage, owned and inherited, not connections; the model's own, not the
// library's (start, done, subparts, ...)
const parts = featuresWithInherited(d).filter((f) => is(f, "PartUsage") && !is(f, "ConnectionUsage"));

typesOf(part);                               // what a usage is typed by: [PartDefinition, ...]

// The value a feature has in a context (`attribute :>> mass = 2.5;` in the part's definition or body)
const mass = model.resolve("Pkg::Component::mass");   // the declaration; declarationOf(f) finds it from a redefinition
const expr = boundValue(part, mass);         // an Expression, or null
number(expr);                                // its number: a literal, or a sign applied to one (-40.0)

const [lower, upper] = multiplicityOf(usage);   // [2, 2] for [2]; [1, 1] by default; upper null for *
const text = lower === upper ? `[${lower}]` : `[${lower}..${upper ?? "*"}]`;

// Roll-up: an attribute summed over a definition's direct parts (mass, cost, power); for a deeper
// tree, apply it to each part that has parts of its own (featuresWithInherited(p))
let total = 0; const missing = [];
for (const p of parts) {
  const e = boundValue(p, mass), [lo, hi] = multiplicityOf(p);
  if (e === null || lo !== hi) missing.push(p.name);   // no value, or a range ([4..6], *): report, never guess
  else total += number(e) * lo;
}

// Ports: the definition, and whether it is conjugated (`port p : ~PowerPort;`). `portDefinition`
// (an array) is refused; `port.isConjugated` is false on a `~` port: the conjugation is its type,
// the ConjugatedPortDefinition that PowerPort owns (name "~PowerPort", qualified name
// "Pkg::PowerPort::'~PowerPort'", quotes included)
for (const t of typesOf(port))
  console.log(is(t, "ConjugatedPortDefinition") ? `~${t.originalPortDefinition.qualifiedName}` : t.qualifiedName);

// Connections (ConnectionUsage: connect, interfaces, allocations): the ends, the source first. The
// ends of an inherited connection are the supertype's features (Drone::rotors, not a redefining
// `part :>> rotors[8];`): featureIn(d, path(end)[0]) is the one that stands for it in d
for (const c of featuresWithInherited(d).filter((f) => is(f, "ConnectionUsage"))) {
  console.log(ends(c).map((end) => path(end).map((f) => f.name).join(".")).join(" -> "));   // battery.powerOut -> ...
  const portTypes = ends(c).map((end) => typesOf(path(end).at(-1)));   // per end: [PortDefinition or ConjugatedPortDefinition]
}
// Flows (FlowUsage), bindings (BindingConnectorAsUsage) and successions are ConnectorAsUsage too,
// with the same ends()
flow.payloadType;                            // [the flowing item's definition]

// States
const machine = model.resolve("Pkg::Controller::modes");   // an ExhibitStateUsage or StateUsage
machine.nestedState;                         // its own states
machine.isParallel; machine.entryAction;
const initial = initialStates(machine);      // `first start then off;`, else `entry; then off;`
const reachable = reachableStates(machine);  // from the initial states along the transitions
for (const t of machine.nestedTransition) {  // t.source, t.target: the states it leaves and enters; t.guardExpression
  // a transition from the entry action leaves an action, not a state
  const signals = t.triggerAction.length ? acceptedTypes(t.triggerAction[0]) : [];   // [ItemDefinition, ...]
  if (t.triggerAction.length) t.triggerAction[0].payloadArgument;   // TriggerInvocationExpression for `accept at`/`when` (.kind)
}

// Requirements
for (const s of elementsOfType(model, "SatisfyRequirementUsage")) {
  const req = s.satisfiedRequirement;        // the requirement usage
  const by = satisfyingFeature(s);           // the part that satisfies it
  const definition = typesOf(req);           // [RequirementDefinition]
  const subject = subjectOf(req);            // its subject parameter, or null; often the definition's
                                             // (`subject bike : Bike;` in MassLimit: MassLimit::bike)
  const limitF = typesOf(req).flatMap((t) => featuresWithInherited(t)).find((f) => f.name === "maxMass");
  const limit = boundValue(req, limitF);     // the requirement's value for its definition's maxMass
  req.ownedMembership.filter((m) => is(m, "RequirementConstraintMembership") && m.kind === "requirement")
    .map((m) => m.ownedConstraint);          // its own constraints
}
constraint.ownedMembership.find((m) => is(m, "ResultExpressionMembership")).ownedResultExpression;
```

## Multiplicity

`multiplicity` is only what the usage itself declares; `multiplicityOf` above applies SysML's rule:
a usage without one takes the multiplicity of the features it redefines or subsets as written
(nearest first; `part :>> battery[2];` declares its own), and one that redefines or subsets nothing
is `[1..1]` if it is an attribute, item, part or port usage owned by a definition or usage, and
unconstrained (`[0..*]`) otherwise. Implied subsettings (`s.isImplied`, such as every part's
subsetting of the library's `parts`) do not count. A bound may be an expression to evaluate in
context (`Rotor[rotorCount]`); `bounds` throws for it.

## Evaluating the model's expressions

Expressions are elements: `OperatorExpression` (`operator` such as `"<="`, `"and"`, `"not"`;
`argument`), `FeatureReferenceExpression` (`referent`), `FeatureChainExpression` (`a.b`:
`argument[0]` is `a`, `targetFeature` is `b`; it is an OperatorExpression too, so test it first),
literals with `.value` (`LiteralInteger`, `LiteralRational`, `LiteralBoolean`, `LiteralString`,
`LiteralInfinity` for `*`), `TriggerInvocationExpression` (`kind`: `at`, `after`, `when`). An
enumeration literal is an `EnumerationUsage` whose `owningNamespace` is the `EnumerationDefinition`
(its `owningType` is null, by the specification). Through the SysML Toolkit, `argument` is refused:
an expression's operands are its `ownedFeature`s, each bound by a `FeatureValue` in its
`ownedMembership`.

The SysML Toolkit's `evaluate(target)` operation evaluates some expressions (it returns elements);
beyond that, the SDK does not evaluate. The SDK's source repository
(https://github.com/Open-MBEE/sysml-sdk, not the release packages) has, in
`examples/queries/typescript/queries.mjs`, an evaluator in three-valued logic and complete queries:
reachable states with shortest trigger sequences, bill of materials, attribute roll-up,
connectivity, requirement checks. Where it is at hand, start from it for such questions; the recipes
above cover the simple cases.

## Other differences from the specification

- **With the library loaded**, `usage`/`feature` (in a payload) include library features (`self`,
  `start`, `subparts`, ...): filter with `isLibraryElement`. A flow's `connectorEnd` also lists the
  library flow's ends; use `ends`.
- The second operand of `and`/`or`/`implies` is the operand expression itself, not the
  `FeatureReferenceExpression` to it that the specification builds. Accept both.
- An unnamed `satisfy` has no `name`, but a qualified-name lookup may still find it under the name
  of the requirement it satisfies. A feature named only through what it redefines has `name` from it
  and `declaredName` null (a satisfy's subject parameter is named `subj`, although it redefines the
  subject of the requirement's definition). Display `name`; test `declaredName` for what was
  written.
- `mayTimeVary`, `isVariable` and `isConstant` on usages throw `NotImplementedInToolkit`.
- In the SysML Toolkit's export, an alias (`alias ax for x;`) hides the membership of the feature it
  names from what specializations inherit, and a conjugated port's `portDefinition` is the
  `ConjugatedPortDefinition` (`~PowerPort`), as the specification says.
- A payload answers what its writer wrote: stand-ins where the writer had no value (null, `false`,
  `[]`), and `UnresolvedReference` for references into the standard
  library unless it was given the library JSON.

## Verify

- Run the same query through the SysML Toolkit (with the helpers) and on its export as a payload
  (the plain derived properties), matching elements by `$id`; differences point at the
  SysML Toolkit, the export, or your code.
- Work out a few answers by hand and assert them.
- For more examples: the guide and runnable tutorial (`examples/typescript/`) and the query examples
  (`examples/queries/typescript/`) in the SDK repository.
