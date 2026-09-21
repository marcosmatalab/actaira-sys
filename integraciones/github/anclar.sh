#!/usr/bin/env bash
# Clava cada `uses:` del flujo a un digest, con su etiqueta al lado.
#
# POR QUE ESTO NO VIENE HECHO
# -----------------------------
# Un digest se resuelve preguntandole a GitHub, y escribir aqui uno de memoria
# seria publicar un hecho que nadie comprobo: la primera negativa de esta casa
# aplicada a su propia integracion. Asi que se resuelve en tu maquina, con tu
# `gh`, contra el repositorio de verdad, y el resultado queda escrito en tu
# flujo con la etiqueta al lado para que se lea.
#
#   ./anclar.sh .github/workflows/actaira.yml
#
# Vuelve a correrlo cuando quieras subir de version: el diff dira exactamente
# que codigo pasa a ejecutarse dentro de tu integracion continua, que es la
# pregunta que una etiqueta movil no deja hacer.
set -euo pipefail

flujo="${1:?uso: anclar.sh <fichero de flujo>}"
command -v gh >/dev/null || { echo "hace falta el cliente gh"; exit 2; }

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
cp "$flujo" "$tmp"

grep -oE 'uses: [A-Za-z0-9._/-]+@[A-Za-z0-9._-]+' "$flujo" | sort -u | while read -r _ ref; do
  repo="${ref%@*}"; etiqueta="${ref#*@}"
  case "$etiqueta" in
    [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*)
      echo "ya anclado: $ref"; continue ;;
  esac
  # Una accion puede vivir en un subdirectorio (github/codeql-action/upload-sarif):
  # el digest es el del repositorio, que son los dos primeros segmentos.
  duenyo="$(echo "$repo" | cut -d/ -f1)"; nombre="$(echo "$repo" | cut -d/ -f2)"
  sha="$(gh api "repos/$duenyo/$nombre/commits/$etiqueta" --jq .sha)"
  [ -n "$sha" ] || { echo "no se pudo resolver $ref"; exit 1; }
  echo "$repo@$etiqueta -> $sha"
  sed -i.bak "s|uses: $repo@$etiqueta|uses: $repo@$sha  # $etiqueta|g" "$tmp"
  rm -f "$tmp.bak"
done

mv "$tmp" "$flujo"
trap - EXIT
echo "anclado: $flujo"
