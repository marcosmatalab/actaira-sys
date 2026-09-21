<div align="center">

# Actaira

**Regulation (EU) 2024/1689 and ISO/IEC 42001, checked by reading your repository.**

With provenance per claim, and without inventing a percentage.

[![Gate](https://github.com/marcosmatalab/actaira-sys/actions/workflows/ci.yml/badge.svg)](https://github.com/marcosmatalab/actaira-sys/actions/workflows/ci.yml)
[![Version](https://img.shields.io/github/v/tag/marcosmatalab/actaira-sys?label=version&color=90099C)](docs/CAMBIOS.md)
[![Licence](https://img.shields.io/badge/licence-Apache--2.0-90099C)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-Python%20and%20Go-90099C)](motor/tests)
[![Acceptance gate](https://img.shields.io/badge/gate-make%20todo-90099C)](herramientas/todo.py)

<img src="docs/imagenes/panel.gif" width="680" alt="The Actaira panel: what binds you, what was checked by reading bytes, what is left to answer, the technical file, the search box and the six languages.">

<sub>Thirty seconds against the real API and the example repository. None of
this is staged: it is recorded by one command, and that same command is the
gate that checks the screen works.</sub>

**[Full user manual](docs/MANUAL.en.md)** · **[Castellano](README.md)**

</div>

---

## The problem

A compliance consultancy hands you a risk map, a controls matrix and a
three-hundred-question survey. All three describe what your organisation
**says** it does. None of them looks at your code.

The Regulation is not written that way. Article 12 asks that the system
**automatically record** events over its lifetime. Article 14 asks that a person
**be able to intervene**. Article 15 asks for a level of accuracy that is
**maintained**. Those are properties of a program, and a program can be read.

Actaira reads the repository, decides what can be decided by reading bytes, and
says out loud what it cannot decide.

## The four refusals

They are not aspirations: they are invariants with gates holding them up, and
each one has its test.

| | |
|---|---|
| **Never a number** | There is no «87 % compliant» and there never will be. Counts of obligations are published, never proportions. |
| **Never judge, only cite** | Seeing `verify_signature` in the code is seeing a pattern, not knowing a measure has been adopted. A person signs the interpretation. |
| **Never infer the unobserved** | An `INDETERMINADO` with no written reason is a `NO_CUMPLE` in disguise. If it could not be looked at, it says what and why. |
| **Never act on what was observed** | Actaira says what must be looked at again. Whether that blocks a deployment is your call, in your own CI file, where the decision gets reviewed. |

## What it does, in four commands

```bash
pip install git+https://github.com/marcosmatalab/actaira-sys

actaira plan .      --rol proveedor --alto-riesgo si   # what binds you, and what was checked
actaira preguntar . --rol proveedor --alto-riesgo si   # what must be asked of you, and what need not
actaira anexo .     --rol proveedor --alto-riesgo si   # Annex IV, with provenance per section
actaira soa .       --rol proveedor --alto-riesgo si   # the ISO 42001 statement of applicability
```

> It installs from the repository and not from PyPI because **it is not
> published on PyPI yet**, and saying `pip install actaira-motor` would send you
> to a 404 on the very first command. When it is published, that will be the
> line and this note disappears. A gate checks it: while `PUBLICADO_EN_PYPI` is
> `False`, no document may say otherwise.

> **The verbs, the flags and the values are Spanish words**, and that is a
> decision: the engine emits this same vocabulary *inside* the documents it
> produces, so two runs of the same thing compare line by line. A second set of
> English spellings would be two names for one verb, which is the failure this
> tree has already hit four times. `si` means yes, `no` means no, `preguntar`
> means ask, `--alto-riesgo` means high-risk — and the
> [manual glosses every one of them](docs/MANUAL.en.md#the-vocabulary-is-spanish-and-it-stays-that-way).
> A wrong value is rejected loudly, never quietly.

Needs Python 3.12 or later. None of this uploads your code anywhere and no
account is required: it runs with the network unplugged.

The **[user manual](docs/MANUAL.en.md)** covers all of it: every command, every
button, every state, and the step-by-step start.

## The platform

The engine is an executable and that is enough on its own. On top of it sits a
Go server that exposes it over HTTP, and a panel of
<!--cifra:vistas_del_panel-->11<!--/cifra--> views in
<!--cifra:idiomas-->6<!--/cifra--> languages that **computes nothing**: every
number it shows arrives inside the document the engine emitted, and so does
every sentence explaining it.

<img src="docs/imagenes/panel.png" alt="The whole panel: product category, the cycle with its counts, the profile and the answer.">

At the top, the product category and the cycle. They do not change what the
engine says: they change what you ask it for and what you see first, which is
the only thing a commercial category has any right to change.

<table>
<tr>
<td width="50%"><img src="docs/imagenes/panel-plan.png" alt="The plan: obligation by obligation, with its state and its remediation."></td>
<td width="50%"><img src="docs/imagenes/panel-cuestionario.png" alt="The questionnaire: every question states which article, which clause and which Annex A control it serves."></td>
</tr>
<tr>
<td><b>The plan.</b> Obligation by obligation: what binds you, what was checked
by reading bytes, where the finding is and what to do about it.</td>
<td><b>The questionnaire.</b> Every question declares what it serves with
identifiers from <b>all three</b> catalogues at once. One answer closes article
16, article 17, clause 5.3 and control A.3.2.</td>
</tr>
<tr>
<td><img src="docs/imagenes/panel-soa.png" alt="The ISO 42001 statement of applicability, control by control."></td>
<td><img src="docs/imagenes/panel-anexo-iv.png" alt="Annex IV, section by section, each one saying where it came from or why it is missing."></td>
</tr>
<tr>
<td><b>The statement of applicability.</b> The
<!--cifra:controles_iso-->38<!--/cifra--> Annex A controls, each with its
justification.</td>
<td><b>The technical file.</b> Annex IV section by section, and each section
says where it came from <i>or why it is missing</i>.</td>
</tr>
</table>

In dark mode too, because that is half the screenshots anyone looks at and the
half that is usually broken:

<img src="docs/imagenes/panel-oscuro.png" width="49%" alt="The panel in dark theme.">

### The interface language and the document language

The platform speaks **Spanish, English, French, Portuguese, Italian and
German**. The engine emits normative content in **two**: Spanish and English.
This is not a limitation to be fixed by translating more — obligation titles,
reasons and remediations are written by **a person**, and machine-translating
them is exactly what this house's second refusal forbids.

So there are not two settings. **There is one, and the other is derived from
it**:

| interface in | the document arrives in |
|---|---|
| Spanish | Spanish |
| any of the other five | English, and the screen says so, in that language |

There is nowhere to pick the document language separately, and a gate checks it
by looking at the `Accept-Language` header the panel actually sends: six
interface languages, one control, and the rule above.

## The numbers

None of them is hand-written. They come from the catalogue and from the tree,
`herramientas/generar_docs.py` fills them in, and the gate fails if any goes
stale.

| | |
|---|---|
| Obligations of the Regulation | <!--cifra:obligaciones-->48<!--/cifra--> (<!--cifra:obligaciones_maquina-->13<!--/cifra--> checkable by reading bytes, <!--cifra:obligaciones_organizativa-->27<!--/cifra--> organisational) |
| ISO/IEC 42001 requirements | <!--cifra:requisitos-->88<!--/cifra--> across <!--cifra:clausulas-->32<!--/cifra--> clauses |
| Annex A controls | <!--cifra:controles_iso-->38<!--/cifra--> |
| Cross-framework pairs | <!--cifra:pares-->101<!--/cifra-->, with <!--cifra:pares_rotos-->0<!--/cifra--> broken and <!--cifra:huecos-->0<!--/cifra--> coverage gaps |
| Rules that read code | <!--cifra:reglas-->68<!--/cifra--> in <!--cifra:paquetes_de_reglas-->17<!--/cifra--> packs |
| Questions in the bank | <!--cifra:preguntas-->90<!--/cifra-->, each tied to all three catalogues |
| Tests | <!--cifra:pruebas-->563<!--/cifra--> Python + <!--cifra:pruebas_go-->98<!--/cifra--> Go |
| Acceptance gate phases | <!--cifra:fases_de_la_puerta-->25<!--/cifra--> |
| Defects from adversarial passes | <!--cifra:defectos_adversariales-->129<!--/cifra-->, each named in `docs/BACKLOG.md` |

And the number that does **not** exist: there is no compliance percentage. With
an unanswered profile, <!--cifra:indeterminadas_perfil_vacio-->48<!--/cifra-->
obligations come back unresolved and none comes back clean. There is no path
from an empty form to a green result.

## What it costs in time

Measured against the whole stack — compiled Go server, engine as a separate
process, the example repository — with a command anyone can repeat:

```bash
python herramientas/navegador.py --latencias
```

| | |
|---|---|
| Loading the panel | **21 ms** to DOM, **1 ms** response: a single <!--cifra:panel_kb-->269<!--/cifra--> KB file —fonts included— and **zero network requests** |
| Transport for one verb (HTTP + JSON) | **~4 ms** median; all 11 views add up to under 100 ms |
| The analysis itself | **9–28 ms**, depending on the verb, on the example repository |
| Starting the interpreter that runs it | **440–1,750 ms** |

That last row is **between 94 and 98 %** of the time, and it is not a defect:
**it is the boundary**. Each verb is a separate process so that the engine
answering over HTTP is exactly the same binary your auditor runs on their own
machine. The price of that guarantee is one Python start-up per request. Loading
the entire catalogue — <!--cifra:obligaciones-->48<!--/cifra--> obligations,
<!--cifra:controles_iso-->38<!--/cifra--> controls,
<!--cifra:reglas-->68<!--/cifra--> rules, 39 JSON files — costs **4 ms**, so
there is nothing to optimise there: what you would be optimising is the
interpreter.

That is also why the server carries per-client and global concurrency caps, with
`Retry-After` on rejection. A verb is not a cheap request: it is a process that
reads someone's entire repository.

## How it holds up

```bash
make todo               # the whole gate
make fase F=navegador   # just one phase
```

Every phase **asserts** something concrete and goes red if it does not hold.
Whatever cannot be measured on a given machine is declared SKIPPED with its
reason, and in CI it runs with `--sin-omitir`, where a skip is a red: if
something stops being installed, the summary cannot keep saying «0 red».

- **The matrix.** The gate runs on **Ubuntu and Windows × Python 3.12 and
  3.13**. This is not a convenience. With tests running only on Windows, the git
  connector was broken on all POSIX and its five tests were green; with Linux
  only, three verbs blew up on the cp850 code page and the traceback exited with
  the code that means «there are findings». Each defect was invisible from the
  other system.
- **The race detector.** The platform tests run under `-race`, with the engine
  installed and the fixture pointed at, and **zero skipped**: a test that skips
  is not a test that passes.
- **The browser.** One phase opens the panel in Chromium, clicks all
  <!--cifra:vistas_del_panel-->11<!--/cifra--> views against the real API and
  checks that each one paints rows — or says why not — that the six languages do
  not print `undefined`, and that the console does not emit a single error. It
  exists because the panel had **not one test that executed its JavaScript**:
  seven of the eleven views were unreachable without anything failing, and a
  `ReferenceError` that broke all eleven passed four audits in a row.
- **The contract.** <!--cifra:vistas_del_panel-->11<!--/cifra--> JSON schemas
  published in `contrato/`, checked against what the engine emits and against
  the fields the panel reads. If the engine renames a field, the gate says so
  instead of the screen going blank with nothing failing.
- **The adversarial passes.** Every phase closes with one before the next opens,
  and what turns up is written into `docs/BACKLOG.md` with its number and its
  lesson. <!--cifra:defectos_adversariales-->129<!--/cifra--> so far. The
  expensive ones were not crashes: they were plausible, false answers, which is
  the worst thing a tool headed for an auditor can emit.

And one rule that comes from needing it twice: **a new gate must be seen to
fail** against the broken code before you believe it. Writing it is not enough.
One of them was born dead because a bash heredoc turned the `\b` of its regular
expression into a literal backspace byte, and it passed green with the defect
right in front of it.

## In your continuous integration

Copy [`integraciones/github/actaira.yml`](integraciones/github/actaira.yml) into
`.github/workflows/`. Findings come out as **SARIF**, which means the Security
tab and the pull request review, with the remediation written next to them. The
finding reaches whoever can fix it, on the day they wrote the line.

The gate that blocks deployment is **commented out** in the template. There is a
test that checks it stays commented out.

### Monitoring that does not poll

Evidence is superseded by **the digest of the subject it was taken on**, not by
that subject's name. And a control's subject is exactly the files that control
reads.

> Measured on the example repository: adding one line to `datos/README.md`
> supersedes **one** of the twelve controls with evidence and leaves **eleven**
> intact. The superseded one is article 10's, the only one that reads that data
> sheet.

| alternative | what happens |
|---|---|
| digest of the whole repository | a wall of red on every typo; people learn to ignore it in two weeks |
| the control's name | nothing is ever superseded; expiry becomes a timer |

Cost consequence: polling N repositories every minute is N × 1440 runs a day.
Reacting to a push plus one expiry is on the order of how often you commit, plus
one.

## What it does NOT do

- It does not emit a compliance percentage. There is no such thing.
- It does not say you comply. It says what was checked by reading bytes, with
  which rule, of which version and by which author, and what falls outside the
  scope of that check.
- It does not close an Annex A control because a Regulation check came back
  clean: the standard asks for things the Regulation does not, and the crosswalk
  says so.
- It does not sign for you. The EU declaration of conformity is emitted with the
  word **BORRADOR** (draft) in the header while the signature of Annex V point 8
  does not exist, and there is no flag that removes it by another route: points 3
  and 4 are claims made by the provider under their sole responsibility.

## How it is built

```
catalogo/     the normative content as DATA, not as code, so a lawyer can
              review it instead of a programmer
motor/        Python. A generic control engine; the articles are JSON
plataforma/   Go. Serves the verbs over HTTP, with roles, per-client caps and
              continuous monitoring. It decides nothing: it invokes the engine
panel/        built from three pieces with `make panel`; a single page that
              opens without a server and never stores the credential anywhere
sitio/        the landing page, in six languages, with figures taken from the tree
consola/      built from the engine with `make consola`, not hand-edited
contrato/     the JSON schemas the engine promises, checked on both sides
herramientas/ the acceptance gate, the browser harness and the generators
integraciones/ SARIF and the CI template
.github/      the gate run on TWO operating systems
docs/         ARQUITECTURA.md (decisions and why), MANUAL.md / MANUAL.en.md
              (the user manual), BACKLOG.md (every adversarial pass's defects,
              each with its name) and imagenes/
```

### How these images were made

With the same harness that holds the panel up, against the real stack. There is
no staged screenshot and no invented data:

```bash
python herramientas/navegador.py --capturas    # the images in this README and the manual
python herramientas/navegador.py --gif         # the 30-second walkthrough
python herramientas/navegador.py --puerta      # and the gate that checks it works
```

**The GIF is only regenerated when the screen actually changes.** That is not
penny-pinching: a recorded video never comes out the same twice, so every
regeneration adds a new object to git history and none of them ever leave. That
is why it weighs 3 MB and not 8 — 680 px, 5 fps, 64 colours; the headline, the
categories and the cycle still read, which is what a README GIF has to show —
and why the command goes red above 5 MB. Still screenshots do not have that
problem: a PNG of the same screen comes out nearly identical and git recognises
it.

## Licence and catalogue scope

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

The text of ISO/IEC 42001:2023 is **not reproduced**: the standard is paid for.
The catalogues list identifiers, numbering and titles, and add original work —
the level of checkability, the crosswalk between frameworks, the rules and their
remediations. Regulation (EU) 2024/1689 is public and is cited by reference,
never in bulk.

The rules and the remediations were written by a person. A model may draft a
rule offline; it never writes rules or remediations at runtime.
