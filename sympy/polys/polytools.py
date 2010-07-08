"""User-friendly public interface to polynomial functions. """

from sympy import (
    S, Basic, I, Integer, Add, Mul, sympify, ask,
)

from sympy.core.decorators import (
    _sympifyit,
)

from sympy.polys.polyclasses import (
    GFP, DMP, SDP, ANP, DMF,
)

from sympy.polys.polyutils import (
    dict_from_basic,
    basic_from_dict,
    _sort_gens,
    _unify_gens,
    _analyze_gens,
    _dict_reorder,
    _dict_from_basic_no_gens,
)

from sympy.polys.rootisolation import (
    dup_isolate_real_roots_list,
)

from sympy.polys.groebnertools import (
    sdp_from_dict, sdp_div, sdp_groebner,
)

from sympy.polys.monomialtools import (
    Monomial, monomial_key,
)

from sympy.polys.polyerrors import (
    OperationNotSupported, DomainError,
    CoercionFailed, UnificationFailed,
    GeneratorsNeeded, PolynomialError,
    ExactQuotientFailed
)

from sympy.polys.polycontext import (
    register_context,
)

from sympy.mpmath import (
    polyroots as npolyroots,
)

from sympy.utilities import (
    any, all, group, numbered_symbols,
)

from sympy.ntheory import isprime

import sympy.polys

import re

_re_dom_poly = re.compile("^(Z|ZZ|Q|QQ)\[(.+)\]$")
_re_dom_frac = re.compile("^(Z|ZZ|Q|QQ)\((.+)\)$")

_re_dom_algebraic = re.compile("^(Q|QQ)\<(.+)\>$")

from sympy.polys.algebratools import Algebra, ZZ, QQ, RR, EX

from sympy.polys.polyoptions import Options

def _construct_domain(rep, extension=None, field=False, composite=True, **args):
    """Constructs the minimal domain that the coefficients of `rep` fit in. """

    args.update({'extension':extension, 'field':field, 'composite':composite})

    def _construct_simple(rep):
        """Handle ZZ, QQ, RR and algebraic number domains. """
        result, rational, inexact, algebraic = {}, False, False, False

        if extension is True:
            is_algebraic = lambda coeff: ask(coeff, 'algebraic')
        else:
            is_algebraic = lambda coeff: False

        for coeff in rep.itervalues():
            if coeff.is_Rational:
                if not coeff.is_Integer:
                    rational = True
            elif coeff.is_Real:
                if not algebraic:
                    inexact = True
                else:
                    return False
            elif is_algebraic(coeff):
                if not inexact:
                    algebraic = True
                else:
                    return False
            else:
                return None

        if algebraic:
            from numberfields import primitive_element

            monoms, coeffs, exts = [], [], set([])

            for monom, coeff in rep.iteritems():
                if coeff.is_Rational:
                    coeff = (None, 0, QQ.from_sympy(coeff))
                else:
                    a, _ = coeff.as_coeff_factors()
                    coeff -= a

                    b, _ = coeff.as_coeff_terms()
                    coeff /= b

                    exts.add(coeff)

                    a = QQ.from_sympy(a)
                    b = QQ.from_sympy(b)

                    coeff = (coeff, b, a)

                monoms.append(monom)
                coeffs.append(coeff)

            exts = list(exts)

            g, span, H = primitive_element(exts, ex=True, polys=True)
            root = sum([ s*ext for s, ext in zip(span, exts) ])

            K, g = QQ.algebraic_field((g, root)), g.rep.rep

            for monom, (coeff, a, b) in zip(monoms, coeffs):
                if coeff is not None:
                    coeff = a*ANP.from_list(H[exts.index(coeff)], g, QQ) + b
                else:
                    coeff = ANP.from_list([b], g, QQ)

                result[monom] = coeff
        else:
            if inexact:
                K = RR
            else:
                if field or rational:
                    K = QQ
                else:
                    K = ZZ

            for monom, coeff in rep.iteritems():
                result[monom] = K.from_sympy(coeff)

        return K, result

    def _construct_composite(rep):
        """Handle domains like ZZ[X], QQ[X], ZZ(X) or QQ(X). """
        numers, denoms = [], []

        for coeff in rep.itervalues():
            num, den = coeff.as_numer_denom()

            try:
                numers.append(_dict_from_basic_no_gens(num))
            except GeneratorsNeeded:
                numers.append((num, None))

            try:
                denoms.append(_dict_from_basic_no_gens(den))
            except GeneratorsNeeded:
                denoms.append((den, None))

        gens = set([])

        for _, num_gens in numers:
            if num_gens is not None:
                gens.update(num_gens)

        fractions = False

        for _, den_gens in denoms:
            if den_gens is not None:
                gens.update(den_gens)
                fractions = True

        if any(gen.is_number for gen in gens):
            return None

        gens = _sort_gens(gens, **args)
        k, coeffs = len(gens), []

        if not field and not fractions:
            if all(den is S.One for den, _ in denoms):
                K = ZZ.poly_ring(*gens)

                for num, num_gens in numers:
                    if num_gens is not None:
                        num_monoms, num_coeffs = _dict_reorder(num, num_gens, gens)
                    else:
                        num_monoms, num_coeffs = [(0,)*k], [num]

                    num_coeffs = [ K.dom.from_sympy(c) for c in num_coeffs ]
                    coeffs.append(K(dict(zip(num_monoms, num_coeffs))))
            else:
                K = QQ.poly_ring(*gens)

                for (num, num_gens), (den, _) in zip(numers, denoms):
                    if num_gens is not None:
                        num_monoms, num_coeffs = _dict_reorder(num, num_gens, gens)
                        num_coeffs = [ coeff/den for coeff in num_coeffs ]
                    else:
                        num_monoms, num_coeffs = [(0,)*k], [num/den]

                    num_coeffs = [ K.dom.from_sympy(c) for c in num_coeffs ]
                    coeffs.append(K(dict(zip(num_monoms, num_coeffs))))
        else:
            K = ZZ.frac_field(*gens)

            for (num, num_gens), (den, den_gens) in zip(numers, denoms):
                if num_gens is not None:
                    num_monoms, num_coeffs = _dict_reorder(num, num_gens, gens)
                else:
                    num_monoms, num_coeffs = [(0,)*k], [num]

                if den_gens is not None:
                    den_monoms, den_coeffs = _dict_reorder(den, den_gens, gens)
                else:
                    den_monoms, den_coeffs = [(0,)*k], [den]

                num_coeffs = [ K.dom.from_sympy(c) for c in num_coeffs ]
                den_coeffs = [ K.dom.from_sympy(c) for c in den_coeffs ]

                num = dict(zip(num_monoms, num_coeffs))
                den = dict(zip(den_monoms, den_coeffs))

                coeffs.append(K((num, den)))

        return K, dict(zip(rep.keys(), coeffs))

    def _construct_expression(rep):
        """The last resort case, i.e. use EX domain. """
        result, K = {}, EX

        for monom, coeff in rep.iteritems():
            result[monom] = K.from_sympy(coeff)

        return EX, result

    rep = dict(rep)

    for monom, coeff in rep.items():
        rep[monom] = sympify(coeff)

    result = _construct_simple(rep)

    if result is not None:
        if result is not False:
            return result
        else:
            return _construct_expression(rep)
    else:
        if composite:
            result = _construct_composite(rep)
        else:
            result = None

        if result is not None:
            return result
        else:
            return _construct_expression(rep)

def _init_poly_from_dict(dict_rep, *gens, **args):
    """Initialize a Poly given a dict instance. """
    domain = args.get('domain')
    modulus = args.get('modulus')
    symmetric = args.get('symmetric')

    if modulus is not None:
        if len(gens) != 1:
            raise PolynomialError("multivariate polynomials over GF(p) are not supported")
        else:
            return GFP(dict_rep, modulus, domain, symmetric)
    else:
        if domain is not None:
            for k, v in dict_rep.iteritems():
                dict_rep[k] = domain.convert(v)
        else:
            domain, dict_rep = _construct_domain(dict_rep, **args)

        return DMP(dict_rep, domain, len(gens)-1)

def _init_poly_from_list(list_rep, *gens, **args):
    """Initialize a Poly given a list instance. """
    domain = args.get('domain')
    modulus = args.get('modulus')
    symmetric = args.get('symmetric')

    if len(gens) != 1:
        raise PolynomialError("can't create a multivariate polynomial from a list")

    if modulus is not None:
        return GFP(list_rep, modulus, domain, symmetric)
    else:
        if domain is not None:
            rep = map(domain.convert, list_rep)
        else:
            dict_rep = dict(enumerate(reversed(list_rep)))
            domain, rep = _construct_domain(dict_rep, **args)

        return DMP(rep, domain, len(gens)-1)

def _init_poly_from_poly(poly_rep, *gens, **args):
    """Initialize a Poly given a Poly instance. """
    field = args.get('field')
    domain = args.get('domain')
    modulus = args.get('modulus')
    symmetric = args.get('symmetric')

    if isinstance(poly_rep.rep, DMP):
        if not gens or poly_rep.gens == gens:
            if field is not None or domain is not None or modulus is not None:
                rep = poly_rep.rep
            else:
                return poly_rep
        else:
            if set(gens) != set(poly_rep.gens):
                return Poly(poly_rep.as_basic(), *gens, **args)
            else:
                dict_rep = dict(zip(*_dict_reorder(
                    poly_rep.rep.to_dict(), poly_rep.gens, gens)))

                rep = DMP(dict_rep, poly_rep.rep.dom, len(gens)-1)

        if domain is not None:
            rep = rep.convert(domain)
        elif field is not None and field:
            rep = rep.convert(rep.dom.get_field())

        if modulus is not None:
            if not rep.lev and rep.dom.is_ZZ:
                rep = GFP(rep.rep, modulus, rep.dom, symmetric)
            else:
                raise PolynomialError("can't make GF(p) polynomial out of %s" % rep)
    else:
        if not gens or poly_rep.gens == gens:
            if domain is not None or modulus is not None:
                if modulus is not None:
                    rep = GFP(poly_rep.rep.rep, modulus, poly_rep.rep.dom, symmetric)
                else:
                    rep = poly_rep.rep

                if domain is not None:
                    rep = rep.convert(domain)
            else:
                return poly_rep
        else:
            raise PolynomialError("multivariate polynomials over GF(p) are not supported")

    return (rep, gens or poly_rep.gens)

def _init_poly_from_basic(basic_rep, *gens, **args):
    """Initialize a Poly given a Basic expression. """
    if not gens:
        try:
            dict_rep, gens = dict_from_basic(basic_rep, **args)
        except GeneratorsNeeded:
            return basic_rep
    else:
        dict_rep = dict_from_basic(basic_rep, gens, **args)

    def _dict_set_domain(rep, domain):
        result = {}

        for k, v in rep.iteritems():
            result[k] = domain.from_sympy(v)

        return result

    domain = args.get('domain')
    modulus = args.get('modulus')
    symmetric = args.get('symmetric')

    if modulus is not None:
        if len(gens) > 1:
            raise PolynomialError("multivariate polynomials over GF(p) are not supported")
        else:
            result = GFP(_dict_set_domain(dict_rep, domain), modulus, domain, symmetric)
    else:
        if domain is not None:
            dict_rep = _dict_set_domain(dict_rep, domain)
        else:
            domain, dict_rep = _construct_domain(dict_rep, **args)

        result = DMP(dict_rep, domain, len(gens)-1)

    return result, gens

