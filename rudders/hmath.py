"""Hyperbolic math"""

import tensorflow as tf

MIN_NORM = 1e-15
MAX_TANH_ARG = 15.0
BALL_EPS = {tf.float32: 4e-3, tf.float64: 1e-10}


def artanh(x):
    eps = BALL_EPS[x.dtype]
    return tf.atanh(tf.minimum(tf.maximum(x, -1 + eps), 1 - eps))


def tanh(x):
    return tf.tanh(tf.minimum(tf.maximum(x, -MAX_TANH_ARG), MAX_TANH_ARG))


def expmap0(u, c):
    """Hyperbolic exponential map at origin of space in the Poincare ball model.

    Args:
      u: Tensor of size B x dimension representing tangent vectors.
      c: Tensor of size 1 representing the absolute hyperbolic curvature.

    Returns:
      Tensor of shape B x dimension.
    """
    sqrt_c = tf.sqrt(c)
    u_norm = tf.maximum(tf.norm(u, axis=-1, keepdims=True), MIN_NORM)
    gamma_1 = tanh(sqrt_c * u_norm) * u / (sqrt_c * u_norm)
    ret = project(gamma_1, c)
    return ret


def logmap0(y, c):
    """Hyperbolic logarithmic map at origin of space in the Poincare ball model.

    Args:
      y: Tensor of size B x dimension representing hyperbolic points
      c: Tensor of size 1 representing the absolute hyperbolic curvature.

    Returns:
      Tensor of shape B x dimension.
    """
    sqrt_c = tf.sqrt(c)
    y_norm = tf.maximum(tf.norm(y, axis=-1, keepdims=True), MIN_NORM)
    return y / y_norm / sqrt_c * artanh(sqrt_c * y_norm)


def project(x, c):
    """Projects points to the Poincare ball.

    Args:
      x: Tensor of size B x dimension.
      c: Tensor of size 1 representing the absolute hyperbolic curvature.

    Returns:
      Tensor of shape B x dimension where each row is a point that lies within
      the Poincare ball.
    """
    eps = BALL_EPS[x.dtype]
    return tf.clip_by_norm(t=x, clip_norm=(1. - eps) / tf.sqrt(c), axes=[1])


def mobius_add(x, y, c):
    """Element-wise Mobius addition.

    Args:
      x: Tensor of size B x dimension representing hyperbolic points.
      y: Tensor of size B x dimension representing hyperbolic points.
      c: Tensor of size 1 representing the absolute hyperbolic curvature.

    Returns:
      Tensor of shape B x dimension representing the element-wise Mobius addition
      of x and y, given by:
                    (1 + 2c<x,y> + c|y|^2)x + (1 - c|x|^2)y
    x +_m y =   -----------------------------------------------
                       1 + 2c<x,y> + c^2 |x|^2 |y|^2
    """
    cx2 = c * tf.reduce_sum(x * x, axis=-1, keepdims=True)
    cy2 = c * tf.reduce_sum(y * y, axis=-1, keepdims=True)
    cxy = c * tf.reduce_sum(x * y, axis=-1, keepdims=True)
    num = (1 + 2 * cxy + cy2) * x + (1 - cx2) * y
    denom = 1 + 2 * cxy + cx2 * cy2
    return project(num / tf.maximum(denom, MIN_NORM), c)


def hyp_distance(x, y, c):
    """Hyperbolic distance on the Poincare ball.

    The distance is calculated following the formula
        d(x, y) = 2/sqrt(c) atanh(sqrt(c) ||(-x) +_m y||)
    while calculating the norm of the mobius addition directly.

    Args:
      x: Tensor of shape (b1, b2, ..., bn, d), where n is at least 1.
      y: Tensor of the same shape (a1, a2, ..., an, d) so that if both
        ak and bk are not equal to 1 then ak=bk.
      c: Tensor of size 1 representing the absolute hyperbolic curvature.

    Returns:
      Tensor of size (c1, c2, ..., cn, 1) where ck=max(bk,ak)
    """
    sqrt_c = tf.sqrt(c)
    x2 = tf.reduce_sum(x * x, axis=-1, keepdims=True)
    y2 = tf.reduce_sum(y * y, axis=-1, keepdims=True)
    xy = tf.reduce_sum(x * y, axis=-1, keepdims=True)
    c1 = 1 - 2 * c * xy + c * y2
    c2 = 1 - c * x2
    num = tf.sqrt(tf.square(c1) * x2 + tf.square(c2) * y2 - (2 * c1 * c2) * xy)
    denom = 1 - 2 * c * xy + tf.square(c) * x2 * y2
    pairwise_norm = num / tf.maximum(denom, MIN_NORM)
    dist = artanh(sqrt_c * pairwise_norm)
    return 2 * dist / sqrt_c


def hyp_distance_all_pairs(x, y, c):
    """Hyperbolic distance between all pairs among x and y.

    Args:
      x: Tensor of shape (b1, d).
      y: Tensor of shape (b2, d).
      c: Tensor of size 1 representing the absolute hyperbolic curvature.

    Returns:
      Tensor of size (b1, b2).
    """
    x = tf.expand_dims(x, 1)
    y = tf.expand_dims(y, 0)
    return tf.squeeze(hyp_distance(x, y, c), axis=[-1])


def hyp_distance_batch_rhs(x, y, c):
    """Hyperbolic distance between the points x and the corresponding batch y.

    Should be used when for each point in the batch b1 of x, there are b2 points
    in y we need to calculate the distance with.

    Args:
      x: Tensor of shape (b1, d).
      y: Tensor of shape (b1, b2, d).
      c: Tensor of size 1 representing the absolute hyperbolic curvature.

    Returns:
      Tensor of size (b1, b2).
    """
    x = tf.expand_dims(x, 1)
    return tf.squeeze(hyp_distance(x, y, c), axis=[-1])
