# -*- coding: utf-8 -*-

""" Gates in a :class:`discopy.quantum.circuit.Circuit`. """

from collections.abc import Callable
import numpy

from discopy import messages
from discopy.cat import AxiomError, rsubs
from discopy.tensor import array2string, Dim, Tensor
from discopy.quantum.circuit import Digit, Ty, bit, qubit, Box, Swap, Sum, Id
from discopy.quantum.circuit import Qudit, qudit


def _get_qudit(obj):
    if hasattr(obj, 'objects'):
        obj = obj.objects
        if len(obj) != 1:
            raise ValueError()  # TODO Error spec
        obj = obj[0]
    if not isinstance(obj, Qudit):
        raise TypeError(messages.type_err(Qudit, obj))
    return obj


def _get_qudit_dims(obj):
    if hasattr(obj, 'objects'):
        if not all(map(lambda v: isinstance(v, Qudit), obj.objects)):
            raise TypeError(messages.type_err(Qudit, None))
        return tuple(map(lambda v: v.dim, obj.objects))
    raise TypeError(messages.type_err(type(qudit(2)), obj))


def _gbox_type(t, *, exp_size=None, min_dim=2):
    np = numpy
    n = 1 if not exp_size else exp_size
    t = qudit(t) ** n if isinstance(t, int) else t
    t = Ty(t) if isinstance(t, Qudit) else t
    _get_qudit_dims(t)
    if exp_size and len(t) != exp_size:
        raise ValueError(f'Expected {exp_size} qudits in {t}, found {len(t)}')
    if min_dim and np.any(np.array(list(map(lambda obj: obj.dim, t))) < min_dim):
        raise ValueError(f'Dimension less than the expected {min_dim}')
    return t


def format_number(data):
    """ Tries to format a number. """
    try:
        return '{:.3g}'.format(data)
    except TypeError:
        return data


class QuantumGate(Box):
    """ Quantum gates, i.e. unitaries on n qubits. """
    def __init__(self, name, n_qubits, array=None, data=None, _dagger=False):
        dom = qubit ** n_qubits
        if array is not None:
            self._array = Tensor.np.array(array).reshape(
                2 * n_qubits * (2, ) or (1, ))
        super().__init__(
            name, dom, dom, is_mixed=False, data=data, _dagger=_dagger)

    @property
    def array(self):
        """ The array of a quantum gate. """
        return self._array

    def __repr__(self):
        if self in GATES:
            return self.name
        return "QuantumGate({}, n_qubits={}, array={})".format(
            repr(self.name), len(self.dom),
            array2string(self.array.flatten()))

    def dagger(self):
        return QuantumGate(
            self.name, len(self.dom), self.array,
            _dagger=None if self._dagger is None else not self._dagger)


def _gate_pow(gate, times, period=None):
    """
    Helper for gate's __pow__.

    Parameters
    ----------
    gate : (Generalised)QuantumGate.
    period : int or None
        When not None, the minimum integer k such that
        U^k=I, that is the gate is involutory and k is the
        minimum exponent that produces the identity.

    """
    if not isinstance(times, int):
        raise TypeError(messages.type_err(int, times))
    dg, times = times < 0, abs(times)
    if period:
        period = int(period)
        assert period > 0
        times = times % period
        if period - times < times:
            dg = not dg
            times = period - times
    result = gate.id(gate.dom)
    for _ in range(times):
        result = result >> gate
    return result.dagger() if dg else result


class GeneralizedQuantumGate(Box):
    def __init__(self, name, dom, array=None, data=None, _dagger=False):
        if array is not None:
            shape = _get_qudit_dims(dom)
            self._array = Tensor.np.array(array).reshape(shape*2)
        super().__init__(
            name, dom, dom, is_mixed=False, data=data, _dagger=_dagger)

    @property
    def array(self):
        """ The array of a quantum gate. """
        return self._array

    def __repr__(self):
        if self in GATES:
            return self.name
        return "GeneralizedQuantumGate({}, dom={}, array={})".format(
            repr(self.name), repr(self.dom),
            array2string(self.array.flatten()))

    def dagger(self):
        return GeneralizedQuantumGate(
            self.name, dom=self.dom, array=self.array,
            _dagger=None if self._dagger is None else not self._dagger)

    def __pow__(self, times):
        return _gate_pow(self, times)