class Poly(Basic):
    """Generic class for representing polynomials in SymPy. """

    __slots__ = ['rep', 'gens']

    is_Poly = True

    def __new__(cls, rep, *gens, **args):
        """Create a new polynomial instance out of something useful. """
        if gens or len(args) != 1 or 'options' not in args:
            options = Options(gens, args)
        else:
            options = args['options']

        if isinstance(rep, (DMP, GFP)):
            if rep.lev != len(options.gens)-1 or options.args:
                raise PolynomialError("invalid arguments to construct a polynomial")
        else:
            if isinstance(rep, (dict, list)):
                if not options.gens:
                    raise GeneratorsNeeded("can't initialize from %s without generators" % type(rep).__name__)

                if isinstance(rep, dict):
                    rep = _init_poly_from_dict(rep, *options.gens, **options.args)
                else:
                    rep = _init_poly_from_list(rep, *options.gens, **options.args)
            else:
                rep = sympify(rep)

                if rep.is_Poly:
                    result = _init_poly_from_poly(rep, *options.gens, **options.args)
                else:
                    result = _init_poly_from_basic(rep, *options.gens, **options.args)

                if type(result) is tuple:
                    rep, options['gens'] = result
                else:
                    if result.is_Poly or not options.strict:
                        return result
                    else:
                        raise GeneratorsNeeded("can't initialize from %s without generators" % rep)

        obj = Basic.__new__(cls)

        obj.rep = rep
        obj.gens = options.gens

        return obj

    def __getnewargs__(self):
        """Data used by pickling protocol version 2. """
        return (self.rep, self.gens)

    def _hashable_content(self):
        """Allow SymPy to hash Poly instances. """
        return (self.rep, self.gens)

    @property
    def args(self):
        """
        Don't mess up with the core.

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x).args
        [1 + x**2]
        """
        return [self.as_basic()]

    @property
    def gen(self):
        """
        Return principal generator.

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x).gen
        x
        """
        return self.gens[0]

    def unify(f, g):
        """
        Make `f` and `g` belong to the same domain.

        **Example**::

            >>> from sympy import Poly
            >>> from sympy.abc import x, y
            >>> Poly(x**2 + 1).unify(Poly(y**2 + 1)) # doctest: +SKIP
            (ZZ, <function per at 0x1010397d0>, DMP([[1], [], [1]], ZZ),
             DMP([[1, 0, 1]], ZZ))
        """
        g = sympify(g)

        if not g.is_Poly:
            try:
                return f.rep.dom, f.per, f.rep, f.rep.per(f.rep.dom.from_sympy(g))
            except CoercionFailed:
                raise UnificationFailed("can't unify %s with %s" % (f, g))

        if isinstance(f.rep, DMP) and isinstance(g.rep, DMP):
            gens = _unify_gens(f.gens, g.gens)

            dom, lev = f.rep.dom.unify(g.rep.dom, gens), len(gens)-1

            if f.gens != gens:
                f_monoms, f_coeffs = _dict_reorder(f.rep.to_dict(), f.gens, gens)

                if f.rep.dom != dom:
                    f_coeffs = [ dom.convert(c, f.rep.dom) for c in f_coeffs ]

                F = DMP(dict(zip(f_monoms, f_coeffs)), dom, lev)
            else:
                F = f.rep.convert(dom)

            if g.gens != gens:
                g_monoms, g_coeffs = _dict_reorder(g.rep.to_dict(), g.gens, gens)

                if g.rep.dom != dom:
                    g_coeffs = [ dom.convert(c, g.rep.dom) for c in g_coeffs ]

                G = DMP(dict(zip(g_monoms, g_coeffs)), dom, lev)
            else:
                G = g.rep.convert(dom)
        elif isinstance(f.rep, GFP) and isinstance(g.rep, DMP) and f.gens == g.gens:
            dom, G, F, gens = f.rep.dom, GFP(g.rep.convert(f.rep.dom).rep, f.rep.mod, f.rep.dom, f.rep.sym), f.rep, f.gens
        elif isinstance(f.rep, DMP) and isinstance(g.rep, GFP) and f.gens == g.gens:
            dom, F, G, gens = g.rep.dom, GFP(f.rep.convert(g.rep.dom).rep, g.rep.mod, g.rep.dom, g.rep.sym), g.rep, g.gens
        elif isinstance(f.rep, GFP) and isinstance(g.rep, GFP) and f.gens == g.gens and f.rep.mod == g.rep.mod:
            dom, gens, sym = f.rep.dom.unify(g.rep.dom), f.gens, max(f.rep.sym, g.rep.sym)
            F = GFP(f.rep.convert(dom).rep, f.rep.mod, dom, sym)
            G = GFP(g.rep.convert(dom).rep, g.rep.mod, dom, sym)
        else:
            raise UnificationFailed("can't unify %s with %s" % (f, g))

        def per(rep, dom=dom, gens=gens, remove=None):
            if remove is not None:
                gens = gens[:remove]+gens[remove+1:]

                if not gens:
                    return dom.to_sympy(rep)

            return Poly(rep, *gens)

        return dom, per, F, G

    def per(f, rep, gens=None, remove=None):
        """
        Create a Poly out of the given representation.

        **Example**

        >>> from sympy import Poly, ZZ
        >>> from sympy.abc import x, y
        >>> from sympy.polys.polyclasses import DMP
        >>> a = Poly(x**2 + 1)
        >>> a.per(DMP([ZZ(1), ZZ(1)], ZZ), gens=[y])
        Poly(y + 1, y, domain='ZZ')
        """
        if gens is None:
            gens = f.gens

        if remove is not None:
            gens = gens[:remove]+gens[remove+1:]

            if not gens:
                return f.rep.dom.to_sympy(rep)

        return Poly(rep, *gens)

    def unit(f):
        """Return unit of `f`'s polynomial algebra. """
        # XXX: This doesn't seem to work.
        return f.per(f.rep.unit())

    @classmethod
    def _analyze_gens(cls, gens, args):
        """Support for passing generators as `*gens` and `[gens]`. """
        if len(gens) == 1 and hasattr(gens[0], '__iter__'):
            gens = tuple(gens[0])

        if not gens:
            gens = args.pop('gens', ())

            if not hasattr(gens, '__iter__'):
                gens = (gens,)

        if len(set(gens)) != len(gens):
            raise PolynomialError("duplicated generators: %s" % str(gens))

        return gens

    @classmethod
    def _analyze_order(cls, args):
        """Convert `order` to an internal representation. """
        order = args.get('order')

        if order is not None:
            order = monomial_key(order)

        return order

    @classmethod
    def _analyze_domain(cls, args):
        """Convert `domain` to an internal representation. """
        domain = args.get('domain')

        if domain is not None:
            domain = cls._parse_domain(domain)

        return domain

    @classmethod
    def _parse_domain(cls, dom):
        """Make an algebra out of a string representation. """
        if isinstance(dom, Algebra):
            return dom

        if isinstance(dom, basestring):
            if dom in ['Z', 'ZZ']:
                return ZZ

            if dom in ['Q', 'QQ']:
                return QQ

            if dom in ['R', 'RR']:
                return RR

            if dom == 'EX':
                return EX

            r = re.match(_re_dom_poly, dom)

            if r is not None:
                ground, gens = r.groups()

                gens = map(sympify, gens.split(','))

                if ground in ['Z', 'ZZ']:
                    return ZZ.poly_ring(*gens)
                else:
                    return QQ.poly_ring(*gens)

            r = re.match(_re_dom_frac, dom)

            if r is not None:
                ground, gens = r.groups()

                gens = map(sympify, gens.split(','))

                if ground in ['Z', 'ZZ']:
                    return ZZ.frac_field(*gens)
                else:
                    return QQ.frac_field(*gens)

            r = re.match(_re_dom_algebraic, dom)

            if r is not None:
                gens = map(sympify, r.groups()[1].split(','))
                return QQ.algebraic_field(*gens)

        raise ValueError('expected a valid domain specification, got %s' % dom)

    def set_domain(f, domain):
        """
        Set the ground domain of `f`.

        **Example**

        >>> from sympy import Poly, QQ
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1).set_domain(QQ)
        Poly(x**2 + 1, x, domain='QQ')
        """
        return f.per(f.rep.convert(f._parse_domain(domain)))

    def get_domain(f):
        """
        Get the ground domain of `f`.

        **Example**

        >>> from sympy import Poly, ZZ
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, domain=ZZ).get_domain()
        ZZ
        """
        return f.rep.dom

    @classmethod
    def _analyze_modulus(cls, args):
        """Convert `modulus` to an internal representation. """
        modulus = args.get('modulus')

        if modulus is not None:
            modulus = cls._parse_modulus(modulus)

        return modulus

    @classmethod
    def _parse_modulus(cls, modulus):
        """Check if we were given a valid modulus. """
        if isinstance(modulus, (int, Integer)) and isprime(modulus):
            return int(modulus)
        else:
            raise ValueError("modulus must be a prime integer, got %s" % modulus)

    def set_modulus(f, modulus):
        """
        Set the modulus of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(5*x**2 + 2*x - 1, x).set_modulus(2)
        Poly(x**2 + 1, x, modulus=2)
        """
        modulus = f._parse_modulus(modulus)

        if isinstance(f.rep, GFP):
            return f.per(f.rep.trunc(modulus))
        elif f.rep.dom.is_ZZ and f.is_univariate:
            return f.per(GFP(f.rep.rep, modulus, f.rep.dom))
        else:
            raise PolynomialError("not a polynomial over a Galois field")

    def get_modulus(f):
        """
        Get the modulus of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, modulus=2).get_modulus()
        2
        """
        if isinstance(f.rep, GFP):
            return Integer(f.rep.mod)
        else:
            raise PolynomialError("not a polynomial over a Galois field")

    @classmethod
    def _analyze_extension(cls, args):
        """Convert `extension` to an internal representation. """
        extension = args.get('extension')
        gaussian = args.get('gaussian')
        split = args.get('split')

        if extension is not None:
            if gaussian is not None:
                raise PolynomialError("'extension' is not allowed together with 'gaussian'")

            if split is not None:
                raise PolynomialError("'extension' is not allowed together with 'split'")

            if isinstance(extension, bool):
                if extension is False:
                    extension = None
            else:
                if not hasattr(extension, '__iter__'):
                    extension = set([extension])
                else:
                    if not extension:
                        extension = None
                    else:
                        extension = set(extension)
        elif gaussian is not None:
            if split is not None:
                raise PolynomialError("'gaussian' is not allowed together with 'split'")
            elif gaussian:
                extension = set([S.ImaginaryUnit])
        elif split is not None:
            raise NotImplementedError('splitting extensions are not supported')

        return extension

    def exclude(f):
        """
        Remove unnecessary generators from `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import a, b, c, d, x
        >>> Poly(a + x, a, b, c, d, x).exclude()
        Poly(a + x, a, x, domain='ZZ')
        """
        J, new = f.rep.exclude()
        newgens = []
        for i in range(len(f.gens)):
            if i not in J:
                newgens.append(f.gens[i])

        return f.per(new, gens=newgens)

    def replace(f, x, y=None):
        """
        Replace `x` with `y` in generators list.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**2 + 1, x).replace(x, y)
        Poly(y**2 + 1, y, domain='ZZ')
        """
        if y is None:
            if f.is_univariate:
                x, y = f.gen, x
            else:
                raise PolynomialError("syntax supported only in univariate case")

        if x == y:
            return f

        if x in f.gens and y not in f.gens:
            dom = f.get_domain()

            if not dom.is_Composite or y not in dom.gens:
                gens = list(f.gens)
                gens[gens.index(x)] = y
                return f.per(f.rep, gens=gens)

        raise PolynomialError("can't replace %s with %s in %s" % (x, y, f))

    def reorder(f, *gens, **args):
        """
        Efficiently apply new order of generators.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**2 + x*y**2, x, y).reorder(y, x)
        Poly(y**2*x + x**2, y, x, domain='ZZ')
        """
        if not gens:
            gens = _sort_gens(f.gens, **args)
        elif set(f.gens) != set(gens):
            raise PolynomialError("generators list can differ only up to order of elements")

        rep = dict(zip(*_dict_reorder(f.rep.to_dict(), f.gens, gens)))

        return f.per(DMP(rep, f.rep.dom, len(gens)-1), gens=gens)

    def to_ring(f):
        """
        Make the ground domain a ring.

        **Example**

        >>> from sympy import Poly, QQ
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, domain=QQ).to_ring()
        Poly(x**2 + 1, x, domain='ZZ')
        """
        try:
            result = f.rep.to_ring()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'to_ring')

        return f.per(result)

    def to_field(f):
        """
        Make the ground domain a field.

        **Example**

        >>> from sympy import Poly, ZZ
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x, domain=ZZ).to_field()
        Poly(x**2 + 1, x, domain='QQ')
        """
        try:
            result = f.rep.to_field()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'to_field')

        return f.per(result)

    def to_exact(f):
        """
        Make the ground domain exact.

        **Example**

        >>> from sympy import Poly, RR
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1.0, x, RR).to_exact()
        Poly(x**2 + 1, x, RR, domain='QQ')
        """
        try:
            result = f.rep.to_exact()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'to_exact')

        return f.per(result)

    def coeffs(f, order=None):
        """
        Returns all non-zero coefficients from `f` in lex order.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**3 + 2*x + 3, x).coeffs()
        [1, 2, 3]
        """
        return [ f.rep.dom.to_sympy(c) for c in f.rep.coeffs(order=order) ]

    def monoms(f, order=None):
        """
        Returns all non-zero monomials from `f` in lex order.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**2 + 2*x*y**2 + x*y + 3*y, x, y).monoms()
        [(2, 0), (1, 2), (1, 1), (0, 1)]
        """
        return f.rep.monoms(order=order)

    def terms(f, order=None):
        """
        Returns all non-zero terms from `f` in lex order.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**2 + 2*x*y**2 + x*y + 3*y, x, y).terms()
        [((2, 0), 1), ((1, 2), 2), ((1, 1), 1), ((0, 1), 3)]
        """
        return [ (m, f.rep.dom.to_sympy(c)) for m, c in f.rep.terms(order=order) ]

    def all_coeffs(f):
        """
        Returns all coefficients from a univariate polynomial `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**3 + 2*x - 1, x).all_coeffs()
        [1, 0, 2, -1]
        """
        return [ f.rep.dom.to_sympy(c) for c in f.rep.all_coeffs() ]

    def all_monoms(f):
        """
        Returns all monomials from a univariate polynomial `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**3 + 2*x - 1, x).all_monoms()
        [(3,), (2,), (1,), (0,)]
        """
        return f.rep.all_monoms()

    def all_terms(f):
        """
        Returns all terms from a univariate polynomial `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**3 + 2*x - 1, x).all_terms()
        [((3,), 1), ((2,), 0), ((1,), 2), ((0,), -1)]
        """
        return [ (m, f.rep.dom.to_sympy(c)) for m, c in f.rep.all_terms() ]

    def length(f):
        """
        Returns the number of non-zero terms in `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 2*x - 1).length()
        3
        """
        return len(f.as_dict())

    def as_dict(f):
        """
        Switch to a dict representation with SymPy coefficients.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**2 + 2*x*y**2 - y, x, y).as_dict()
        {(0, 1): -1, (1, 2): 2, (2, 0): 1}
        """
        return f.rep.to_sympy_dict()

    def as_basic(f, *gens):
        """
        Convert a polynomial instance to a SymPy expression.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**2 + 2*x*y**2 - y, x, y).as_basic()
        -y + x**2 + 2*x*y**2
        """
        return basic_from_dict(f.rep.to_sympy_dict(), *(gens or f.gens))

    def lift(f):
        """
        Convert algebraic coefficients to rationals.

        **Example**

        >>> from sympy import Poly, I
        >>> from sympy.abc import x
        >>> Poly(x**2 + I*x + 1, x, extension=[I]).lift()
        Poly(x**4 + 3*x**2 + 1, x, domain='QQ')
        """
        try:
            result = f.rep.lift()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'lift')

        return f.per(result)

    def deflate(f):
        """
        Reduce degree of `f` by mapping `x_i**m` to `y_i`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**6*y**2 + x**3 + 1, x, y).deflate()
        ((3, 2), Poly(x**2*y + x + 1, x, y, domain='ZZ'))
        """
        try:
            J, result = f.rep.deflate()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'deflate')

        return J, f.per(result)

    def terms_gcd(f):
        """
        Remove GCD of terms from the polynomial `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**6*y**2 + x**3*y, x, y).terms_gcd()
        ((3, 1), Poly(x**3*y + 1, x, y, domain='ZZ'))
        """
        try:
            J, result = f.rep.terms_gcd()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'terms_gcd')

        return J, f.per(result)

    def abs(f):
        """
        Make all coefficients in `f` positive.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 - 1, x).abs()
        Poly(x**2 + 1, x, domain='ZZ')
        """
        try:
            result = f.rep.abs()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'abs')

        return f.per(result)

    def neg(f):
        """
        Negate all cefficients in `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 - 1, x).neg()
        Poly(-x**2 + 1, x, domain='ZZ')
        >>> -Poly(x**2 - 1, x)
        Poly(-x**2 + 1, x, domain='ZZ')
        """
        try:
            result = f.rep.neg()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'neg')

        return f.per(result)

    def add(f, g):
        """
        Add two polynomials `f` and `g`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x).add(Poly(x - 2, x))
        Poly(x**2 + x - 1, x, domain='ZZ')
        >>> Poly(x**2 + 1, x) + Poly(x - 2, x)
        Poly(x**2 + x - 1, x, domain='ZZ')
        """
        _, per, F, G = f.unify(g)

        try:
            result = F.add(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'add')

        return per(result)

    def sub(f, g):
        """
        Subtract two polynomials `f` and `g`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x).sub(Poly(x - 2, x))
        Poly(x**2 - x + 3, x, domain='ZZ')
        >>> Poly(x**2 + 1, x) - Poly(x - 2, x)
        Poly(x**2 - x + 3, x, domain='ZZ')
        """
        _, per, F, G = f.unify(g)

        try:
            result = F.sub(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'sub')

        return per(result)

    def mul(f, g):
        """
        Multiply two polynomials `f` and `g`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x).mul(Poly(x - 2, x))
        Poly(x**3 - 2*x**2 + x - 2, x, domain='ZZ')
        >>> Poly(x**2 + 1, x)*Poly(x - 2, x)
        Poly(x**3 - 2*x**2 + x - 2, x, domain='ZZ')
        """
        _, per, F, G = f.unify(g)

        try:
            result = F.mul(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'mul')

        return per(result)

    def sqr(f):
        """
        Square a polynomial `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x - 2, x).sqr()
        Poly(x**2 - 4*x + 4, x, domain='ZZ')
        >>> Poly(x - 2, x)**2
        Poly(x**2 - 4*x + 4, x, domain='ZZ')
        """
        try:
            result = f.rep.sqr()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'sqr')

        return f.per(result)

    def pow(f, n):
        """
        Raise `f` to a non-negative power `n`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x - 2, x).pow(3)
        Poly(x**3 - 6*x**2 + 12*x - 8, x, domain='ZZ')
        >>> Poly(x - 2, x)**3
        Poly(x**3 - 6*x**2 + 12*x - 8, x, domain='ZZ')
        """
        n = int(n)

        try:
            result = f.rep.pow(n)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'pow')

        return f.per(result)

    def pdiv(f, g):
        """
        Polynomial pseudo-division of `f` by `g`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x).pdiv(Poly(2*x - 4, x))
        (Poly(2*x + 4, x, domain='ZZ'), Poly(20, x, domain='ZZ'))
        """
        _, per, F, G = f.unify(g)

        try:
            q, r = F.pdiv(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'pdiv')

        return per(q), per(r)

    def prem(f, g):
        """
        Polynomial pseudo-remainder of `f` by `g`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x).prem(Poly(2*x - 4, x))
        Poly(20, x, domain='ZZ')
        """
        _, per, F, G = f.unify(g)

        try:
            result = F.prem(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'prem')

        return per(result)

    def pquo(f, g):
        """
        Polynomial pseudo-quotient of `f` by `g`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x).pquo(Poly(2*x - 4, x)) #doctest: +SKIP
        Traceback (most recent call last):
        ...
        ExactQuotientFailed: [2, -4] does not divide [1, 0, 1]
        >>> Poly(x**2 - 1, x).pquo(Poly(2*x - 2, x))
        Poly(2*x + 2, x, domain='ZZ')
        """
        _, per, F, G = f.unify(g)

        try:
            result = F.pquo(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'pquo')

        return per(result)

    def pexquo(f, g):
        """
        Polynomial exact pseudo-quotient of `f` by `g`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x).pexquo(Poly(2*x - 4, x)) #doctest: +SKIP
        Poly(2*x + 4, x, domain='ZZ')
        >>> Poly(x**2 - 1, x).pexquo(Poly(2*x - 2, x))
        Poly(2*x + 2, x, domain='ZZ')
        """
        _, per, F, G = f.unify(g)

        try:
            result = F.pexquo(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'pexquo')

        return per(result)

    def div(f, g):
        """
        Polynomial division with remainder of `f` by `g`.

        **Example**

        >>> from sympy import Poly, QQ, ZZ
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x, domain=ZZ).div(Poly(2*x - 4, x, domain=ZZ))
        (Poly(0, x, domain='ZZ'), Poly(x**2 + 1, x, domain='ZZ'))
        >>> Poly(x**2 + 1, x, domain=QQ).div(Poly(2*x - 4, x, domain=QQ))
        (Poly(1/2*x + 1, x, domain='QQ'), Poly(5, x, domain='QQ'))
        """
        _, per, F, G = f.unify(g)

        try:
            q, r = F.div(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'div')

        return per(q), per(r)

    def rem(f, g):
        """
        Computes the polynomial remainder of `f` by `g`.

        **Example**

        >>> from sympy import Poly, ZZ, QQ
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x, domain=ZZ).rem(Poly(2*x - 4, x, domain=ZZ))
        Poly(x**2 + 1, x, domain='ZZ')
        >>> Poly(x**2 + 1, x, domain=QQ).rem(Poly(2*x - 4, x, domain=QQ))
        Poly(5, x, domain='QQ')
        """
        _, per, F, G = f.unify(g)

        try:
            result = F.rem(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'rem')

        return per(result)

    def quo(f, g):
        """
        Computes polynomial quotient of `f` by `g`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x).quo(Poly(2*x - 4, x)) #doctest: +SKIP
        Traceback (most recent call last):
        ...
        ExactQuotientFailed: [2, -4] does not divide [1, 0, 1]
        >>> Poly(x**2 - 1, x).quo(Poly(x - 1, x))
        Poly(x + 1, x, domain='ZZ')
        """
        _, per, F, G = f.unify(g)

        try:
            result = F.quo(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'quo')

        return per(result)

    def exquo(f, g):
        """
        Computes polynomial exact quotient of `f` by `g`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x).exquo(Poly(2*x - 4, x))
        Poly(0, x, domain='ZZ')
        >>> Poly(x**2 - 1, x).exquo(Poly(x - 1, x))
        Poly(x + 1, x, domain='ZZ')
        """
        _, per, F, G = f.unify(g)

        try:
            result = F.exquo(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'exquo')

        return per(result)

    def _gen_to_level(f, gen):
        """Returns level associated with the given generator. """
        if isinstance(gen, int):
            length = len(f.gens)

            if -length <= gen < length:
                if gen < 0:
                    return length + gen
                else:
                    return gen
            else:
                raise PolynomialError("-%s <= gen < %s expected, got %s" % (length, length, gen))
        else:
            try:
                return list(f.gens).index(sympify(gen))
            except ValueError:
                raise PolynomialError("a valid generator expected, got %s" % gen)

    def degree(f, gen=0):
        """
        Returns degree of `f` in `x_j`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**2 + y*x + 1, x, y).degree()
        2
        >>> Poly(x**2 + y*x + y, x, y).degree(y)
        1
        """
        j = f._gen_to_level(gen)

        try:
            return f.rep.degree(j)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'degree')

    def degree_list(f):
        """
        Returns a list of degrees of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**2 + y*x + 1, x, y).degree_list()
        (2, 1)
        """
        try:
            return f.rep.degree_list()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'degree_list')

    def total_degree(f):
        """
        Returns the total degree of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**2 + y*x + 1, x, y).total_degree()
        3
        """
        try:
            return f.rep.total_degree()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'total_degree')

    def LC(f, order=None):
        """
        Returns the leading coefficent of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(4*x**3 + 2*x**2 + 3*x, x).LC()
        4
        """
        if order is not None:
            return f.coeffs(order)[0]

        try:
            result = f.rep.LC()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'LC')

        return f.rep.dom.to_sympy(result)

    def TC(f):
        """
        Returns the trailing coefficent of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**3 + 2*x**2 + 3*x, x).TC()
        0
        """
        try:
            result = f.rep.TC()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'TC')

        return f.rep.dom.to_sympy(result)

    def EC(f, order=None):
        """
        Returns the last non-zero coefficent of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**3 + 2*x**2 + 3*x, x).EC()
        3
        """
        try:
            return f.coeffs(order)[-1]
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'EC')

    def nth(f, *N):
        """
        Returns the `n`-th coefficient of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**3 + 2*x**2 + 3*x, x).nth(2)
        2
        >>> Poly(x**3 + 2*x*y**2 + y**2, x, y).nth(1, 2)
        2
        """
        try:
            result = f.rep.nth(*map(int, N))
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'nth')

        return f.rep.dom.to_sympy(result)

    def LM(f, order=None):
        """
        Returns the leading monomial of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(4*x**2 + 2*x*y**2 + x*y + 3*y, x, y).LM()
        (2, 0)
        """
        return f.monoms(order)[0]

    def EM(f, order=None):
        """
        Returns the last non-zero monomial of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(4*x**2 + 2*x*y**2 + x*y + 3*y, x, y).EM()
        (0, 1)
        """
        return f.monoms(order)[-1]

    def LT(f, order=None):
        """
        Returns the leading term of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(4*x**2 + 2*x*y**2 + x*y + 3*y, x, y).LT()
        ((2, 0), 4)
        """
        return f.terms(order)[0]

    def ET(f, order=None):
        """
        Returns the last non-zero term of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(4*x**2 + 2*x*y**2 + x*y + 3*y, x, y).ET()
        ((0, 1), 3)
        """
        return f.terms(order)[-1]

    def max_norm(f):
        """
        Returns maximum norm of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(-x**2 + 2*x - 3, x).max_norm()
        3
        """
        try:
            result = f.rep.max_norm()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'max_norm')

        return f.rep.dom.to_sympy(result)

    def l1_norm(f):
        """
        Returns l1 norm of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(-x**2 + 2*x - 3, x).l1_norm()
        6
        """
        try:
            result = f.rep.l1_norm()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'l1_norm')

        return f.rep.dom.to_sympy(result)

    def clear_denoms(f, convert=False):
        """
        Clear denominators, but keep the ground domain.

        **Example**

        >>> from sympy import Poly, S, QQ
        >>> from sympy.abc import x
        >>> Poly(x/2 + S(1)/3, x, domain=QQ).clear_denoms()
        (6, Poly(3*x + 2, x, domain='QQ'))
        >>> Poly(x/2 + S(1)/3, x, domain=QQ).clear_denoms(convert=True)
        (6, Poly(3*x + 2, x, domain='ZZ'))
        """
        try:
            coeff, result = f.rep.clear_denoms()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'clear_denoms')

        dom = f.get_domain()
        if dom.has_assoc_Ring:
            coeff, f = dom.get_ring().to_sympy(coeff), f.per(result)
        else:
            coeff, f = dom.to_sympy(coeff), f.per(result)

        if not convert:
            return coeff, f
        else:
            return coeff, f.to_ring()

    def integrate(f, *specs, **args):
        """
        Computes indefinite integral of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**2 + 2*x + 1, x).integrate()
        Poly(1/3*x**3 + x**2 + x, x, domain='QQ')
        >>> Poly(x*y**2 + x, x, y).integrate((0, 1), (1, 0))
        Poly(1/2*x**2*y**2 + 1/2*x**2, x, y, domain='QQ')
        """
        if args.get('auto', True) and f.rep.dom.has_Ring:
            f = f.to_field()

        try:
            if not specs:
                return f.per(f.rep.integrate(m=1))

            rep = f.rep

            for spec in specs:
                if type(spec) is tuple:
                    gen, m = spec
                else:
                    gen, m = spec, 1

                rep = rep.integrate(int(m), f._gen_to_level(gen))

            return f.per(rep)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'integrate')

    def diff(f, *specs):
        """
        Computes partial derivative of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**2 + 2*x + 1, x).diff()
        Poly(2*x + 2, x, domain='ZZ')
        >>> Poly(x*y**2 + x, x, y).diff((0, 0), (1, 1))
        Poly(2*x*y, x, y, domain='ZZ')
        """
        try:
            if not specs:
                return f.per(f.rep.diff(m=1))

            rep = f.rep

            for spec in specs:
                if type(spec) is tuple:
                    gen, m = spec
                else:
                    gen, m = spec, 1

                rep = rep.diff(int(m), f._gen_to_level(gen))

            return f.per(rep)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'diff')

    def eval(f, a, gen=0):
        """
        Efficiently evaluates `f` at `a` in the given variable.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**2 + 2*x + 3, x).eval(2)
        11
        >>> Poly(2*x*y + 3*x + y + 2, x, y).eval(2, gen=x)
        Poly(5*y + 8, y, domain='ZZ')
        """
        j = f._gen_to_level(gen)

        try:
            result = f.rep.eval(a, j)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'eval')

        return f.per(result, remove=j)

    def half_gcdex(f, g, auto=True):
        """
        Half extended Euclidean algorithm of `f` and `g`.

        Returns `(s, h)` such that `h = gcd(f, g)` and `s*f = h (mod g)`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**4 - 2*x**3 - 6*x**2 + 12*x + 15, x).half_gcdex(
        ... Poly(x**3 + x**2 - 4*x - 4, x))
        (Poly(-1/5*x + 3/5, x, domain='QQ'), Poly(x + 1, x, domain='QQ'))
        """
        dom, per, F, G = f.unify(g)

        if auto and dom.has_Ring:
            F, G = F.to_field(), G.to_field()

        try:
            s, h = F.half_gcdex(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'half_gcdex')

        return per(s), per(h)

    def gcdex(f, g, auto=True):
        """
        Extended Euclidean algorithm of `f` and `g`.

        Returns `(s, t, h)` such that `h = gcd(f, g)` and `s*f + t*g = h`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**4 - 2*x**3 - 6*x**2 + 12*x + 15, x).gcdex(
        ... Poly(x**3 + x**2 - 4*x - 4, x))
        (Poly(-1/5*x + 3/5, x, domain='QQ'),
         Poly(1/5*x**2 - 6/5*x + 2, x, domain='QQ'), Poly(x + 1, x, domain='QQ'))
        """
        dom, per, F, G = f.unify(g)

        if auto and dom.has_Ring:
            F, G = F.to_field(), G.to_field()

        try:
            s, t, h = F.gcdex(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'gcdex')

        return per(s), per(t), per(h)

    def invert(f, g, auto=True):
        """
        Invert `f` modulo `g`, if possible.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 - 1, x).invert(Poly(2*x - 1, x))
        Poly(-4/3, x, domain='QQ')
        >>> Poly(x**2 - 1, x).invert(Poly(x - 1, x))
        Traceback (most recent call last):
        ...
        NotInvertible: zero divisor
        """
        dom, per, F, G = f.unify(g)

        if auto and dom.has_Ring:
            F, G = F.to_field(), G.to_field()

        try:
            result = F.invert(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'invert')

        return per(result)

    def subresultants(f, g):
        """
        Computes the subresultant PRS sequence of `f` and `g`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x).subresultants(Poly(x**2 - 1, x))
        [Poly(x**2 + 1, x, domain='ZZ'), Poly(x**2 - 1, x, domain='ZZ'),
         Poly(-2, x, domain='ZZ')]
        """
        _, per, F, G = f.unify(g)

        try:
            result = F.subresultants(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'subresultants')

        return map(per, result)

    def resultant(f, g, includePRS=False):
        """
        Computes the resultant of `f` and `g` via PRS.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x).resultant(Poly(x**2 - 1, x))
        4
        >>> Poly(x**2 + 1, x).resultant(Poly(x**2 - 1, x), includePRS=True)
        (4, [Poly(x**2 + 1, x, domain='ZZ'), Poly(x**2 - 1, x, domain='ZZ'),
             Poly(-2, x, domain='ZZ')])
        """
        _, per, F, G = f.unify(g)

        try:
            if includePRS:
                result, R = F.resultant(G, includePRS)
            else:
                result = F.resultant(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'resultant')

        if includePRS:
            return (per(result, remove=0), map(per, R))
        return per(result, remove=0)

    def discriminant(f):
        """
        Computes the discriminant of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + 2*x + 3, x).discriminant()
        -8
        """
        try:
            result = f.rep.discriminant()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'discriminant')

        return f.per(result, remove=0)

    def cofactors(f, g):
        """
        Returns the GCD of `f` and `g` and their cofactors.

        Returns `(h, cff, cfg)` such that `a = gcd(f, g)`, `cff = quo(f, h)`,
        and `cfg = quo(g, h)`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 - 1, x).cofactors(Poly(x**2 - 3*x + 2, x))
        (Poly(x - 1, x, domain='ZZ'), Poly(x + 1, x, domain='ZZ'),
         Poly(x - 2, x, domain='ZZ'))
        """
        _, per, F, G = f.unify(g)

        try:
            h, cff, cfg = F.cofactors(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'cofactors')

        return per(h), per(cff), per(cfg)

    def gcd(f, g):
        """
        Returns the polynomial GCD of `f` and `g`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 - 1, x).gcd(Poly(x**2 - 3*x + 2, x))
        Poly(x - 1, x, domain='ZZ')
        """
        _, per, F, G = f.unify(g)

        try:
            result = F.gcd(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'gcd')

        return per(result)

    def lcm(f, g):
        """
        Returns polynomial LCM of `f` and `g`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 - 1, x).lcm(Poly(x**2 - 3*x + 2, x))
        Poly(x**3 - 2*x**2 - x + 2, x, domain='ZZ')
        """
        _, per, F, G = f.unify(g)

        try:
            result = F.lcm(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'lcm')

        return per(result)

    def trunc(f, p):
        """
        Reduce `f` modulo a constant `p`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(2*x**3 + 3*x**2 + 5*x + 7, x).trunc(3)
        Poly(-x**3 - x + 1, x, domain='ZZ')
        """
        p = f.rep.dom.convert(p)

        try:
            result = f.rep.trunc(p)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'trunc')

        return f.per(result)

    def monic(f, auto=True):
        """
        Divides all coefficients by `LC(f)`.

        **Example**

        >>> from sympy import Poly, ZZ
        >>> from sympy.abc import x
        >>> Poly(3*x**2 + 6*x + 9, x, domain=ZZ).monic()
        Poly(x**2 + 2*x + 3, x, domain='QQ')
        >>> Poly(3*x**2 + 4*x + 2, x, domain=ZZ).monic()
        Poly(x**2 + 4/3*x + 2/3, x, domain='QQ')
        """
        if auto and f.rep.dom.has_Ring:
            f = f.to_field()

        try:
            result = f.rep.monic()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'monic')

        return f.per(result)

    def content(f):
        """
        Returns the GCD of polynomial coefficients.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(6*x**2 + 8*x + 12, x).content()
        2
        """
        try:
            result = f.rep.content()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'content')

        return f.rep.dom.to_sympy(result)

    def primitive(f):
        """
        Returns the content and a primitive form of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(2*x**2 + 8*x + 12, x).primitive()
        (2, Poly(x**2 + 4*x + 6, x, domain='ZZ'))
        """
        try:
            cont, result = f.rep.primitive()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'primitive')

        return f.rep.dom.to_sympy(cont), f.per(result)

    def compose(f, g):
        """
        Computes the functional composition of `f` and `g`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + x, x).compose(Poly(x - 1, x))
        Poly(x**2 - x, x, domain='ZZ')
        """
        _, per, F, G = f.unify(g)

        try:
            result = F.compose(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'compose')

        return per(result)

    def decompose(f):
        """
        Computes a functional decomposition of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**4 + 2*x**3 - x - 1, x, domain='ZZ').decompose()
        [Poly(x**2 - x - 1, x, domain='ZZ'), Poly(x**2 + x, x, domain='ZZ')]
        """
        try:
            result = f.rep.decompose()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'decompose')

        return map(f.per, result)

    def sturm(f, auto=True):
        """
        Computes the Sturm sequence of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**3 - 2*x**2 + x - 3, x).sturm()
        [Poly(x**3 - 2*x**2 + x - 3, x, domain='QQ'),
         Poly(3*x**2 - 4*x + 1, x, domain='QQ'),
         Poly(2/9*x + 25/9, x, domain='QQ'), Poly(-2079/4, x, domain='QQ')]
        """
        if auto and f.rep.dom.has_Ring:
            f = f.to_field()

        try:
            result = f.rep.sturm()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'sturm')

        return map(f.per, result)

    def sqf_norm(f):
        """
        Computes square-free norm of `f`.

        Returns `s`, `f`, `r`, such that `g(x) = f(x-sa)` and `r(x) = Norm(g(x))`
        is a square-free polynomtal over K, where `a` is the algebraic extension
        of `K`.

        **Example**

        >>> from sympy import Poly, sqrt
        >>> from sympy.abc import x
        >>> Poly(x**2 + 1, x, extension=[sqrt(3)]).sqf_norm()
        (1, Poly(x**2 - 2*3**(1/2)*x + 4, x, domain='QQ<3**(1/2)>'),
         Poly(x**4 - 4*x**2 + 16, x, domain='QQ'))
        """
        try:
            s, g, r = f.rep.sqf_norm()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'sqf_norm')

        return s, f.per(g), f.per(r)

    def sqf_part(f):
        """
        Computes square-free part of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**3 - 3*x - 2, x).sqf_part()
        Poly(x**2 - x - 2, x, domain='ZZ')
        """
        try:
            result = f.rep.sqf_part()
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'sqf_part')

        return f.per(result)

    def sqf_list(f, all=False):
        """
        Returns a list of square-free factors of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(2*x**5 + 16*x**4 + 50*x**3 + 76*x**2 + 56*x + 16, x).sqf_list()
        (2, [(Poly(x + 1, x, domain='ZZ'), 2),
             (Poly(x + 2, x, domain='ZZ'), 3)])
        >>> Poly(2*x**5 + 16*x**4 + 50*x**3 + 76*x**2 + 56*x + 16,
        ... x).sqf_list(all=True)
        (2, [(Poly(1, x, domain='ZZ'), 1), (Poly(x + 1, x, domain='ZZ'), 2),
             (Poly(x + 2, x, domain='ZZ'), 3)])
        """
        try:
            coeff, factors = f.rep.sqf_list(all)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'sqf_list')

        return f.rep.dom.to_sympy(coeff), [ (f.per(g), k) for g, k in factors ]

    def sqf_list_include(f, all=False):
        """
        Returns a list of square-free factors of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(2*x**5 + 16*x**4 + 50*x**3 + 76*x**2 + 56*x + 16,
        ... x).sqf_list_include()
        [(Poly(2*x + 2, x, domain='ZZ'), 2),
         (Poly(x + 2, x, domain='ZZ'), 3)]
        >>> Poly(2*x**5 + 16*x**4 + 50*x**3 + 76*x**2 + 56*x + 16,
        ... x).sqf_list_include(all=True)
        [(Poly(2, x, domain='ZZ'), 1), (Poly(x + 1, x, domain='ZZ'), 2),
         (Poly(x + 2, x, domain='ZZ'), 3)]
        """
        try:
            factors = f.rep.sqf_list_include(all)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'sqf_list_include')

        return [ (f.per(g), k) for g, k in factors ]

    def factor_list(f):
        """
        Returns a list of irreducible factors of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(4*x**2*y**2 + 4*x**3*y**2 + 2*x**4 + 2*y**4 + 2*x*y**4 +
        ... 2*x**5, x, y).factor_list()
        (2, [(Poly(x + 1, x, y, domain='ZZ'), 1),
             (Poly(x**2 + y**2, x, y, domain='ZZ'), 2)])
        """
        try:
            coeff, factors = f.rep.factor_list()
        except DomainError:
            return S.One, [(f, 1)]
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'factor_list')

        return f.rep.dom.to_sympy(coeff), [ (f.per(g), k) for g, k in factors ]

    def factor_list_include(f):
        """
        Returns a list of irreducible factors of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(4*x**2*y**2 + 4*x**3*y**2 + 2*x**4 + 2*y**4 + 2*x*y**4 +
        ... 2*x**5, x, y).factor_list_include()
        [(Poly(2*x + 2, x, y, domain='ZZ'), 1),
         (Poly(x**2 + y**2, x, y, domain='ZZ'), 2)]
        """
        try:
            factors = f.rep.factor_list_include()
        except DomainError:
            return [(f, 1)]
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'factor_list_include')

        return [ (f.per(g), k) for g, k in factors ]

    def intervals(f, all=False, eps=None, inf=None, sup=None, fast=False, sqf=False):
        """
        Compute isolating intervals for roots of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 - 3, x).intervals()
        [((-2, -1), 1), ((1, 2), 1)]
        >>> Poly(x**2 - 3, x).intervals(eps=1e-2)
        [((-26/15, -19/11), 1), ((19/11, 26/15), 1)]
        """
        if eps is not None:
            eps = QQ.convert(eps)

        if inf is not None:
            inf = QQ.convert(inf)
        if sup is not None:
            sup = QQ.convert(sup)

        try:
            result = f.rep.intervals(all=all, eps=eps, inf=inf, sup=sup, fast=fast, sqf=sqf)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'intervals')

        if sqf:
            def _real((s, t)):
                return (QQ.to_sympy(s), QQ.to_sympy(t))

            if not all:
                return map(_real, result)

            def _complex(((u, v), (s, t))):
                return (QQ.to_sympy(u) + I*QQ.to_sympy(v),
                        QQ.to_sympy(s) + I*QQ.to_sympy(t))

            real_part, complex_part = result

            return map(_real, real_part), map(_complex, complex_part)
        else:
            def _real(((s, t), k)):
                return ((QQ.to_sympy(s), QQ.to_sympy(t)), k)

            if not all:
                return map(_real, result)

            def _complex((((u, v), (s, t)), k)):
                return ((QQ.to_sympy(u) + I*QQ.to_sympy(v),
                         QQ.to_sympy(s) + I*QQ.to_sympy(t)), k)

            real_part, complex_part = result

            return map(_real, real_part), map(_complex, complex_part)

    def refine_root(f, s, t, eps=None, steps=None, fast=False, check_sqf=False):
        """
        Refine an isolating interval of a root to the given precision.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 - 3, x).refine_root(1, 2, eps=1e-2)
        (19/11, 26/15)
        """
        if check_sqf and not f.is_sqf:
            raise PolynomialError("only square-free polynomials supported")

        s, t = QQ.convert(s), QQ.convert(t)

        if eps is not None:
            eps = QQ.convert(eps)

        if steps is not None:
            steps = int(steps)
        elif eps is None:
            steps = 1

        try:
            S, T = f.rep.refine_root(s, t, eps=eps, steps=steps, fast=fast)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'refine_root')

        return QQ.to_sympy(S), QQ.to_sympy(T)

    def count_roots(f, inf=None, sup=None):
        """
        Return the number of roots of ``f`` in ``[inf, sup]`` interval.

        **Example**

        >>> from sympy import Poly, I
        >>> from sympy.abc import x
        >>> Poly(x**4 - 4, x).count_roots(-3, 3)
        2
        >>> Poly(x**4 - 4, x).count_roots(0, 1 + 3*I)
        1
        """
        inf_real, sup_real = True, True

        if inf is not None:
            inf = sympify(inf)

            if inf is S.NegativeInfinity:
                inf = None
            else:
                re, im = inf.as_real_imag()

                if not im:
                    inf = QQ.convert(inf)
                else:
                    inf, inf_real = map(QQ.convert, (re, im)), False

        if sup is not None:
            sup = sympify(sup)

            if sup is S.Infinity:
                sup = None
            else:
                re, im = sup.as_real_imag()

                if not im:
                    sup = QQ.convert(sup)
                else:
                    sup, sup_real = map(QQ.convert, (re, im)), False

        if inf_real and sup_real:
            try:
                count = f.rep.count_real_roots(inf=inf, sup=sup)
            except AttributeError: # pragma: no cover
                raise OperationNotSupported(f, 'count_real_roots')
        else:
            if inf_real and inf is not None:
                inf = (inf, QQ.zero)

            if sup_real and sup is not None:
                sup = (sup, QQ.zero)

            try:
                count = f.rep.count_complex_roots(inf=inf, sup=sup)
            except AttributeError: # pragma: no cover
                raise OperationNotSupported(f, 'count_complex_roots')

        return Integer(count)

    def real_roots(f, multiple=True):
        """
        Return a list of real roots with multiplicities.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(2*x**3 - 7*x**2 + 4*x + 4, x).real_roots()
        [-1/2, 2, 2]
        """
        reals = sympy.polys.rootoftools.RootOf(f)

        if multiple:
            return reals
        else:
            return group(reals, multiple=False)

    def nroots(f, maxsteps=50, cleanup=True, error=False):
        """
        Compute numerical approximations of roots of `f`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 - 3).nroots()
        [-1.73205080756888, 1.73205080756888]
        """
        if f.is_multivariate:
            raise PolynomialError("can't compute numerical roots of a multivariate polynomial")

        if f.degree() <= 0:
            return []

        try:
            coeffs = [ complex(c) for c in f.all_coeffs() ]
        except ValueError:
            raise DomainError("numerical domain expected, got %s" % f.rep.dom)

        return sympify(npolyroots(coeffs, maxsteps=maxsteps, cleanup=cleanup, error=error))

    def cancel(f, g, include=False):
        """
        Cancel common factors in a rational function `f/g`.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(2*x**2 - 2, x).cancel(Poly(x**2 - 2*x + 1, x))
        (1, Poly(2*x + 2, x, domain='ZZ'), Poly(x - 1, x, domain='ZZ'))
        >>> Poly(2*x**2 - 2, x).cancel(Poly(x**2 - 2*x + 1, x), include=True)
        (Poly(2*x + 2, x, domain='ZZ'), Poly(x - 1, x, domain='ZZ'))
        """
        dom, per, F, G = f.unify(g)

        if (F.is_zero or G.is_zero) and not include:
            return S.One, per(F), per(G)

        if dom.has_Field and dom.has_assoc_Ring:
            cF, F = F.clear_denoms()
            cG, G = G.clear_denoms()
            cF = dom.convert(cF, f.rep.dom.get_ring())
            cG = dom.convert(cG, g.rep.dom.get_ring())

            F = F.to_ring()
            G = G.to_ring()

        try:
            _, P, Q = F.cofactors(G)
        except AttributeError: # pragma: no cover
            raise OperationNotSupported(f, 'cofactors')

        if dom.has_Field and dom.has_assoc_Ring:
            P, Q = P.to_field(), Q.to_field()

            cF = dom.to_sympy(cF)
            cG = dom.to_sympy(cG)

            coeff = cG/cF
        else:
            coeff, cF, cG = [S.One]*3

        if include:
            return (per(P)*Poly(cG, *g.gens, **{'domain':dom}),
                per(Q)*Poly(cF, *f.gens, **{'domain':dom}))

        return coeff, per(P), per(Q)

    @property
    def is_zero(f):
        """
        Returns `True` if `f` is a zero polynomial.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(0, x).is_zero
        True
        >>> Poly(1, x).is_zero
        False
        """
        return f.rep.is_zero

    @property
    def is_one(f):
        """
        Returns `True` if `f` is a unit polynomial.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(0, x).is_one
        False
        >>> Poly(1, x).is_one
        True
        """
        return f.rep.is_one

    @property
    def is_sqf(f):
        """
        Returns `True` if `f` is a square-free polynomial.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 - 2*x + 1, x).is_sqf
        False
        >>> Poly(x**2 - 1, x).is_sqf
        True
        """
        return f.rep.is_sqf

    @property
    def is_monic(f):
        """
        Returns `True` if the leading coefficient of `f` is one.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x + 2, x).is_monic
        True
        >>> Poly(2*x + 2, x).is_monic
        False
        """
        return f.rep.is_monic

    @property
    def is_primitive(f):
        """
        Returns `True` if GCD of the coefficients of `f` is one.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(2*x**2 + 6*x + 12, x).is_primitive
        False
        >>> Poly(x**2 + 3*x + 6, x).is_primitive
        True
        """
        return f.rep.is_primitive

    @property
    def is_ground(f):
        """
        Returns `True` if `f` is an element of the ground domain.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x, x).is_ground
        False
        >>> Poly(2, x).is_ground
        True
        >>> Poly(y, x).is_ground
        True
        """
        return f.rep.is_ground

    @property
    def is_linear(f):
        """
        Returns `True` if `f` is linear in all its variables.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x + y + 2, x, y).is_linear
        True
        >>> Poly(x*y + 2, x, y).is_linear
        False
        """
        return f.rep.is_linear

    @property
    def is_monomial(f):
        """
        Returns `True` if `f` is zero or has only one term.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(3*x**2, x).is_monomial
        True
        >>> Poly(3*x**2 + 1, x).is_monomial
        False
        """
        return f.length() <= 1

    @property
    def is_homogeneous(f):
        """
        Returns `True` if `f` has zero trailing coefficient.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x*y + x + y, x, y).is_homogeneous
        True
        >>> Poly(x*y + x + y + 1, x, y).is_homogenous
        False
        """
        return f.rep.is_homogeneous

    @property
    def is_irreducible(f):
        """
        Returns `True` if `f` has no factors over its domain.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x
        >>> Poly(x**2 + x + 1, x, modulus=2).is_irreducible
        True
        >>> Poly(x**2 + 1, x, modulus=2).is_irreducible
        False
        """
        return f.rep.is_irreducible

    @property
    def is_univariate(f):
        """
        Returns `True` if `f` is an univariate polynomial.

        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**2 + x + 1, x).is_univariate
        True
        >>> Poly(x*y**2 + x*y + 1, x, y).is_univariate
        False
        >>> Poly(x*y**2 + x*y + 1, x).is_univariate
        True
        >>> Poly(x**2 + x + 1, x, y).is_univariate
        False
        """
        return len(f.gens) == 1

    @property
    def is_multivariate(f):
        """
        Returns `True` if `f` is a multivariate polynomial.
        **Example**

        >>> from sympy import Poly
        >>> from sympy.abc import x, y
        >>> Poly(x**2 + x + 1, x).is_multivariate
        False
        >>> Poly(x*y**2 + x*y + 1, x, y).is_multivariate
        True
        >>> Poly(x*y**2 + x*y + 1, x).is_multivariate
        False
        >>> Poly(x**2 + x + 1, x, y).is_multivariate
        True
        """
        return len(f.gens) != 1

    def __abs__(f):
        return f.abs()

    def __neg__(f):
        return f.neg()

    @_sympifyit('g', NotImplemented)
    def __add__(f, g):
        if not g.is_Poly:
            try:
                g = Poly(g, *f.gens)
            except PolynomialError:
                return f.as_basic() + g

        return f.add(g)

    @_sympifyit('g', NotImplemented)
    def __radd__(f, g): # pragma: no cover
        if not g.is_Poly:
            try:
                g = Poly(g, *f.gens)
            except PolynomialError:
                return g + f.as_basic()

        return g.add(f)

    @_sympifyit('g', NotImplemented)
    def __sub__(f, g):
        if not g.is_Poly:
            try:
                g = Poly(g, *f.gens)
            except PolynomialError:
                return f.as_basic() - g

        return f.sub(g)

    @_sympifyit('g', NotImplemented)
    def __rsub__(f, g): # pragma: no cover
        if not g.is_Poly:
            try:
                g = Poly(g, *f.gens)
            except PolynomialError:
                return g - f.as_basic()

        return g.sub(f)

    @_sympifyit('g', NotImplemented)
    def __mul__(f, g):
        if not g.is_Poly:
            try:
                g = Poly(g, *f.gens)
            except PolynomialError:
                return f.as_basic()*g

        return f.mul(g)

    @_sympifyit('g', NotImplemented)
    def __rmul__(f, g): # pragma: no cover
        if not g.is_Poly:
            try:
                g = Poly(g, *f.gens)
            except PolynomialError:
                return g*f.as_basic()

        return g.mul(f)

    @_sympifyit('n', NotImplemented)
    def __pow__(f, n):
        if n.is_Integer and n >= 0:
            return f.pow(n)
        else:
            return f.as_basic()**n

    @_sympifyit('g', NotImplemented)
    def __divmod__(f, g):
        if not g.is_Poly:
            g = Poly(g, *f.gens)

        return f.div(g)

    @_sympifyit('g', NotImplemented)
    def __rdivmod__(f, g): # pragma: no cover
        if not g.is_Poly:
            g = Poly(g, *f.gens)

        return g.div(f)

    @_sympifyit('g', NotImplemented)
    def __mod__(f, g):
        if not g.is_Poly:
            g = Poly(g, *f.gens)

        return f.rem(g)

    @_sympifyit('g', NotImplemented)
    def __rmod__(f, g): # pragma: no cover
        if not g.is_Poly:
            g = Poly(g, *f.gens)

        return g.rem(f)

    @_sympifyit('g', NotImplemented)
    def __floordiv__(f, g):
        if not g.is_Poly:
            g = Poly(g, *f.gens)

        return f.exquo(g)

    @_sympifyit('g', NotImplemented)
    def __rfloordiv__(f, g): # pragma: no cover
        if not g.is_Poly:
            g = Poly(g, *f.gens)

        return g.exquo(f)

    @_sympifyit('g', NotImplemented)
    def __eq__(f, g):
        if not g.is_Poly:
            try:
                g = Poly(g, *f.gens, **{'domain': f.get_domain()})
            except (PolynomialError, DomainError, CoercionFailed):
                return False

        if f.gens != g.gens:
            return False

        if f.rep.dom != g.rep.dom:
            try:
                dom = f.rep.dom.unify(g.rep.dom, f.gens)
            except UnificationFailed:
                return False

            f = f.set_domain(dom)
            g = g.set_domain(dom)

        return f.rep == g.rep

    @_sympifyit('g', NotImplemented)
    def __ne__(f, g):
        return not f.__eq__(g)

    def __nonzero__(f):
        return not f.is_zero

