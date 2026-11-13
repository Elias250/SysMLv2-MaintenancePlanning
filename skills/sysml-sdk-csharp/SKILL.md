---
name: sysml-sdk-csharp
description: Writes C# (.NET 8) code that reads, navigates and queries SysML v2 and KerML models with the OpenMBEE.SysML NuGet package, through the OpenMBEE SysML Toolkit (a native binding library), the SysML v2 Pilot Implementation, or a full-form interchange JSON payload. Use when a task involves loading .sysml/.kerml files or SysML v2 JSON in C#, walking parts, features, states, connections or requirements, evaluating a model's expressions, or answering questions about a SysML v2 model with code.
---

# SysML v2 SDK for C#

The SDK is the OMG metamodel as C# interfaces with default members: every KerML and SysML
metaclass, property and operation, under its specification name, with the metaclass hierarchy as
interface inheritance. A model comes from one of three backends:

- **the SysML Toolkit**, through its native binding library (P/Invoke): reads SysML text, resolves
  names, computes derived properties and evaluates operations, and refuses what it cannot derive
  completely;
- **the SysML v2 Pilot Implementation**, run in a Java process: reads the text too, and computes
  every property and operation with its own code;
- **a payload**: a full-form interchange JSON export from any SysML v2 tool, pure .NET.

Besides the specification's members, the interfaces have `Find` convenience members (`FindParts()`,
`FindPartDefs()`, `FindValue()`, ...) for what takes several steps in the specification.

The SDK never guesses. A member the SysML Toolkit does not answer throws
`NotImplementedInToolkitException` with the reason the SysML Toolkit gives; a reference that does
not resolve throws `UnresolvedReferenceException`. Never catch these to substitute a made-up
value; read around them as described below, or report them.

## Setup

```sh
dotnet add package OpenMBEE.SysML --version 0.2.0 --source <folder with the .nupkg>
```

`--source` is not saved in the project; for later restores (another machine, a cleared cache), add
a `nuget.config` beside the project:

```xml
<configuration>
  <packageSources>
    <add key="sysml-sdk" value="path/to/folder-with-the-nupkg" />
  </packageSources>
</configuration>
```

- The package carries the binding library for Windows x64, Linux x64, and macOS on
  Apple silicon and on Intel; .NET puts the one for the running platform beside the program, where
  `ToolkitBackend.DefaultLibrary` finds it. To use another build, set `SYSMLV2_ABI` to it, or name it
  in code with `new ToolkitBackend.Library(path)` in place of `ToolkitBackend.DefaultLibrary` (one
  per process; it is not disposable).
- The package also carries the standard library models.

**Initialize first: get the standard library.** Nearly every model refers to it (`ScalarValues::Real`,
`ISQ::mass`, and implicitly `Parts::parts`, `Items::items`, ...). Do this once, at the start of the
program, before loading any model:

```csharp
var libraryDir = StandardLibrary.Directory();   // the models the package carries (copied out to the user cache once)
var libraryJson = StandardLibrary.Json();       // the library as JSON, for a payload's PayloadLibrary
```