class ClassicalGate(Box):
    """
    Classical gates, i.e. from digits to digits.

    >>> from sympy import symbols
    >>> array = symbols("a b c d")
    >>> f = ClassicalGate('f', 1, 1, array)
    >>> f
    ClassicalGate('f', bit, bit, data=[a, b, c, d])
    >>> f.lambdify(*array)(1, 2, 3, 4)
    ClassicalGate('f', bit, bit, data=[1, 2, 3, 4])
    """
    def __init__(self, name, dom, cod, data=None, _dagger=False):
        if isinstance(dom, int):
            dom = bit ** dom
        if isinstance(cod, int):
            cod = bit ** cod
        if data is not None:
            data = Tensor.np.array(data).reshape(
                (len(dom) + len(cod)) * (2, ) or (1, ))
        super().__init__(
            name, dom, cod, is_mixed=False, data=data, _dagger=_dagger)

    @property
    def array(self):
        """ The array of a classical gate. """
        return self.data

    def __eq__(self, other):
        if not isinstance(other, ClassicalGate):
            return super().__eq__(other)
        return (self.name, self.dom, self.cod)\
            == (other.name, other.dom, other.cod)\
            and Tensor.np.all(self.array == other.array)

    def __repr__(self):
        if self.is_dagger:
            return repr(self.dagger()) + ".dagger()"
        data = array2string(self.array.flatten())
        return "ClassicalGate({}, {}, {}, data={})"\
            .format(repr(self.name), self.dom, self.cod, data)

    def dagger(self):
        _dagger = None if self._dagger is None else not self._dagger
        return ClassicalGate(
            self.name, self.cod, self.dom, self.array, _dagger)

    def subs(self, *args):
        data = rsubs(list(self.data.flatten()), *args)
        return ClassicalGate(self.name, self.dom, self.cod, data)

    def lambdify(self, *symbols, **kwargs):
        from sympy import lambdify
        data = lambdify(symbols, self.data, dict(kwargs, modules=Tensor.np))
        return lambda *xs: ClassicalGate(
            self.name, self.dom, self.cod, data(*xs))

    def grad(self, var, **params):
        if var not in self.free_symbols:
            return Sum([], self.dom, self.cod)
        name = "{}.grad({})".format(self.name, var)
        data = self.eval().grad(var, **params).array
        return ClassicalGate(name, self.dom, self.cod, data)


class Copy(ClassicalGate):
    """ Takes a bit, returns two copies of it. """
    def __init__(self):
        super().__init__("Copy", 1, 2, [1, 0, 0, 0, 0, 0, 0, 1])
        self.draw_as_spider, self.color = True, "black"
        self.drawing_name = ""

    def dagger(self):
        return Match()


class Match(ClassicalGate):
    """ Takes two bits in, returns them if they are equal. """
    def __init__(self):
        super().__init__("Match", 2, 1, [1, 0, 0, 0, 0, 0, 0, 1])
        self.draw_as_spider, self.color = True, "black"
        self.drawing_name = ""

    def dagger(self):
        return Copy()


class Digits(ClassicalGate):
    """
    Classical state for a given string of digits of a given dimension.

    Examples
    --------
    >>> assert Bits(1, 0) == Digits(1, 0, dim=2)
    >>> assert Digits(2, dim=4).eval()\\
    ...     == Tensor(dom=Dim(1), cod=Dim(4), array=[0, 0, 1, 0])
    """
    def __init__(self, *digits, dim=None, _dagger=False):
        if not isinstance(dim, int):
            raise TypeError(int, dim)
        self._digits, self._dim = digits, dim
        name = "Digits({}, dim={})".format(', '.join(map(str, digits)), dim)\
            if dim != 2 else "Bits({})".format(', '.join(map(str, digits)))
        dom, cod = Ty(), Ty(Digit(dim)) ** len(digits)
        dom, cod = (cod, dom) if _dagger else (dom, cod)
        super().__init__(name, dom, cod, _dagger=_dagger)

    def __repr__(self):
        return self.name + (".dagger()" if self._dagger else "")

    @property
    def dim(self):
        """
        The dimension of the information units.

        >>> assert Bits(1, 0).dim == 2
        """
        return self._dim

    @property
    def digits(self):
        """ The digits of a classical state. """
        return list(self._digits)

    @property
    def array(self):
        array = numpy.zeros(len(self._digits) * (self._dim, ) or (1, ))
        array[self._digits] = 1
        return array

    def dagger(self):
        return Digits(*self.digits, dim=self.dim, _dagger=not self._dagger)


