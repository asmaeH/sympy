"""
This module contains dsolve() and different helper functions that it uses.

dsolve() solves ordinary differential equations
See the docstring on the various functions for their uses.
"""


def dsolve(eq, funcs):
    """
    Solves any (supported) kind of differential equation.

    Usage

        dsolve(f, y(x)) -> Solve a differential equation f for the function y


    Details

        @param f: ordinary differential equation (either just the left hand
            side, or the Equality class)

        @param y: indeterminate function of one variable

        - You can declare the derivative of an unknown function this way:
        >>> from sympy import *
        >>> x = Symbol('x') # x is the independent variable
        >>> f = Function("f")(x) # f is a function of x
        >>> f_ = Derivative(f, x) # f_ will be the derivative of \
        f with respect to x

        - This function just parses the equation "eq" and determines the type of
        differential equation by its order, then it determines all the
        coefficients and then calls the particular solver, which just accepts
        the coefficients.
        - "eq" can be either an Equality, or just the left hand side (in which
          case the right hand side is assumed to be 0)
        - See test_ode.py for many tests, which serve also as a set of examples
          how to use dsolve
        - dsolve always returns an equality class.  If possible, it solves the
          solution explicitly for the function being solved for. Otherwise, it
          returns an implicit solution.
        - Arbitrary constants are symbols named C1, C2, and so on.

    Examples

        >>> from sympy import *
        >>> x = Symbol('x')

        >>> f = Function('f')
        >>> dsolve(Derivative(f(x),x,x)+9*f(x), f(x))
        f(x) == C1*sin(3*x) + C2*cos(3*x)
        >>> dsolve(Eq(Derivative(f(x),x,x)+9*f(x)+1, 1), f(x))
        f(x) == C1*sin(3*x) + C2*cos(3*x)

    """

    if isinstance(eq, Equality):
        if eq.rhs != 0:
            return dsolve(eq.lhs-eq.rhs, funcs)
        eq = eq.lhs

    #currently only solve for one function
    if isinstance(funcs, Basic) or len(funcs) == 1:
        if isinstance(funcs, (list, tuple)): # normalize args
            f = funcs[0]
        else:
            f = funcs

        if len(f.args) != 1:
            raise NotImplementedError("Only functions of one variable are supported")
        x = f.args[0]
        f = f.func

        # Collect diff(f(x),x) terms so that match will work correctly
        eq = collect(eq, f(x).diff(x))
        #We first get the order of the equation, so that we can choose the
        #corresponding methods. Currently, only first and second
        #order odes can be handled.
        order = deriv_degree(eq, f(x))

        if order > 1:
            return constantsimp(solve_ODE_higher_order(eq, f(x), order), x, 2*order)
        if  order > 2:
           raise NotImplementedError("dsolve: Cannot solve " + str(eq))
        elif order == 2:
            return solve_ODE_second_order(eq, f(x))
        elif order == 1:
           return constantsimp(solve_ODE_first_order(eq, f(x)), x, 1)
        else:
            raise NotImplementedError("Not a differential equation.")