`StandardLibrary.Json()` downloads the JSON from the SDK's GitHub release on its first call (checked
against the SHA-256 GitHub states, kept in the user cache; later calls read the cache) and throws
`LibraryUnavailableException` with instructions when it cannot. Offline, `SYSML_LIBRARY_JSON` names a
copy (the `sysml.library.full.json` of the release's `sysml_library-0.2.0.zip`). Call only the one
the chosen backend needs.

Costs: opening a model with the standard library takes one to three seconds; the SysML Toolkit's
JSON export of a model takes a few seconds; the library JSON is about 160 MB and takes a few seconds
to read (read it once). A model file that does not exist throws `FileNotFoundException`, a library
directory `DirectoryNotFoundException`; a model that does not load throws an `SdkException` with a
status, and the SysML Toolkit's reason (a parse error) is printed on stderr.

## Loading a model

Through the SysML Toolkit:

```csharp
using OpenMBEE.SysML;
using SpecType = OpenMBEE.SysML.Type;      // the metaclass Type, beside System.Type

using var toolkit = ToolkitBackend.Open(ToolkitBackend.DefaultLibrary,   // the package's binding library, or SYSMLV2_ABI's
    new[] { "model.sysml" },                          // your files; Array.Empty<string>() with sources
    null,                                             // or in-memory sources: new Dictionary<string, string> { ["m.sysml"] = text }
    libraryDir);                                      // the standard library, from the initialization
var model = new Model(toolkit);                       // the session closes when `toolkit` is disposed
```

From a payload (a JSON export you have):

```csharp
using OpenMBEE.SysML;
using SpecType = OpenMBEE.SysML.Type;

var library = PayloadLibrary.FromJson(File.ReadAllText(libraryJson));  // once, share it
var model = Model.FromFullJson(File.ReadAllText("model.json"), library);
```

The code here assumes the implicit usings `dotnet new console` turns on (`System`, `System.IO`,
`System.Linq`, `System.Collections.Generic`, ...). Load the standard library whenever the model uses
it, which nearly every model does (`ScalarValues::Real`, `ISQ::mass`, and implicitly
`Parts::parts`). Without it, references into the library stay unresolved: harmless until you read
one, then `UnresolvedReferenceException`. (`ToolkitBackend.Open("a.sysml", "b.sysml")` and
`ToolkitBackend.OpenSources(sources)` open without it.) Relative paths are relative to the working
directory. Element ids depend on the file names given. With sources given, paths are ignored.

A payload refers to the standard library's elements without containing them; pass the library JSON
and those references resolve. Library elements are not the model's (`All()`, `Roots()`,
`ElementsOfType<T>()` skip them); a qualified name is looked up in the payload first. The library
JSON lists each library element's own members only, not what it inherits.

Through the SysML v2 Pilot Implementation, which runs in a Java process:

```csharp
using var pilot = PilotBackend.Open(new[] { "model.sysml" });   // or OpenSources(new Dictionary<...>)
var model = new Model(pilot);
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
  raises `BackendException`.

## The shape of the API

- **Find:** `model.Resolve("Pkg::Part::feature")` returns `IElement?`: cast it
  (`(PartDefinition)model.Resolve(...)!`). `model.ElementsOfType<PartUsage>()` (subclasses
  included), `model.All()`, `model.Roots()` (top-level namespaces; the packages are their
  `ownedMember`). `model.Resolve` is the SysML Toolkit's own name lookup: it also finds inherited
  members and members of a feature's type (`"EBikes::CargoEBike::wheels"` is `Bike::wheels`), and it
  answers where the specification's `resolve` operation is refused.
- **Properties** keep the specification name, lower camel case: `el.qualifiedName`,
  `el.ownedFeature`; C# keywords are escaped (`operation.@operator`). **Operations** are methods:
  `el.effectiveName()`, `ns.resolve("Name")`; one sharing a property's name takes `Op`:
  `instantiatedTypeOp()`. Runtime members are PascalCase: `ElementId`, `MetaclassName`, `Handle`,
  `Model`, `GetRaw(prop)`.
- **Members are default interface members:** they are visible only through a variable typed as an
  interface that declares them. Keep variables typed as the metaclass (`PartUsage p`), not as a class
  or `object`.
- **Metaclass tests:** `el is PartUsage p`, `OfType<PartUsage>()`. `ConnectionUsage`,
  `InterfaceUsage` and `AllocationUsage` are `PartUsage`s too (`FlowUsage` is not); every connector,
  connections, flows, successions and bindings alike, is a `ConnectorAsUsage`. A definition's
  `ownedPart` therefore lists its connections too.
- **Every element** (`IElement`) has the members of `Element`: `name`, `declaredName`,
  `qualifiedName`, `owner`, `owningNamespace`, `documentation`, `isLibraryElement`,
  `effectiveName()`.
- **Values:** multi-valued properties are `IReadOnlyList<T>` (empty when absent); single-valued ones
  nullable: `bool?` (test `== true`), `long?` for Integer, `double?` for Real, `string?` (enumeration
  values are lowercase strings: `"requirement"`). `sourceFeature` is one feature, `targetFeature` a
  list. An unnamed element has `name` null.
- **Identity:** within one model, `Equals`/`GetHashCode` go by element id, so elements work in
  `HashSet`/`Dictionary`. The same element read through two models (the SysML Toolkit's and its
  export's) is not `Equals`: compare their `ElementId`s.
- **Errors:** `NotImplementedInToolkitException`, `UnresolvedReferenceException`, `GoneException`,
  all `SdkException`s. An operation argument that must be an element and is null throws
  `ArgumentException`.
- **Operations** need the SysML Toolkit (a payload throws for every one) and take the
  specification's parameters in order, as the interfaces declare them
  (`inheritedMemberships(excludedNamespaces, excludedTypes, excludeImplied)`). The SysML Toolkit has
  a body for about a third of them and answers a call only where its evidence for the model is
  complete. Answered on a typical model: `effectiveName()` (not on every unnamed feature),
  `effectiveShortName()`, `resolveGlobal`, `supertypes(true)` (the argument is `excludeImplied`),
  `evaluate(target)` (target: the element to evaluate in, such as the part usage, never null; it
  returns elements, such as the literal a feature is bound to), `modelLevelEvaluable`. Refused
  there: `resolve`, `resolveLocal`, `resolveVisible`, `visibleMemberships`, `namesOf`,
  `inheritedMemberships`, `supertypes(false)`. No body at all: `isCompatibleWith`, `specializes`,
  `allSupertypes`, `directionOf`, ... Catch the refusal.

## Convenience members

Besides the specification's members, the interfaces have `Find` members (312), each defined by the
SDK over the specification's properties and operations; every one has its definition as XML
documentation. Use one wherever it answers: one call instead of a walk.

```csharp
d.FindParts();                       // the part usages d owns (a connection is a part too)
d.FindPartsExact();                  // exactly PartUsage; d.FindPart("engine"): by name, or null
d.FindParts(Scope.All);              // owned, then inherited; Scope.Inherited: inherited only
d.FindPartsSemantic();               // the features typed by a part definition
pkg.FindPartDefs();                  // the part definitions a namespace owns; FindPartDef(name)
pkg.FindPartDefsByName();            // a dictionary from every name and short name to its definition
pkg.FindPartDefs().FindPorts();      // a list carries its elements' members (extension methods)
feature.FindDeclaredTypes();         // the types as written; t.FindDeclaredSupertypes()
feature.FindRedefinitionRoot();      // the feature its written redefinitions start from
feature.FindValue();                 // the value expression (=, :=, default), or null
expr.FindLiteral();                  // a Literal: IntegerValue, RealValue, BooleanValue,
                                     //   StringValue or Unbounded; AsLong(), AsDouble(), ... read it