class Bits(Digits):
    """
    Implements bit preparation for a given bitstring.

    >>> assert Bits(1, 0).cod == bit ** 2
    >>> assert Bits(1, 0).eval()\\
    ...     == Tensor(dom=Dim(1), cod=Dim(2, 2), array=[0, 0, 1, 0])
    """
    def __init__(self, *bitstring, _dagger=False):
        super().__init__(*bitstring, dim=2, _dagger=_dagger)

    @property
    def bitstring(self):
        """ The bitstring of a classical state. """
        return list(self._digits)

    def dagger(self):
        return Bits(*self.bitstring, _dagger=not self._dagger)


class Ket(Box):
    """
    Implements qubit preparation for a given bitstring.

    >>> assert Ket(1, 0).cod == qubit ** 2
    >>> assert Ket(1, 0).eval()\\
    ...     == Tensor(dom=Dim(1), cod=Dim(2, 2), array=[0, 0, 1, 0])
    """
    def __init__(self, *bitstring):
        if not all([bit in [0, 1] for bit in bitstring]):
            raise Exception('Bitstring can only contain integers 0 or 1.')

        dom, cod = qubit ** 0, qubit ** len(bitstring)
        name = "Ket({})".format(', '.join(map(str, bitstring)))
        super().__init__(name, dom, cod, is_mixed=False)
        self._digits, self._dim, self.draw_as_brakets = bitstring, 2, True

    @property
    def bitstring(self):
        """ The bitstring of a Ket. """
        return list(self._digits)

    def dagger(self):
        return Bra(*self.bitstring)

    array = Bits.array


class Bra(Box):
    """
    Implements qubit post-selection for a given bitstring.

    >>> assert Bra(1, 0).dom == qubit ** 2
    >>> assert Bra(1, 0).eval()\\
    ...     == Tensor(dom=Dim(2, 2), cod=Dim(1), array=[0, 0, 1, 0])
    """
    def __init__(self, *bitstring):
        if not all([bit in [0, 1] for bit in bitstring]):
            raise Exception('Bitstring can only contain integers 0 or 1.')

        name = "Bra({})".format(', '.join(map(str, bitstring)))
        dom, cod = qubit ** len(bitstring), qubit ** 0
        super().__init__(name, dom, cod, is_mixed=False)
        self._digits, self._dim, self.draw_as_brakets = bitstring, 2, True

    @property
    def bitstring(self):
        """ The bitstring of a Bra. """
        return list(self._digits)

    def dagger(self):
        return Ket(*self.bitstring)

    array = Bits.array


def _e_k(n, k):
    v = [0] * n
    v[k] = 1
    return v


def _gbraket_array(*string, type_):
    np = numpy
    type_ = _get_qudit_dims(type_)
    if len(string) != len(type_):
        raise ValueError('Mismatching string and type lengths')
    tensor = Tensor.id(Dim(1)).tensor(*(
        Tensor(Dim(1), Dim(n), _e_k(n, k)) for n, k in zip(type_, string)))
    return np.reshape(tensor.array, tuple(type_) + (1, ))


class GKet(Box):
    def __init__(self, *string, cod):
        dom, cod = qubit ** 0, _gbox_type(cod)
        name = "GKet({})".format(', '.join(map(str, string)))    # TODO Include dom
        super().__init__(name, dom, cod)
        self._digits = string
        self.array = _gbraket_array(*string, type_=cod)
    
    @property
    def digits(self):
        """ The digits of a generalized Ket. """
        return list(self._digits)

    def dagger(self):
        return GBra(*self._digits, dom=self.cod)


