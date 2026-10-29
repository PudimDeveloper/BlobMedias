from flask import Flask, request, jsonify, redirect
from werkzeug.utils import secure_filename
from vercel.blob import sync as blob
from pathlib import Path
import mimetypes
import traceback
import uuid
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PREFIXO = "medias/"
BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://blob-medias.vercel.app"
).rstrip("/")

app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

MIMES_GENERICOS = {
    "application/octet-stream",
    "binary/octet-stream",
    "application/x-octet-stream",
}

MIME_POR_EXTENSAO = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".avif": "image/avif",
    ".bmp": "image/bmp",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
    ".pdf": "application/pdf",
}

EXTENSAO_POR_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
    "image/bmp": ".bmp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "application/pdf": ".pdf",
}

EXTENSOES_EXIBIVEIS = set(MIME_POR_EXTENSAO)


def mime_por_assinatura(conteudo):
    if conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    if conteudo.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    if conteudo.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"

    if len(conteudo) >= 12 and conteudo[:4] == b"RIFF":
        if conteudo[8:12] == b"WEBP":
            return "image/webp"

        if conteudo[8:12] == b"WAVE":
            return "audio/wav"

    if conteudo.startswith(b"%PDF-"):
        return "application/pdf"

    if conteudo.startswith(b"OggS"):
        return "audio/ogg"

    if conteudo.startswith(b"ID3"):
        return "audio/mpeg"

    if conteudo.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"

    if len(conteudo) >= 12 and conteudo[4:8] == b"ftyp":
        marca = conteudo[8:12]

        if marca in {b"avif", b"avis"}:
            return "image/avif"

        if marca == b"qt  ":
            return "video/quicktime"

        return "video/mp4"

    return None


def determinar_mime(nome, mime_recebido, conteudo):
    mime_assinatura = mime_por_assinatura(conteudo)

    if mime_assinatura:
        return mime_assinatura

    extensao = Path(nome).suffix.lower()

    mime_extensao = (
        MIME_POR_EXTENSAO.get(extensao)
        or mimetypes.guess_type(nome)[0]
    )

    mime_recebido = (
        (mime_recebido or "")
        .split(";", 1)[0]
        .strip()
        .lower()
    )

    if mime_extensao and mime_extensao not in MIMES_GENERICOS:
        return mime_extensao

    if mime_recebido and mime_recebido not in MIMES_GENERICOS:
        return mime_recebido

    return mime_extensao or mime_recebido or "application/octet-stream"


def determinar_extensao(nome_original, mime):
    extensao = Path(nome_original).suffix.lower()

    mime_extensao = (
        MIME_POR_EXTENSAO.get(extensao)
        or mimetypes.guess_type(nome_original)[0]
    )

    extensao_correta = EXTENSAO_POR_MIME.get(mime)

    if extensao_correta and (
        not extensao
        or not mime_extensao
        or mime_extensao in MIMES_GENERICOS
        or mime_extensao != mime
    ):
        return extensao_correta

    return extensao


def erro_json(mensagem, erro, status=500):
    app.logger.error(
        "%s | %s: %s\n%s",
        mensagem,
        type(erro).__name__,
        erro,
        traceback.format_exc()
    )

    return jsonify({
        "ok": False,
        "error": str(erro),
        "tipo": type(erro).__name__
    }), status


def parece_exibivel(nome, mime):
    mime = (mime or "").lower()
    extensao = Path(nome).suffix.lower()

    return (
        mime.startswith(("image/", "video/", "audio/"))
        or mime in {
            "application/pdf",
            "text/plain",
            "application/json",
            "text/xml",
        }
        or extensao in EXTENSOES_EXIBIVEIS
    )


def validar_nome(nome):
    nome_seguro = secure_filename(nome)

    return nome_seguro if nome_seguro == nome and nome_seguro else None


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Olá! API está funcionando!",
        "status": 200,
        "params": [
            "/enviarMedia",
            "/viewMedias",
            "/viewMedias/<nome>",
            "/diagnostico/<nome>",
        ]
    }), 200