expr.FindLiteral<long>();            // the value as the type given
t.FindLowerBound(); t.FindUpperBound();   // t's own multiplicity as a Literal; null without one
```

- The feature kinds (27): `FindAttributes`, `FindPorts`, `FindItems`, `FindActions`, `FindStates`,
  `FindConnections`, `FindRequirements`, `FindConstraints`, ... Every list takes `scope`,
  `visibility` (`VisibilityFilter.Public`, `Protected`; `Any` by default) and `library` (`true`
  keeps what the standard library's types contribute, left out by default). On a namespace:
  `Find<Kind>Defs()`, `Find<Kind>Def(name)`, `Find<Kind>DefsByName()`, and the usages it has through
  any membership, `FindMember<Kinds>()`.
- Also: `FindSubsettedFeatures()`, `FindRedefinedFeatures()`, `FindReferencedFeature()`,
  `FindEffectiveFeature(f)`, `FindUnit()` (`1500 [kg]`: `SI::kilogram`), `FindParameters()`,
  `FindInputs()`, `FindOutputs()`, `FindInitialStates()`, `FindAcceptedTypes()`,
  `FindIsAcceptedType(t)`, `FindResultExpression()`, `FindPath()`, `FindAppliedMetadata()`,
  `FindDocText()`.
- `RefusedException` (a `NotAnsweredException`): the member's definition gives no answer for this
  element (`FindLiteral()` of `2 * x`, or of a value with a unit). `NotAnsweredException`: the
  backend cannot answer something the member reads, named in the message
  (`NotImplementedInToolkitException` from the SysML Toolkit).
- **On the Pilot Implementation** every member answers.
- **On the SysML Toolkit**, the members answer: every list, lookup and exact list in the owned scope;
  the definition lists and name maps of a package; the types, supertypes, subsettings and
  redefinitions as written; values, unsigned literals and own bounds; paths, metadata and
  documentation. They are refused, with the reason: the inherited scope and `Scope.All` of feature
  and member lists and the semantic lists (`specializes()`), `FindEffectiveFeature`, the implied
  supertypes, `FindParameters`, `FindInputs` and `FindOutputs` (`directionOf()`), the accepted types
  (`payloadParameter`), `FindInitialStates`, `FindResultExpression`, and a literal with a sign or a
  unit (`argument`). For those, use the helpers below: `FeaturesWithInherited`, `AcceptedTypes`,
  `InitialStates`, `Number`.
- `FindLowerBound()`/`FindUpperBound()` read the type's own multiplicity only; for SysML's default
  and the multiplicity a usage takes from what it redefines, use `MultiplicityOf` below.
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
  enumeration values, and `type` on some parameters and reference usages (use `TypesOf` below
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
copy them as they are: static local functions in a top-level program, or static methods of a class).
`isImplied` marks the relationships the SysML Toolkit adds from the library, which the model does
not write.

```csharp
// The features a feature redefines or subsets as the model writes them (ownedSubsetting holds the
// redefinitions too; isImplied marks what the SysML Toolkit adds from the library).
static List<Feature> WrittenGenerals(Feature feature) =>
    feature.ownedSubsetting.Where(s => s.isImplied != true).Select(s => s.subsettedFeature!).ToList();

