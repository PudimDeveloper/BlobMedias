import os
import hmac
import mimetypes
import inspect

from flask import Flask, request, jsonify, redirect
from werkzeug.utils import secure_filename
from vercel.blob import sync as blob

app = Flask(__name__)

PREFIXO = "medias/"
MEDIA_KEY = os.environ.get("MEDIA_KEY", "")


@app.route("/")
def index():
    return jsonify({
        "status": "online",
        "servico": "Blob Medias"
    })


@app.route("/enviarMedia", methods=["POST"])
def enviar_media():
    try:
        if "file" not in request.files:
            return jsonify({
                "erro": "Nenhum arquivo enviado."
            }), 400

        arquivo = request.files["file"]

        if not arquivo.filename:
            return jsonify({
                "erro": "Nome de arquivo inválido."
            }), 400

        nome_original = secure_filename(arquivo.filename)

        if not nome_original:
            return jsonify({
                "erro": "Nome de arquivo inválido."
            }), 400

        conteudo = arquivo.read()

        if not conteudo:
            return jsonify({
                "erro": "O arquivo está vazio."
            }), 400

        mimetype = (
            arquivo.mimetype
            or mimetypes.guess_type(nome_original)[0]
            or "application/octet-stream"
        )

        nome = nome_original
        caminho = f"{PREFIXO}{nome}"

        # Exibe a assinatura instalada para facilitar o diagnóstico.
        print("put_blob:", inspect.signature(blob.put_blob))

        # A chamada usa somente os dois argumentos aceitos
        # pela assinatura indicada no erro recebido.
        resultado = blob.put_blob(caminho, conteudo)

        return jsonify({
            "sucesso": True,
            "nome": nome,
            "url": resultado.url if hasattr(resultado, "url") else None,
            "mimetype": mimetype
        }), 200

    except Exception as erro:
        print("Erro ao enviar mídia:", repr(erro))

        return jsonify({
            "erro": "Não foi possível enviar a mídia.",
            "detalhes": str(erro)
        }), 500


@app.route("/viewMedias", methods=["GET"])
def listar_medias():
    try:
        medias = []

        for item in blob.query_blobs(prefix=PREFIXO):
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
        print("Erro ao listar mídias:", repr(erro))

        return jsonify({
            "erro": "Não foi possível listar as mídias.",
            "detalhes": str(erro)
        }), 500


@app.route("/viewMedias/<path:nome>", methods=["GET"])
def visualizar_media(nome):
    try:
        chave = request.args.get("key", "")

        if not MEDIA_KEY or not hmac.compare_digest(chave, MEDIA_KEY):
            return jsonify({
                "erro": "Key incorreta."
            }), 403

        nome = secure_filename(nome)

        if not nome:
            return jsonify({
                "erro": "Nome de mídia inválido."
            }), 400

        caminho = f"{PREFIXO}{nome}"
        resultado = blob.head_blob(caminho)

        if not resultado:
            return jsonify({
                "erro": "Mídia não encontrada."
            }), 404

        return redirect(resultado.url)

    except Exception as erro:
        print("Erro ao visualizar mídia:", repr(erro))

        return jsonify({
            "erro": "Não foi possível visualizar a mídia.",
            "detalhes": str(erro)
        }), 500


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=porta)
