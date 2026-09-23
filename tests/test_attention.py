"""Tests propios de atencion.py.

NO reemplazan a atencion/test_atencion.py (el de la catedra, que todavia no
esta en el repo). Cubren propiedades matematicas y casos chicos calculados a
mano, para poder desarrollar la parte 4 sin el archivo oficial.
"""
import numpy as np
import pytest

from atencion import softmax, atencion, autoatencion, multicabeza, layer_norm


# --------------------------------------------------------------------- softmax

def test_softmax_suma_uno_por_fila():
    x = np.array([[1.0, 2.0, 3.0], [-5.0, 0.0, 5.0]])
    assert np.allclose(softmax(x).sum(axis=-1), 1.0)


def test_softmax_valores_conocidos():
    # softmax([0, ln 2, ln 4]) = [1/7, 2/7, 4/7]
    x = np.array([0.0, np.log(2), np.log(4)])
    assert np.allclose(softmax(x), [1 / 7, 2 / 7, 4 / 7])


def test_softmax_es_estable_con_valores_grandes():
    x = np.array([1000.0, 1000.0, 1000.0])
    out = softmax(x)
    assert np.all(np.isfinite(out)) and np.allclose(out, 1 / 3)


def test_softmax_invariante_a_desplazamiento():
    x = np.array([[0.3, -1.2, 2.0]])
    assert np.allclose(softmax(x), softmax(x + 17.5))


def test_softmax_respeta_el_eje():
    x = np.array([[1.0, 2.0], [3.0, 4.0]])
    assert np.allclose(softmax(x, eje=0).sum(axis=0), 1.0)


def test_softmax_ignora_menos_infinito():
    x = np.array([1.0, -np.inf, 1.0])
    out = softmax(x)
    assert out[1] == 0.0 and np.allclose(out[[0, 2]], 0.5)


# -------------------------------------------------------------------- atencion

def test_atencion_devuelve_salida_y_pesos():
    Q = np.zeros((3, 4))
    K = np.zeros((3, 4))
    V = np.eye(3, 4)
    salida, pesos = atencion(Q, K, V)
    assert salida.shape == (3, 4)
    assert pesos.shape == (3, 3)


def test_atencion_con_scores_nulos_promedia_V():
    # Q = 0 => todos los scores 0 => pesos uniformes => salida = media de V
    Q = np.zeros((2, 3))
    K = np.random.default_rng(0).normal(size=(4, 3))
    V = np.arange(8.0).reshape(4, 2)
    salida, pesos = atencion(Q, K, V)
    assert np.allclose(pesos, 0.25)
    assert np.allclose(salida, V.mean(axis=0))


def test_atencion_escala_por_raiz_de_dk():
    # Con d_k = 4, score crudo 8 => escalado 4. Verificado contra el calculo directo.
    Q = np.array([[2.0, 2.0, 0.0, 0.0]])
    K = np.array([[2.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0]])
    V = np.array([[1.0], [0.0]])
    _, pesos = atencion(Q, K, V)
    esperado = softmax(np.array([4.0 / np.sqrt(4), 0.0]))
    assert np.allclose(pesos[0], esperado)


def test_atencion_con_mascara_booleana_anula_posiciones():
    Q = np.zeros((1, 2))
    K = np.zeros((3, 2))
    V = np.array([[1.0], [2.0], [3.0]])
    mascara = np.array([[True, False, True]])
    salida, pesos = atencion(Q, K, V, mascara=mascara)
    assert pesos[0, 1] == 0.0
    assert np.allclose(salida, 2.0)  # media de 1 y 3


def test_atencion_acepta_mascara_aditiva():
    Q = np.zeros((1, 2))
    K = np.zeros((2, 2))
    V = np.array([[1.0], [3.0]])
    aditiva = np.array([[0.0, -np.inf]])
    _, pesos = atencion(Q, K, V, mascara=aditiva)
    assert np.allclose(pesos, [[1.0, 0.0]])


# ---------------------------------------------------------------- autoatencion

def _entradas_cat():
    """Ejemplo de clase: 3 tokens ("the cat sat"), d = 4."""
    X = np.array([
        [1.0, 0.0, 1.0, 0.0],
        [0.0, 2.0, 0.0, 2.0],
        [1.0, 1.0, 1.0, 1.0],
    ])
    W_q = np.array([[1.0, 0.0, 1.0, 0.0],
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 1.0, 0.0, 1.0]])
    W_k = np.array([[0.0, 0.0, 1.0, 0.0],
                    [1.0, 1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 1.0],
                    [1.0, 0.0, 0.0, 0.0]])
    W_v = np.eye(4)
    return X, W_q, W_k, W_v


def test_autoatencion_formas():
    X, W_q, W_k, W_v = _entradas_cat()
    salida, pesos = autoatencion(X, W_q, W_k, W_v)
    assert salida.shape == (3, 4)
    assert pesos.shape == (3, 3)
    assert np.allclose(pesos.sum(axis=-1), 1.0)