// A definition's supertypes as the model writes them, without the library ones the SysML Toolkit
// implies (Parts::Part for a part definition).
static List<Classifier> WrittenSupertypes(Classifier definition) =>
    definition.ownedSubclassification.Where(s => s.isImplied != true).Select(s => s.superclassifier!).ToList();

// A feature's types: type where the SysML Toolkit answers it; else its own typings; else those of
// the features it redefines or subsets as written (`part :>> battery[2];`).
static IReadOnlyList<SpecType> TypesOf(Feature feature)
{
    try { return feature.type; } catch (NotImplementedInToolkitException) { /* read around it */ }
    var own = feature.ownedTyping.Select(t => t.type!).ToList();
    if (own.Count > 0) return own;
    foreach (var general in WrittenGenerals(feature))
        if (TypesOf(general) is { Count: > 0 } found) return found;
    return Array.Empty<SpecType>();
}

// t's own features, then those it inherits along what the model writes (a definition's
// supertypes; a usage's types and the usages it redefines or subsets), without the ones redefined
// on the way. The model's own features, not the library's; not the specification's full
// derivation (no visibility, no imports).
static List<Feature> FeaturesWithInherited(SpecType t, HashSet<IElement>? seen = null)
{
    seen ??= new HashSet<IElement>();
    if (!seen.Add(t)) return new List<Feature>();
    var own = t.ownedFeature.ToList();
    var redefined = own.SelectMany(o => o.ownedRedefinition).Select(r => r.redefinedFeature!).ToHashSet();
    IEnumerable<SpecType> bases = t is Classifier c ? WrittenSupertypes(c)
        : t is Feature feature ? TypesOf(feature).Concat(WrittenGenerals(feature))
        : Enumerable.Empty<SpecType>();
    foreach (var b in bases)
        foreach (var inherited in FeaturesWithInherited(b, seen))
            if (!redefined.Contains(inherited) && !own.Contains(inherited)) own.Add(inherited);
    return own;
}

// The feature that stands for `feature` in `context`: `feature` itself where the context inherits
// it, or the nearest one that redefines it, directly or through other redefinitions; null where the
// context has neither (pass the declaration, `Component::mass`, not a redefinition in some other
// definition).
static Feature? FeatureIn(SpecType context, Feature feature)
{
    static bool Redefines(Feature f, Feature target, HashSet<IElement> seen) =>
        f.ownedRedefinition.Any(r => r.redefinedFeature!.Equals(target)
            || (seen.Add(r.redefinedFeature!) && Redefines(r.redefinedFeature!, target, seen)));
    return FeaturesWithInherited(context).FirstOrDefault(x => x.Equals(feature) || Redefines(x, feature, new HashSet<IElement> { x }));
}

// The expression that gives `feature` its value in `context` (`attribute :>> mass = 2.5;` in the
// context's definition or body), or null. Initial values (`:=`) and defaults (`default =`) count
// too; the FeatureValue's isInitial / isDefault tell them apart.
static Expression? BoundValue(SpecType context, Feature feature) =>
    FeatureIn(context, feature)?.ownedMembership.OfType<FeatureValue>().FirstOrDefault()?.value;