class GBra(Box):
    def __init__(self, *string, dom):
        dom, cod = _gbox_type(dom), qubit ** 0
        name = "GBra({})".format(', '.join(map(str, string)))
        super().__init__(name, dom, cod)
        self._digits = string
        self.array = _gbraket_array(*string, type_=dom).T

    @property
    def digits(self):
        """ The digits string of a generalized Bra. """
        return list(self._digits)

    def dagger(self):
        return GKet(*self._digits, cod=self.dom)


class Controlled(QuantumGate):
    """
    Abstract class for controled quantum gates.

    Parameters
    ----------
    controlled : QuantumGate
        Gate to control, e.g. :code:`CX = Controlled(X)`.
    distance : int, optional
        Number of qubits from the control to the target, default is :code:`0`.
        If negative, the control is on the right of the target.
    """
    def __init__(self, controlled, distance=0):
        if not isinstance(controlled, QuantumGate):
            raise TypeError(QuantumGate, controlled)
        self.controlled, self.distance = controlled, distance
        self.draw_as_controlled = True
        array = numpy.zeros((4, 4), dtype=complex)
        array[:2, :2] = numpy.eye(2)
        array[2:, 2:] = controlled.array
        if distance != 0:
            raise NotImplementedError
        name = "C" + controlled.name
        n_qubits = len(controlled.dom) + (
            distance + 1 if distance >= 0 else -distance)
        super().__init__(name, n_qubits, array)

    def dagger(self):
        return Controlled(self.controlled.dagger(), distance=self.distance)


class Parametrized(Box):
    """
    Abstract class for parametrized boxes in a quantum circuit.

    Parameters
    ----------
    name : str
        Name of the parametrized class, e.g. :code:`"CRz"`.
    dom, cod : discopy.quantum.circuit.Ty
        Domain and codomain.
    data : any
        Data of the box, potentially with free symbols.
    datatype : type
        Type to cast whenever there are no free symbols.

    Example
    -------
    >>> from sympy.abc import phi
    >>> from sympy import pi, exp, I
    >>> assert Rz(phi)\\
    ...     == Parametrized('Rz', qubit, qubit, data=phi, is_mixed=False)
    >>> assert Rz(phi).array[0,0] == exp(-1.0 * I * pi * phi)
    >>> c = Rz(phi) >> Rz(-phi)
    >>> assert list(c.eval().array.flatten()) == [1, 0, 0, 1]
    >>> assert c.lambdify(phi)(.25) == Rz(.25) >> Rz(-.25)
    """
    def __init__(self, name, dom, cod, data=None, **params):
        self.drawing_name = '{}({})'.format(name, data)
        Box.__init__(
            self, name, dom, cod, data=data,
            is_mixed=params.get('is_mixed', True),
            _dagger=params.get('_dagger', False))

    @property
    def modules(self):
        if self.free_symbols:
            import sympy
            return sympy
        else:
            return Tensor.np

    def subs(self, *args):
        data = rsubs(self.data, *args)
        return type(self)(data)

    def lambdify(self, *symbols, **kwargs):
        from sympy import lambdify
        data = lambdify(symbols, self.data, dict(kwargs, modules=Tensor.np))
        return lambda *xs: type(self)(data(*xs))

    @property
    def name(self):
        return '{}({})'.format(self._name, format_number(self.data))

    def __repr__(self):
        return self.name


class Rotation(Parametrized, QuantumGate):
    """ Abstract class for rotation gates. """
    def __init__(self, phase, name=None, n_qubits=1):
        QuantumGate.__init__(self, name, n_qubits)
        Parametrized.__init__(
            self, name, self.dom, self.cod,
            datatype=float, is_mixed=False, data=phase)

    @property
    def phase(self):
        """ The phase of a rotation gate. """
        return self.data

    def dagger(self):
        return type(self)(-self.phase)

    def grad(self, var, **params):
        if var not in self.free_symbols:
            return Sum([], self.dom, self.cod)
        gradient = self.phase.diff(var)
        gradient = complex(gradient) if not gradient.free_symbols else gradient

        if params.get('mixed', True):
            if len(self.dom) != 1:
                raise NotImplementedError
            s = scalar(Tensor.np.pi * gradient, is_mixed=True)
            t1 = type(self)(self.phase + .25)
            t2 = type(self)(self.phase - .25)
            return s @ (t1 + scalar(-1, is_mixed=True) @ t2)

        return scalar(Tensor.np.pi * gradient) @ type(self)(self.phase + .5)