def test_autoatencion_coincide_con_atencion_explicita():
    X, W_q, W_k, W_v = _entradas_cat()
    salida, pesos = autoatencion(X, W_q, W_k, W_v)
    ref_salida, ref_pesos = atencion(X @ W_q, X @ W_k, X @ W_v)
    assert np.allclose(salida, ref_salida)
    assert np.allclose(pesos, ref_pesos)


def test_autoatencion_causal_es_triangular_inferior():
    X, W_q, W_k, W_v = _entradas_cat()
    _, pesos = autoatencion(X, W_q, W_k, W_v, mascara=True)
    assert np.allclose(np.triu(pesos, k=1), 0.0)
    assert np.allclose(pesos.sum(axis=-1), 1.0)
    assert np.allclose(pesos[0], [1.0, 0.0, 0.0])


def test_autoatencion_causal_no_cambia_el_primer_token_al_agregar_tokens():
    X, W_q, W_k, W_v = _entradas_cat()
    corta, _ = autoatencion(X[:2], W_q, W_k, W_v, mascara=True)
    larga, _ = autoatencion(X, W_q, W_k, W_v, mascara=True)
    assert np.allclose(corta, larga[:2])


# ----------------------------------------------------------------- multicabeza

def _dos_cabezas():
    """Dos cabezas sobre subespacios distintos de las mismas proyecciones."""
    _, W_q, W_k, W_v = _entradas_cat()
    return [(W_q[:, :2], W_k[:, :2], W_v[:, :2]), (W_q[:, 2:], W_k[:, 2:], W_v[:, 2:])]


def test_multicabeza_forma_la_da_wo():
    X, *_ = _entradas_cat()
    salida = multicabeza(X, _dos_cabezas(), np.eye(4))
    assert salida.shape == (3, 4)


def test_multicabeza_con_una_cabeza_y_wo_identidad_es_autoatencion():
    X, W_q, W_k, W_v = _entradas_cat()
    esperado, _ = autoatencion(X, W_q, W_k, W_v)
    assert np.allclose(multicabeza(X, [(W_q, W_k, W_v)], np.eye(4)), esperado)


def test_multicabeza_concatena_en_el_orden_de_las_cabezas():
    X, *_ = _entradas_cat()
    cabezas = _dos_cabezas()
    esperado = np.concatenate(
        [autoatencion(X, *c)[0] for c in cabezas], axis=1
    ) @ np.eye(4)
    assert np.allclose(multicabeza(X, cabezas, np.eye(4)), esperado)


def test_multicabeza_propaga_la_mascara_a_cada_cabeza():
    X, *_ = _entradas_cat()
    cabezas = _dos_cabezas()
    esperado = np.concatenate(
        [autoatencion(X, *c, mascara=True)[0] for c in cabezas], axis=1
    )
    assert np.allclose(multicabeza(X, cabezas, np.eye(4), mascara=True), esperado)


def test_multicabeza_rechaza_lista_vacia():
    X, *_ = _entradas_cat()
    with pytest.raises(ValueError):
        multicabeza(X, [], np.eye(4))


# ------------------------------------------------------------------ layer_norm

def test_layer_norm_media_cero_varianza_uno():
    x = np.array([[1.0, 2.0, 3.0, 4.0], [10.0, -2.0, 0.5, 7.0]])
    out = layer_norm(x)
    assert np.allclose(out.mean(axis=-1), 0.0, atol=1e-6)
    assert np.allclose(out.std(axis=-1), 1.0, atol=1e-4)


def test_layer_norm_valores_conocidos():
    # [1,2,3,4]: media 2.5, desvio poblacional sqrt(1.25)
    x = np.array([1.0, 2.0, 3.0, 4.0])
    esperado = (x - 2.5) / np.sqrt(1.25 + 1e-5)
    assert np.allclose(layer_norm(x), esperado)


def test_layer_norm_aplica_gamma_y_beta():
    x = np.array([[1.0, 2.0, 3.0, 4.0]])
    gamma = np.array([2.0, 2.0, 2.0, 2.0])
    beta = np.array([1.0, 1.0, 1.0, 1.0])
    assert np.allclose(layer_norm(x, gamma=gamma, beta=beta), layer_norm(x) * 2.0 + 1.0)


def test_layer_norm_es_invariante_a_escala_y_desplazamiento():
    x = np.array([[1.0, 2.0, 3.0, 4.0]])
    assert np.allclose(layer_norm(x), layer_norm(3.0 * x + 5.0), atol=1e-4)


def test_layer_norm_no_explota_con_entrada_constante():
    x = np.full((1, 4), 7.0)
    assert np.all(np.isfinite(layer_norm(x)))
