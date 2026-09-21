# Actaira user manual

**[Versión en castellano](MANUAL.md)** · [Back to the README](../README.en.md)

This manual covers the whole product: what each command does, what each button
does, and what everything on screen means. It is written so that someone who
has never seen Actaira can start and get all the way to the technical file
without asking anyone anything.

If you just want to try it, jump to [Start in five
minutes](#start-in-five-minutes).

---

## Contents

1. [What Actaira is, in one paragraph](#what-actaira-is-in-one-paragraph)
2. [Start in five minutes](#start-in-five-minutes)
3. [The vocabulary is Spanish](#the-vocabulary-is-spanish-and-it-stays-that-way)
4. [The commands](#the-commands)
5. [Exit codes](#exit-codes)
6. [Running the platform](#running-the-platform)
7. [The panel, piece by piece](#the-panel-piece-by-piece)
8. [The eleven views, one by one](#the-eleven-views-one-by-one)
9. [How to read a row](#how-to-read-a-row)
10. [Languages](#languages)
11. [The landing page](#the-landing-page)
12. [Putting it in your CI](#putting-it-in-your-ci)
13. [Questions that always come up](#questions-that-always-come-up)

---

## What Actaira is, in one paragraph

Actaira reads your repository and tells you what binds you under **Regulation
(EU) 2024/1689** and **ISO/IEC 42001**, what can be checked by reading your
bytes, what has to be asked of you because it is not in the code, and what
technical file comes out of all that. It does not grade you, it does not say you
comply, and it does not sign for you. It says what it looked at, with which
rule, and what it left out.

---

## Start in five minutes

### 1. Install

```bash
pip install git+https://github.com/marcosmatalab/actaira-sys
```

You need **Python 3.12 or later**. No account, no sign-up, and nothing you do
leaves your machine: you can run it with the network unplugged.

> It installs from the repository because the package is **not published on PyPI
> yet**. The day it is, the command becomes `pip install actaira-motor` and this
> note goes away.

### 2. Ask what binds you

Start here, because it **does not read a single byte of your code**: the answer
comes only from what you declare about yourself.

```bash
actaira aplicabilidad --rol proveedor --alto-riesgo si --via-anexo anexo_iii
```

### 3. Run it over your repository

```bash
cd /path/to/your/repository
actaira plan . --rol proveedor --alto-riesgo si
```

That gives you, obligation by obligation, what was checked by reading bytes,
what turned up, where it is and what to do about it.

### 4. See what is left to answer

```bash
actaira preguntar . --rol proveedor --alto-riesgo si
```

Whatever the code cannot answer, it asks you. And each question states which
article, which clause and which control it serves.

### 5. Get the technical file

```bash
actaira anexo . --rol proveedor --alto-riesgo si   # Annex IV
actaira soa .   --rol proveedor --alto-riesgo si   # the statement of applicability
```

That is the whole product from the command line. What follows — the platform and
the panel — is the same thing with a screen, for several people and several
systems.

---

## The vocabulary is Spanish, and it stays that way

Before the first command: **the verbs and the flags are Spanish words, and the
values are too.** `actaira preguntar . --alto-riesgo si` is not a typo.

That is a decision, not an oversight. The engine emits this same vocabulary
*inside* the documents it produces — the state of every obligation, the reason,
the verb that produced it — so that two runs of the same thing can be compared
line by line. Adding English spellings would mean **two names for one verb**,
and this tree has already been bitten four times by two lists that were supposed
to say the same thing and drifted: the role names, the flag whitelist, the view
table and the published figures. A wrong value is rejected loudly — `--alto-riesgo yes`
exits with `invalid choice: 'yes' (choose from si, no, null)` — so nothing here
fails quietly.

So instead of a second vocabulary, here is the whole first one.

### The verbs

| you type | it means |
|---|---|
| `aplicabilidad` | applicability — what binds you |
| `plan` | plan |
| `preguntar` | ask — what is left to answer |
| `contestar` | answer — seals a person's answers as evidence |
| `comprobar` | check — the article 50 control |
| `soa` | statement of applicability |
| `anexo` | annex — the technical file |
| `vigilar` | monitor |
| `almacen` | store — the evidence chain |
| `noconformidad` | nonconformity |
| `revision` | review — management review |
| `empujon` | push — an outside event |
| `remediar` | remediate |
| `conectar` | connect — fetch the code from wherever it lives and run the plan |
| `sellar` | seal — sign the file |
| `verificar` | verify a seal |
| `exportar` | export |
| `ortografia` | spelling — checks the catalogue's Spanish accents |

### The flags

| you type | it means |
|---|---|
| `--rol` | role. Repeatable |
| `--alto-riesgo` | high-risk |
| `--via-anexo` | by which annex route: `anexo_iii` or `anexo_i` |
| `--sector-publico` | public sector |
| `--modelo-uso-general` | general-purpose model |
| `--riesgo-sistemico` | systemic risk |
| `--fecha` | date, `YYYY-MM-DD` |
| `--ahora` | now — the clock, for expiry |
| `--idioma` | language: `es` or `en` |
| `--almacen` | store — path to the evidence file |
| `--registrar` | record what was observed into the store |
| `--solo-almacen` | store only — do not read the repository |
| `--respuestas` | answers — path to the form answers |
| `--cual` | which — e.g. `--cual iv` for Annex IV |
| `--catalogo` | catalogue path |
| `--clave-esperada` | expected key, for verifying a seal |
| `--json` | raw document instead of prose |

### The values

| you type | it means |
|---|---|
| `si` | yes |
| `no` | no |
| `null` | unanswered — and this is a real state, not a blank |

And the ones the server takes: `--clientes` (client root), `--credenciales`
(credentials file), `--motor` (the engine executable), `--escucha` (listen
address), `--revisar-cada` (how often to review), `--bitacora` (log file),
`--emisor` (identity provider), `--tope-global` and `--tope-por-cliente`
(concurrency caps), `--plazo` (per-verb deadline).

---

## The commands

All of them accept `--json` for the raw document, and `--idioma es|en`.

| command | what it does | does it read your code? |
|---|---|---|
| `actaira aplicabilidad` | What binds you and what does not, from your profile | No |
| `actaira plan <path>` | Obligation by obligation, with findings and remediation | Yes |
| `actaira preguntar <path>` | What has to be asked of you, and what no longer needs asking | Yes |
| `actaira comprobar <path>` | The article 50 control, on its own | Yes |
| `actaira soa <path>` | The ISO 42001 statement of applicability | Yes |
| `actaira anexo <path> --cual iv` | The Annex IV technical file | Yes |
| `actaira vigilar <path> --registrar` | Observes and stores the sealed evidence | Yes |
| `actaira vigilar --solo-almacen` | What expired, without touching the repository | No |
| `actaira almacen verificar` | Whether the evidence chain is the one this house wrote | No |
| `actaira noconformidad listar` | What is open | No |
| `actaira revision` | The management review, with what supports it | No |

### The profile

Nearly all of them take the same flags to state **who you are with respect to
the system**. You can declare **several roles**: an organisation is usually the
provider of one system and the deployer of another.

| `--rol` | article | what it means |
|---|---|---|
| `proveedor` | 3.3 | you develop the system, or have it developed, and place it on the market under your own name |
| `responsable_despliegue` | 3.4 | you use it under your own authority |
| `representante_autorizado` | 3.5 | you represent a non-EU provider within the Union |
| `importador` | 3.6 | you place it on the market coming from outside the Union |
| `distribuidor` | 3.7 | you make it available without being any of the above |
| `fabricante_producto` | 25.3 | you build it into a regulated product of your own |
| `proveedor_modelo` | 53 | you provide a general-purpose AI model |

And the rest of the profile:

- `--alto-riesgo si|no` — whether the system is high-risk.
- `--via-anexo anexo_iii|anexo_i` — **by which route** it is. This decides your
  date: 2 December 2027 (Annex III, standalone system under art. 6.2) or
  2 August 2028 (Annex I, safety component of a regulated product, art. 6.1).
- `--sector-publico si|no`, `--modelo-uso-general si|no`,
  `--riesgo-sistemico si|no`.
- `--fecha YYYY-MM-DD` — the assessment date.

> **Leaving something unanswered is not a trick for coming out clean.** With an
> empty profile no obligation comes back resolved: they all come back
> unresolved, and each one says what is left to answer. There is no path from a
> blank form to a green result.

---

## Exit codes

This matters if you put it in a script: **a finding is not an error**. A
compliance tool that finds something has done its job.

| code | means | is it a failure? |
|---|---|---|
| `0` | It looked and nothing was left pending | No |
| `1` | Something turned up | **No** — that is work, not a breakdown |
| `3` | Something is left to answer, or something has to be looked at again | **No** |
| `4` | The analyser broke | Yes |
| `5` | The store is not the one this house wrote | Yes |

If you treat `1` as an error, your gate goes red exactly when the product is
working, and the natural response to that is to lower the bar until it stops
looking at anything.

---

## Running the platform

The engine on its own is already enough. The platform adds HTTP, several
clients, roles and continuous monitoring.

### The client space

```
clientes/
  acme/
    trabajo/           <- a copy of the client's repository
    evidencia.jsonl    <- written by the platform when it monitors
    respuestas.json    <- the form answers, if there are any
```

### The credentials

A JSON file mapping `token → client`, **with 0600 permissions**:

```json
{ "a-long-random-token": "acme" }
```

### Start it

```bash
actaira-api \
  --clientes ./clientes \
  --credenciales ./cred.json \
  --motor actaira \
  --escucha 127.0.0.1:8787
```

Without a credentials file it **will not start**, and without a client root it
will not either: there is no default configuration fit for production, and that
is deliberate. By default it listens on localhost only; exposing it to the
network is a decision, not an oversight.

Other flags worth knowing:

| flag | what for |
|---|---|
| `--revisar-cada 1h` | how often it checks what expired without anyone pushing anything. `0` turns it off, and turning it off is announced out loud at start-up |
| `--bitacora file.jsonl` | logs every monitoring pass and every delivery attempt, **including the passes with no alerts** |
| `--emisor issuer.json` | use a real identity provider (OIDC): client and roles come from the signed token |
| `--tope-global 4` / `--tope-por-cliente 2` | how many engine verbs may run at once. Each one is a **process** reading an entire repository |
| `--plazo 3m` | how long a verb may take before it is cut off |

### The roles

With OIDC, each credential carries roles and each verb requires one:

| role | what it can do |
|---|---|
| `lectura` | read what has already been observed: applicability, questionnaire, SoA, annex, evidence, nonconformities, review |
| `observacion` | also start the engine over the repository: plan, monitor, check |
| `remediacion` | also move work and receive outside events: push, remediate |
| `admin` | everything |

### The panel

The server **serves the panel from its own origin**, so opening the address it
listens on is enough:

```
http://127.0.0.1:8787/
```

That is not a convenience: the content security policy carries
`connect-src 'self'`, which is what stops a script that ends up on the page from
shipping a client's technical file somewhere else.

---

## The panel, piece by piece

This is the whole screen, with the profile filled in and the plan requested:

![The whole panel](imagenes/panel.png)

**The panel computes nothing.** Every number you see arrives inside the document
the engine emitted, and so does every sentence explaining it. If the engine did
not say it, it does not appear here.

### 1. The header

![The header](imagenes/manual-cabecera.png)

Left to right:

- **The logo.**
- **The connection indicator.** Says whether you are connected; clicking it
  takes you to the server field.
- **The interface language.** Six: ES, EN, FR, PT, IT, DE.
- **The theme.** ☼ light and ☾ dark. Click the active one again to follow the
  system setting.

### 2. The product category

![The three categories](imagenes/manual-categorias.png)

The three change **what you ask the engine for and what you see first**. They do
not change what the engine says: no category hides a finding or alters a
verdict.

| category | for whom | what it shows |
|---|---|---|
| **Technical team** | whoever writes the code | the plan, article 50, the evidence and the nonconformities |
| **SME** | whoever is accountable for complying | what binds you, the plan, the questionnaire, the SoA, the technical file and what expired |
| **Enterprise** | whoever governs several systems | all eleven |

### 3. The cycle

![The cycle](imagenes/manual-ciclo.png)

Five counts that fill in as you ask for things: **what binds you**, **what
turned up**, **what has to be asked of you**, **what expired** and **what is
open**. Anything you have not requested yet reads *not asked for yet* — which is
not the same as zero.

### 4. Connection

![The connection card](imagenes/manual-conexion-vacia.png)

- **Server.** Fills itself in with the page's origin when a server is serving
  it. If you open the panel as a local file, type it in.
- **Client.** The space identifier: the folder under `clientes/`.
- **Credential.** The token.

Click **Connect**. The panel first tries `/salud` and then a route that **does**
require a credential: saying «connected» because the server is breathing would
be promising something that has not been checked.

Once connected, the header indicator lights up and **Disconnect** appears, which
wipes the credential from memory and clears everything you asked for:

![The connection card, connected](imagenes/manual-conexion.png)

> **The credential is not stored.** Not in `localStorage`, not in
> `sessionStorage`, not in a cookie. It lives in a variable and is lost on
> reload. It is deliberately inconvenient: a token in browser storage is
> readable by any script that ends up on the page, and that token is enough to
> read a client's entire technical file.

### 5. Your profile

![The profile card](imagenes/manual-perfil.png)

The same fields as the command-line flags. **Roles accepts several**: hold Ctrl
or Cmd.

Each dropdown has three options — **Unanswered / Yes / No** — and «unanswered»
is a real state, not a blank: the obligations that depend on that answer come
back unresolved and say so.

### 6. What you want to see

![The eleven buttons](imagenes/manual-vistas.png)

The eleven buttons. The ones outside the chosen category are hidden. They all go
disabled while the engine runs and come back when it finishes.

### 7. Counts

![The counts](imagenes/manual-recuento.png)

The pills are **counts of obligations**, never proportions. On the right, the
**seal**: the document's schema and the exit code the engine answered with.

> There is no compliance percentage here and there never will be. An 87 % means
> nothing: an obligation is met by an organisation, not by a control.

### 8. Obligation by obligation

![The list](imagenes/manual-lineas.png)

- **The search box** filters by text and says how many are left.
- **All / Findings / Questions** filters by what each line carries inside.

![The search box](imagenes/manual-buscador.png)

If there is nothing to show, the screen distinguishes two things that are not
the same: *«this document brings no lines»* and *«no line matches this filter»*.

### 9. The document as it is

![The raw document](imagenes/manual-crudo.png)

What the engine returned, untouched. It is there so you can check the screen
against its source: **if something you see above is not inside here, that is a
defect of the panel**.

---

## The eleven views, one by one

### What binds me — `aplicabilidad`

![What binds me](imagenes/vista-aplicabilidad.png)

The product's first question. It **reads no bytes of your code**: it comes only
from the profile, so it is instant and you can play with the answers to see what
changes.

### Ask for the plan — `plan`

![The plan](imagenes/vista-plan.png)

The bulk of it. Obligation by obligation: what binds you, what was checked by
reading bytes, what turned up, where and with which rule, and what to do.

### Article 50 — `comprobar`

![Article 50](imagenes/vista-articulo50.png)

The article 50 transparency control, on its own. It **takes no profile**: it
reads the code and says what it sees. It shows which files it looked at, which
is half the product's promise.

### What is left to answer — `preguntar`

![The questionnaire](imagenes/vista-cuestionario.png)

The questionnaire that spares you a questionnaire. Every question declares what
it serves with identifiers from **all three catalogues at once** — Regulation
article, standard clause and Annex A control — so one answer closes several
things.

And a question **disappears** as soon as a control reads the bytes that answer
it. The subtraction is published with the list of controls that produced it: a
number with no list behind it is advertising.

### Statement of applicability — `soa`

![The statement of applicability](imagenes/vista-soa.png)

The ISO/IEC 42001 Annex A controls, each with whether it is included and with
its justification.

### Technical file — `anexo`

![Annex IV](imagenes/vista-anexo-iv.png)

Annex IV section by section. Each section says **where it came from**, and the
missing ones say **why they are missing**.

### Ask for monitoring — `vigilar`

![Monitoring](imagenes/vista-vigilancia.png)

Observes the repository and **stores the sealed evidence**. Anything already
there and unchanged is not rewritten: it is **revalidated**, which moves the
freshness clock without inflating the file.

### Evidence — `almacen`

![The evidence](imagenes/vista-evidencia.png)

The state of the evidence chain, which is the only claim this product makes to a
third party:

- **File** — whether it exists. Its not existing **is not a failure**: a client
  that has observed nothing yet has no store.
- **Chain** — whether the seals hold from start to end.
- **Head** — the last line's seal. Write it down elsewhere: it is the only thing
  that detects someone rewriting the whole file and resealing it.
- **Expected head** — comes back *unresolved* if nobody stated what they
  expected. That is **not the same** as it matching.
- The counts of sealed observations and of lines with no demonstrable chain.

### What expired — `vencimientos`

![What expired](imagenes/vista-vencimientos.png)

What has to be looked at again, **without touching your repository**: knowing
what expired needs the store and a clock, not your code. This is the route a
cron job can run.

Evidence is superseded by the **digest of the subject** it was taken on, not by
that subject's name. Touching a README does not supersede the evidence of a
control that does not read that README.

### Nonconformities — `noconformidad`

![The nonconformities](imagenes/vista-noconformidades.png)

What is open, with how many days it has been open, whether it is overdue,
whether it is stalled and whether there are inconsistencies.

> **EXECUTED is not closed.** Clause 10.2 asks whether the action worked, and
> that is a later observation.

### Management review — `revision`

![The management review](imagenes/vista-revision.png)

The inputs clause 9.3 asks for, each with the clauses it covers and with what
supports it.

---

## How to read a row

![A row with the remediation expanded](imagenes/manual-fila-abierta.png)

Every line has four parts:

1. **On the left**, the key: the article, the obligation identifier or the
   control identifier.
2. **In the middle**, the title and, underneath, the reason — why it is in that
   state.
3. **Expandables**: *Remediation* (what to do, where it is and which rule found
   it) and *Questions* (what has to be answered).
4. **On the right**, the badge with the state.

The states come **inside the document**, not from this page: the vocabulary
belongs to the engine. The ones you will see most:

| badge | what it means |
|---|---|
| **will bind you** | it binds you, but its date has not arrived yet |
| **checked** | the bytes were read and they answer what the obligation asks |
| **with findings** | it was looked at and something turned up |
| **must be asked** | the code cannot answer it; a person is needed |
| **unresolved** | it could not be decided, and the row says why |
| **form only** | it is not checkable by reading code, by its nature |
| **does not bind you** | with the profile you declared, it does not apply |

> An **INDETERMINADO** with no written reason is a NO_CUMPLE in disguise. If
> Actaira could not look at something, it tells you what and why.

---

## Languages

The platform speaks **six**: Spanish, English, French, Portuguese, Italian and
German. The engine emits normative content in **two**: Spanish and English.

This is not a limitation to be fixed by translating more. Obligation titles,
reasons and remediations are written by **a person**, and machine-translating
them is exactly what the product forbids itself.

**There are not two settings. There is one, and the other is derived from it:**

| interface in | the document arrives in |
|---|---|
| Spanish | Spanish |
| any of the other five | English |

And when it falls back to English, the screen **says so**, in whatever language
you have set:

![The language notice](imagenes/manual-idioma-aviso.png)

There is nowhere to pick the document language separately. If there were,
someone would end up with the screen in German and the technical file in
Spanish.

---

## The landing page

If what you need is to explain it to someone, the product's landing page lives
in `sitio/` and opens without a server, in six languages:

![The Actaira landing page](imagenes/portada-en.png)

It is built with `make portada`, and its figures come from the catalogue and
from the tree: there is not one hand-written number on it, and there is a test
that checks that.

---

## Putting it in your CI

Copy [`integraciones/github/actaira.yml`](../integraciones/github/actaira.yml)
into your repository's `.github/workflows/`.

What it gives you:

- Findings come out as **SARIF**: they show up in the Security tab and inside
  the pull request review, with the remediation next to them. The finding
  reaches whoever can fix it, on the day they wrote the line.
- The observed evidence is stored in `.actaira/evidencia.jsonl` and committed,
  so the technical file lives in your repository and not on someone else's
  machine.

**The gate that blocks deployment is commented out.** Actaira says what has to
be looked at again; whether that blocks a deployment is your call, in your own
CI file, where the decision gets reviewed. There is a test that checks it stays
commented out.

---

## Questions that always come up

**Does it give me a compliance percentage?**
No, and it never will. Counts of obligations are published, never proportions.

**Does it say I comply?**
No. It says what was checked by reading bytes, with which rule, of which version
and by which author, and what falls outside the scope of that check. A person
signs the interpretation.

**Does it upload my code anywhere?**
No. Neither the engine nor the platform sends anything out. You can run it with
the network unplugged.

**Can it sign my declaration of conformity?**
No. The EU declaration comes out with the word **BORRADOR** (draft) in the
header while the signature of Annex V point 8 does not exist, and no flag
removes it: points 3 and 4 are claims made by the provider under their sole
responsibility.

**If the plan comes back clean, can I close the equivalent Annex A control?**
Not automatically. The standard asks for things the Regulation does not, and the
crosswalk between the two catalogues says so control by control.

**Why does each button take half a second?**
Because every verb starts a **separate process**, and that is deliberate: the
engine answering over HTTP is exactly the same binary your auditor runs on their
own machine. The analysis itself takes between 9 and 28 ms; the rest is starting
the interpreter.

**Why does the evidence say «there is no store yet»?**
Because nobody has monitored in that client space yet. Click **Ask for
monitoring** and look again: the platform stores what was observed and seals the
chain.

---

Anything missing? Write to **marcosmata@actaira.com**.