def NonStrictPoly(f, *gens, **args):
    """
    Create a Poly instance with the `strict` keyword set to False.

    This means that the result might not necessarily be an instance of Poly.

    **Example**

    >>> from sympy.polys.polytools import Poly, NonStrictPoly
    >>> from sympy.abc import x
    >>> Poly(1)
    Traceback (most recent call last):
    ...
    GeneratorsNeeded: can't initialize from 1 without generators
    >>> NonStrictPoly(1)
    1
    """
    args = dict(args)
    args['strict'] = False
    return Poly(f, *gens, **args)

def _polify_basic(f, g, *gens, **args):
    """Cooperatively make polynomials out of `f` and `g`. """
    if gens:
        F = NonStrictPoly(f, *gens, **args)
        G = NonStrictPoly(g, *gens, **args)

        if not F.is_Poly or not G.is_Poly:
            raise CoercionFailed(F, G) # pragma: no cover
        else:
            return F, G
    else:
        F = NonStrictPoly(f, **args)
        G = NonStrictPoly(g, **args)

        if F.is_Poly:
            if G.is_Poly:
                return F, G
            else:
                return F, Poly(g, *F.gens, **args)
        else:
            if G.is_Poly:
                return Poly(f, *G.gens, **args), G
            else:
                raise CoercionFailed(F, G)