def classify_ode(eq, func, match=False):
    """
    Returns a tuple of possible dsolve() classifications for an ODE.

    The first item in the tuple is the classification that dsolve uses to solve
    the ode by default.  To make dsolve use a different classification, use
    dsolve(ode, func, hint=<classification>).

    == Meta-Hints ==
    Aside from the various methods, there are also some meta-hints that you can
    pass to dsolve():
    "default":
            This uses whatever hint is returned first by classify_ode().
            This is the default argument to dsolve().
    "all":
            To make dsolve apply all relevant classification hints, use
            dsolve(ode, func, hint="all").  This will return a dictionary of
            hint:solution terms.  If a hint causes dsolve to raise an exception,
            value of that hint's key will be the exception object raised.
    "all_Integral":
            This is the same as "all", except if a hint also has a corresponding
            "_Integral" hint, it only returns the "_Integral" hint.  This is
            useful if "all" causes dsolve() to hang because of a difficult
            or impossible integral.  This meta-hint will also be much faster
            than "all", because integrate() is an expensive routine.
    "best":
            To have dsolve() try all methods and return the simplest one, use
            dsolve(ode, func, hint="best").  This takes into account whether
            the solution is solvable in the function, whether it contains any
            Integral classes (i.e. unevaluatable integrals), and which one
            is the shortest in size.
    "_best":
            Hints with coresponding "_alt" classifications will also have a
            "_best" meta-classification.  This will evaluate both hints
            and return the best of the two, using the same considerations as the
            normal "best" meta-hint.

    == Notes on Hint Names ==
    === "_Integral" ===
    If a classification has "_Integral" at the end, it will return the
    expression with an unevaluated Integral class in it.  Note that a hint may
    do this anyway if integrate cannot do the integral.  An Integral hint will
    always be faster than its corresponding hint without Integral because
    integrate() is an expensive routine.  If dsolve() hangs, it is probably
    because integrate() is hanging on a tough or impossible integral.  Try
    using an "_Integral" hint to get it return something.
    Note that some hints do not have "_Integral" counterparts.  This is because
    integrate() is not used in solving the ode.  For example, nth order linear
    homogeneous ODEs with constant coefficients do not require integration to
    solve, so there is no "nth_linear_homogeneous_constant_coeff_Integrate" hint.
    You can easliy evaluate any Integrals in an expression by doing expr.doit().

    === Ordinals ===
    Some hints contain an ordinal such as "1st_linear".  This is to help
    differentiate them from other hints. If a hint has "nth" in it, such as the
    "nth_linear" hints, this means that the method used to applies to any order
    of ODE.

    === "indep" and "dep" ===
    Some hints contain the words "indep" or "dep".  These reference the
    independent variable and the dependent function, respectively. For example,
    if an ODE is in terms of f(x), then "indep" will refer to x and "dep" will
    refer to f.

    === "subs" ===
    If a hints has the word "subs" in it, it means the the ODE is solved by
    substituting the expression given after the word "subs" for a single dummy
    variable.  This is usually in terms of "indep" and "dep" as above.

    == Note ==
    Because all solutions should be mathematically equivalent, some dsolve hints
    may return the exact same result for an ode.  Often, though, two different
    hints will return the same solution formatted differently.  The two should
    be equivalent.

    == Examples ==

    """
    # TODO: Add examples to the docstring

    # A list of hints in the order that they should be applied.  That means
    # that, in general, hints earlier in the list should produce simpler results
    # than those later for odes that fit both.  This is just based on my own
    # empirical observations, so if you find that *in general*, a hint later in
    # the list is better than one before it, fell free to modify the list.  Note
    # however that you can easily override in dsolve for a specific ODE
    # (see the docstring).  In general, "_Integral" hints should be grouped
    # at the end of the list, unless there is a method that returns an unevaluatable
    # integral most of the time (which should surely go near the end of the list
    # anyway).
    # "default", "all", "best", and "all_Integral" meta-hints should not be
    # included in list, but "_best" meta hints should be included.
    allhints = ("separable", "exact", "1st_linear", "Bernoulli",
    "1st_homogeneous_coeff_best", "1st_homogeneous_coeff_subs_indep/dep",
    "1st_homogeneous_coeff_dep/indep", "nth_linear_homogeneous_constant_coeff",
    "nth_linear_constant_coeff_undetermined_coefficients",
    "nth_linear_constant_coeff_variation_of_paramters",
    "Liouville", "seperable_Integral", "exact_Integral", "1st_linear_Integral",
    "Bernoulli_Integral", "1st_homogeneous_coeff_best_Integral",
    "1st_homogeneous_coeff_subs_indep/dep_Integral",
    "1st_homogeneous_coeff_subs_dep/indep_Integral",
    "nth_linear_constant_coeff_variation_of_parameters_Integral",
    "Liouville_Integral")

    x = f.args[0]
    f = f.func
    y = Symbol('y', dummy=True)
    if isinstance(eq, Equality):
        if eq.rhs != 0:
            return dsolve(eq.lhs-eq.rhs, funcs)
        eq = eq.lhs
    # Currently only solve for one function
    if isinstance(funcs, Basic) or len(funcs) == 1:
        if isinstance(funcs, (list, tuple)): # normalize args
            f = funcs[0]
        else:
            f = funcs
        if len(f.args) != 1:
            raise ValueError("dsolve() and classify_ode() only with functions " + \
            "of one variable")
        # Collect diff(f(x),x) terms so that match will work correctly
        eq = collect(eq, f(x).diff(x))
        order = deriv_degree(eq, f(x))

    matching_hints = {} # hint:matchdict or hint:(tuple of matchdicts)
    a = Wild('a', exclude=[f(x)])
    b = Wild('b', exclude=[f(x)])
    c = Wild('c', exclude=[f(x)])
    d = Wild('d', exclude=[f(x).diff(x)])
    e = Wild('e', exclude=[f(x).diff(x)])
    g = Wild('g', exclude=[f(x).diff(x)])
    n = Wild('n', exclude=[f(x)])



    if order == 1:
        # We can save a lot of time by skipping these if the ODE isn't 1st order

        # Linear case: a(x)*y'+b(x)*y+c(x) == 0
        r = eq.match(a*diff(f(x),x) + b*f(x) + c)
        if r:
            matching_hints["1st_linear"] = r
            matching_hints["1st_linear_Integral"] = r

        # Bernoulli case: a(x)*y'+b(x)*y+c(x)*y**n == 0
        r = eq.match(a*diff(f(x),x) + b*f(x) + c*f(x)**n)
        if r:
            matching_hints["Bernioulli"] = r
            matching_hints["Bernioulli_Integral"] = r

        # This match is used for several cases below.
        r = eq.match(d+e*diff(f(x),x))
        if r:
            r[d] = r[d].subs(f(x),y)
            r[e] = r[e].subs(f(x),y)

            # Separable Case: y' == P(y)*Q(x)
            r[d] = separatevars(r[d])
            r[e] = separatevars(r[e])
            # m1[coeff]*m1[x]*m1[y] + m2[coeff]*m2[x]*m2[y]*y'
            m1 = separatevars(r[d], dict=True, symbols=(x, y))
            m2 = separatevars(r[e], dict=True, symbols=(x, y))
            if m1 and m2:
                matching_hints["seperable"] = (m1, m2)
                matching_hints["seperable_Integral"] = (m1, m2)

            # Exact Differential Equation: P(x,y)+Q(x,y)*y'=0 where dP/dy == dQ/dx
            if simplify(r[d].diff(y)) == simplify(r[e].diff(x)) and r[d] != 0:
                matching_hints["exact"] = r
                matching_hints["exact_Integral"] = r

            # First order equation with homogeneous coefficients:
            # dy/dx == F(y/x) or dy/dx == F(x/y)
            ordera = homogeneous_order(r[d], x, y)
            orderb = homogeneous_order(r[e], x, y)
            if ordera == orderb and ordera != None:
                matching_hints["1st_homogeneous_coeff_best"] = r
                matching_hints["1st_homogeneous_coeff_subs_indep/dep"] = r
                matching_hints["1st_homogeneous_coeff_dep/indep"] = r
                matching_hints["1st_homogeneous_coeff_best_Integral"] = r
                matching_hints["1st_homogeneous_coeff_subs_indep/dep_Integral"] = r
                matching_hints["1st_homogeneous_coeff_dep/indep_Integral"] = r

    # nth order linear ODE
    # a_n(x)y^(n) + ... + a_1(x)y' + a_0(x)y = F(x)
    j = 0
    s = S(0)
    wilds = []
    # Build a match expression for a nth order linear ode
    for i in numbered_symbols(prefix='a', function=Wild, exclude=[f(x)]):
        if j == order+1:
            break
        wilds.append(i)
        s += i*f(x).diff(x,j)
        j += 1
    s += b

    r = eq.match(s)
    if r and all([not r[i].has(x) for i in wilds]):
        # Inhomogeneous case: F(x) is not identically 0
        if r[b]:
            matching_hints["nth_linear_constant_coeff_undetermined_coefficients"] = r
            matching_hints["nth_linear_constant_coeff_variation_of_paramters"] = r
            matching_hints["nth_linear_constant_coeff_variation_of_paramters_Integral"] = r
        # Homogeneous case: F(x) is identically 0
        else:
            matching_hints["nth_linear_homogeneous_constant_coeff"] = r

    s = d*f(x).diff(x, 2) + e*f(x).diff(x)**2 + g*f(x).diff(x)
    r = eq.match(s)
    if r:
        matching_hints["Liouville"] = r
        matching_hints["Liouville_Integral"] = r




