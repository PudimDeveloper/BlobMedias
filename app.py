import os
import hmac
import mimetypes
import uuid

from pathlib import Path
from flask import Flask, request, jsonify, redirect
from werkzeug.utils import secure_filename
from vercel.blob import sync as blob

app = Flask(__name__)

PREFIXO = "medias/"
Key = os.environ.get("MEDIA_KEY", "")


@app.route("/enviarMedia", methods=["POST"])
def enviar_media():
    if "file" not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado."}), 400

    arquivo = request.files["file"]

    if not arquivo.filename:
        return jsonify({"erro": "Nome do arquivo inválido."}), 400

    nome = secure_filename(arquivo.filename)

    if not nome:
        return jsonify({"erro": "Nome do arquivo inválido."}), 400

    extensao = Path(nome).suffix
    nome_final = f"{uuid.uuid4().hex}{extensao}"
    caminho = f"{PREFIXO}{nome_final}"

    try:
        conteudo = arquivo.read()

        resultado = blob.put_blob(
            caminho,
            conteudo,
            {
                "content_type": (
                    arquivo.content_type
                    or mimetypes.guess_type(nome)[0]
                    or "application/octet-stream"
                )
            }
        )

        return jsonify({
            "sucesso": True,
            "nome": nome_final,
            "url": resultado.url
        }), 201

    except Exception as erro:
        print("Erro ao enviar mídia:", erro)

        return jsonify({
            "erro": "Não foi possível enviar a mídia."
        }), 500


@app.route("/viewMedias", methods=["GET"])
def listar_medias():
    try:
        resultado = blob.query_blobs(prefix=PREFIXO)

        medias = []

        for item in resultado.blobs:
            nome = item.pathname.removeprefix(PREFIXO)

            medias.append({
                "nome": nome,
                "url": f"/viewMedias/{nome}"
            })

        return jsonify({
            "total": len(medias),
            "medias": medias
        })

    except Exception as erro:
        print("Erro ao listar mídias:", erro)

        return jsonify({
            "erro": "Não foi possível listar as mídias."
        }), 500


@app.route("/viewMedias/<nome>", methods=["GET"])
def visualizar_media(nome):
    chave = request.args.get("key", "")

    if not Key or not hmac.compare_digest(chave, Key):
        return jsonify({
            "erro": "Key incorreta."
        }), 403

    nome = secure_filename(nome)

    if not nome:
        return jsonify({
            "erro": "Nome de mídia inválido."
        }), 400

    try:
        resultado = blob.head_blob(f"{PREFIXO}{nome}")

        if not resultado:
            return jsonify({
                "erro": "Mídia não encontrada."
            }), 404

        return redirect(resultado.url)

    except Exception as erro:
        print("Erro ao visualizar mídia:", erro)

        return jsonify({
            "erro": "Não foi possível visualizar a mídia."
        }), 500


if __name__ == "__main__":
    app.run()