class Rx(Rotation):
    """ X rotations. """
    def __init__(self, phase):
        super().__init__(phase, name="Rx")

    @property
    def array(self):
        half_theta = self.modules.pi * self.phase
        sin, cos = self.modules.sin(half_theta), self.modules.cos(half_theta)
        return Tensor.np.array([[cos, -1j * sin], [-1j * sin, cos]])


class Ry(Rotation):
    """ Y rotations. """
    def __init__(self, phase):
        super().__init__(phase, name="Ry")

    @property
    def array(self):
        half_theta = self.modules.pi * self.phase
        sin, cos = self.modules.sin(half_theta), self.modules.cos(half_theta)
        return Tensor.np.array([[cos, -1 * sin], [sin, cos]])


class Rz(Rotation):
    """ Z rotations. """
    def __init__(self, phase):
        super().__init__(phase, name="Rz")

    @property
    def array(self):
        half_theta = self.modules.pi * self.phase
        return Tensor.np.array(
            [[self.modules.exp(-1j * half_theta), 0],
             [0, self.modules.exp(1j * half_theta)]])


def _outer_prod_diag(*bitstring):
    return Bra(*bitstring) >> Ket(*bitstring)


class CU1(Rotation):
    """ Controlled Z rotations. """
    def __init__(self, phase):
        super().__init__(phase, name="CU1", n_qubits=2)

    @property
    def array(self):
        theta = 2 * self.modules.pi * self.phase
        return Tensor.np.array(
            [1, 0, 0, 0,
             0, 1, 0, 0,
             0, 0, 1, 0,
             0, 0, 0, self.modules.exp(1j * theta)]).reshape(2, 2, 2, 2)

    def grad(self, var, **params):
        if var not in self.free_symbols:
            return Sum([], self.dom, self.cod)
        if params.get('mixed', True):
            return super().grad(var, **params)
        gradient = self.phase.diff(var)
        gradient = complex(gradient) if not gradient.free_symbols else gradient
        _i_2_pi = 1j * 2 * self.modules.pi
        s = scalar(_i_2_pi * gradient * self.modules.exp(_i_2_pi * self.phase))
        return _outer_prod_diag(1, 1) @ s


class CRz(Rotation):
    """ Controlled Z rotations. """
    def __init__(self, phase):
        super().__init__(phase, name="CRz", n_qubits=2)

    @property
    def array(self):
        half_theta = self.modules.pi * self.phase
        exp_m = self.modules.exp(-1j * half_theta)
        exp_p = self.modules.exp(1j * half_theta)
        return Tensor.np.array(
            [1, 0, 0, 0,
             0, 1, 0, 0,
             0, 0, exp_m, 0,
             0, 0, 0, exp_p]).reshape(2, 2, 2, 2)

    def grad(self, var, **params):
        if var not in self.free_symbols:
            return Sum([], self.dom, self.cod)
        if params.get('mixed', True):
            return super().grad(var, **params)
        gradient = self.phase.diff(var)
        gradient = complex(gradient) if not gradient.free_symbols else gradient
        _i_half_pi = .5j * self.modules.pi
        op1 = Z @ Z @ scalar(_i_half_pi * gradient)
        op2 = Id(qubit) @ Z @ scalar(-_i_half_pi * gradient)
        return self >> (op1 + op2)


class CRx(Rotation):
    """ Controlled Z rotations. """
    def __init__(self, phase):
        super().__init__(phase, name="CRx", n_qubits=2)

    @property
    def array(self):
        half_theta = self.modules.pi * self.phase
        cos, sin = self.modules.cos(half_theta), self.modules.sin(half_theta)
        return Tensor.np.array(
            [1, 0, 0, 0,
             0, 1, 0, 0,
             0, 0, cos, -1j * sin,
             0, 0, -1j * sin, cos]).reshape(2, 2, 2, 2)

    def grad(self, var, **params):
        if var not in self.free_symbols:
            return Sum([], self.dom, self.cod)
        if params.get('mixed', True):
            return super().grad(var, **params)
        gradient = self.phase.diff(var)
        gradient = complex(gradient) if not gradient.free_symbols else gradient
        _i_half_pi = .5j * self.modules.pi
        op1 = Z @ X @ scalar(_i_half_pi * gradient)
        op2 = Id(qubit) @ X @ scalar(-_i_half_pi * gradient)
        return self >> (op1 + op2)