def _update_args(args, key, value):
    """Add a new `(key, value)` pair to arguments dict. """
    args = dict(args)

    if not args.has_key(key):
        args[key] = value

    return args

def _filter_args(args, *keys):
    """Filter the given keys from the args dict. """
    if not keys:
        return {}

    keys, result = set(keys), {}

    for key, value in args.items():
        if key in keys:
            result[key] = value

    return result

def _should_return_basic(*polys, **args):
    """Figure out if results should be returned as basic. """
    query = args.get('polys')

    if query is not None:
        return not query
    else:
        return not all(isinstance(poly, Poly) for poly in polys)

def _keep_coeff(coeff, factors):
    """Return ``coeff*factors`` unevaluated if necessary. """
    if coeff == 1:
        return factors
    elif coeff == -1:
        return -factors
    elif not factors.is_Add:
        return coeff*factors
    else:
        return Mul(coeff, factors, evaluate=False)

def degree(f, *gens, **args):
    """
    Returns the degree of `f` in the given generator.

    **Example**

    >>> from sympy import degree
    >>> from sympy.abc import x, y
    >>> degree(x**2 + y*x + 1, x)
    2
    >>> degree(x**2 + y*x + 1, y)
    1
    """
    try:
        F = Poly(f, *_analyze_gens(gens), **args)
    except GeneratorsNeeded:
        raise GeneratorsNeeded("can't compute degree of %s without generators" % f)

    degree = F.degree(args.get('gen', 0))

    return Integer(degree)

