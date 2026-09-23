"""Parte 4 de la mision: una capa de atencion escrita solo con NumPy.

Cinco piezas, en el orden en que se componen dentro de un bloque de transformer:

    softmax      -> convierte scores en una distribucion de probabilidad
    atencion     -> scaled dot-product attention sobre Q, K, V ya proyectados
    autoatencion -> proyecta X con W_q/W_k/W_v y llama a `atencion`
    multicabeza  -> parte la dimension del modelo en cabezas y las concatena
    layer_norm   -> normaliza por token, lo que estabiliza el residual

Convenciones:

- La ultima dimension es siempre la del modelo (`d_modelo`) y la anteultima la
  de los tokens. Las funciones aceptan dimensiones de batch a la izquierda.
- `atencion` y las que la usan devuelven `(salida, pesos)`, porque los pesos son
  lo que se inspecciona para explicar que mira cada token.
- Las mascaras pueden ser booleanas (`True` = posicion visible) o aditivas
  (0 visible, `-inf` tapada).
"""
from __future__ import annotations

import numpy as np

__all__ = ["softmax", "atencion", "autoatencion", "multicabeza", "layer_norm"]


def softmax(x: np.ndarray, eje: int = -1) -> np.ndarray:
    """Softmax numericamente estable a lo largo de `eje`.

    Se resta el maximo antes de exponenciar: no cambia el resultado (softmax es
    invariante a desplazamientos constantes) y evita que `exp` desborde.
    """
    x = np.asarray(x, dtype=float)
    maximo = np.max(x, axis=eje, keepdims=True)
    # Un maximo -inf significa que toda la fila esta tapada; se lo lleva a 0
    # para no generar nan en la resta (-inf - -inf).
    maximo = np.where(np.isfinite(maximo), maximo, 0.0)
    exponenciales = np.exp(x - maximo)
    return exponenciales / np.sum(exponenciales, axis=eje, keepdims=True)


def _aplicar_mascara(scores: np.ndarray, mascara: np.ndarray | None) -> np.ndarray:
    """Suma -inf donde la mascara tapa, aceptando forma booleana o aditiva."""
    if mascara is None:
        return scores
    mascara = np.asarray(mascara)
    if mascara.dtype == bool:
        return np.where(mascara, scores, -np.inf)
    return scores + mascara.astype(float)


def _mascara_causal(n_consultas: int, n_claves: int) -> np.ndarray:
    """Triangular inferior: el token i solo ve hasta el i.

    Es lo que impide que el modelo haga trampa mirando el futuro cuando genera
    texto token a token.
    """
    return np.tril(np.ones((n_consultas, n_claves), dtype=bool))


def atencion(
    Q: np.ndarray,
    K: np.ndarray,
    V: np.ndarray,
    mascara: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Scaled dot-product attention.

        pesos  = softmax(Q Kᵀ / sqrt(d_k) + mascara)
        salida = pesos V

    El producto punto mide cuanto se parece cada consulta a cada clave. Se
    divide por sqrt(d_k) porque la varianza del producto crece con la dimension,
    y sin ese freno el softmax se satura y los gradientes se apagan.
    """
    Q = np.asarray(Q, dtype=float)
    K = np.asarray(K, dtype=float)
    V = np.asarray(V, dtype=float)

    d_k = Q.shape[-1]
    scores = np.matmul(Q, np.swapaxes(K, -1, -2)) / np.sqrt(d_k)
    pesos = softmax(_aplicar_mascara(scores, mascara), eje=-1)
    return np.matmul(pesos, V), pesos


def autoatencion(
    X: np.ndarray,
    W_q: np.ndarray,
    W_k: np.ndarray,
    W_v: np.ndarray,
    causal: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Autoatencion de una cabeza: Q, K y V salen todos de la misma X.

    Las tres proyecciones son lo que le da al modelo tres roles distintos para
    el mismo token: que busca (Q), como se ofrece (K) y que aporta (V).
    """
    X = np.asarray(X, dtype=float)
    Q, K, V = X @ np.asarray(W_q), X @ np.asarray(W_k), X @ np.asarray(W_v)

    mascara = _mascara_causal(Q.shape[-2], K.shape[-2]) if causal else None
    return atencion(Q, K, V, mascara=mascara)


def multicabeza(
    X: np.ndarray,
    W_q: np.ndarray,
    W_k: np.ndarray,
    W_v: np.ndarray,
    W_o: np.ndarray,
    n_cabezas: int = 1,
    causal: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Atencion multicabeza.

    Se proyecta una sola vez con las matrices completas y despues se parte el
    resultado en `n_cabezas` bloques de `d_modelo / n_cabezas`. Cada cabeza
    atiende en su propio subespacio -una puede seguir concordancia sintactica y
    otra correferencia-, se concatenan y `W_o` vuelve a mezclarlas.

    Devuelve `(salida, pesos)` con `pesos` de forma `(n_cabezas, n_tokens, n_tokens)`.
    """
    X = np.asarray(X, dtype=float)
    n_tokens, d_modelo = X.shape[-2], X.shape[-1]

    if d_modelo % n_cabezas != 0:
        raise ValueError(
            f"d_modelo={d_modelo} no es divisible por n_cabezas={n_cabezas}"
        )
    d_cabeza = d_modelo // n_cabezas

    def _partir(M: np.ndarray) -> np.ndarray:
        """(..., n_tokens, d_modelo) -> (..., n_cabezas, n_tokens, d_cabeza)."""
        partido = M.reshape(*M.shape[:-1], n_cabezas, d_cabeza)
        return np.swapaxes(partido, -3, -2)

    Q = _partir(X @ np.asarray(W_q))
    K = _partir(X @ np.asarray(W_k))
    V = _partir(X @ np.asarray(W_v))

    mascara = _mascara_causal(n_tokens, n_tokens) if causal else None
    salida_cabezas, pesos = atencion(Q, K, V, mascara=mascara)

    # Concatenar: (..., n_cabezas, n_tokens, d_cabeza) -> (..., n_tokens, d_modelo)
    concatenado = np.swapaxes(salida_cabezas, -3, -2).reshape(
        *X.shape[:-1], d_modelo
    )
    return concatenado @ np.asarray(W_o), pesos


def layer_norm(
    x: np.ndarray,
    gamma: np.ndarray | None = None,
    beta: np.ndarray | None = None,
    eps: float = 1e-5,
) -> np.ndarray:
    """Normalizacion por token sobre la ultima dimension.

        y = gamma * (x - media) / sqrt(varianza + eps) + beta

    Normaliza cada token por separado (no por batch), asi la escala de la
    activacion no depende de con quien le toco viajar. `eps` evita dividir por
    cero cuando el token es constante; `gamma` y `beta` le devuelven al modelo
    la libertad de re-escalar y correr lo que la normalizacion borro.
    """
    x = np.asarray(x, dtype=float)
    media = np.mean(x, axis=-1, keepdims=True)
    varianza = np.var(x, axis=-1, keepdims=True)  # poblacional, no muestral
    normalizado = (x - media) / np.sqrt(varianza + eps)

    if gamma is not None:
        normalizado = normalizado * np.asarray(gamma, dtype=float)
    if beta is not None:
        normalizado = normalizado + np.asarray(beta, dtype=float)
    return normalizado