class GX(GeneralizedQuantumGate):
    """ Generalized X gate. """
    def __init__(self, dom):
        dom = _gbox_type(dom, exp_size=1, min_dim=2)
        super().__init__(name='X', dom=dom)

    @property
    def array(self):
        d = _get_qudit_dims(self.dom)[0]
        np = numpy
        return np.eye(d)[:, (np.arange(d)+1) % d]

    def __pow__(self, times):
        d = _get_qudit_dims(self.dom)[0]
        return _gate_pow(self, times, period=d)


class Neg(GeneralizedQuantumGate):
    """ Negation gate. """
    def __init__(self, dom):
        dom = _gbox_type(dom, exp_size=1, min_dim=2)
        super().__init__(name='Neg', dom=dom)

    @property
    def array(self):
        np = numpy
        d = _get_qudit_dims(self.dom)[0]
        return np.eye(d)[:, (d - np.arange(d)) % d]

    def dagger(self):
        return type(self)(self.dom)

    def __pow__(self, times):
        d = _get_qudit_dims(self.dom)[0]
        return _gate_pow(self, times,
                         period=2 if d > 2 else 1)


class GZ(GeneralizedQuantumGate):
    """ Generalized Z gate. """
    def __init__(self, dom):
        dom = _gbox_type(dom, exp_size=1, min_dim=2)
        super().__init__(name=f'Z', dom=dom)

    @property
    def array(self):
        np = numpy
        d = _get_qudit_dims(self.dom)[0]
        diag = np.exp(np.arange(d)*2j*np.pi/d)
        return np.diag(diag)

    def __pow__(self, times):
        d = _get_qudit_dims(self.dom)[0]
        return _gate_pow(self, times, period=d)


class GH(GeneralizedQuantumGate):
    """
    Discrete Fourier transform gate. Note that in a qubit system this corresponds
    to the one-qubit Hadamard gate.
    """
    def __init__(self, dom):
        dom = _gbox_type(dom, exp_size=1)
        super().__init__(name=f'H', dom=dom)

    @property
    def array(self):
        np = numpy
        d = _get_qudit_dims(self.dom)[0]
        m = (np.arange(d)*2j*np.pi/d)[..., np.newaxis]
        m = m @ np.arange(d)[np.newaxis]
        m = np.exp(m)/np.sqrt(d)
        return m

    def __pow__(self, times):
        d = _get_qudit_dims(self.dom)[0]
        return _gate_pow(self, times, period=4 if d > 2 else 2)


class Add(GeneralizedQuantumGate):
    def __init__(self, dom):
        dom = _gbox_type(dom, exp_size=2)
        if dom[0] != dom[1]:
            raise ValueError('Qudits expected having same dimension')
        super().__init__(name=f'Add', dom=dom)

    @property
    def array(self):
        np = numpy
        d = _get_qudit_dims(self.dom)[0]
        p = np.mgrid[:d, :d].reshape((2, -1)).T
        p = np.sum(p, axis=1) % d
        p += np.repeat(np.arange(d)*d, d)
        return np.eye(len(p))[:, p]

    def __pow__(self, times):
        d = _get_qudit_dims(self.dom)[0]
        return _gate_pow(self, times, period=d)


def nadd(dom):
    """
    Create the NADD gate which corresponds to the Add gate followed by
    Neg applied to the least significant qudit.
    """
    dom = _gbox_type(dom, exp_size=2)
    if _get_qudit_dims(dom)[0] <= 2:
        return Add(dom)
    return Add(dom) >> (Id(Ty(dom[1])) @ Neg(dom[0]))


def gcopy(t):
    """
    The copy dot.
    :param t: Leg type.
    """
    t = _gbox_type(t, exp_size=1)
    return (Id(t) @ GKet(0, cod=t)) >> Add(t @ t)


def gplus(t):
    """
    The plus dot.
    :param t: Leg type.
    """
    t = _gbox_type(t, exp_size=1)
    return ((GKet(0, cod=t) >> GH(t)) @ Id(t)) >> nadd(t)


