# Escribir un conector

Cómo enchufar Actaira a **tu** sistema: de dónde saca el código, y a dónde
manda lo que hay que arreglar.

Este documento va dirigido a quien integra Actaira con el sistema de gestión de
otra empresa —un GRC, un sistema de tickets, un repositorio en un sitio raro— y
supone que ya sabes qué hace el producto. Si no, empieza por
[ARQUITECTURA.md](ARQUITECTURA.md).

---

## 1. Hay dos clases de conector, y no se mezclan

| | de dónde | a dónde |
|---|---|---|
| **Conector de fuente** | trae el código a observar | — |
| **Remediador** | — | manda el hallazgo a donde el cliente trabaja |

Están separados a propósito. Mezclarlos en un solo conector hace que cambiar de
proveedor de tickets obligue a tocar el que lee el código, y son dos ciclos de
vida distintos: uno se usa en cada observación, el otro sólo cuando hay un
hallazgo que alguien tiene que arreglar.

Y son dos superficies de permiso distintas. Leer el repositorio de un cliente y
escribir en el sistema donde organiza su trabajo no se piden juntos, y un
conector que pidiera las dos cosas obligaría a conceder la segunda a quien sólo
necesita la primera.

---

## 2. Un conector de fuente

Tres métodos. Vive en `motor/src/actaira_motor/conectores/`.

```python
class MiConector:
    nombre = "mi-sistema"
    version = "1.0.0"

    @staticmethod
    def resuelve(ubicacion: str) -> bool:
        """Si ESTE conector atiende esa ubicación. No la abre: la reconoce."""

    def fuente(self, ubicacion: str, referencia: str) -> Fuente:
        """Resuelve la referencia a algo INMUTABLE. Aquí está el trabajo."""

    def materializar(self, fuente: Fuente, destino: Path) -> Path:
        """Deja el árbol en `destino`. El destino lo gestiona quien llama."""

    def limites(self) -> tuple[LimiteDelConector, ...]:
        """Lo que este conector NO ve, para que viaje con la observación."""
```

### `fuente` es donde está todo

Una `Fuente` con `reproducible=False` no se materializa: el motor se niega. El
motivo es el producto entero — una observación que no se puede repetir no es
evidencia de nada, porque mañana el mismo comando sobre la misma entrada da
otra cosa y nadie puede decir cuál valía.

Así que «la rama `main`» no es una referencia: es un nombre que apunta a cosas
distintas según cuándo lo mires. Tu conector tiene que resolverlo a algo que no
cambie —un commit, un digest, una versión sellada— y si su sistema no puede,
eso se dice en `limites` y se deja de materializar.

### `limites` no es documentación

Lo que devuelve viaja **dentro** de la observación y acaba en el expediente que
lee un auditor. El conector de git declara dos: que no clona submódulos, y que
no ve lo que `.gitignore` excluye. Las dos son ciertas, las dos importan, y un
auditor que no las vea concluirá que se miró lo que no se miró.

Si tu sistema tiene un límite parecido —un tamaño máximo, un tipo de fichero
que no baja, una rama protegida a la que no llegas— va aquí. Un conector sin
límites declarados está diciendo que lo ve todo.

---

## 3. Un remediador

Tres métodos. Vive en `motor/src/actaira_motor/remediacion/`.

```python
class MiRemediador:
    nombre = "mi-tablero"
    version = "1.0.0"
    destino: str          # el proyecto, la cola, la carpeta

    def abrir(self, encargo: Encargo, idioma: str = "es") -> Delegacion:
        """Abre el ticket y devuelve su referencia. NO decide nada."""

    def consultar(self, delegacion: Delegacion) -> Delegacion:
        """Lo último que dice el otro sistema. Crudo, sin traducir."""

    def limites(self) -> tuple[LimiteDelRemediador, ...]:
        """Lo que delegar NO alcanza."""
```

### Las tres cosas que un remediador no puede hacer

**No verifica.** Puede abrir un ticket, leer su estado y decirlo. No puede
concluir que la no conformidad quedó resuelta. La cláusula 10.2 pide revisar la
**eficacia**, y el estado de una columna en un tablero no la revisa: que alguien
arrastre la tarjeta a «hecho» no demuestra que la causa dejó de producir el
efecto. Por eso el estado `VERIFICADA` no sale de un remediador nunca, y el
ciclo se queda en `ejecutada` hasta que hay una observación posterior.

