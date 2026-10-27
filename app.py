from flask import Flask, request, jsonify, redirect
from werkzeug.utils import secure_filename
from vercel.blob import sync as blob
from pathlib import Path
import mimetypes
import traceback
import uuid

app = Flask(__name__)

PREFIXO = "medias/"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


def erro_json(mensagem, erro, status=500):
    app.logger.error(
        "%s:\n%s",
        mensagem,
        traceback.format_exc()
    )

    return jsonify({
        "ok": False,
        "error": str(erro),
        "tipo": type(erro).__name__
    }), status


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Olá! API está funcionando!",
        "status": 200,
        "params": [
            "/enviarMedia",
            "/viewMedias",
            "/viewMedias/<nome>"
        ]
    }), 200


@app.route("/enviarMedia", methods=["POST"])
def blobMedia():
    arquivo = request.files.get("blob")

    if not arquivo or not arquivo.filename:
        return jsonify({
            "ok": False,
            "error": "Nenhum arquivo enviado"
        }), 400

    nome_original = secure_filename(arquivo.filename)

    if not nome_original:
        return jsonify({
            "ok": False,
            "error": "Nome de arquivo inválido"
        }), 400

    extensao = Path(nome_original).suffix.lower()
    nome = f"{uuid.uuid4().hex}{extensao}"
    caminho = f"{PREFIXO}{nome}"

    try:
        conteudo = arquivo.read()

        if not conteudo:
            return jsonify({
                "ok": False,
                "error": "O arquivo está vazio"
            }), 400

        tipo = (
            arquivo.mimetype
            or mimetypes.guess_type(nome_original)[0]
            or "application/octet-stream"
        )

        resultado = blob.put_blob(
            caminho,
            conteudo,
            access="public",
            content_type=tipo
        )

        return jsonify({
            "ok": True,
            "nome": nome,
            "url": f"/viewMedias/{nome}",
            "blobUrl": resultado.url
        }), 201

    except Exception as erro:
        return erro_json("Falha ao enviar mídia", erro)


@app.route("/viewMedias", methods=["GET"])
def viewMedias():
    try:
        arquivos = []

        for item in blob.query_blobs(prefix=PREFIXO):
            nome = item.pathname.removeprefix(PREFIXO)

            arquivos.append({
                "nome": nome,
                "url": f"/viewMedias/{nome}",
                "blobUrl": item.url
            })

        arquivos.sort(key=lambda item: item["nome"])

        return jsonify(arquivos), 200

    except Exception as erro:
        return erro_json("Falha ao listar mídias", erro)


@app.route("/viewMedias/<nome>", methods=["GET"])
def viewMedia(nome):
    nome_seguro = secure_filename(nome)

    if not nome_seguro or nome_seguro != nome:
        return jsonify({
            "ok": False,
            "error": "Nome inválido"
        }), 400

    try:
        resultado = blob.head_blob(f"{PREFIXO}{nome_seguro}")

        return redirect(resultado.url, code=302)

    except Exception as erro:
        app.logger.error(
            "Falha ao localizar mídia %s:\n%s",
            nome_seguro,
            traceback.format_exc()
        )

        return jsonify({
            "ok": False,
            "error": "Mídia não encontrada",
            "tipo": type(erro).__name__
        }), 404


@app.errorhandler(413)
def arquivo_grande(_erro):
    return jsonify({
        "ok": False,
        "error": "Arquivo excede o limite de 50 MB"
    }), 413


@app.errorhandler(500)
def erro_interno(_erro):
    return jsonify({
        "ok": False,
        "error": "Erro interno da API"
    }), 500


if __name__ == "__main__":
    app.run()