// The feature a chain of written redefinitions starts from (`Frame::mass` -> `Unit::mass`): the
// declaration to pass to BoundValue and FeatureIn.
static Feature DeclarationOf(Feature feature)
{
    var seen = new HashSet<IElement> { feature };
    while (feature.ownedRedefinition.FirstOrDefault(r => r.isImplied != true)?.redefinedFeature is { } next && seen.Add(next))
        feature = next;
    return feature;
}

// (lower, upper) of a MultiplicityRange with literal bounds; upper null for `*`. `[4]` has only an
// upper bound: lower = upper then. A bound that is an expression (`[rotorCount]`) throws.
static (long? Lower, long? Upper) Bounds(MultiplicityRange range)
{
    static long? Literal(Expression? e) => e switch
    {
        LiteralInfinity => null,
        LiteralInteger i => i.value,
        _ => throw new InvalidOperationException($"a bound to evaluate in context: {e?.MetaclassName}"),
    };
    var upper = Literal(range.upperBound);
    return (range.lowerBound is null ? upper : Literal(range.lowerBound), upper);
}

// (lower, upper) of the multiplicity that applies to a usage: its own; else, nearest first, that
// of the features it redefines or subsets as written; else (1, 1) where SysML gives the default (an
// attribute, item, part or port usage, not a connection, owned by a definition or usage); else
// (0, null), unconstrained.
static (long? Lower, long? Upper) MultiplicityOf(Feature usage)
{
    var seen = new HashSet<IElement> { usage };
    var todo = new Queue<Feature>(new[] { usage });
    while (todo.Count > 0)
    {
        var u = todo.Dequeue();
        if (u.multiplicity is MultiplicityRange range) return Bounds(range);
        var generals = WrittenGenerals(u);
        if (generals.Count == 0)
        {
            var kind = (u is AttributeUsage || u is ItemUsage || u is PortUsage) && u is not ConnectionUsage;   // a PartUsage is an ItemUsage
            var owned = u.owningType is Definition || u.owningType is Usage;
            return kind && owned ? (1, 1) : (0, null);
        }
        foreach (var g in generals) if (seen.Add(g)) todo.Enqueue(g);
    }
    return (0, null);
}

// A connector's ends in order, the source first: the features or feature chains it connects. For
// connections, flows, successions and bindings alike.
static List<Feature> Ends(Connector connector)
{
    try { return new[] { connector.sourceFeature }.OfType<Feature>().Concat(connector.targetFeature).ToList(); }
    catch (NotImplementedInToolkitException) { /* read around it */ }
    return connector.ownedFeature.Where(e => e.isEnd == true && e.ownedReferenceSubsetting != null)
        .Select(e => e.ownedReferenceSubsetting!.referencedFeature!).ToList();
}

// A feature chain as its features ([battery, powerOut] for battery.powerOut); else [feature].
static IReadOnlyList<Feature> PathOf(Feature feature) =>
    feature.chainingFeature.Count > 0 ? feature.chainingFeature : new[] { feature };

// What an accept action accepts (a transition's triggerAction[0]): its payload's types.
static IReadOnlyList<SpecType> AcceptedTypes(AcceptActionUsage accept)
{
    try { return accept.payloadParameter?.type ?? Array.Empty<SpecType>(); }
    catch (NotImplementedInToolkitException) { /* read around it */ }
    return TypesOf(accept.ownedMembership.OfType<ParameterMembership>().First().ownedMemberParameter!);
}

// What satisfies the requirement in `satisfy r by x;`: x.
static Feature? SatisfyingFeature(SatisfyRequirementUsage satisfy)
{
    try { return satisfy.satisfyingFeature; } catch (NotImplementedInToolkitException) { /* read around it */ }
    var subject = satisfy.ownedMembership.OfType<SubjectMembership>().First().ownedSubjectParameter!;
    return (subject.ownedMembership.OfType<FeatureValue>().First().value as FeatureReferenceExpression)?.referent;
}