@vectorize(0)
def constantsimp(expr, independentsymbol, endnumber, startnumber=1,
    symbolname='C'):
    """
    Simplifies an expression with arbitrary constants in it.

    This function is written specifically to work with dsolve(), and is not
    indented for general use.

    This is done by "absorbing" the arbitrary constants in to other arbitrary
    constants, numbers, and symbols for which they are not independent of.

    The symbols must all have the same name with numbers after it, for example,
    C1, C2, C3.  The symbolname here would be 'C', the startnumber would be 1,
    and the end number would be 3.  If the arbitrary constants are independent
    of the variable x, then the independentsymbol would be x.

    Because terms are "absorbed" into arbitrary constants and because constants
    are renumbered after simplifying, the arbitrary constants in expr are not
    necessarily equal to the ones of the same name in the returned result.

    If two or more arbitrary constants are added, multiplied, or raised to the
    power of each other, they are first absorbed together into a single
    arbitrary constant.  Then the new constant is combined into other terms
    if necessary.

    Absorption is done naively.  constantsimp() does not attempt to expand
    or simplify the expression first to obtain better absorption.

    Constants are renumbered after simplification so that they are sequential,
    such as C1, C2, C3, and so on.

    Example:
    >>> from sympy import *
    >>> C1, C2, C3, x, y = symbols('C1 C2 C3 x y')
    >>> constantsimp(2*C1*x, x, 3)
    C1*x
    >>> constantsimp(C1 + 2 + x + y, x, 3)
    C1 + x
    >>> constantsimp(C1*C2 + 2 + x + y + C3*x, x, 3)
    C1 + x + C2*x
    """
    # We need to have an internal recursive function so that newstartnumber
    # maintains its values throughout recursive calls

    global newstartnumber
    newstartnumber = 1

    def _constantsimp(expr, independentsymbol, endnumber, startnumber=1,
    symbolname='C'):
        """
        The function works recursively.  The idea is that, for Mul, Add, Pow, and
        Function, if the class has a constant in it, then we can simplify it,
        which we do by recursing down and simplifying up.  Otherwise, we can skip
        that part of the expression.
        """
        constantsymbols = [Symbol(symbolname+"%d" % t) for t in range(startnumber,
        endnumber + 1)]
        x = independentsymbol

        if isinstance(expr, Equality):
            return Equality(_constantsimp(expr.lhs, x, endnumber, startnumber,
                symbolname), _constantsimp(expr.rhs, x, endnumber, startnumber,
                symbolname))

        if type(expr) not in (Mul, Add, Pow) and not expr.is_Function:
            # We don't know how to handle other classes
            # This also serves as the base case for the recursion
            return expr
        elif not any(t in expr for t in constantsymbols):
            return expr
        else:
            newargs = []
            hasconst = False
            isPowExp = False
            reeval = False
            for i in expr.args:
                if i not in constantsymbols:
                    newargs.append(i)
                else:
                    newconst = i
                    hasconst = True
                    if expr.is_Pow and i == expr.exp:
                        isPowExp = True

            for i in range(len(newargs)):
                isimp = _constantsimp(newargs[i], x, endnumber, startnumber,
                symbolname)
                if isimp in constantsymbols:
                    reeval = True
                    hasconst = True
                    newconst = isimp
                    if expr.is_Pow and i == 1:
                        isPowExp = True
                newargs[i] = isimp
            if hasconst:
                newargs = [i for i in newargs if i.has(x)]
                if isPowExp:
                    newargs = newargs + [newconst] # Order matters in this case
                else:
                    newargs = [newconst] + newargs
            if expr.is_Pow and len(newargs) == 1:
                newargs.append(S.One)
            if expr.is_Function:
                if (len(newargs) == 0 or hasconst and len(newargs) == 1):
                    return newconst
                else:
                    newfuncargs = [_constantsimp(t, x, endnumber, startnumber,
                    symbolname) for t in expr.args]
                    return expr.new(*newfuncargs)
            else:
                newexpr = expr.new(*newargs)
                if reeval:
                    return _constantsimp(newexpr, x, endnumber, startnumber,
                    symbolname)
                else:
                    return newexpr

    def _renumber(expr, symbolname, startnumber, endnumber):
        """
        Renumber arbitrary constants in expr.

        This is a simple function that goes through and renumbers any Symbol
        with a name in the form symbolname + num where num is in the range
        from startnumber to endnumber.

        Symbols are renumbered in the order that they are encountered via
        a depth first search through args, so they should be numbered roughly
        in the order that they appear in the final, printed expression.

        The structure of the function is very similar to _constantsimp().
        """
        constantsymbols = [Symbol(symbolname+"%d" % t) for t in range(startnumber,
        endnumber + 1)]
        global newstartnumber

        if isinstance(expr, Equality):
            return Equality(_renumber(expr.lhs, symbolname, startnumber, endnumber),
            _renumber(expr.rhs, symbolname, startnumber, endnumber))

        if type(expr) not in (Mul, Add, Pow) and not expr.is_Function and\
        not any(t in expr for t in constantsymbols):
            # Base case, as above.  We better hope there aren't constants inside
            # of some other class, because they won't be simplified.
            return expr
        elif expr in constantsymbols:
            # Renumbering happens here
            newconst = Symbol(symbolname + str(newstartnumber))
            newstartnumber += 1
            return newconst
        else:
            sortedargs = list(expr.args)
            sortedargs.sort(Basic._compare_pretty)
            if expr.is_Function or expr.is_Pow:
                return expr.new(*map(lambda x: _renumber(x, symbolname, \
                startnumber, endnumber), expr.args))
            else:
                return expr.new(*map(lambda x: _renumber(x, symbolname, \
                startnumber, endnumber), sortedargs))


    simpexpr = _constantsimp(expr, independentsymbol, endnumber, startnumber,
    symbolname)

    return _renumber(simpexpr, symbolname, startnumber, endnumber)