def degree_list(f, *gens, **args):
    """
    Returns a list of degrees of `f` in all generators.

    **Example**

    >>> from sympy import degree_list
    >>> from sympy.abc import x, y
    >>> degree_list(x**2 + y*x + 1)
    (2, 1)
    """
    try:
        F = Poly(f, *_analyze_gens(gens), **args)
    except GeneratorsNeeded:
        raise GeneratorsNeeded("can't compute degrees list of %s without generators" % f)

    degrees = F.degree_list()

    return tuple(map(Integer, degrees))

def LC(f, *gens, **args):
    """
    Returns the leading coefficient of `f`.

    **Example**

    >>> from sympy import LC
    >>> from sympy.abc import x
    >>> LC(4*x**3 + 2*x**2 + 3*x)
    4
    """
    order = args.pop('order', None)

    try:
        return Poly(f, *gens, **args).LC(order=order)
    except GeneratorsNeeded:
        raise GeneratorsNeeded("can't compute the leading coefficient of %s without generators" % f)

def LM(f, *gens, **args):
    """
    Returns the leading monomial of `f`.

    **Example**
    >>> from sympy import LM
    >>> from sympy.abc import x, y
    >>> LM(4*x**2 + 2*x*y**2 + x*y + 3*y, x, y)
    x**2
    """
    order = args.pop('order', None)

    try:
        f = Poly(f, *gens, **args)
    except GeneratorsNeeded:
        raise GeneratorsNeeded("can't compute the leading monomial of %s without generators" % f)

    return Monomial(*f.LM(order=order)).as_basic(*f.gens)

