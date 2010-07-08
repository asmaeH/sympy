"""Most of these tests come from the examples in Bronstein's book."""
from sympy import Poly
from sympy.integrals.rde import (weak_normalizer, )
from sympy.abc import x, t, z

def test_weak_normalizer():
    a = Poly((1 + x)*t**5 + 4*t**4 + (-1 - 3*x)*t**3 - 4*t**2 + (-2 + 2*x)*t, t, domain='ZZ[x]')
    d = Poly(t**4 - 3*t**2 + 2, t, domain='ZZ')
    D = Poly(t, t)
    assert weak_normalizer(a, d, D, x, t) == \
        (Poly(t**5 - t**4 - 4*t**3 + 4*t**2 + 4*t - 4, t, domain='ZZ[x]'),
        (Poly((1 + x)*t**2 + x*t, t, domain='ZZ[x]'), Poly(t + 1, t, domain='ZZ[x]')))
    assert weak_normalizer(Poly(1 + t**2), Poly(t**2 - 1, t), D, x, t, z) == \
        (Poly(t**4 - 2*t**2 + 1, t, domain='ZZ'),
        (Poly(-3*t**2 + 1, t, domain='ZZ'), Poly(t**2 - 1, t, domain='ZZ')))
    D = Poly(1 + t**2)
    assert weak_normalizer(Poly(1 + t**2), Poly(t, t), Poly(1 + t**2, t), x, t, z) == \
        (Poly(t, t, domain='ZZ'), (Poly(0, t, domain='ZZ'), Poly(t**2, t, domain='ZZ')))