def deriv_degree(expr, func):
    """ get the order of a given ode, the function is implemented
    recursively """
    a = Wild('a', exclude=[func])

    order = 0
    if isinstance(expr, Derivative):
        order = len(expr.symbols)
    else:
        for arg in expr.args:
            if isinstance(arg, Derivative):
                order = max(order, len(arg.symbols))
            elif expr.match(a):
                order = 0
            else :
                for arg1 in arg.args:
                    order = max(order, deriv_degree(arg1, func))

    return order

def solve_ODE_first_order(eq, f):
    """
    Solves many kinds of first order odes.
    Different methods are used depending on the form of the given equation.
    Now the linear, Bernoulli, exact, and first order homogeneous cases are
    implemented.
    """
    from sympy.integrals.integrals import integrate
    x = f.args[0]
    f = f.func
    C1 = Symbol('C1')

    # Linear case: a(x)*y'+b(x)*y+c(x) == 0
    a = Wild('a', exclude=[f(x)])
    b = Wild('b', exclude=[f(x)])
    c = Wild('c', exclude=[f(x)])

    r = eq.match(a*diff(f(x),x) + b*f(x) + c)
    if r:
        t = exp(integrate(r[b]/r[a], x))
        tt = integrate(t*(-r[c]/r[a]), x)
        return Equality(f(x),(tt + C1)/t)

    # Bernoulli case: a(x)*y'+b(x)*y+c(x)*y**n == 0
    n = Wild('n', exclude=[f(x)])

    r = eq.match(a*diff(f(x),x) + b*f(x) + c*f(x)**n)

    if r:
        if r[n] != 1:
            t = C.exp((1-r[n])*integrate(r[b]/r[a],x))
            tt = (r[n]-1)*integrate(t*r[c]/r[a],x)
            return Equality(f(x),((tt + C1)/t)**(1/(1-r[n])))
        #if r[n] == 1:
         #   return Equality(f(x),C1*exp(integrate(-(r[b]+r[c]), x)))

    a = Wild('a', exclude=[f(x).diff(x)])
    b = Wild('b', exclude=[f(x).diff(x)])
    r = eq.match(a+b*diff(f(x),x))
    # This match is used for several cases below.
    if r:
        y = Symbol('y', dummy=True)
        r[a] = r[a].subs(f(x),y)
        r[b] = r[b].subs(f(x),y)

        # Separable Case: y' == P(y)*Q(x)
        r[a] = separatevars(r[a])
        r[b] = separatevars(r[b])
        # m1[coeff]*m1[x]*m1[y] + m2[coeff]*m2[x]*m2[y]*y'
        m1 = separatevars(r[a], dict=True, symbols=(x, y))
        m2 = separatevars(r[b], dict=True, symbols=(x, y))

        if m1 and m2:
            return Equality(integrate(m2['coeff']*m2[y]/m1[y], y).subs(y, f(x)),\
            integrate(-m1['coeff']*m1[x]/m2[x], x)+C1)
        # Exact Differential Equation: P(x,y)+Q(x,y)*y'=0 where dP/dy == dQ/dx
        if simplify(r[a].diff(y)) == simplify(r[b].diff(x)) and r[a]!=0:
            x0 = Symbol('x0', dummy=True)
            y0 = Symbol('y0', dummy=True)
            tmpsol = integrate(r[b].subs(x,x0),(y,y0,y))+integrate(r[a],(x,x0,x))
            sol = 0
            assert tmpsol.is_Add
            for i in tmpsol.args:
                if x0 not in i and y0 not in i:
                    sol += i
            assert sol != 0
            sol = Equality(sol,C1)

            try:
                # See if the equation can be solved explicitly for f
                # This part of the code will change when solve returns RootOf.
                sol1 = solve(sol,y)
            except NotImplementedError:
                return sol.subs(y,f(x))
            else:
                if len(sol1) !=1:
                    return sol.subs(y,f(x))
                else:
                    return Equality(f(x),sol1[0].subs(y,f(x)))

        # First order equation with homogeneous coefficients:
        # dy/dx == F(y/x) or dy/dx == F(x/y)
        ordera = homogeneous_order(r[a], x, y)
        orderb = homogeneous_order(r[b], x, y)
        if ordera == orderb and ordera != None:
            # There are two substitutions that solve the equation, u=x/y and u=y/x
            # They produce different integrals, so try them both and see which
            # one is easier.
            u1 = Symbol('u1', dummy=True) # u1 == y/x
            u2 = Symbol('u2', dummy=True) # u2 == x/y
            _a = Symbol('_a', dummy=True)
            #print ((-r[b]/(r[a]+u1*r[b])).subs({x:1, y:u1}),
            #print (-r[a]/(r[b]+u2*r[a])).subs({x:u2, y:1}))
            int1 = integrate((-r[b]/(r[a]+u1*r[b])).subs({x:1, y:u1}), u1)
            int2 = integrate((-r[a]/(r[b]+u2*r[a])).subs({x:u2, y:1}), u2)
            # Substitute back in for u1 and u2.
            if int1.has(C.Integral):
                int1 = C.Integral(int1.args[0],(u1,_a,f(x)/x))
            else:
                int1 = int1.subs(u1,f(x)/x)
            if int2.has(C.Integral):
                int2 = C.Integral(int2.args[0],(u2,_a,x/f(x)))
            else:
                int2 = int2.subs(u2,x/f(x))
            sol1 = logcombine(Equality(log(x), int1 + log(C1)), assume_pos_real=True)
            sol2 = logcombine(Equality(log(f(x)), int2 + log(C1)), assume_pos_real=True)
            if sol1.lhs.is_Function and sol1.lhs.func == log and sol1.rhs == 0:
                sol1 = Equality(sol1.lhs.args[0]*C1,C1)
            if sol2.lhs.is_Function and sol2.lhs.func == log and sol2.rhs == 0:
                sol2 = Equality(sol2.lhs.args[0]*C1,C1)

            # There are two solutions.  We need to determine which one to use
            # First, if they are the same, don't bother testing which one to use
            if sol1 == sol2:
                # But still try to solve for f
                try:
                    sol1s = map((lambda t: t.subs(y, f(x))),\
                    solve(sol1.lhs.subs(f(x),y)-sol1.rhs.subs(f(x),y), y))
                    if sol1s == []:
                        raise NotImplementedError
                except NotImplementedError:
                    return sol1
                else:
                    sol1sr = map((lambda t: Equality(f(x), t.subs({u1:f(x)/x,\
                    y:f(x)}))), sol1s)
                    if len(sol1sr) == 1:
                        return logcombine(sol1sr[0], assume_pos_real=True)
                    else:
                        return [logcombine(t, assume_pos_real=True) for t in sol1sr]
            # Second, try to return an evaluated integral:
            if sol1.has(C.Integral):
                return sol2
            if sol2.has(C.Integral):
                return sol1
            # Next, try to return an explicit solution.  This code will change
            # when RootOf is implemented in solve().
            try:
                sol1s = map((lambda t: t.subs(y, f(x))),\
                solve(sol1.lhs.subs(f(x),y)-sol1.rhs.subs(f(x),y), y))
                if sol1s == []:
                    raise NotImplementedError
            except NotImplementedError:
                pass
            else:
                sol1sr = map((lambda t: Equality(f(x), t.subs({u1:f(x)/x,\
                y:f(x)}))), sol1s)
                if len(sol1sr) == 1:
                    return logcombine(sol1sr[0], assume_pos_real=True)
                else:
                    return [logcombine(t, assume_pos_real=True) for t in sol1sr]
            try:
                sol2s = map((lambda t: t.subs(y, f(x))),\
                solve(sol2.lhs.subs(f(x),y)-sol2.rhs.subs(f(x),y), y))
                if sol2s == []:
                    raise NotImplementedError
            except NotImplementedError:
                pass
            else:
                sol2sr = map((lambda t: Equality(f(x), t.subs({u2:x/f(x),\
                y:f(x)}))), sol2s)
                if len(sol2sr) == 1:
                    return logcombine(sol2sr[0], assume_pos_real=True)
                else:
                    return [logcombine(t, assume_pos_real=True) for t in sol2srs]

            # Finally, try to return the shortest expression, naively computed
            # based on the length of the string version of the expression.  This
            # may favor combined fractions because they will not have duplicate
            # denominators, and may slightly favor expressions with fewer
            # additions and subtractions, as those are separated by spaces by
            # the printer.
            return min(sol1, sol2, key=(lambda x: len(str(x))))

    # Other cases of first order odes will be implemented here

    raise NotImplementedError("solve_ODE_first_order: Cannot solve " + str(eq))