def LT(f, *gens, **args):
    """
    Returns the leading term of `f`.

    **Example**

    >>> from sympy import LT
    >>> from sympy.abc import x, y
    >>> LT(4*x**2 + 2*x*y**2 + x*y + 3*y, x, y)
    4*x**2
    """
    order = args.pop('order', None)

    try:
        f = Poly(f, *gens, **args)
    except GeneratorsNeeded:
        raise GeneratorsNeeded("can't compute the leading term of %s without generators" % f)

    monom, coeff = f.LT(order=order)

    return coeff*Monomial(*monom).as_basic(*f.gens)

def pdiv(f, g, *gens, **args):
    """
    Polynomial pseudo-division of `f` and `g`.

    **Example**

    >>> from sympy import pdiv
    >>> from sympy.abc import x
    >>> pdiv(x**2 + 1, 2*x - 4)
    (4 + 2*x, 20)
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        raise GeneratorsNeeded("can't compute pseudo division of %s and %s without generators" % (f, g))

    q, r = F.pdiv(G)

    if _should_return_basic(f, g, **args):
        return q.as_basic(), r.as_basic()
    else:
        return q, r

def prem(f, g, *gens, **args):
    """
    Polynomial pseudo-remainder of `f` and `g`.

    **Example**

    >>> from sympy import prem
    >>> from sympy.abc import x
    >>> prem(x**2 + 1, 2*x - 4)
    20
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        raise GeneratorsNeeded("can't compute pseudo remainder of %s and %s without generators" % (f, g))

    r = F.prem(G)

    if _should_return_basic(f, g, **args):
        return r.as_basic()
    else:
        return r

def pquo(f, g, *gens, **args):
    """
    Polynomial pseudo-quotient of `f` and `g`.

    **Example**

    >>> from sympy import pquo
    >>> from sympy.abc import x
    >>> pquo(x**2 + 1, 2*x - 4)
    Traceback (most recent call last):
    ...
    ExactQuotientFailed: -4 + 2*x does not divide 1 + x**2 in ZZ
    >>> pquo(x**2 - 1, 2*x - 2)
    2 + 2*x
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        raise GeneratorsNeeded("can't compute pseudo quotient of %s and %s without generators" % (f, g))

    try:
        q = F.pquo(G)
    except ExactQuotientFailed:
        raise ExactQuotientFailed("%s does not divide %s in %s" % (g, f, F.get_domain()))

    if _should_return_basic(f, g, **args):
        return q.as_basic()
    else:
        return q

def pexquo(f, g, *gens, **args):
    """
    Polynomial exact pseudo-quotient of `f` and `g`.

    **Example**

    >>> from sympy import pexquo
    >>> from sympy.abc import x
    >>> pexquo(x**2 + 1, 2*x - 4)
    4 + 2*x
    >>> pexquo(x**2 - 1, 2*x - 1)
    1 + 2*x
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        raise GeneratorsNeeded("can't compute pseudo quotient of %s and %s without generators" % (f, g))

    q = F.pexquo(G)

    if _should_return_basic(f, g, **args):
        return q.as_basic()
    else:
        return q

def div(f, g, *gens, **args):
    """
    Polynomial division with remainder of `f` and `g`.

    **Example**

    >>> from sympy import div, ZZ, QQ
    >>> from sympy.abc import x
    >>> div(x**2 + 1, 2*x - 4, domain=ZZ)
    (0, 1 + x**2)
    >>> div(x**2 + 1, 2*x - 4, domain=QQ)
    (1 + x/2, 5)
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        raise GeneratorsNeeded("can't compute division of %s and %s without generators" % (f, g))

    q, r = F.div(G)

    if _should_return_basic(f, g, **args):
        return q.as_basic(), r.as_basic()
    else:
        return q, r

def rem(f, g, *gens, **args):
    """
    Computes the polynomial remainder of `f` and `g`.

    **Example**

    >>> from sympy import rem, ZZ, QQ
    >>> from sympy.abc import x
    >>> rem(x**2 + 1, 2*x - 4, domain=ZZ)
    1 + x**2
    >>> rem(x**2 + 1, 2*x - 4, domain=QQ)
    5
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        raise GeneratorsNeeded("can't compute remainder of %s and %s without generators" % (f, g))

    r = F.rem(G)

    if _should_return_basic(f, g, **args):
        return r.as_basic()
    else:
        return r

def quo(f, g, *gens, **args):
    """
    Computes polynomial quotient of `f` and `g`.

    **Example**

    >>> from sympy import quo
    >>> from sympy.abc import x
    >>> quo(x**2 + 1, 2*x - 4)
    Traceback (most recent call last):
    ...
    ExactQuotientFailed: -4 + 2*x does not divide 1 + x**2 in ZZ
    >>> quo(x**2 - 1, x - 1)
    1 + x
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        raise GeneratorsNeeded("can't compute quotient of %s and %s without generators" % (f, g))

    try:
        q = F.quo(G)
    except ExactQuotientFailed:
        raise ExactQuotientFailed("%s does not divide %s in %s" % (g, f, F.get_domain()))

    if _should_return_basic(f, g, **args):
        return q.as_basic()
    else:
        return q

def exquo(f, g, *gens, **args):
    """
    Computes polynomial exact quotient of `f` and `g`.

    **Example**

    >>> from sympy import exquo
    >>> from sympy.abc import x
    >>> exquo(x**2 + 1, 2*x - 4)
    0
    >>> exquo(x**2 - 1, x - 1)
    1 + x
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        raise GeneratorsNeeded("can't compute quotient of %s and %s without generators" % (f, g))

    q = F.exquo(G)

    if _should_return_basic(f, g, **args):
        return q.as_basic()
    else:
        return q

def half_gcdex(f, g, *gens, **args):
    """
    Half extended Euclidean algorithm of `f` and `g`.

    Returns `(s, h)` such that `h = gcd(f, g)` and `s*f = h (mod g)`.

    **Example**

    >>> from sympy import half_gcdex
    >>> from sympy.abc import x
    >>> half_gcdex(x**4 - 2*x**3 - 6*x**2 + 12*x + 15, x**3 + x**2 - 4*x - 4)
    (3/5 - x/5, 1 + x)
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        try:
            return f.half_gcdex(g)
        except (AttributeError, TypeError): # pragma: no cover
            raise GeneratorsNeeded("can't compute half extended GCD of %s and %s without generators" % (f, g))

    s, h = F.half_gcdex(G, **_filter_args(args, 'auto'))

    if _should_return_basic(f, g, **args):
        return s.as_basic(), h.as_basic()
    else:
        return s, h

def gcdex(f, g, *gens, **args):
    """
    Extended Euclidean algorithm of `f` and `g`.

    Returns `(s, t, h)` such that `h = gcd(f, g)` and `s*f + t*g = h`.

    **Example**

    >>> from sympy import gcdex
    >>> from sympy.abc import x
    >>> gcdex(x**4 - 2*x**3 - 6*x**2 + 12*x + 15, x**3 + x**2 - 4*x - 4)
    (3/5 - x/5, 2 - 6*x/5 + x**2/5, 1 + x)
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        try:
            return f.gcdex(g)
        except (AttributeError, TypeError): # pragma: no cover
            raise GeneratorsNeeded("can't compute extended GCD of %s and %s without generators" % (f, g))

    s, t, h = F.gcdex(G, **_filter_args(args, 'auto'))

    if _should_return_basic(f, g, **args):
        return s.as_basic(), t.as_basic(), h.as_basic()
    else:
        return s, t, h

def invert(f, g, *gens, **args):
    """
    Invert `f` modulo `g`, if possible.

    **Example**

    >>> from sympy import invert
    >>> from sympy.abc import x
    >>> invert(x**2 - 1, 2*x - 1)
    -4/3
    >>> invert(x**2 - 1, x - 1)
    Traceback (most recent call last):
    ...
    NotInvertible: zero divisor
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        try:
            return f.invert(g)
        except (AttributeError, TypeError): # pragma: no cover
            raise GeneratorsNeeded("can't compute inversion of %s modulo %s without generators" % (f, g))

    h = F.invert(G, **_filter_args(args, 'auto'))

    if _should_return_basic(f, g, **args):
        return h.as_basic()
    else:
        return h

def subresultants(f, g, *gens, **args):
    """
    Computes the subresultant PRS sequence of `f` and `g`.

    **Example**

    >>> from sympy import subresultants
    >>> from sympy.abc import x
    >>> subresultants(x**2 + 1, x**2 - 1)
    [1 + x**2, -1 + x**2, -2]
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        raise GeneratorsNeeded("can't compute subresultants of %s and %s without generators" % (f, g))

    result = F.subresultants(G)

    if _should_return_basic(f, g, **args):
        return [ r.as_basic() for r in result ]
    else:
        return result