// The subject parameter of a requirement or requirement definition: its own `subject`; else,
// nearest first, that of its definitions or of what it specializes as written; else null.
static Usage? SubjectOf(SpecType requirement)
{
    try
    {
        if (requirement is RequirementUsage ru) return ru.subjectParameter;
        if (requirement is RequirementDefinition rd) return rd.subjectParameter;
    }
    catch (NotImplementedInToolkitException) { /* read around it */ }
    var own = requirement.ownedMembership.OfType<SubjectMembership>().FirstOrDefault();
    if (own != null) return own.ownedSubjectParameter;
    IEnumerable<SpecType> bases = requirement is Classifier c ? WrittenSupertypes(c)
        : requirement is Feature f ? TypesOf(f).Concat(WrittenGenerals(f))
        : Enumerable.Empty<SpecType>();
    foreach (var b in bases)
        if (SubjectOf(b) is { } found) return found;
    return null;
}

// The states a state machine (a StateUsage or StateDefinition) starts in, as FindInitialStates
// defines them: the targets of its successions from the library's `start` (`first start then
// off;`), and only where there are none, from its entry action (`entry; then off;`).
static List<StateUsage> InitialStates(SpecType machine)
{
    var entry = machine is StateUsage su ? su.entryAction : machine is StateDefinition sd ? sd.entryAction : null;
    var fromStart = new List<StateUsage>();
    var fromEntry = new List<StateUsage>();
    foreach (var f in machine.ownedFeature)
    {
        if (f is not SuccessionAsUsage s) continue;
        var e = Ends(s);
        if (e.Count != 2 || e[1] is not StateUsage next) continue;
        if (e[0].isLibraryElement == true && e[0].name == "start") fromStart.Add(next);
        else if (entry != null && entry.Equals(e[0])) fromEntry.Add(next);
    }
    return fromStart.Count > 0 ? fromStart : fromEntry;
}

// The states of a state machine reachable from its initial states along its own transitions, in the
// order found (guards and triggers not considered; the transitions inside composite states not
// followed).
static List<StateUsage> ReachableStates(SpecType machine)
{
    var next = machine.ownedFeature.OfType<TransitionUsage>().Where(t => t.source != null)
        .GroupBy(t => (IElement)t.source!).ToDictionary(g => g.Key, g => g.Select(t => t.target).ToList());
    var reached = InitialStates(machine);
    for (var i = 0; i < reached.Count; i++)
        if (next.TryGetValue(reached[i], out var targets))
            foreach (var n in targets)
                if (n is StateUsage s && !reached.Contains(s)) reached.Add(s);
    return reached;
}

// The number an expression stands for when it is a literal, or a sign applied to one (`-40.0` is an
// OperatorExpression `-` whose operand is the literal 40.0). Anything else throws: evaluate it in
// context (the SysML Toolkit's evaluate refuses operator expressions).
static double Number(Expression expr)
{
    switch (expr)
    {
        case LiteralInteger i: return i.value!.Value;
        case LiteralRational r: return r.value!.Value;
        case OperatorExpression op when op.@operator is "-" or "+":
            // The operands' parameters through the owned relationships: the SysML Toolkit refuses an
            // operator expression's ownedFeature in this release.
            var operands = op.ownedRelationship.OfType<ParameterMembership>().SelectMany(r => r.ownedRelatedElement.OfType<Feature>())
                .SelectMany(f => f.ownedMembership.OfType<FeatureValue>()).Select(v => v.value!).ToList();
            if (operands.Count == 1) return op.@operator == "-" ? -Number(operands[0]) : Number(operands[0]);
            break;
    }
    throw new InvalidOperationException($"not a literal number: {expr.MetaclassName}");
}
```

**2. Query the SysML Toolkit's export as a payload** when a question needs the specification's full
derivation across a whole model (inherited members with visibility and imports, connector ends of
library connections). The export is written by the SysML Toolkit's compatibility path: it carries a
value for every property, including the ones the checked reader refuses, which the SysML Toolkit
does not vouch for. Say so in your answer when the result depends on them.

```csharp
var library = PayloadLibrary.FromJson(File.ReadAllText(StandardLibrary.Json()));  // once
var exported = Model.FromFullJson(toolkit.FullJson(), library);   // same element ids as the SysML Toolkit's
```

**3. Never** substitute an empty list, a guess or a default for a refused read.

## Navigation recipes

With the helpers above; each works through the SysML Toolkit and on a payload.

```csharp
// d, part, port, usage, flow, machine and constraint stand for elements you have at hand (d: a
// definition or usage, as a SpecType); model is the Model.

