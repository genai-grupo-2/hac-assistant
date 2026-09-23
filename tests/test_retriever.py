"""Tests del recuperador (parte 1).

Corren sin descargar modelos: se usa un encoder falso, deterministico, basado en
bolsa de palabras. Lo que se verifica aca es el troceado, el contrato del indice
y el formato de salida; la calidad del encoder se mide con el evaluador de la
catedra, no con tests.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from retriever.chunking import Fragmento, trocear
from retriever.config import Config, ConfigChunking, cargar_config
from retriever.corpus import cargar_corpus
from retriever.encoders import normalizar
from retriever.index import Indice
import recuperar


DOC_VISITAS = """# Regimen de visitas

Texto introductorio del reglamento de visitas del hospital Arroyo Claro.

## Sala general

El horario de visita en sala general es de 14 a 18 horas, todos los dias.
Se admiten hasta dos visitantes por paciente.

## Terapia intensiva

En terapia intensiva la visita es de 16 a 17 horas, un visitante por vez.
"""

DOC_ESTUDIOS = """# Preparacion para estudios

## Ecografia abdominal

Hay que venir en ayunas de ocho horas y con la vejiga llena.
"""


@pytest.fixture()
def corpus(tmp_path: Path) -> Path:
    directorio = tmp_path / "corpus"
    directorio.mkdir()
    (directorio / "visitas.md").write_text(DOC_VISITAS, encoding="utf-8")
    (directorio / "estudios.md").write_text(DOC_ESTUDIOS, encoding="utf-8")
    return directorio


class EncoderBolsa:
    """Encoder falso: una dimension por palabra del vocabulario visto."""

    nombre = "bolsa"

    def __init__(self) -> None:
        self._vocabulario: dict[str, int] = {}

    def _vector(self, texto: str, crecer: bool) -> np.ndarray:
        cuenta: dict[int, int] = {}
        for palabra in texto.lower().split():
            if palabra not in self._vocabulario:
                if not crecer:
                    continue
                self._vocabulario[palabra] = len(self._vocabulario)
            indice = self._vocabulario[palabra]
            cuenta[indice] = cuenta.get(indice, 0) + 1
        return cuenta  # type: ignore[return-value]

    def _matriz(self, textos: list[str], crecer: bool) -> np.ndarray:
        cuentas = [self._vector(t, crecer) for t in textos]
        matriz = np.zeros((len(textos), max(len(self._vocabulario), 1)))
        for fila, cuenta in enumerate(cuentas):
            for columna, valor in cuenta.items():  # type: ignore[union-attr]
                matriz[fila, columna] = valor
        return normalizar(matriz)

    def codificar_pasajes(self, textos: list[str]) -> np.ndarray:
        return self._matriz(textos, crecer=True)

    def codificar_consultas(self, textos: list[str]) -> np.ndarray:
        return self._matriz(textos, crecer=False)


# ---------------------------------------------------------------------- corpus

def test_cargar_corpus_ordena_y_toma_el_titulo(corpus: Path):
    documentos = cargar_corpus(corpus)
    assert [d.doc_id for d in documentos] == ["estudios", "visitas"]
    assert documentos[1].titulo == "Regimen de visitas"


def test_cargar_corpus_falla_claro_si_no_existe(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="datos/corpus"):
        cargar_corpus(tmp_path / "no_existe")


# -------------------------------------------------------------------- chunking

def test_chunking_por_estructura_separa_secciones(corpus: Path):
    fragmentos = trocear(cargar_corpus(corpus), ConfigChunking(min_palabras=1))
    secciones = {f.seccion for f in fragmentos if f.doc_id == "visitas"}
    assert {"Sala general", "Terapia intensiva"} <= secciones


def test_chunking_por_estructura_no_mezcla_horarios(corpus: Path):
    """Lo que hace util el corte por seccion: cada horario queda aislado."""
    fragmentos = trocear(cargar_corpus(corpus), ConfigChunking(min_palabras=1))
    sala = next(f for f in fragmentos if f.seccion == "Sala general")
    assert "14 a 18" in sala.texto
    assert "16 a 17" not in sala.texto


def test_chunking_respeta_el_maximo_de_palabras(corpus: Path):
    cfg = ConfigChunking(max_palabras=8, min_palabras=1)
    fragmentos = trocear(cargar_corpus(corpus), cfg)
    assert all(len(f.texto.split()) <= 8 for f in fragmentos)


def test_chunking_fusiona_fragmentos_muy_cortos(corpus: Path):
    sueltos = trocear(cargar_corpus(corpus), ConfigChunking(min_palabras=1))
    fusionados = trocear(cargar_corpus(corpus), ConfigChunking(min_palabras=200))
    assert len(fusionados) < len(sueltos)


def test_chunking_por_ventana_solapa(corpus: Path):
    cfg = ConfigChunking(estrategia="ventana", tamano=10, solapamiento=5)
    fragmentos = [f for f in trocear(cargar_corpus(corpus), cfg) if f.doc_id == "visitas"]
    assert len(fragmentos) > 1
    cola = fragmentos[0].texto.split()[-5:]
    assert fragmentos[1].texto.split()[:5] == cola


def test_chunking_por_ventana_rechaza_solapamiento_invalido(corpus: Path):
    cfg = ConfigChunking(estrategia="ventana", tamano=10, solapamiento=10)
    with pytest.raises(ValueError, match="solapamiento"):
        trocear(cargar_corpus(corpus), cfg)


def test_chunking_rechaza_estrategia_desconocida(corpus: Path):
    with pytest.raises(ValueError, match="desconocida"):
        trocear(cargar_corpus(corpus), ConfigChunking(estrategia="magia"))


def test_prefijo_de_metadatos_agrega_contexto():
    frag = Fragmento(texto="De 14 a 18.", doc_id="v", documento="Visitas", seccion="Sala general")
    assert frag.para_embeber(True).startswith("Visitas > Sala general")
    assert frag.para_embeber(False) == "De 14 a 18."


# ---------------------------------------------------------------------- indice

def _indice(corpus: Path, **busqueda) -> Indice:
    cfg = Config(chunking=ConfigChunking(min_palabras=1)).con(busqueda=busqueda or {"top_k": 2})
    return Indice.construir(cfg, encoder=EncoderBolsa(), ruta_corpus=corpus)


def test_indice_recupera_la_seccion_correcta(corpus: Path):
    resultados = _indice(corpus).buscar("horario de visita en terapia intensiva")
    assert "16 a 17" in resultados[0].fragmento.texto


def test_indice_respeta_top_k(corpus: Path):
    assert len(_indice(corpus, top_k=1).buscar("visita")) == 1


def test_indice_ordena_por_score_descendente(corpus: Path):
    scores = [r.score for r in _indice(corpus, top_k=5).buscar("ayunas ecografia")]
    assert scores == sorted(scores, reverse=True)


def test_indice_aplica_el_umbral(corpus: Path):
    sin_umbral = _indice(corpus, top_k=5).buscar("visita")
    con_umbral = _indice(corpus, top_k=5, umbral=0.99).buscar("visita")
    assert len(con_umbral) < len(sin_umbral)


def test_indice_es_determinista(corpus: Path):
    a = [r.fragmento.texto for r in _indice(corpus, top_k=3).buscar("visita")]
    b = [r.fragmento.texto for r in _indice(corpus, top_k=3).buscar("visita")]
    assert a == b


# ------------------------------------------------------------------ config CLI

def test_config_por_defecto_si_no_hay_archivo(tmp_path: Path):
    cfg = cargar_config(tmp_path / "no_existe.yaml")
    assert cfg.encoder and cfg.busqueda.top_k > 0


def test_config_del_repo_se_lee():
    cfg = cargar_config()
    assert cfg.chunking.estrategia in {"estructura", "ventana"}


def test_config_con_pisa_solo_lo_indicado():
    cfg = Config().con(encoder="minilm", busqueda={"top_k": 9})
    assert cfg.encoder == "minilm"
    assert cfg.busqueda.top_k == 9
    assert cfg.busqueda.umbral == Config().busqueda.umbral


def test_flags_del_barrido_pisan_el_yaml():
    args = recuperar.parsear_argumentos(
        ["--preguntas", "p", "--salida", "s", "--encoder", "bert_base", "--top-k", "7"]
    )
    cfg = recuperar.construir_config(args)
    assert cfg.encoder == "bert_base" and cfg.busqueda.top_k == 7


def test_texto_de_acepta_varios_nombres_de_campo():
    assert recuperar.texto_de({"id": "R01", "pregunta": "hola"}) == "hola"
    assert recuperar.texto_de({"id": "R01", "consulta": "hola"}) == "hola"
    with pytest.raises(KeyError):
        recuperar.texto_de({"id": "R01"})


def test_salida_cumple_el_contrato(corpus: Path, tmp_path: Path):
    preguntas = [
        {"id": "R01", "pregunta": "horario de visita en terapia intensiva"},
        {"id": "R02", "pregunta": "como me preparo para una ecografia"},
    ]
    filas = recuperar.recuperar(preguntas, _indice(corpus, top_k=2))
    destino = tmp_path / "resultados.jsonl"
    recuperar.escribir_jsonl(filas, destino)

    leidas = [json.loads(l) for l in destino.read_text(encoding="utf-8").splitlines()]
    assert [f["id"] for f in leidas] == ["R01", "R02"]
    assert all(isinstance(f["fragmentos"], list) for f in leidas)
    assert all(isinstance(t, str) for f in leidas for t in f["fragmentos"])