@app.route("/enviarMedia", methods=["POST"])
def enviar_media():
    arquivo = request.files.get("blob")

    if not arquivo or not arquivo.filename:
        return jsonify({
            "ok": False,
            "error": "Nenhum arquivo enviado no campo 'blob'."
        }), 400

    nome_original = secure_filename(arquivo.filename)

    if not nome_original:
        return jsonify({
            "ok": False,
            "error": "Nome de arquivo inválido."
        }), 400

    try:
        conteudo = arquivo.read()

        if not conteudo:
            return jsonify({
                "ok": False,
                "error": "O arquivo está vazio."
            }), 400

        mime = determinar_mime(
            nome_original,
            arquivo.mimetype,
            conteudo
        )

        extensao = determinar_extensao(nome_original, mime)
        nome = f"{uuid.uuid4().hex}{extensao}"
        caminho = f"{PREFIXO}{nome}"

        resultado = blob.put_blob(
            caminho,
            conteudo,
            access="public",
            content_type=mime
        )

        content_type = getattr(resultado, "content_type", None) or mime
        content_disposition = getattr(
            resultado,
            "content_disposition",
            None
        )

        app.logger.info(
            "Mídia enviada: nome=%s, tamanho=%d, MIME=%s, disposição=%s",
            nome,
            len(conteudo),
            content_type,
            content_disposition
        )

        return jsonify({
            "ok": True,
            "nome": nome,
            "url": f"{BASE_URL}/viewMedias/{nome}",
            "blobUrl": resultado.url,
            "contentType": content_type,
            "contentDisposition": content_disposition
        }), 201

    except Exception as erro:
        return erro_json("Falha ao enviar mídia", erro)


@app.route("/viewMedias", methods=["GET"])
def listar_medias():
    try:
        arquivos = []

        for item in blob.query_blobs(prefix=PREFIXO):
            nome = item.pathname.removeprefix(PREFIXO)

            arquivos.append({
                "nome": nome,
                "blobUrl": item.url
            })

        arquivos.sort(key=lambda item: item["nome"])

        return jsonify(arquivos), 200

    except Exception as erro:
        return erro_json("Falha ao listar mídias", erro)


@app.route("/diagnostico/<nome>", methods=["GET"])
def diagnostico_media(nome):
    nome_seguro = validar_nome(nome)

    if not nome_seguro:
        return jsonify({
            "ok": False,
            "error": "Nome inválido."
        }), 400

    try:
        metadata = blob.head_blob(f"{PREFIXO}{nome_seguro}")

        return jsonify({
            "ok": True,
            "nome": metadata.pathname,
            "url": metadata.url,
            "contentType": metadata.content_type,
            "contentDisposition": metadata.content_disposition,
            "cacheControl": metadata.cache_control,
            "size": metadata.size,
            "exibivel": parece_exibivel(
                nome_seguro,
                metadata.content_type
            )
        }), 200

    except Exception as erro:
        if type(erro).__name__ == "BlobNotFoundError":
            return jsonify({
                "ok": False,
                "error": "Mídia não encontrada."
            }), 404

        return erro_json("Falha ao consultar metadados", erro)


@app.route("/viewMedias/<nome>", methods=["GET"])
def visualizar_media(nome):
    nome_seguro = validar_nome(nome)

    if not nome_seguro:
        return jsonify({
            "ok": False,
            "error": "Nome inválido."
        }), 400

    try:
        metadata = blob.head_blob(f"{PREFIXO}{nome_seguro}")

        content_type = metadata.content_type or ""
        content_disposition = (
            metadata.content_disposition or ""
        ).lower()

        if (
            "attachment" in content_disposition
            and parece_exibivel(nome_seguro, content_type)
        ):
            return jsonify({
                "ok": False,
                "error": (
                    "Esta mídia foi armazenada com disposição de download. "
                    "A rota não consegue alterar os metadados já gravados."
                ),
                "contentType": content_type,
                "contentDisposition": metadata.content_disposition,
                "solucao": (
                    "Envie novamente a mídia após atualizar o código. "
                    "O novo arquivo terá uma URL própria."
                )
            }), 409

        return redirect(metadata.url, code=302)

    except Exception as erro:
        if type(erro).__name__ == "BlobNotFoundError":
            return jsonify({
                "ok": False,
                "error": "Mídia não encontrada."
            }), 404

        return erro_json("Falha ao localizar mídia", erro)


@app.errorhandler(413)
def arquivo_grande(_erro):
    return jsonify({
        "ok": False,
        "error": "O arquivo excede o limite de 50 MB."
    }), 413


@app.errorhandler(500)
def erro_interno(_erro):
    return jsonify({
        "ok": False,
        "error": "Erro interno da API."
    }), 500


if __name__ == "__main__":
    app.run()
