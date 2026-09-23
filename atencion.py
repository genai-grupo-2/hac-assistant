"""Parte 4 de la mision: una capa de atencion escrita solo con NumPy.

Firmas segun `atencion/test_atencion.py` (los valores de referencia son los del
ejemplo de la clase 8, "the cat sat", d = 4):

    softmax(M)                                  softmax por fila (ultimo eje)
    atencion(Q, K, V, mascara=False)            -> (salida, A)
    autoatencion(X, Wq, Wk, Wv, mascara=False)  -> (salida, A)
    multicabeza(X, cabezas, Wo, mascara=False)  -> salida
    layer_norm(x, eps=1e-5)                     media 0 y varianza 1 por fila

`mascara=True` aplica la mascara causal (triangular inferior). Tambien se acepta
una mascara explicita como arreglo, booleano (`True` = posicion visible) o
aditivo (0 visible, `-inf` tapada), que es lo que se usa en un batch con padding.
"""
import numpy as np

__all__ = ["softmax", "atencion", "autoatencion", "multicabeza", "layer_norm"]


def softmax(M, eje=-1):
    """Softmax numericamente estable a lo largo de `eje` (por defecto, por fila).

    Se resta el maximo antes de exponenciar: no cambia el resultado -softmax es
    invariante a desplazamientos constantes- y evita que `exp` desborde.
    """
    M = np.asarray(M, dtype=float)
    maximo = np.max(M, axis=eje, keepdims=True)
    # Un maximo -inf significa que toda la fila esta tapada; se lo lleva a 0
    # para no generar nan en la resta (-inf - -inf).
    maximo = np.where(np.isfinite(maximo), maximo, 0.0)
    exponenciales = np.exp(M - maximo)
    return exponenciales / np.sum(exponenciales, axis=eje, keepdims=True)


def _mascara_causal(n_consultas, n_claves):
    """Triangular inferior: el token i solo ve hasta el i.

    Es lo que impide que el modelo haga trampa mirando el futuro cuando genera
    texto token a token.
    """
    return np.tril(np.ones((n_consultas, n_claves), dtype=bool))


def _aplicar_mascara(scores, mascara):
    """Tapa con -inf donde corresponda.

    `mascara` puede ser un booleano (True = causal), o un arreglo booleano
    (True = visible) o aditivo (0 visible, -inf tapada).
    """
    if mascara is None or mascara is False:
        return scores
    if mascara is True:
        mascara = _mascara_causal(scores.shape[-2], scores.shape[-1])

    mascara = np.asarray(mascara)
    if mascara.dtype == bool:
        return np.where(mascara, scores, -np.inf)
    return scores + mascara.astype(float)


def atencion(Q, K, V, mascara=False):
    """Scaled dot-product attention.

        A      = softmax(Q Kᵀ / sqrt(d_k) + mascara)
        salida = A V

    El producto punto mide cuanto se parece cada consulta a cada clave. Se divide
    por sqrt(d_k) porque la varianza del producto crece con la dimension, y sin
    ese freno el softmax se satura y los gradientes se apagan.

    Devuelve `(salida, A)`: la matriz de atencion es lo que se inspecciona para
    explicar que mira cada token. `d_v` no tiene por que ser igual a `d_k`, asi
    que la salida sale con la dimension de V.
    """
    Q = np.asarray(Q, dtype=float)
    K = np.asarray(K, dtype=float)
    V = np.asarray(V, dtype=float)

    d_k = Q.shape[-1]
    scores = np.matmul(Q, np.swapaxes(K, -1, -2)) / np.sqrt(d_k)
    A = softmax(_aplicar_mascara(scores, mascara))
    return np.matmul(A, V), A


def autoatencion(X, Wq, Wk, Wv, mascara=False):
    """Autoatencion de una cabeza: Q, K y V salen todos de la misma X.

    Las tres proyecciones son lo que le da al modelo tres roles distintos para el
    mismo token: que busca (Q), como se ofrece (K) y que aporta (V).
    """
    X = np.asarray(X, dtype=float)
    Q = X @ np.asarray(Wq, dtype=float)
    K = X @ np.asarray(Wk, dtype=float)
    V = X @ np.asarray(Wv, dtype=float)
    return atencion(Q, K, V, mascara=mascara)


def multicabeza(X, cabezas, Wo, mascara=False):
    """Atencion multicabeza.

    `cabezas` es una lista de ternas `(Wq, Wk, Wv)`, una por cabeza. Cada cabeza
    atiende en su propio subespacio -una puede seguir concordancia sintactica y
    otra correferencia-, las salidas se concatenan sobre la dimension de rasgos
    y `Wo` las vuelve a mezclar en un solo vector por token.

    Devuelve solo la salida: los pesos de cada cabeza se obtienen llamando a
    `autoatencion` con esa terna.
    """
    if not len(cabezas):
        raise ValueError("multicabeza necesita al menos una cabeza")

    salidas = [autoatencion(X, Wq, Wk, Wv, mascara=mascara)[0] for Wq, Wk, Wv in cabezas]
    concatenado = np.concatenate(salidas, axis=-1)
    return concatenado @ np.asarray(Wo, dtype=float)


def layer_norm(x, eps=1e-5, gamma=None, beta=None):
    """Normalizacion por fila (por token) sobre la ultima dimension.

        y = gamma * (x - media) / sqrt(varianza + eps) + beta

    Normaliza cada token por separado -no por batch-, asi la escala de la
    activacion no depende de con quien le toco viajar. `eps` evita dividir por
    cero cuando el token es constante. `gamma` y `beta` son opcionales y le
    devuelven al modelo la libertad de re-escalar y correr lo que la
    normalizacion borro; sin ellos la salida tiene media 0 y varianza 1.
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
