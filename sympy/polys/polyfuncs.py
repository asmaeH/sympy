"""High--level polynomials manipulation functions. """

from sympy.polys.polytools import poly_from_expr, Poly
from sympy.polys.polyoptions import allowed_flags

from sympy.polys.specialpolys import (
    symmetric_poly, interpolating_poly,
)

from sympy.polys.polyerrors import (
    PolificationFailed, ComputationFailed,
)

from sympy.utilities import (
    all, any, numbered_symbols,
)

from sympy.core import S, Add, Mul

def symmetrize(f, *gens, **args):
    """
    Rewrite a polynomial in terms of elementary symmetric polynomials.

    A symmetric polynomial is a multivariate polynomial that remains invariant
    under any variable permutation, i.e., if ``f = f(x_1, x_2, ..., x_n)``, then
    ``f = f(x_{i_1}, x_{i_2}, ..., x_{i_n})``, where ``(i_1, i_2, ..., i_n)`` is
    a permutation of ``(1, 2, ..., n)`` (an element of the group ``S_n``).

    Returns a list of symmetric polynomials ``(f1, f2, ..., fn)`` such that
    ``f = f1 + f2 + ... + fn``.

    **Example**

    >>> from sympy import symmetrize
    >>> from sympy.abc import x, y
    >>> symmetrize(2*x**4 + y**2 - x**2 + y**3)
    (2*x*y - (x + y)**2 + 4*x**2*y**2 - 8*x*y*(x + y)**2 + 2*(x + y)**4,
     2*y**2 + y**3 - 2*y**4)
    >>> symmetrize(2*x**4 + y**2 - x**2 + y**3, formal=True)
    (2*s2 - s1**2 + 4*s2**2 - 8*s2*s1**2 + 2*s1**4, 2*y**2 + y**3 - 2*y**4,
     {s1: x + y, s2: x*y})

    """
    allowed_flags(args, ['formal'])

    try:
        f, opt = poly_from_expr(f, *gens, **args)
    except PolificationFailed, exc:
        return ComputationFailed('symmetrize', 1, exc)

    polys, symbols = [], numbered_symbols('s', start=1)

    gens, dom = f.gens, f.get_domain()

    for i in range(0, len(f.gens)):
        poly = symmetric_poly(i+1, gens, polys=True)
        polys.append((symbols.next(), poly.set_domain(dom)))

    indices = range(0, len(gens) - 1)
    weights = range(len(gens), 0, -1)

    symmetric = []

    if not f.is_homogeneous:
        symmetric.append(f.TC())
        f -= f.TC()

    while f:
        _height, _monom, _coeff = -1, None, None

        for i, (monom, coeff) in enumerate(f.terms()):
            if all(monom[i] >= monom[i+1] for i in indices):
                height = max([ n*m for n, m in zip(weights, monom) ])

                if height > _height:
                    _height, _monom, _coeff = height, monom, coeff

        if _height != -1:
            monom, coeff = _monom, _coeff
        else:
            break

        exponents = []

        for m1, m2 in zip(monom, monom[1:] + (0,)):
            exponents.append(m1 - m2)

        term = [ s**n for (s, _), n in zip(polys, exponents) ]
        poly = [ p**n for (_, p), n in zip(polys, exponents) ]

        symmetric.append(Mul(coeff, *term))

        product = poly[0].mul(coeff)

        for p in poly[1:]:
            product = product.mul(p)

        f -= product

    polys = [ (s, p.as_basic()) for s, p in polys ]

    if opt.formal:
        return (Add(*symmetric), f.as_basic(), dict(polys))
    else:
        return (Add(*symmetric).subs(polys), f.as_basic())

def horner(f, *gens, **args):
    """
    Rewrite a polynomial in Horner form.

    Among other applications, evaluation of a polynomial at a point is optimal
    when it is applied using the Horner scheme ([1]).

    **Example**

    >>> from sympy import horner
    >>> from sympy.abc import x
    >>> horner(2*x**4 + 2*x**3 + x + 1)
    1 + x*(1 + x**2*(2 + 2*x))

    **References**
    [1] - http://en.wikipedia.org/wiki/Horner_scheme

    """
    allowed_flags(args, [])

    try:
        F, opt = poly_from_expr(f, *gens, **args)
    except PolificationFailed, exc:
        return exc.expr

    form, gen = S.Zero, F.gen

    if F.is_univariate:
        for coeff in F.all_coeffs():
            form = form*gen + coeff
    else:
        F, gens = Poly(F, gen), gens[1:]

        for coeff in F.all_coeffs():
            form = form*gen + horner(coeff, *gens, **args)

    return form

def interpolate(data, x):
    """Construct an interpolating polynomial for the data points.

    **Example**

    >>> from sympy import interpolate
    >>> from sympy.abc import x

    >>> interpolate([1,4,9,16], x)
    x**2
    >>> interpolate([(1, 1), (2, 4), (3, 9)], x)
    x**2
    >>> interpolate([(1, 2), (2, 5), (3, 10)], x)
    1 + x**2
    >>> interpolate({1: 2, 2: 5, 3: 10}, x)
    1 + x**2

    """
    n = len(data)

    if isinstance(data, dict):
        X, Y = zip(*data.items())
    else:
        if isinstance(data[0], tuple):
            X, Y = zip(*data)
        else:
            X = range(1, n+1)
            Y = list(data)

    poly = interpolating_poly(n, x, X, Y)

    return poly.expand()