def resultant(f, g, *gens, **args):
    """
    Computes the resultant of `f` and `g` via PRS.

    **Example**

    >>> from sympy import resultant
    >>> from sympy.abc import x
    >>> resultant(x**2 + 1, x**2 - 1)
    4
    >>> resultant(x**2 + 1, x**2 - 1, includePRS=True)
    (4, [1 + x**2, -1 + x**2, -2])
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        raise GeneratorsNeeded("can't compute resultant of %s and %s without generators" % (f, g))

    includePRS = args.get('includePRS', False)
    if includePRS:
        result, R = F.resultant(G, includePRS)
    else:
        result = F.resultant(G)

    if includePRS:
        if _should_return_basic(f, g, **args):
            return (result.as_basic(), [ r.as_basic() for r in R])
        else:
            return (result, R)
    if _should_return_basic(f, g, **args):
        return result.as_basic()
    else:
        return result

def discriminant(f, *gens, **args):
    """
    Computes the discriminant of `f`.

    **Example**

    >>> from sympy import discriminant
    >>> from sympy.abc import x
    >>> discriminant(x**2 + 2*x + 3)
    -8
    """
    F = NonStrictPoly(f, *_analyze_gens(gens), **args)

    if not F.is_Poly:
        raise GeneratorsNeeded("can't compute discriminant of %s without generators" % f)

    result = F.discriminant()

    if _should_return_basic(f, **args):
        return result.as_basic()
    else:
        return result

def cofactors(f, g, *gens, **args):
    """
    Returns the GCD of `f` and `g` and their cofactors.

    Returns `(h, cff, cfg)` such that `a = gcd(f, g)`, `cff = quo(f, h)`,
    and `cfg = quo(g, h)`.

    **Example**

    >>> from sympy import cofactors
    >>> from sympy.abc import x
    >>> cofactors(x**2 - 1, x**2 - 3*x + 2)
    (-1 + x, 1 + x, -2 + x)
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        try:
            return f.cofactors(g)
        except (AttributeError, TypeError): # pragma: no cover
            raise GeneratorsNeeded("can't compute cofactors of %s and %s without generators" % (f, g))

    h, cff, cfg = F.cofactors(G)

    if _should_return_basic(f, g, **args):
        return h.as_basic(), cff.as_basic(), cfg.as_basic()
    else:
        return h, cff, cfg

def gcd(f, g, *gens, **args):
    """
    Returns the polynomial GCD of `f` and `g`.

    **Example**

    >>> from sympy import gcd
    >>> from sympy.abc import x
    >>> gcd(x**2 - 1, x**2 - 3*x + 2)
    -1 + x
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        try:
            return f.gcd(g)
        except (AttributeError, TypeError): # pragma: no cover
            raise GeneratorsNeeded("can't compute GCD of %s and %s without generators" % (f, g))

    result = F.gcd(G)

    if _should_return_basic(f, g, **args):
        return result.as_basic()
    else:
        return result

def lcm(f, g, *gens, **args):
    """
    Returns polynomial LCM of `f` and `g`.

    **Example**

    >>> from sympy import lcm
    >>> from sympy.abc import x
    >>> lcm(x**2 - 1, x**2 - 3*x + 2)
    2 - x - 2*x**2 + x**3
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        try:
            return f.lcm(g)
        except (AttributeError, TypeError): # pragma: no cover
            raise GeneratorsNeeded("can't compute LCM of %s and %s without generators" % (f, g))

    result = F.lcm(G)

    if _should_return_basic(f, g, **args):
        return result.as_basic()
    else:
        return result

def terms_gcd(f, *gens, **args):
    """
    Remove GCD of terms from the polynomial `f`.

    **Example**

    >>> from sympy import terms_gcd
    >>> from sympy.abc import x, y
    >>> terms_gcd(x**6*y**2 + x**3*y, x, y)
    y*x**3*(1 + y*x**3)
    """
    try:
        f = Poly(f, *_analyze_gens(gens), **args)
    except GeneratorsNeeded:
        return f

    (J, f), dom = f.terms_gcd(), f.get_domain()

    if dom.has_Ring:
        if dom.has_Field:
            denom, f = f.clear_denoms(convert=True)

        coeff, f = f.primitive()

        if dom.has_Field:
            coeff /= denom
    else:
        coeff = 1

    term = Mul(*[ x**j for x, j in zip(f.gens, J) ])

    return _keep_coeff(coeff, term*f.as_basic())

def trunc(f, p, *gens, **args):
    """
    Reduce `f` modulo a constant `p`.

    **Example**

    >>> from sympy import trunc
    >>> from sympy.abc import x
    >>> trunc(2*x**3 + 3*x**2 + 5*x + 7, 3)
    1 - x - x**3
    """
    F = NonStrictPoly(f, *_analyze_gens(gens), **args)

    if not F.is_Poly:
        return F % p

    if _should_return_basic(f, **args):
        return F.trunc(p).as_basic()
    else:
        return F.trunc(p)

def monic(f, *gens, **args):
    """
    Divides all coefficients by `LC(f)`.

    **Example**

    >>> from sympy import monic
    >>> from sympy.abc import x
    >>> monic(3*x**2 + 4*x + 2)
    2/3 + 4*x/3 + x**2
    """
    F = NonStrictPoly(f, *_analyze_gens(gens), **args)

    if not F.is_Poly:
        raise GeneratorsNeeded("can't compute monic polynomial of %s without generators" % f)

    G = F.monic(**_filter_args(args, 'auto'))

    if _should_return_basic(f, **args):
        return G.as_basic()
    else:
        return G

def content(f, *gens, **args):
    """
    Returns the GCD of polynomial coefficients.

    **Example**

    >>> from sympy import content
    >>> from sympy.abc import x
    >>> content(6*x**2 + 8*x + 12)
    2
    """
    F = NonStrictPoly(f, *_analyze_gens(gens), **args)

    if not F.is_Poly:
        raise GeneratorsNeeded("can't compute content of %s without generators" % f)
    else:
        return F.content()

def primitive(f, *gens, **args):
    """
    Returns the content and a primitive form of `f`.

    **Example**

    >>> from sympy import primitive
    >>> from sympy.abc import x
    >>> primitive(6*x**2 + 8*x + 12)
    (2, 6 + 4*x + 3*x**2)
    """
    F = NonStrictPoly(f, *_analyze_gens(gens), **args)

    if not F.is_Poly:
        raise GeneratorsNeeded("can't compute primitive part of %s without generators" % f)

    cont, result = F.primitive()

    if _should_return_basic(f, **args):
        return cont, result.as_basic()
    else:
        return cont, result

def compose(f, g, *gens, **args):
    """
    Efficiently computes the functional composition `f(g)`.

    **Example**

    >>> from sympy import compose
    >>> from sympy.abc import x
    >>> compose(x**2 + x, x - 1)
    -x + x**2
    """
    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(f, g, *gens, **args)
    except CoercionFailed, (f, g):
        raise GeneratorsNeeded("can't compute composition of %s and %s without generators" % (f, g))

    result = F.compose(G)

    if _should_return_basic(f, g, **args):
        return result.as_basic()
    else:
        return result

def decompose(f, *gens, **args):
    """
    Computes a functional decomposition of `f`.

    **Example**

    >>> from sympy import decompose
    >>> from sympy.abc import x
    >>> decompose(x**4 + 2*x**3 - x - 1)
    [-1 - x + x**2, x + x**2]
    """
    F = NonStrictPoly(f, *_analyze_gens(gens), **args)

    if not F.is_Poly:
        raise GeneratorsNeeded("can't compute functional decomposition of %s without generators" % f)

    result = F.decompose()

    if _should_return_basic(f, **args):
        return [ r.as_basic() for r in result ]
    else:
        return result

def sturm(f, *gens, **args):
    """
    Computes the Sturm sequence of `f`.

    **Example**

    >>> from sympy import sturm
    >>> from sympy.abc import x
    >>> sturm(x**3 - 2*x**2 + x - 3)
    [-3 + x - 2*x**2 + x**3, 1 - 4*x + 3*x**2, 25/9 + 2*x/9, -2079/4]
    """
    F = NonStrictPoly(f, *_analyze_gens(gens), **args)

    if not F.is_Poly:
        raise GeneratorsNeeded("can't compute Sturm sequence of %s without generators" % f)

    result = F.sturm(**_filter_args(args, 'auto'))

    if _should_return_basic(f, **args):
        return [ r.as_basic() for r in result ]
    else:
        return result

def sqf_norm(f, *gens, **args):
    """
    Computes square-free norm of `f`.

    Returns `s`, `f`, `r`, such that `g(x) = f(x-sa)` and `r(x) = Norm(g(x))`
    is a square-free polynomtal over K, where `a` is the algebraic extension
    of the ground domain `K`.

    **Example**

    >>> from sympy import sqf_norm, sqrt
    >>> from sympy.abc import x
    >>> sqf_norm(x**2 + 1, extension=[sqrt(3)])
    (1, 4 - 2*x*3**(1/2) + x**2, 16 - 4*x**2 + x**4)
    """
    F = NonStrictPoly(f, *_analyze_gens(gens), **args)

    if not F.is_Poly:
        raise GeneratorsNeeded("can't compute square-free norm of %s without generators" % f)

    s, g, r = F.sqf_norm()

    if _should_return_basic(f, **args):
        return Integer(s), g.as_basic(), r.as_basic()
    else:
        return Integer(s), g, r

def sqf_part(f, *gens, **args):
    """
    Computes the square-free part of `f`.

    **Example**

    >>> from sympy import sqf_part
    >>> from sympy.abc import x
    >>> sqf_part(x**3 - 3*x - 2)
    -2 - x + x**2
    """
    F = NonStrictPoly(f, *_analyze_gens(gens), **args)

    if not F.is_Poly:
        raise GeneratorsNeeded("can't compute square-free part of %s without generators" % f)

    result = F.sqf_part()

    if _should_return_basic(f, **args):
        return result.as_basic()
    else:
        return result

def sqf_list(f, *gens, **args):
    """
    Returns a list of square-free factors of `f`.

    **Example**

    >>> from sympy import sqf_list
    >>> from sympy.abc import x
    >>> sqf_list(2*x**5 + 16*x**4 + 50*x**3 + 76*x**2 + 56*x + 16)
    (2, [(1 + x, 2), (2 + x, 3)])
    >>> sqf_list(2*x**5 + 16*x**4 + 50*x**3 + 76*x**2 + 56*x + 16, all=True)
    (2, [(1, 1), (1 + x, 2), (2 + x, 3)])
    """
    F = NonStrictPoly(f, *_analyze_gens(gens), **args)

    if not F.is_Poly:
        raise GeneratorsNeeded("can't compute square-free decomposition of %s without generators" % f)

    all = args.get('all', False)

    if not args.get('include', False):
        coeff, factors = result = F.sqf_list(all)

        if _should_return_basic(f, **args):
            return coeff, [ (g.as_basic(), k) for g, k in factors ]
        else:
            return coeff, factors
    else:
        factors = F.sqf_list_include()

        if _should_return_basic(f, **args):
            return [ (g.as_basic(), k) for g, k in factors ]
        else:
            return factors

def sqf(f, *gens, **args):
    """
    Returns the square-free decomposition of `f`.

    **Example**

    >>> from sympy import sqf
    >>> from sympy.abc import x
    >>> sqf(2*x**5 + 16*x**4 + 50*x**3 + 76*x**2 + 56*x + 16)
    2*(1 + x)**2*(2 + x)**3
    """
    frac = args.get('frac', False)
    gens = _analyze_gens(gens)

    def _sqf(f):
        """Squaqre-free factor a true polynomial expression. """
        F = NonStrictPoly(f, *gens, **args)

        if not F.is_Poly:
            return (S.One, F)

        (coeff, factors), result = F.sqf_list(), S.One

        for g, k in factors:
            result *= g.as_basic()**k

        return (coeff, result)

    if not frac:
        coeff, factors = _sqf(f)
    else:
        p, q = cancel(f).as_numer_denom()

        coeff_p, factors_p = _sqf(p)
        coeff_q, factors_q = _sqf(q)

        coeff = coeff_p / coeff_q
        factors = factors_p / factors_q

    return _keep_coeff(coeff, factors)

def factor_list(f, *gens, **args):
    """
    Returns a list of irreducible factors of `f`.

    **Example**

    >>> from sympy import factor_list
    >>> from sympy.abc import x, y
    >>> factor_list(4*x**2*y**2 + 4*x**3*y**2 + 2*x**4 + 2*y**4 + 2*x*y**4 +
    ... 2*x**5, x, y)
    (2, [(1 + x, 1), (x**2 + y**2, 2)])
    """
    F = NonStrictPoly(f, *_analyze_gens(gens), **args)

    if not F.is_Poly:
        raise GeneratorsNeeded("can't compute factorization of %s without generators" % f)

    if not args.get('include', False):
        coeff, factors = result = F.factor_list()

        if _should_return_basic(f, **args):
            return coeff, [ (g.as_basic(), k) for g, k in factors ]
        else:
            return coeff, factors
    else:
        factors = F.factor_list_include()

        if _should_return_basic(f, **args):
            return [ (g.as_basic(), k) for g, k in factors ]
        else:
            return factors