**No inventa autores.** Una transición sin persona no se puede auditar. Si tu
sistema no dice quién movió el ticket, no escribas `"sistema"`: di que falta el
autor y no muevas nada.

**No manda más de lo que hace falta.** El encargo lleva el texto de la regla y
de su remediación, que son nuestros y están revisados por una persona en los dos
idiomas. Las rutas de fichero del cliente sólo salen si alguien lo pide
expresamente, porque un ticket lo lee muchísima más gente que un expediente
firmado.

### Sin escribir Python: un perfil

Para un sistema que hable HTTP y JSON no hace falta código. Un perfil es un
fichero JSON que dice a qué URL llamar, con qué cuerpo y de dónde sacar la
referencia de vuelta. Los que vienen de serie están en
`motor/src/actaira_motor/remediacion/perfiles/` y son el mejor punto de partida:
cópialo, cambia las URLs y pásalo con `--perfil ruta/al/tuyo.json`.

La credencial se lee **del entorno**, nunca del perfil. Un secreto dentro de un
fichero de configuración acaba en un repositorio.

---

## 4. Antes de mandar nada: `--simular`

```
actaira remediar abrir --destino ... --id NC-9 \
  --responsable datos --compromiso 2027-10-15 --simular
```

Enseña exactamente lo que saldría y **no llama a nadie ni escribe en el
almacén**. Sale con código 3 —«falta que alguien decida»— que no es limpio ni es
un fallo.

Úsalo mientras escribes el conector. Lo que sale de aquí entra en el sistema
donde el cliente organiza su trabajo: un ticket mal redactado no se borra, lo lee
todo el equipo, y cuesta más explicarlo que haberlo revisado antes.

---

## 5. Los límites de esta guía

**Los conectores de referencia que vienen son tres, y los tres son de sistemas
de tickets**: GitHub, Jira y Linear. No hay conector de ServiceNow, de OneTrust
ni de Archer, y no lo hay por un motivo que conviene decir en vez de dejar un
hueco: escribir uno sin una instalación real contra la que probarlo produciría
código que compila, tiene sus pruebas en verde y nadie ha visto funcionar contra
lo que dice integrar. Eso es exactamente lo que este producto existe para no
hacer.

Lo que sí hay es el contrato que esos conectores cumplen, probado con los tres,
y este documento. Si escribes el de ServiceNow contra un ServiceNow de verdad,
el contrato es el mismo.

**El reparto de responsabilidad, dicho antes de integrar.** Actaira es dueño de
la evidencia, su procedencia, su verificación, su vigencia y el resultado
técnico. Tu GRC sigue siendo dueño de la aceptación formal del riesgo, las
políticas corporativas, las excepciones aprobadas, los propietarios organizativos
y los planes de auditoría. Un conector que traiga las segundas hacia aquí está
convirtiendo esto en un GRC, y entonces sobra uno de los dos.

---

## 6. La API, si integras por HTTP

`contrato/openapi.json` es la especificación, y **se genera**: sale de las rutas
que el enrutador publica de verdad y de los esquemas de `contrato/`. Una
especificación escrita a mano se queda corta en cuanto alguien añade una ruta, y
quien la lea escribirá un conector contra endpoints que no existen.

Dos cosas que conviene entender antes de escribir el cliente:

**El código de salida es un veredicto, no un fallo.** `0` es «se miró y no
apareció nada», `1` es «apareció algo» y `3` es «no se pudo decidir o falta que
alguien conteste». Un `3` es el estado normal de un cliente que empieza. Si tu
integración trata el `1` como error, se pondrá roja justo cuando el producto
funciona.

**La versión que importa viaja dentro del documento.** La de la API dice qué
rutas hay; la del documento, en su campo `esquema`, dice qué forma tiene lo que
devuelven. Una ruta puede seguir igual mientras el documento cambia, y al revés.
Ata tu cliente al `esquema`.

**Firma tus webhooks.** Si mandas eventos a `/v1/clientes/{cliente}/empujon`,
configura el secreto compartido en `ACTAIRA_SECRETO_WEBHOOK_<CLIENTE>` y firma el
cuerpo con HMAC-SHA256. La credencial demuestra que puedes llamar; la firma
demuestra que el cuerpo viene de ti y llegó intacto. Sin ella, la respuesta
llevará `firma_verificada: false` y el expediente registrará que ese evento no se
pudo atribuir a nadie.
