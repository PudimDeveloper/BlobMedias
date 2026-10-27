
from flask import Flask, request, jsonify, redirect
from pathlib import Path
from werkzeug.utils import secure_filename
from vercel.blob import sync as blob
import mimetypes
import uuid

app = Flask(__name__)

PREFIXO = "medias/"


@app.route("/enviarMedia", methods=["POST"])
def blobMedia():
    arquivo = request.files.get("blob")

    if not arquivo or not arquivo.filename:
        return jsonify({
            "ok": False,
            "error": "Nenhum arquivo enviado"
        }), 400

    nome_original = secure_filename(arquivo.filename)
    extensao = Path(nome_original).suffix.lower()
    nome = f"{uuid.uuid4().hex}{extensao}"
    caminho = f"{PREFIXO}{nome}"

    try:
        conteudo = arquivo.read()

        resultado = blob.put_blob(
            caminho,
            conteudo,
            access="public",
            content_type=(
                arquivo.mimetype
                or mimetypes.guess_type(nome)[0]
                or "application/octet-stream"
            )
        )

        return jsonify({
            "ok": True,
            "nome": nome,
            "url": f"/viewMedias/{nome}",
            "blobUrl": resultado.url
        }), 201

    except Exception:
        app.logger.exception("Erro ao enviar mídia")
        
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
        return jsonify(arquivos)

    except Exception:
        app.logger.exception("Erro ao listar mídias")
        return jsonify({
            "ok": False,
            "error": "Falha ao listar mídias"
        }), 500


@app.route("/viewMedias/<nome>", methods=["GET"])
def viewMedia(nome):
    nome = secure_filename(nome)

    if not nome:
        return jsonify({
            "ok": False,
            "error": "Nome inválido"
        }), 400

    caminho = f"{PREFIXO}{nome}"

    try:
        resultado = blob.head_blob(caminho)
        return redirect(resultado.url, code=302)

    except Exception:
        app.logger.exception("Erro ao localizar mídia")
        return jsonify({
            "ok": False,
            "error": "Mídia não encontrada"
        }), 404


@app.route("/")
def home():
    return jsonify({
        "message": "Olá! API está funcionando!",
        "status": 200,
        "params": [
            "/viewMedias",
            "/enviarMedia",
            "/viewMedias/<nome>"
        ]
    })