@register_context
def factor(f, *gens, **args):
    """
    Returns the factorization into irreducibles of `f`.

    The set the `frac` option to True to have `factor()` factor the denominator
    of an expression.

    By default, the factorization is over the same field as the coefficients.
    To factor over an algebraic extension, use the `extension` keyword argument.

    **Example**

    >>> from sympy import factor, I
    >>> from sympy.abc import x, y
    >>> factor(4*x**2*y**2 + 4*x**3*y**2 + 2*x**4 + 2*y**4 + 2*x*y**4 +
    ... 2*x**5)
    2*(x**2 + y**2)**2*(1 + x)

    >>> factor((x**2 - 1)/(x**2 + 4*x + 4))
    -(1 + x)*(1 - x)/(4 + 4*x + x**2)
    >>> factor((x**2 - 1)/(x**2 + 4*x + 4), frac=True)
    -(1 + x)*(1 - x)/(2 + x)**2

    >>> factor(x**2 + 1, extension=[I])
    (x + I)*(x - I)
    """
    frac = args.get('frac', False)

    def _factor(f):
        """Factor a true polynomial expression. """
        F = NonStrictPoly(f, *gens, **args)

        if not F.is_Poly:
            return (S.One, F)

        (coeff, factors), result = F.factor_list(), S.One

        for g, k in factors:
            result *= g.as_basic()**k

        return (coeff, result)

    if not frac:
        coeff, factors = _factor(f)
    else:
        p, q = cancel(f).as_numer_denom()

        coeff_p, factors_p = _factor(p)
        coeff_q, factors_q = _factor(q)

        coeff = coeff_p / coeff_q
        factors = factors_p / factors_q

    return _keep_coeff(coeff, factors)

def intervals(F, all=False, eps=None, inf=None, sup=None, strict=False, fast=False, sqf=False):
    """
    Compute isolating intervals for roots of `f`.

    **Example**

    >>> from sympy import intervals
    >>> from sympy.abc import x
    >>> intervals(x**2 - 3)
    [((-2, -1), 1), ((1, 2), 1)]
    >>> intervals(x**2 - 3, eps=1e-2)
    [((-26/15, -19/11), 1), ((19/11, 26/15), 1)]
    """
    if not hasattr(F, '__iter__'):
        try:
            F = Poly(F)
        except GeneratorsNeeded:
            return []

        return F.intervals(all=all, eps=eps, inf=inf, sup=sup, fast=fast, sqf=sqf)
    else:
        # XXX: the following should read:
        #
        #   F, gens, dom = parallel_from_basic(F)
        #
        #   if len(gens) > 1:
        #       raise MultivariatePolynomialError("...")
        #
        #   (the same applies to groebner(), reduced() ...)

        G, gens = [], set([])

        for f in F:
            try:
                g = Poly(f, domain=QQ)

                gens |= set(g.gens)

                if len(gens) > 1:
                    raise PolynomialError("multivariate polynomials are not supported")
                else:
                    G.append(g.rep.rep)
            except GeneratorsNeeded:
                G.append([])

        if eps is not None:
            eps = QQ.convert(eps)
        if inf is not None:
            inf = QQ.convert(inf)
        if sup is not None:
            sup = QQ.convert(sup)

        intervals = dup_isolate_real_roots_list(G, QQ,
            eps=eps, inf=inf, sup=sup, strict=strict, fast=fast)

        result = []

        for (s, t), indices in intervals:
            result.append(((QQ.to_sympy(s), QQ.to_sympy(t)), indices))

        return result

def refine_root(f, s, t, eps=None, steps=None, fast=False, check_sqf=False):
    """
    Refine an isolating interval of a root to the given precision.

    **Example**

    >>> from sympy import refine_root
    >>> from sympy.abc import x
    >>> refine_root(x**2 - 3, 1, 2, eps=1e-2)
    (19/11, 26/15)
    """
    try:
        F = Poly(f)
    except GeneratorsNeeded:
        raise PolynomialError("can't refine a root of %s, not a polynomial" % f)

    return F.refine_root(s, t, eps=eps, steps=steps, fast=fast, check_sqf=check_sqf)

def count_roots(f, inf=None, sup=None):
    """
    Return the number of roots of ``f`` in ``[inf, sup]`` interval.

    If one of `inf` or `sup` is complex, it will return the number of roots
    in the complex rectangle with corners at `inf` and `sup`.

    **Example**

    >>> from sympy import count_roots, I
    >>> from sympy.abc import x
    >>> count_roots(x**4 - 4, -3, 3)
    2
    >>> count_roots(x**4 - 4, 0, 1 + 3*I)
    1
    """
    try:
        F = Poly(f, greedy=False)
    except GeneratorsNeeded:
        raise PolynomialError("can't count roots of %s, not a polynomial" % f)

    return F.count_roots(inf=inf, sup=sup)

def real_roots(f, multiple=True):
    """
    Return a list of real roots with multiplicities of ``f``.

    **Example**

    >>> from sympy import real_roots
    >>> from sympy.abc import x
    >>> real_roots(2*x**3 - 7*x**2 + 4*x + 4)
    [-1/2, 2, 2]
    """
    try:
        F = Poly(f, greedy=False)
    except GeneratorsNeeded:
        raise PolynomialError("can't compute real roots of %s, not a polynomial" % f)

    return F.real_roots(multiple=multiple)

def nroots(f, maxsteps=50, cleanup=True, error=False):
    """
    Compute numerical approximations of roots of `f`.

    **Example**

    >>> from sympy import nroots
    >>> from sympy.abc import x
    >>> nroots(x**2 - 3)
    [-1.73205080756888, 1.73205080756888]
    """
    try:
        F = Poly(f, greedy=False)
    except GeneratorsNeeded:
        raise PolynomialError("can't compute numerical roots of %s, not a polynomial" % f)

    return F.nroots(maxsteps=maxsteps, cleanup=cleanup, error=error)

def cancel(f, *gens, **args):
    """
    Cancel common factors in a rational function `f`.

    **Example**

    >>> from sympy import cancel
    >>> from sympy.abc import x
    >>> cancel((2*x**2 - 2)/(x**2 - 2*x + 1))
    -(2 + 2*x)/(1 - x)
    """
    f = sympify(f)

    if type(f) is not tuple:
        if f.is_Number:
            return f
        else:
            p, q = f.as_numer_denom()
    else:
        p, q = f

    gens = _analyze_gens(gens)

    try:
        F, G = _polify_basic(p, q, *gens, **args)
    except CoercionFailed:
        if type(f) is not tuple:
            return f
        else:
            return S.One, p, q

    c, P, Q = F.cancel(G)

    if type(f) is not tuple:
        return c*(P.as_basic()/Q.as_basic())
    else:
        if _should_return_basic(p, q, **args):
            return c, P.as_basic(), Q.as_basic()
        else:
            return c, P, Q

def reduced(f, G, *gens, **args):
    """
    Reduces a polynomial `f` modulo a set of polynomials `G`.

    Given a polynomial `f` and a set of polynomials `G = (g_1, ..., g_n)`,
    computes a set of quotients `q = (q_1, ..., q_n)` and remainder `r`
    such that `f = q_1*f_1 + ... + q_n*f_n + r`, where `r = 0` or `r`
    is a completely reduced polynomial with respect to `G`.

    **Example**

    >>> from sympy import reduced
    >>> from sympy.abc import x, y
    >>> reduced(2*x**4 + y**2 - x**2 + y**3, [x**3 - x, y**3 - y])
    ([2*x, 1], y + x**2 + y**2)
    """
    if 'modulus' in args:
        raise PolynomialError("can't reduce a polynomial over a finite field")

    H = [f] + list(G)

    order = Poly._analyze_order({'order': args.pop('order', 'lex')})
    basic = _should_return_basic(*H, **args)

    gens = _analyze_gens(gens)

    H = [ Poly(h, *gens, **args) for h in H ]
    dom, gens = H[0].get_domain(), H[0].gens

    for h in H[1:]:
        gens = _unify_gens(gens, h.gens)
        dom = dom.unify(h.get_domain(), gens)

    lev = len(gens) - 1

    for i, h in enumerate(H):
        h = Poly(h, *gens, **{'domain': dom})
        H[i] = sdp_from_dict(h.rep.to_dict(), order)

    Q, r = sdp_div(H[0], H[1:], lev, order, dom)

    Q = [ Poly(DMP(dict(q), dom, lev), *gens) for q in Q ]
    r =   Poly(DMP(dict(r), dom, lev), *gens)

    if basic:
        return [ q.as_basic() for q in Q ], r.as_basic()
    else:
        return Q, r

def groebner(F, *gens, **args):
    """
    Computes the reduced Groebner basis for a set of polynomials.

    Use the `order` argument to set the monomial ordering used to compute the
    basis.  Allowed orders are `lex`, `grlex`, and `grevlex`.  If no order is
    specified, it defaults to `lex`.

    For more information on Groebner bases, see the references and the docstring
    of `solve_poly_system()`.

    **Example**

    Example taken from [1].

    >>> from sympy import groebner
    >>> from sympy.abc import x, y
    >>> groebner([x*y - 2*y, 2*y**2 - x**2], order='lex')
    [x**2 - 2*y**2, -2*y + x*y, -2*y + y**3]
    >>> groebner([x*y - 2*y, 2*y**2 - x**2], order='grlex')
    [-2*y + y**3, x**2 - 2*y**2, -2*y + x*y]
    >>> groebner([x*y - 2*y, 2*y**2 - x**2], order='grevlex')
    [-2*x**2 + x**3, y**2 - x**2/2, -2*y + x*y]

    **References**

    [1] B. Buchberger, Groebner Bases: A Short Introduction for
        Systems Theorists,  In: R. Moreno-Diaz,  B. Buchberger,
        J.L. Freire, Proceedings of EUROCAST'01, February, 2001

    [2] D. Cox, J. Little, D. O'Shea, Ideals, Varieties and
        Algorithms, Springer, Second Edition, 1997, pp. 112
    """
    if 'modulus' in args:
        raise PolynomialError("can't compute Groebner basis over a finite field")

    order = Poly._analyze_order({'order': args.pop('order', 'lex')})
    monic = args.pop('monic', True)

    basic = _should_return_basic(*F, **args)

    args = _update_args(args, 'field', True)
    gens = _analyze_gens(gens)

    if not F:
        return []

    F = [ Poly(f, *gens, **args) for f in F ]
    dom, gens = F[0].get_domain(), F[0].gens

    for f in F[1:]:
        gens = _unify_gens(gens, f.gens)
        dom = dom.unify(f.get_domain(), gens)

    lev = len(gens) - 1

    for i, f in enumerate(F):
        f = Poly(f, *gens, **{'domain': dom})
        F[i] = sdp_from_dict(f.rep.to_dict(), order)

    G = sdp_groebner(F, lev, order, dom, monic=monic)

    G = [ Poly(DMP(dict(g), dom, lev), *gens) for g in G ]

    if basic:
        return [ g.as_basic() for g in G ]
    else:
        return G

def symmetrize(f, *gens, **args):
    """
    Rewrite a polynomial in terms of elementary symmetric polynomials.

    A symmetric polynomial is a multivariate polynomial that remains invariant
    under any variable permutation, i.e., if `f = f(x_1, x_2, ..., x_n)`, then
    `f = f(x_{i_1}, x_{i_2}, ..., x_{i_n})`, where `(i_1, i_2, ..., i_n)` is a
    permutation of `(1, 2, ..., n)` (an element of the group `S_n`).

    Returns a list of symmetric polynomials `(f1, f2, ..., fn)` such that
    `f = f1 + f2 + ... + fn`.

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
    try:
        f = Poly(f, *_analyze_gens(gens), **args)
    except GeneratorsNeeded:
        if args.get('formal', False):
            return (f, S.Zero, {})
        else:
            return (f, S.Zero)

    from sympy.polys.specialpolys import symmetric_poly

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

    if args.get('formal', False):
        return (Add(*symmetric), f.as_basic(), dict(polys))
    else:
        return (Add(*symmetric).subs(polys), f.as_basic())

def horner(f, *gens, **args):
    """
    Apply Horner's rule to put a polynomial in Horner form.

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
    F = NonStrictPoly(f, *_analyze_gens(gens), **args)

    if not F.is_Poly:
        return F

    form, gen = S.Zero, F.gen

    if F.is_univariate:
        for coeff in F.all_coeffs():
            form = form*gen + coeff
    else:
        F, gens = Poly(F, gen), gens[1:]

        for coeff in F.all_coeffs():
            form = form*gen + horner(coeff, *gens, **args)

    return form

def poly(expr, **args):
    """
    Efficiently transform an expression into a polynomial.

    **Example**

    >>> from sympy import poly
    >>> from sympy.abc import x
    >>> poly((x**2 + x + 1)**3)
    Poly(x**6 + 3*x**5 + 6*x**4 + 7*x**3 + 6*x**2 + 3*x + 1, x, domain='ZZ')
    """
    expr = sympify(expr)

    if expr.is_Poly:
        return expr.reorder(**args)

    terms, poly_terms = [], []

    for term in expr.as_Add():
        factors, poly_factors = [], []

        for factor in term.as_Mul():
            if factor.is_Add:
                poly_factors.append(poly(factor))
            elif factor.is_Pow and factor.base.is_Add and factor.exp.is_Integer:
                poly_factors.append(poly(factor.base).pow(factor.exp))
            else:
                factors.append(factor)

        if not poly_factors:
            terms.append(term)
        else:
            product = poly_factors[0]

            for factor in poly_factors[1:]:
                product = product.mul(factor)

            if factors:
                factor = Mul(*factors)

                if factor.is_Number:
                    product = product.mul(factor)
                else:
                    product = product.mul(Poly(factor, expand=False))

            poly_terms.append(product)

    if not poly_terms:
        result = Poly(expr, expand=False)
    else:
        result = poly_terms[0]

        for term in poly_terms[1:]:
            result = result.add(term)

        if terms:
            term = Add(*terms)

            if term.is_Number:
                result = result.add(term)
            else:
                result = result.add(Poly(term, expand=False))

    return result.reorder(**args)

