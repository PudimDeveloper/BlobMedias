from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)

PASTA = Path("/medias")
PASTA.mkdir(parents=True, exist_ok=True)


@app.route("/enviarMedia", methods=["POST"])
def blobMedia():
    arquivo = request.files.get("blob")

    if not arquivo:
        return jsonify({
            "ok": False,
            "error": "Nenhum arquivo enviado"
        }), 400

    nome_original = secure_filename(arquivo.filename or "media.bin")
    extensao = Path(nome_original).suffix
    nome = f"{uuid.uuid4().hex}{extensao}"

    caminho = PASTA / nome
    arquivo.save(caminho)

    return jsonify({
        "ok": True,
        "url": f"/viewMedias/{nome}"
    })


@app.route("/viewMedias", methods=["GET"])
def viewMedias():
    if not PASTA.exists():
        return jsonify([])

    arquivos = [
        {
            "nome": arquivo.name,
            "url": f"/viewMedias/{arquivo.name}"
        }
        for arquivo in sorted(PASTA.iterdir(), key=lambda item: item.name)
        if arquivo.is_file()
    ]

    return jsonify(arquivos)


@app.route("/viewMedias/<nome>", methods=["GET"])
def viewMedia(nome):
    return send_from_directory(PASTA, nome)


@app.route("/")
def home():
    return {
        "message": "Olá! Api está funcionando!",
        "status": 200,
        "params": [
            "/viewMedias",
            "/enviarMedia"
        ]
    }


if __name__ == "__main__":
    app.run(debug=True)