def solve_ODE_higher_order(eq, f, order):
    from sympy.integrals.integrals import integrate
    x = f.args[0]
    f = f.func
    b = Wild('b', exclude=[f(x)])
    j = 0
    s = S(0)
    wilds = []
    constants = numbered_symbols(prefix='C', function=Symbol, start=1)
    # Build a match expression for a homogeneous nth order ode
    for i in numbered_symbols(prefix='a', function=Wild, exclude=[f(x)]):
        if j == order+1:
            break
        wilds.append(i)
        s += i*f(x).diff(x,j)
        j += 1
    s += b

    r = eq.match(s)
    if r:
        # The ODE is linear
        if all([not r[i].has(x) for i in wilds]):
            # First, set up characteristic equation.
            m = Symbol('m', dummy=True)
            chareq = S(0)
            for i in r:
                if i == b:
                    pass
                else:
                    chareq += r[i]*m**S(i.name[1:])
            chareqroots = RootsOf(chareq, m)
            charroots_exact = list(chareqroots.exact_roots())
            charroots_formal = list(chareqroots.formal_roots())
            if charroots_formal and discriminant(chareq, m) == 0:
                # If Poly cannot find the roots explicitly, we can only return
                # an expression in terms of RootOf's if we know the roots
                # are not repeated.  We use the fact that a polynomial has
                # repeated roots iff its discriminant == 0.

                # TODO: cancel out roots from charroots_exact, then check
                # the discriminant of chareq.
                raise NotImplementedError("Cannot find all of the roots of " + \
                "characteristic equation " + str(chareq) + ", which has " + \
                "repeated roots.")
            # Create a dict root: multiplicity or charroots
            charroots = {}
            for i in charroots_exact + charroots_formal:
                if i in charroots:
                    charroots[i] += 1
                else:
                    charroots[i] = 1
            gsol = S(0)
            psol = S(0)
            # We need keep track of terms so we can run collect() at the end.
            # This is necessary for constantsimp to work properly.
            collectterms = []
            for root, multiplicity in charroots.items():
                for i in range(multiplicity):
                    if isinstance(root, RootOf):
                        # re and im do not work with RootOf, so the work around is
                        # to put solution in non (complex) expanded form.
                        # See issue 1563.
                        gsol += exp(root*x)*constants.next()
                        assert multiplicity == 1
                    else:
                        reroot = re(root)
                        imroot = im(root)
                        gsol += x**i*exp(reroot*x)*(constants.next()*sin(abs(imroot)*x) \
                        + constants.next()*cos(imroot*x))
                        collectterms = [(i, reroot, imroot)] + collectterms
            gsol = expand_mul(gsol, deep=False)
            for i, reroot, imroot in collectterms:
                gsol = collect(gsol, x**i*exp(reroot*x)*sin(abs(imroot)*x))
                gsol = collect(gsol, x**i*exp(reroot*x)*cos(imroot*x))
            for i, reroot, imroot in collectterms:
                gsol = collect(gsol, x**i*exp(reroot*x))
            if r[b] != 0:
                # Variation of Paramters
                gensols = []
                # Keep track of when to use sin or cos for nonzero imroot
                trigdict = {}
                if len(collectterms) != order:
                    raise NotImplementedError("Cannot find " + str(order) + \
                    " solutions to homogeneous equation to apply variation " + \
                    "of parameters to " + str(eq))
                for i, reroot, imroot in collectterms:
                    if imroot == 0:
                        gensols.append(x**i*exp(reroot*x))
                    else:
                        if x**i*exp(reroot*x)*sin(abs(imroot)*x) in gensols:
                            gensols.append(x**i*exp(reroot)*cos(imroot*x))
                        else:
                            gensols.append(x**i*exp(reroot*x)*sin(abs(imroot)*x))
                wr = wronskian(gensols, x)
                wr = trigsimp(wr) # to reduce sin(x)**2 + cos(x)**2 to 1
                if not wr:
                    raise NotImplementedError("Cannot find " + str(order) + \
                    " solutions to the homogeneous equation nessesary to apply " + \
                    "variation of parameters to " + str(eq) + " (Wronskian == 0)")
                negoneterm = (-1)**(order)
                for i in gensols:
                    psol += negoneterm*integrate(wronskian(filter(lambda x: x != i, \
                    gensols), x)*r[b]/wr, x)*i/r[wilds[-1]]
                    negoneterm *= -1
            psol = simplify(psol)
            psol = trigsimp(psol, deep=True)
            return Equality(f(x), gsol + psol)


    # Liouville ODE f(x).diff(x, 2) + g(f(x))*(f(x).diff(x, 2))**2 + h(x)*f(x).diff(x)
    # See Goldstein and Braun, "Advanced Methods for the Solution of
    # Differential Equations", pg. 98
    a = Wild('a', exclude=[f(x).diff(x)])
    b = Wild('b', exclude=[f(x).diff(x)])
    c = Wild('c', exclude=[f(x).diff(x)])
    y = Symbol('y', dummy=True)
    C1 = Symbol('C1')
    C2 = Symbol('C2')
    s = a*f(x).diff(x, 2) + b*f(x).diff(x)**2 + c*f(x).diff(x)
    r = eq.match(s)
    if r:
        g = simplify(r[b]/r[a]).subs(f(x), y)
        h = simplify(r[c]/r[a])
        if h.has(f(x)) or g.has(x):
            pass
        else:
            int1 = integrate(exp(integrate(g, y)), y)
            if isinstance(int1, C.Integral):
                # integral cannot be solved, set f(x) as upper limit
                a = Symbol('_a', dummy=True)
                int1 = C.Integral(int1.function, (y, a, f(x)))
                # We already know that we cannot solve for f
                return Equality(int1 + C1*integrate(exp(-integrate(h, x)), x) + C2, 0)
            else:
                int1 = int1.subs(y, f(x))
            # Try solving for f
            try:
                sol = solve(Equality(int1 + C1*integrate(exp(-integrate(h, x)), x) + \
                C2, 0), f(x))
                if sol == []:
                    raise NotImplementedError
            except NotImplementedError:
                return Equality(int1 + C1*integrate(exp(-integrate(h, x)), x) + C2, 0)
            else:
                sol = map(lambda t: Equality(f(x), t), sol)
                if len(sol) == 1:
                    return sol[0]
                else:
                    return sol
    # special equations, that we know how to solve
    a = Wild('a')
    t = x*exp(f(x))
    tt = a*t.diff(x, x)/t
    r = eq.match(tt.expand())
    if r:
        return Equality(f(x),log(constants.next()+constants.next()/x))

    t = x*exp(-f(x))
    tt = a*t.diff(x, x)/t
    r = eq.match(tt.expand())
    if r:
        #check, that we've rewritten the equation correctly:
        #assert ( r[a]*t.diff(x,2)/t ) == eq.subs(f, t)
        return Equality(f(x),-log(constants.next()+constants.next()/x))

    neq = eq*exp(f(x))/exp(-f(x))
    r = neq.match(tt.expand())
    if r:
        #check, that we've rewritten the equation correctly:
        #assert ( t.diff(x,2)*r[a]/t ).expand() == eq
        return Equality(f(x),-log(constants.next()+constants.next()/x))


    raise NotImplementedError("solve_ODE_higher_order: Cannot solve " + str(eq)) # Yet!