class Scalar(Parametrized):
    """ Scalar, i.e. quantum gate with empty domain and codomain. """
    def __init__(self, data, datatype=complex, name=None, is_mixed=False):
        self.drawing_name = format_number(data)
        name = "scalar" if name is None else name
        dom, cod = qubit ** 0, qubit ** 0
        _dagger = None if data.conjugate() == data else False
        super().__init__(
            name, dom, cod,
            datatype=datatype, is_mixed=is_mixed, data=data, _dagger=_dagger)

    def __repr__(self):
        return super().__repr__()[:-1] + (
            ', is_mixed=True)' if self.is_mixed else ')')

    @property
    def array(self):
        return [self.data]

    def grad(self, var, **params):
        if var not in self.free_symbols:
            return Sum([], self.dom, self.cod)
        return Scalar(self.array[0].diff(var))

    def dagger(self):
        return self if self._dagger is None\
            else Scalar(self.array[0].conjugate())


class MixedScalar(Scalar):
    """ Mixed scalar, i.e. where the Born rule has already been applied. """
    def __init__(self, data):
        super().__init__(data, is_mixed=True)


class Sqrt(Scalar):
    """ Square root. """
    def __init__(self, data):
        super().__init__(data, name="sqrt")
        self.drawing_name = "sqrt({})".format(format_number(data))

    @property
    def array(self):
        return [self.data ** .5]


SWAP = Swap(qubit, qubit)
CZ = QuantumGate('CZ', 2, [1, 0, 0, 0,
                           0, 1, 0, 0,
                           0, 0, 1, 0,
                           0, 0, 0, -1], _dagger=None)
H = QuantumGate(
    'H', 1, 1 / numpy.sqrt(2) * numpy.array([1, 1, 1, -1]), _dagger=None)
S = QuantumGate('S', 1, [1, 0, 0, 1j])
T = QuantumGate('T', 1, [1, 0, 0, numpy.exp(1j * numpy.pi / 4)])
X = QuantumGate('X', 1, [0, 1, 1, 0], _dagger=None)
Y = QuantumGate('Y', 1, [0, -1j, 1j, 0])
Z = QuantumGate('Z', 1, [1, 0, 0, -1], _dagger=None)
CX = Controlled(X)

GATES = [SWAP, CZ, CX, H, S, T, X, Y, Z]


def rewire(op, a: int, b: int, *, dom=None):
    """
    Rewire a two-qubits gate (circuit) to arbitrary qubits.
    :param a: The destination qubit index of the leftmost wire of the
    input gate.
    :param b: The destination qubit index of the rightmost wire of the
    input gate.
    :param dom: Optional domain/codomain for the resulting circuit.
    """
    if len(set([a, b])) != 2:
        raise ValueError('The destination indices must be distinct')
    dom = qubit ** (max(a, b) + 1) if dom is None else dom
    if len(dom) < 2:
        raise ValueError('Dom size expected at least 2')
    if op.dom != qubit**2:
        raise ValueError('Input gate\'s dom expected qubit**2')

    if (b - a) == 1:
        # a, b contiguous and not reversed
        return Box.id(a) @ op @ Box.id(len(dom) - (b + 1))
    if (b - a) == -1:
        # a, b contiguous and reversed
        op = (SWAP >> op >> SWAP) if op.cod == op.dom else (SWAP >> op)
        return Box.id(b) @ op @ Box.id(len(dom) - (a + 1))

    if op.cod != op.dom:
        raise NotImplementedError
    reverse = a > b
    a, b = min(a, b), max(a, b)
    perm = list(range(len(dom)))
    perm[0], perm[a] = a, 0
    perm[1], perm[b] = perm[b], perm[1]
    if reverse:
        perm[0], perm[1] = perm[1], perm[0]
    perm = Box.permutation(perm, dom=dom)
    return perm.dagger() >> (op @ Box.id(len(dom) - 2)) >> perm


def sqrt(expr):
    """ Returns a 0-qubit quantum gate that scales by a square root. """
    return Sqrt(expr)


def scalar(expr, is_mixed=False):
    """ Returns a 0-qubit quantum gate that scales by a complex number. """
    return Scalar(expr, is_mixed=is_mixed)
