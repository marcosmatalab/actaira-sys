"""Lo que TODA pagina de este producto tiene que cumplir, comprobado al construir.

POR QUE ESTE FICHERO
---------------------
El panel llevaba una puerta de accesibilidad dentro de su propio constructor y
las otras dos paginas -- la consola y la portada -- no llevaban ninguna. El
resultado se veia a simple vista en cuanto se miraba:

  - Ni `consola.html` ni `index.html` declaraban `<!doctype html>`. Sin
    doctype, cualquier navegador renderiza en MODO QUIRKS, que usa otro modelo
    de caja. No es un detalle de validacion: es que la pagina se mide distinto
    de como se diseno, y nadie lo nota porque casi cuadra.
  - Ninguna de las dos declaraba `lang`. Un lector de pantalla pronuncia
    entonces el castellano con las reglas del ingles, y este producto es
    castellano entero.

La leccion no es que faltaran dos etiquetas. Es que la comprobacion vivia
dentro de UNA pagina, asi que solo protegia a esa pagina. Una puerta que no se
puede reutilizar acaba protegiendo lo que se acordo de protegerla.

LO QUE ESTO **NO** COMPRUEBA, dicho para que nadie lo suponga
--------------------------------------------------------------
El contraste real de los colores compuestos, el orden de tabulacion percibido y
si los textos se entienden. Eso lo mira una persona, y esta puerta no la
sustituye: una lista de comprobaciones invita a creer que estan todas.
"""
from __future__ import annotations

import re


def revisar_estructura(pagina: str, quien: str) -> None:
    """Las propiedades que se pueden comprobar LEYENDO el HTML."""
    fallos: list[str] = []

    # LO QUE HAY DENTRO DE `<script>` Y `<style>` NO ES MARCADO.
    #
    # La primera version miraba la pagina entera y denuncio dos `<input>` «sin
    # id» que no existian: eran cadenas de texto dentro del JavaScript
    # incrustado. Una puerta que da falsos positivos se desactiva, y una puerta
    # desactivada no protege nada, asi que esto no es cosmetico.
    #
    # Los encabezados y el `focus-visible` se buscan sobre la pagina ENTERA a
    # proposito: la regla de foco vive en el `<style>`.
    marcado = re.sub(r"<script\b.*?</script>", "", pagina, flags=re.S | re.I)

    # LO QUE HAY DENTRO DE `<script>` Y `<style>` NO ES MARCADO.
    #
    # La primera version miraba la pagina entera y denuncio dos `<input>` «sin
    # id» que no existian: eran cadenas de texto dentro del JavaScript
    # incrustado. Una puerta que da falsos positivos se desactiva, y una puerta
    # desactivada no protege nada, asi que esto no es cosmetico.
    #
    # Los encabezados y el `focus-visible` se buscan sobre la pagina ENTERA a
    # proposito: la regla de foco vive en el `<style>`.
    marcado = re.sub(r"<script\b.*?</script>", "", pagina, flags=re.S | re.I)

    if not re.match(r"\s*<!doctype html>", pagina, re.I):
        fallos.append(
            "no empieza por `<!doctype html>`: sin el, el navegador renderiza en "
            "modo quirks y la pagina se mide con otro modelo de caja")

    m = re.search(r"<html\b([^>]*)>", pagina, re.I)
    if not m:
        fallos.append("no hay elemento `<html>`")
    elif not re.search(r'\blang="[a-z-]+"', m.group(1)):
        fallos.append(
            "el `<html>` no declara `lang`: un lector de pantalla pronuncia el "
            "castellano con las reglas del ingles")

    niveles = [int(x) for x in re.findall(r"<h([1-6])\b", pagina)]
    if niveles.count(1) != 1:
        fallos.append(f"hay {niveles.count(1)} encabezados <h1> y tiene que haber uno")
    for antes, despues in zip(niveles, niveles[1:]):
        if despues > antes + 1:
            fallos.append(f"el encabezado salta de h{antes} a h{despues}: un lector "
                          f"anuncia la estructura y ahi aparece un hueco")

    if "focus-visible" not in pagina:
        fallos.append("no hay ninguna regla de `:focus-visible`: el foco del teclado "
                      "no se ve, y sin verlo el teclado no sirve")

    # Un control sin nombre es un control que un lector de pantalla no puede
    # anunciar. Los botones de estas paginas nacen vacios a proposito -- el
    # texto lo pone el idioma -- asi que lo que se exige es el `id` que los ata
    # a su clave, o un `aria-label`.
    for m in re.finditer(r"<button\b([^>]*)>(.*?)</button>", marcado, re.S):
        atributos, dentro = m.group(1), m.group(2).strip()
        if not dentro and 'id="' not in atributos and "aria-label" not in atributos:
            fallos.append(f"un <button> sin texto, sin id y sin aria-label: "
                          f"{m.group(0)[:70]}")

    for etiqueta in ("input", "select"):
        for m in re.finditer(rf"<{etiqueta}\b([^>]*)>", marcado):
            atributos = m.group(1)
            if 'type="hidden"' in atributos:
                continue
            ident = re.search(r'\bid="([^"]+)"', atributos)
            if not ident:
                fallos.append(f"un <{etiqueta}> sin id, asi que nada lo puede etiquetar")
                continue
            envuelto = re.search(
                r"<label\b[^>]*>(?:(?!</label>).)*" + re.escape(m.group(0)),
                marcado, re.S)
            if not (envuelto or "aria-label" in atributos
                    or "aria-labelledby" in atributos
                    or f'for="{ident.group(1)}"' in marcado):
                fallos.append(f'<{etiqueta} id="{ident.group(1)}"> no tiene etiqueta')

    if fallos:
        raise SystemExit(f"{quien}:\n  " + "\n  ".join(fallos))


def revisar_textos(textos: dict) -> None:
    """Que los idiomas tengan las MISMAS claves, y ninguna vacia.

    Una clave que falte en uno de los dos sale como `undefined` en la pantalla
    de un cliente, y eso no lo detecta ningun test de unidad porque el fallo
    esta en el dato, no en el codigo.
    """
    idiomas = sorted(textos)
    faltan = [f"{otro}.{k}" for uno in idiomas for otro in idiomas
              for k in textos[uno] if k not in textos[otro]]
    if faltan:
        raise SystemExit(f"textos.json: claves que faltan en un idioma: {sorted(set(faltan))}")
    vacias = [f"{i}.{k}" for i in idiomas for k, v in textos[i].items()
              if not str(v).strip()]
    if vacias:
        raise SystemExit(f"textos.json: claves vacias: {vacias}")