def solve_ODE_second_order(eq, f):
    """
    solves many kinds of second order odes, different methods are used
    depending on the form of the given equation. So far the constants
    coefficients case and a special case are implemented.
    """
    x = f.args[0]
    f = f.func
    C1 = Symbol('C1')
    C2 = Symbol('C2')

    #constant coefficients case: af''(x)+bf'(x)+cf(x)=0
    a = Wild('a', exclude=[x])
    b = Wild('b', exclude=[x])
    c = Wild('c', exclude=[x])

    r = eq.match(a*f(x).diff(x,x) + c*f(x))
    if r:
        return Equality(f(x),C1*C.sin(sqrt(r[c]/r[a])*x)+C2*C.cos(sqrt(r[c]/r[a])*x))

    r = eq.match(a*f(x).diff(x,x) + b*diff(f(x),x) + c*f(x))
    if r:
        r1 = solve(r[a]*x**2 + r[b]*x + r[c], x)
        if r1[0].is_real:
            if len(r1) == 1:
                return Equality(f(x),(C1 + C2*x)*exp(r1[0]*x))
            else:
                return Equality(f(x),C1*exp(r1[0]*x) + C2*exp(r1[1]*x))
        else:
            r2 = abs((r1[0] - r1[1])/(2*S.ImaginaryUnit))
            return Equality(f(x),(C2*C.cos(r2*x) + C1*C.sin(r2*x))*exp((r1[0] + r1[1])*x/2))

    #other cases of the second order odes will be implemented here