// Parts of a definition or usage, owned and inherited, not connections; the model's own, not the
// library's (start, done, subparts, ...)
var parts = FeaturesWithInherited(d).OfType<PartUsage>().Where(p => p is not ConnectionUsage).ToList();

var definitions = TypesOf(part);                       // what a usage is typed by

// The value a feature has in a context (`attribute :>> mass = 2.5;` in the part's definition or body)
var massF = (Feature)model.Resolve("Pkg::Component::mass")!;   // the declaration; DeclarationOf(f) finds it from a redefinition
var expr = BoundValue(part, massF);                    // an Expression, or null
var mass = Number(expr!);                             // a literal, or a sign applied to one (-40.0)

var (lower, upper) = MultiplicityOf(usage);            // (2, 2) for [2]; (1, 1) by default; upper null for *
var text = lower == upper ? $"[{lower}]" : $"[{lower}..{(upper is null ? "*" : upper.ToString())}]";

// Roll-up: an attribute summed over a definition's direct parts (mass, cost, power); for a deeper
// tree, apply it to each part that has parts of its own (FeaturesWithInherited(p))
double total = 0;
var missing = new List<string?>();
foreach (var p in parts)
{
    var e = BoundValue(p, massF);
    var (lo, hi) = MultiplicityOf(p);
    if (e is null || hi is null || lo != hi) missing.Add(p.name);   // no value, or a range ([4..6], *): report, never guess
    else total += Number(e) * lo!.Value;
}

// Ports: the definition, and whether it is conjugated (`port p : ~PowerPort;`). portDefinition
// (a list) is refused; isConjugated is false on a `~` port: the conjugation is its type, the
// ConjugatedPortDefinition that PowerPort owns (name "~PowerPort", qualified name
// "Pkg::PowerPort::'~PowerPort'", quotes included)
foreach (var t in TypesOf(port))
    Console.WriteLine(t is ConjugatedPortDefinition c ? "~" + c.originalPortDefinition!.qualifiedName : t.qualifiedName);

// Connections (ConnectionUsage: connect, interfaces, allocations): the ends, the source first. The
// ends of an inherited connection are the supertype's features (Drone::rotors, not a redefining
// `part :>> rotors[8];`): FeatureIn(d, PathOf(end)[0]) is the one that stands for it in d
foreach (var c in FeaturesWithInherited(d).OfType<ConnectionUsage>())
{
    Console.WriteLine(string.Join(" -> ", Ends(c).Select(e => string.Join(".", PathOf(e).Select(f => f.name)))));
    var portTypes = Ends(c).Select(e => TypesOf(PathOf(e)[^1])).ToList();   // per end: [PortDefinition or ConjugatedPortDefinition]
}
// Flows (FlowUsage), bindings (BindingConnectorAsUsage) and successions are ConnectorAsUsage too,
// with the same Ends()
var items = ((FlowUsage)flow).payloadType;             // the flowing item's definition

// States
var machine = (StateUsage)model.Resolve("Pkg::Controller::modes")!;   // e.g. an ExhibitStateUsage
var states = machine.nestedState;                      // its own states
var initial = InitialStates(machine);                  // `first start then off;`, else `entry; then off;`
var reachable = ReachableStates(machine);              // from the initial states along the transitions
foreach (var t in machine.nestedTransition)            // t.guardExpression
{
    ActionUsage from = t.source!, to = t.target!;      // the states (cast to StateUsage); a
    // transition from the entry action leaves an action, not a state: no cast then
    var signals = t.triggerAction.Count > 0 ? AcceptedTypes(t.triggerAction[0]) : Array.Empty<SpecType>();
    var timeOrChange = t.triggerAction.Count > 0 ? t.triggerAction[0].payloadArgument : null;   // TriggerInvocationExpression for at/when
}

