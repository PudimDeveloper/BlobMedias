from flask import Flask, request, jsonify, redirect
from werkzeug.utils import secure_filename
from vercel.blob import sync as blob
from pathlib import Path
import mimetypes
import traceback
import uuid
import os

app = Flask(__name__)

PREFIXO = "medias/"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


def resposta_erro(mensagem, erro, status=500):
    app.logger.exception(mensagem)

    return jsonify({
        "ok": False,
        "error": str(erro),
        "tipo": type(erro).__name__
    }), status


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

        app.logger.info(
            "Enviando mídia: nome=%s, tamanho=%d, tipo=%s",
            nome,
            len(conteudo),
            tipo
        )

        resultado = blob.put_blob(
            caminho,
            conteudo,
            access="public",
            content_type=tipo
        )

        url_blob = resultado.url

        return jsonify({
            "ok": True,
            "nome": nome,
            "url": f"/viewMedias/{nome}",
            "blobUrl": url_blob
        }), 201

    except Exception as erro:
        app.logger.error(
            "Falha ao enviar mídia:\n%s",
            traceback.format_exc()
        )

        return jsonify({
            "ok": False,
            "error": str(erro),
            "tipo": type(erro).__name__
        }), 500


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
        app.logger.error(
            "Falha ao listar mídias:\n%s",
            traceback.format_exc()
        )

        return jsonify({
            "ok": False,
            "error": str(erro),
            "tipo": type(erro).__name__
        }), 500


@app.route("/viewMedias/<nome>", methods=["GET"])
def viewMedia(nome):
    nome_seguro = secure_filename(nome)

    if not nome_seguro or nome_seguro != nome:
        return jsonify({
            "ok": False,
            "error": "Nome inválido"
        }), 400

    caminho = f"{PREFIXO}{nome_seguro}"

    try:
        resultado = blob.head_blob(caminho)

        return redirect(resultado.url, code=302)

    except Exception as erro:
        app.logger.error(
            "Falha ao localizar mídia %s:\n%s",
            nome_seguro,
            traceback.format_exc()
        )

        return jsonify({
            "ok": False,
            "error": str(erro),
            "tipo": type(erro).__name__
        }), 404


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Olá! API está funcionando!",
        "status": 200,
        "params": [
            "/viewMedias",
            "/enviarMedia",
            "/viewMedias/<nome>"
        ]
    }), 200


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
    