def homogeneous_order(eq, *symbols):
    """
    Determines if a function is homogeneous and if so of what order.
    A function f(x,y,...) is homogeneous of order n if
    f(t*x,t*y,t*...) == t**n*f(x,y,...).  It is implemented recursively.

    Functions can be symbols, but every argument of the function must also be
    a symbol, and the arguments of the function that appear in the expression
    must match those given in the list of symbols.  If a declared function
    appears with different arguments than given in the list of symbols, None is
    returned.
    Example:
    >>> from sympy import *
    >>> from sympy.solvers.solvers import homogeneous_order
    >>> x = Symbol('x')
    >>> y = Symbol('y')
    >>> f = Function('f')
    >>> homogeneous_order(f(x), f(x)) == None
    True
    >>> homogeneous_order(f(x,y), f(y, x), x, y) == None
    True
    >>> homogeneous_order(f(x), f(x), x)
    1

    Returns the order n if g is homogeneous and None if it is not homogeneous.
    Examples:
    >>> homogeneous_order(x**2*f(x)/sqrt(x**2+f(x)**2), x, f(x))
    2
    >>> homogeneous_order(x**2+f(x), x, f(x)) == None
    True
    """
    if eq.has(log):
        eq = logcombine(eq, assume_pos_real=True)
    # This runs as a separate function call so that logcombine doesn't endlessly
    # put back together what homogeneous_order is trying to take apart.
    return _homogeneous_order(eq, *symbols)