// Requirements
foreach (var s in model.ElementsOfType<SatisfyRequirementUsage>())
{
    var req = s.satisfiedRequirement!;                 // the requirement usage
    var by = SatisfyingFeature(s);                     // the part that satisfies it
    var definition = TypesOf(req);                     // [RequirementDefinition]
    var subject = SubjectOf(req);                      // its subject parameter, or null; often the definition's
                                                       // (`subject bike : Bike;` in MassLimit: MassLimit::bike)
    var limitF = TypesOf(req).SelectMany(t => FeaturesWithInherited(t)).First(f => f.name == "maxMass");
    var limit = BoundValue(req, limitF);               // the requirement's value for its definition's maxMass
    var constraints = req.ownedMembership.OfType<RequirementConstraintMembership>()    // its own constraints
        .Where(m => m.kind == "requirement").Select(m => m.ownedConstraint).ToList();
}
var body = constraint.ownedMembership.OfType<ResultExpressionMembership>().First().ownedResultExpression;
```

## Multiplicity

`multiplicity` is only what the usage itself declares; `MultiplicityOf` above applies SysML's rule:
a usage without one takes the multiplicity of the features it redefines or subsets as written
(nearest first; `part :>> battery[2];` declares its own), and one that redefines or subsets nothing
is `[1..1]` if it is an attribute, item, part or port usage owned by a definition or usage, and
unconstrained (`[0..*]`) otherwise. Implied subsettings (`isImplied`, such as every part's
subsetting of the library's `parts`) do not count. A bound may be an expression to evaluate in
context (`Rotor[rotorCount]`); `Bounds` throws for it.

## Evaluating the model's expressions

Expressions are elements: `OperatorExpression` (`@operator` such as `"<="`, `"and"`, `"not"`;
`argument`), `FeatureReferenceExpression` (`referent`), `FeatureChainExpression` (`a.b`:
`argument[0]` is `a`, `targetFeature` is `b`; it is an OperatorExpression too, so match it first),
literals with `value` (`LiteralInteger` `long?`, `LiteralRational` `double?`, `LiteralBoolean`,
`LiteralString`, `LiteralInfinity` for `*`), `TriggerInvocationExpression` (`kind`: `at`, `after`,
`when`). An enumeration literal is an `EnumerationUsage` whose `owningNamespace` is the
`EnumerationDefinition` (its `owningType` is null, by the specification). Through the SysML Toolkit,
`argument` is refused: an expression's operands are its `ownedFeature`s, each bound by a
`FeatureValue` in its `ownedMembership`.

The SysML Toolkit's `evaluate(target)` operation evaluates some expressions (it returns elements);
beyond that, the SDK does not evaluate. The SDK's source repository
(https://github.com/Open-MBEE/sysml-sdk, not the release packages) has, in
`examples/queries/csharp/Queries.cs`, an evaluator in three-valued logic and complete queries:
reachable states with shortest trigger sequences, bill of materials, attribute roll-up,
connectivity, requirement checks. Where it is at hand, start from it for such questions; the recipes
above cover the simple cases.

## Other differences from the specification

- **With the library loaded**, `usage`/`feature` (in a payload) include library features: filter
  with `isLibraryElement`. A flow's `connectorEnd` also lists the library flow's ends; use `Ends`.
- The second operand of `and`/`or`/`implies` is the operand expression itself, not the
  `FeatureReferenceExpression` to it that the specification builds. Accept both.
- An unnamed `satisfy` has no `name`, but a qualified-name lookup may still find it under the name
  of the requirement it satisfies. A feature named only through what it redefines has `name` from it
  and `declaredName` null (a satisfy's subject parameter is named `subj`, although it redefines the
  subject of the requirement's definition).
- `mayTimeVary`, `isVariable` and `isConstant` on usages throw `NotImplementedInToolkitException`.
- In the SysML Toolkit's export, an alias (`alias ax for x;`) hides the membership of the feature it
  names from what specializations inherit, and a conjugated port's `portDefinition` is the
  `ConjugatedPortDefinition` (`~PowerPort`), as the specification says.
- A payload answers what its writer wrote: stand-ins where the writer had no value (null, `false`,
  an empty list), and `UnresolvedReferenceException` for references
  into the standard library unless it was given the library JSON.

## Verify

- Run the same query through the SysML Toolkit (with the helpers) and on its export as a payload
  (the plain derived properties), matching elements by `ElementId`; differences point at the
  SysML Toolkit, the export, or your code.
- Format with `CultureInfo.InvariantCulture` and sort names with `StringComparer.Ordinal`, so output
  does not depend on the machine's culture.
- For more examples: the guide and runnable tutorial (`examples/csharp/`) and the query examples
  (`examples/queries/csharp/`) in the SDK repository.