def _homogeneous_order(eq, *symbols):

    if not symbols:
        raise ValueError, "homogeneous_order: no symbols were given."

    n = set()

    # Replace all functions with dummy variables

    if any(getattr(i, 'is_Function') for i in symbols):
        for i in symbols:
            if i.is_Function:
                if not all(map((lambda i: i in symbols), i.args)):
                    return None
                elif i not in symbols:
                    pass
                else:
                    dummyvar = numbered_symbols(prefix='d', dummy=True).next()
                    eq = eq.subs(i, dummyvar)
                    symbols = list(symbols)
                    symbols.remove(i)
                    symbols.append(dummyvar)
                    symbols = tuple(symbols)

    # The following are not supported
    if eq.is_Order or eq.is_Derivative:
        return None

    # These are all constants
    if type(eq) in (int, float) or eq.is_Number or eq.is_Integer or \
    eq.is_Rational or eq.is_NumberSymbol or eq.is_Real:
        return sympify(0)

    # Break the equation into additive parts
    if eq.is_Add:
        s = set()
        for i in eq.args:
            s.add(_homogeneous_order(i, *symbols))
        if len(s) != 1:
            return None
        else:
            n = s

    if eq.is_Pow:
        if not eq.args[1].is_Number:
            return None
        o = _homogeneous_order(eq.args[0], *symbols)
        if o == None:
            return None
        else:
            n.add(sympify(o*eq.args[1]))

    t = Symbol('t', dummy=True, positive=True) # It is sufficient that t > 0
    r = Wild('r', exclude=[t])
    a = Wild('a', exclude=[t])
    eqs = eq.subs(dict(zip(symbols,(t*i for i in symbols))))

    if eqs.is_Mul:
        if t not in eqs:
            n.add(sympify(0))
        else:
            m = eqs.match(r*t**a)
            if m:
                n.add(sympify(m[a]))
            else:
                s = 0
                for i in eq.args:
                    o = _homogeneous_order(i, *symbols)
                    if o == None:
                        return None
                    else:
                        s += o
                n.add(sympify(s))

    if eq.is_Function:
        if eq.func == log:
            # The only possibility to pull a t out of a function is a power in
            # a logarithm.  This is very likely due to calling of logcombine().
            if eq.args[0].is_Pow:
                return _homogeneous_order(eq.args[0].args[1]*log(eq.args[0].args[0]), *symbols)
            elif eq.args[0].is_Mul and all(i.is_Pow for i in iter(eq.args[0].args)):
                arg = 1
                pows = set()
                for i in eq.args[0].args:
                    if i.args[1].args[0] == -1:
                        arg *= 1/i.args[0]
                        pows.add(sympify(-1*i.args[1]))
                    else:
                        arg *= i.args[0]
                        pows.add(sympify(i.args[1]))
                if len(pows) != 1:
                    return None
                else:
                    return _homogeneous_order(pows.pop()*log(arg), *symbols)
            else:
                if _homogeneous_order(eq.args[0], *symbols) == 0:
                    return sympify(0)
                else:
                    return None
        else:
            if _homogeneous_order(eq.args[0], *symbols) == 0:
                return sympify(0)
            else:
                return None

    if len(n) != 1 or n == None:
        return None
    else:
        return n.pop()

    return None