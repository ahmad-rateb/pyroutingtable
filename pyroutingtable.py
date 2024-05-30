"""
An Implementation of IP Routing Table using two types of retrieval trees:
- Prefix Tree
- PATRICIA Trie (Radix of 2)
"""

from ipaddress import _BaseNetwork, ip_network, ip_address
from abc import ABC, abstractmethod
from itertools import zip_longest
import functools


def sanitize(func):
    """
    Decorator to check and convert function's arguments into appropriate
    values and handle common exceptions that may arise while traversing
    the tree.
    """

    @functools.wraps(func)
    def inner(self, prefix, **attrs):
        if prefix is not None and not isinstance(prefix, _BaseNetwork):
            prefix = ip_network(prefix, strict=False)
        try:
            return func(self, prefix, **attrs)
        except KeyError:
            err = "No exact match for {}.".format(prefix)
            raise RoutingTableValidationError(err) from None
    inner.__defaults__ = func.__defaults__
    return inner


def bits_in_prefix(prefix):
    """
    Returns IP prefix bits based on the length of a given `prefix`.

    >>> bits_in_prefix("192.168.1.0/24")
        '110000001010100000000001'
    >>> bits_in_prefix("2a01:db8:acad:1::/64")
        '0010101000000001000011011011100010101100101011010000000000000001'
    """

    if not isinstance(prefix, _BaseNetwork):
        prefix = ip_network(prefix, strict=False)
    network_id_as_integer = int(prefix.network_address)
    if prefix.version == 4:
        bits = "{:032b}".format(network_id_as_integer)
    else:
        bits = "{:0128b}".format(network_id_as_integer)
    return bits[:prefix.prefixlen]


def bits_in_common(x_bits, y_bits):
    """
    Returns common bits between two prefixes or empty string otherwise.

    >>> bits_in_common("1111111", "1110111")
        '111'
    >>> bits_in_common("0111111", "1111111")
        ''
    """

    common_bits = ""
    for x_bit, y_bit in zip_longest(x_bits, y_bits):
        if x_bit != y_bit:
            return common_bits
        common_bits += x_bit
    return common_bits


def new_dict_without_key(unwanted_key, dct):
    """
    Returns a dict of filtered key-value pairs after ignoring an `unwanted_key`.

    >>> nodes = {"*": "192.168.0.0/23",
                 "0": {"*": "192.168.0.0/24"},
                 "1": {"*": "192.168.1.0/24"}}
    >>> new_dict = new_dict_without_key("*", nodes)
    >>> new_dict
        {'0': {'*': '192.168.0.0/24'},
         '1': {'*': '192.168.1.0/24'}}
    >>> new_dict is nodes
        False
    """

    return {key: val for key, val in dct.items() if key != unwanted_key}


def int_prefix_boundaries(prefix):
    """
    Returns integer representations of the start and end of a `prefix`.

    For example:
        "192.168.1.0/24" would have:
            - start: 192.168.1.0 or 3232235776
            - end: 192.168.1.255 or 3232236031
        "2a01:db8:acad:1::/64" would have:
            - start: 2a01:db8:acad:1::
                or 55833046422572317460453482296053334016
            - end: 2a01:db8:acad:1:ffff:ffff:ffff:ffff
                or 55833046422572317478900226369762885631

    >>> int_prefix_boundaries("192.168.1.0/24")
        (3232235776, 3232236031)
    >>> int_prefix_boundaries("2a01:db8:acad:1::/64")
        (55833046422572317460453482296053334016,
         55833046422572317478900226369762885631)
    """

    if not isinstance(prefix, _BaseNetwork):
        prefix = ip_network(prefix, strict=False)
    prefix_id = int(prefix.network_address)
    bc_address = int(prefix.broadcast_address)
    return prefix_id, bc_address


def int_wildcard_boundaries(address, wildcard):
    """
    Returns integer representations of the start and end of a `wildcard`
    `address` range.

    For example:
        "192.168.0.0" with wildcard of "0.0.3.255" would have:
            - start: 192.168.0.0 or 3232235520
            - end: 192.168.3.255 or 3232236543
        "2a01:db8:acad::" with wildcard of "0:0:0:1::" would have:
            - start: 2a01:db8:acad::
                or 55833046422572317442006738222343782400
            - end: 2a01:db8:acad:1::
                or 55833046422572317460453482296053334016

    >>> int_wildcard_boundaries("192.168.0.0", "0.0.3.255")
        (3232235520, 3232236543)
    >>> int_wildcard_boundaries("2a01:db8:acad::", "0:0:0:1::")
        (55833046422572317442006738222343782400,
         55833046422572317460453482296053334016)
    """

    wc_start = int(ip_address(address))
    wc_end = wc_start | int(ip_address(wildcard))
    return wc_start, wc_end


def has_all_attrs(obj, **attrs):
    """
    Returns True if all of the provided kwargs (`attrs`) are attributes of
    `obj`, or False otherwise.

    >>> route = Route("8.8.8.8/32", via="192.168.1.1")
    >>> has_all_attrs(route, via="192.168.1.1")
        True
    >>> has_all_attrs(route, via="192.168.1.1", dev="eth0")
        False
    >>> has_all_attrs(route, via="192.168.1.2")
        False
    >>> has_all_attrs(route, dev="eth0")
        False
    >>> has_all_attrs(route)
        True
    """

    try:
        return all(getattr(obj, attr) == val for attr, val in attrs.items())
    except AttributeError:
        return False


def objs_with_all_attrs(objs, **attrs):
    """
    Returns a filtered list of `objs` that have all provided `attrs`.

    >>> objs = [Route(prefix="192.168.1.0/24", via="10.0.0.1", dev="eth0"),
                Route(prefix="192.168.1.0/25", via="10.0.0.1", dev="eth0"),
                Route(prefix="192.168.1.0/26", via="10.0.0.2", dev="eth0"),
                Route(prefix="192.168.1.0/27", via="10.3.3.3", dev="eth1")]
    >>> objs_with_all_attrs(objs, via="10.0.0.1", dev="eth0")
        [Route(prefix=192.168.1.0/24, via=10.0.0.1, dev=eth0),
         Route(prefix=192.168.1.0/25, via=10.0.0.1, dev=eth0)]
    >>> objs_with_all_attrs(objs, dev="eth1")
        [Route(prefix=192.168.1.0/27, via=10.3.3.3, dev=eth1)]
    >>> objs_with_all_attrs(objs)
        [Route(prefix="192.168.1.0/24", via="10.0.0.1", dev="eth0"),
         Route(prefix="192.168.1.0/25", via="10.0.0.1", dev="eth0"),
         Route(prefix="192.168.1.0/26", via="10.0.0.2", dev="eth0"),
         Route(prefix="192.168.1.0/27", via="10.3.3.3", dev="eth1")]
    >>> objs_with_all_attrs(objs, dev="eth2")
        []
    """

    return [obj for obj in objs if has_all_attrs(obj, **attrs)]


class Route:
    """
    Container for routing attributes of an IP prefix.
    """

    def __init__(self, prefix, **attrs):
        """
        Initializes a `Route` object with the `prefix` as a property attribute.
        Optional (custom) attributes `attrs` can be passed as kwargs.

        Custom attributes can also be added or modified after object
        instantiation.

        >>> route = Route("8.8.8.8/32", via="192.168.1.1")
        >>> route.dev = "eth0"
        >>> route
            Route(prefix=8.8.8.8/32, via=192.168.1.1, dev=eth0)

        >>> route6 = Route("2002:abcd::/32", via="fd00::1")
        >>> route6.dev = "eth0"
        >>> route6
            Route(prefix=2002:abcd::/32, via=fd00::1, dev=eth0)
        """

        self._prefix = prefix
        self.__dict__.update(attrs)

    def __iter__(self):
        """
        Returns a generator that yields key-value pair of each attribute.

        >>> route = Route("8.8.8.8/32", via="192.168.1.1", dev="eth0")
        >>> dict(route)
            {'prefix': '8.8.8.8/32', 'via': '192.168.1.1', 'dev': 'eth0'}

        >>> route6 = Route("2002:abcd::/32", via="fd00::1", dev="eth0")
        >>> dict(route6)
            {'prefix': '2002:abcd::/32', 'via': 'fd00::1', 'dev': 'eth0'}
        """

        return ((attr.lstrip("_"), val) for attr, val in vars(self).items())

    def __eq__(self, other):
        """
        Compares two `Route` objects using their attributes.

        >>> route1 = Route("8.8.8.8/32", via="192.168.1.1", dev="eth0")
        >>> route2 = Route("8.8.8.8/32", dev="eth0")
        >>> route3 = Route("8.8.8.8/32", dev="eth0")
        >>> route1 == route2
            False
        >>> route2 == route3
            True

        >>> route6_1 = Route("2002:abcd::/32", via="fd00::1", dev="eth0")
        >>> route6_2 = Route("2002:abcd::/32", dev="eth0")
        >>> route6_3 = Route("2002:abcd::/32", dev="eth0")
        >>> route6_1 == route6_2
            False
        >>> route6_2 == route6_3
            True
        """

        if isinstance(other, Route):
            return self.__dict__ == other.__dict__
        return False

    def __str__(self):
        """
        Formats the object representation in a key-value pair fashion.

        >>> route = Route("8.8.8.8/32", via="192.168.1.1", dev="eth0")
        >>> str(route)
            'Route(prefix=8.8.8.8/32, via=192.168.1.1, dev=eth0)'

        >>> route6 = Route("2002:abcd::/32", via="fd00::1", dev="eth0")
        >>> str(route6)
            'Route(prefix=2002:abcd::/32, via=fd00::1, dev=eth0)'
        """

        f_attrs = ", ".join("{}={}".format(attr, val) for attr, val in iter(self))
        return "Route({})".format(f_attrs)

    def __repr__(self):
        """
        Formats the object representation in a key-value pair fashion.

        >>> route = Route("8.8.8.8/32", via="192.168.1.1", dev="eth0")
        >>> route
            Route(prefix=8.8.8.8/32, via=192.168.1.1, dev=eth0)

        >>> route6 = Route("2002:abcd::/32", via="fd00::1", dev="eth0")
        >>> route6
            Route(prefix=2002:abcd::/32, via=fd00::1, dev=eth0)
        """

        return str(self)

    @property
    def prefix(self):
        """Returns the initially set prefix value."""

        return self._prefix


class RoutingTableValidationError(Exception):
    """Bad routing-lookup/modification operation was performed."""


class RoutingTable(ABC):
    """
    An interface for IP Routing Table implementations.
    """

    @abstractmethod
    def __init__(self):
        """Initializes an empty tree (a root node)."""

    @abstractmethod
    def __iter__(self):
        """Iterator that yields each installed `Route` object."""

    @abstractmethod
    def __len__(self):
        """Returns number of installed `Route` objects."""

    @abstractmethod
    def __contains__(self, prefix):
        """Returns True if `prefix` is routable, False otherwise."""

    @abstractmethod
    def _traverse(self, root, **attrs):
        """
        A generator function that recursively traverses a given tree (rooted at
        a given node, e.g. `root` node) to yield each installed `Route` object
        downstream.

        Traversal is implemented like function's call stack, where nodes are
        checked if they have pointers to `Route` objects (i.e. has "*" key).
        If node is branched or has children, they will also be checked, and so
        on until all of the branches are visited.

        If `attrs` (kwargs) are provided, this will further filter the routing
        table to return `Route` objects with matched attribute(s).
        """

    @abstractmethod
    def _sort(self, routes):
        """
        Sorts a given iterable of `Route` objects based on their prefix length.
        """

    @abstractmethod
    def add(self, prefix, **attrs):
        """
        Extends the tree by new `prefix` and a `Route` object.

        If the `prefix` exists already but with different attributes, another
        `Route` object will be added.

        Custom route attributes `attrs` can be passed as kwargs to allow
        attribute-based filtration in lookup operations.
        """

    @abstractmethod
    def get(self, prefix, **attrs):
        """
        Returns a list of longest match `Route` objects for a given `prefix`,
        or an empty list otherwise.

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

    @abstractmethod
    def show(self, prefix=None, as_root=False, **attrs):
        """
        Returns a sorted list of all installed `Route` objects (default, when
        no arguments are provided).

        If `prefix` and/or `attrs` are provided, this will further filter the
        routing table to return matched `Route` object(s).

        If `prefix` is provided, it performs exact match check (not longest-
        match check).

        `as_root` requires `prefix` as it roots the tree at the given `prefix`
        then recursively traverses the tree to yield all `Route` objects
        downstream (including the root `Route` object).
        """

    @abstractmethod
    def parent(self, prefix, **attrs):
        """
        Returns a list of direct parent `Route` objects for an existing
        `prefix`, or an empty list otherwise.

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

    @abstractmethod
    def children(self, prefix, **attrs):
        """
        Returns a sorted list of children `Route` objects for an existing
        `prefix`, or an empty list otherwise.

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

    @abstractmethod
    def match(self, prefix, **attrs):
        """
        Returns a sorted list of `Route` objects that share any prefix-bits
        with the given `prefix` (i.e. all possible matching routes, not just
        the longest-match).

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

    @abstractmethod
    def wcmatch(self, address, wildcard, **attrs):
        """
        Returns a sorted list of `Route` objects that overlap with a `wildcard`
        `address` range.

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

    @abstractmethod
    def delete(self, prefix, **attrs):
        """
        Deletes an existing `prefix` from the tree and releases its
        associations with the `Route` object(s).

        When `attrs` are provided, this will further filter the deletion
        of the `Route` object(s).
        """

    @abstractmethod
    def flush(self, prefix=None, **attrs):
        """
        This method extends the `delete` method's functionality by allowing
        attribute-based deletion.

        If no `prefix` nor `attrs` are provided, the entire tree is flushed
        and all `Route` objects' associations are released.
        """


class IPPrefixTree(RoutingTable):
    """
    A tree of binary digits (bits) that construct IP prefixes.
    """

    def __init__(self):
        """Initializes an empty `IPPrefixTree` object (a root node)."""

        self._root = {}
        self._counter = 0

    def __iter__(self):
        """Iterator that yields each installed `Route` object."""

        return self._traverse(self._root)

    def __len__(self):
        """Returns number of installed `Route` objects."""

        return self._counter

    def __contains__(self, prefix):
        """Returns True if `prefix` is routable, False otherwise."""

        return bool(self.get(prefix))

    def _traverse(self, root, **attrs):
        """
        A generator function that recursively traverses a given tree (rooted at
        a given node, e.g. `root` node) to yield each installed `Route` object
        downstream.

        Traversal is implemented like function's call stack, where nodes are
        checked if they have pointers to `Route` objects (i.e. has "*" key).
        If node is branched or has children, they will also be checked, and so
        on until all of the branches are visited.

        If `attrs` (kwargs) are provided, this will further filter the routing
        table to return `Route` objects with matched attribute(s).
        """

        nodes = list(root.items())

        while nodes:
            node_bit, children = nodes.pop()
            if node_bit == "*":
                routes = children
                for route in routes:
                    if has_all_attrs(route, **attrs):
                        yield route
            else:
                nodes.extend(children.items())

    def _sort(self, routes):
        """
        Sorts a given iterable of `Route` objects based on their prefix length.
        """

        return sorted(routes, key=lambda route: ip_network(route.prefix))

    @sanitize
    def add(self, prefix, **attrs):
        """
        Extends the `IPPrefixTree` object by new `prefix` and a `Route` object.

        If the `prefix` exists already but with different attributes, another
        `Route` object will be added.

        Custom route attributes `attrs` can be passed as kwargs to allow
        attribute-based filtration in lookup operations.
        """

        pointer = self._root

        for bit in bits_in_prefix(prefix):
            pointer = pointer.setdefault(bit, {})

        route = Route(str(prefix), **attrs)
        routes = pointer.setdefault("*", [])

        if route not in routes:
            routes.append(route)
            self._counter += 1

    @sanitize
    def get(self, prefix, **attrs):
        """
        Returns a list of longest match `Route` objects for a given prefix,
        or an empty list otherwise.

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

        pointer = self._root
        routes = pointer.get("*", [])

        for bit in bits_in_prefix(prefix):
            if bit not in pointer:
                break
            pointer = pointer[bit]
            routes = pointer.get("*", routes)

        return objs_with_all_attrs(routes, **attrs)

    def show(self, prefix=None, as_root=False, **attrs):
        """
        Returns a sorted list of all installed `Route` objects (default, when
        no arguments are provided).

        If `prefix` and/or `attrs` are provided, this will further filter the
        routing table to return matched `Route` object(s).

        If `prefix` is provided, it performs exact match check (not longest-
        match check).

        `as_root` requires `prefix` as it roots the `IPPrefixTree` at the given
        prefix then recursively traverses the tree to yield all `Route` objects
        downstream (including the root `Route` object).
        """

        if as_root and prefix is None:
            err = "A prefix is required when as_root is True"
            raise TypeError(err)

        pointer = self._root

        if prefix is not None:
            for bit in bits_in_prefix(prefix):
                if bit not in pointer:
                    return []
                pointer = pointer[bit]
            if not as_root:
                routes = pointer.get("*", [])
                return objs_with_all_attrs(routes, **attrs)

        return self._sort(self._traverse(pointer, **attrs))

    @sanitize
    def parent(self, prefix, **attrs):
        """
        Returns a list of direct parent `Route` objects for an existing
        `prefix`, or an empty list otherwise.

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

        pointer = self._root
        routes = []

        for bit in bits_in_prefix(prefix):
            routes = pointer.get("*", routes)
            pointer = pointer[bit]

        if "*" not in pointer:
            raise KeyError

        return objs_with_all_attrs(routes, **attrs)

    @sanitize
    def children(self, prefix, **attrs):
        """
        Returns a sorted list of children `Route` objects for an existing
        `prefix`, or an empty list otherwise.

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

        pointer = self._root

        for bit in bits_in_prefix(prefix):
            pointer = pointer[bit]

        if "*" not in pointer:
            raise KeyError

        # Ignore "*" marker so that the node is not child of itself
        pointer = new_dict_without_key("*", pointer)

        return self._sort(self._traverse(pointer, **attrs))

    @sanitize
    def match(self, prefix, **attrs):
        """
        Returns a sorted list of `Route` objects that share any prefix-bits
        with the given `prefix` (i.e. all possible matching routes, not just
        the longest-match).

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

        pointer = self._root
        routes = pointer.get("*", [])
        matches = routes.copy()

        for bit in bits_in_prefix(prefix):
            pointer = pointer.get(bit)
            if pointer is None:
                break
            routes = pointer.get("*")
            if routes is not None:
                matches += routes

        return self._sort(objs_with_all_attrs(matches, **attrs))

    def wcmatch(self, address, wildcard, **attrs):
        """
        Returns a sorted list of `Route` objects that overlap with a `wildcard`
        `address` range.

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

        matches = []

        wc_start, wc_end = int_wildcard_boundaries(address, wildcard)

        routes = self._traverse(self._root, **attrs)

        for route in routes:
            network_id, bc_address = int_prefix_boundaries(route.prefix)
            if (network_id & wc_end) == network_id and (wc_start & bc_address) == wc_start:
                matches.append(route)

        return self._sort(matches)

    @sanitize
    def delete(self, prefix, **attrs):
        """
        Deletes an existing `prefix` from the `IPPrefixTree` and releases its
        associations with the `Route` object(s).

        When `attrs` are provided, this will further filter the deletion
        of the `Route` object(s).
        """

        pointer = self._root
        parent_prefix_node = branching_bit = None

        for bit in bits_in_prefix(prefix):
            if len(pointer) > 1:
                parent_prefix_node = pointer
                branching_bit = bit
            pointer = pointer[bit]

        routes = pointer["*"]

        if attrs:
            something_removed = False
            for route in routes.copy():
                if has_all_attrs(route, **attrs):
                    routes.remove(route)
                    self._counter -= 1
                    something_removed = True
            if not something_removed:
                f_attrs = ", ".join("{}={}".format(attr, val) for attr, val in attrs.items())
                err = "No route for {} with [{}] attributes combined."
                raise RoutingTableValidationError(err.format(prefix, f_attrs))

        if not attrs or not routes:
            # Node has child(ren), just dereference the match
            if len(pointer) > 1:
                del pointer["*"]
                self._counter -= len(routes)
            # Node has no child(ren), trim up to the parent prefix node
            elif parent_prefix_node is not None:
                del parent_prefix_node[branching_bit]
                self._counter -= len(routes)
            # Tree only has this node, cut the root of the tree
            else:
                self.flush()

    @sanitize
    def flush(self, prefix=None, **attrs):
        """
        This method extends the `delete` method's functionality by allowing
        attribute-based deletion.

        If no `prefix` nor `attrs` are provided, the entire `IPPrefixTree`
        object is flushed and all `Route` objects' associations are released.
        """

        if prefix is not None:
            return self.delete(prefix, **attrs)
        if not attrs:
            self._root.clear()
            self._counter = 0

        nodes = list(self._root.items())

        while nodes:
            node_bit, children = nodes.pop()
            if node_bit == "*":
                routes = children
                for route in routes.copy():
                    if has_all_attrs(route, **attrs):
                        routes.remove(route)
                        self._counter -= 1
                if not routes:
                    self.delete(route.prefix)
            else:
                nodes.extend(children.items())


class IPRadixTree():
    """
    A compact, space-optimized version of an IP Prefix Tree.
    """

    def __init__(self):
        """Initializes an empty `IPRadixTree` object (a root node)."""

        self._root = {}
        self._counter = 0

    def __iter__(self):
        """Iterator that yields each installed `Route` object."""

        return self._traverse(self._root)

    def __len__(self):
        """Returns number of installed `Route` objects."""

        return self._counter

    def __contains__(self, prefix):
        """Returns True if `prefix` is routable, False otherwise."""

        return bool(self.get(prefix))

    def _traverse(self, root, **attrs):
        """
        A generator function that recursively traverses a given tree (rooted at
        a given node, e.g. `root` node) to yield each installed `Route` object
        downstream.

        Traversal is implemented like function's call stack, where nodes are
        checked if they have pointers to `Route` objects (i.e. has "*" key).
        If node is branched or has children, they will also be checked, and so
        on until all of the branches are visited.

        If `attrs` (kwargs) are provided, this will further filter the routing
        table to return `Route` objects with matched attribute(s).
        """

        nodes = list(root.items())

        while nodes:
            node_bits, children = nodes.pop()
            if node_bits == "*":
                routes = children
                for route in routes:
                    if has_all_attrs(route, **attrs):
                        yield route
            else:
                nodes.extend(children.items())

    def _sort(self, routes):
        """
        Sorts a given iterable of `Route` objects based on their prefix length.
        """

        return sorted(routes, key=lambda route: ip_network(route.prefix))

    @sanitize
    def add(self, prefix, **attrs):
        """
        Extends the `IPRadixTree` object by new `prefix` and a `Route` object.

        If the `prefix` exists already but with different attributes, another
        `Route` object will be added.

        Custom route attributes `attrs` can be passed as kwargs to allow
        attribute-based filtration in lookup operations.
        """

        prefix_bits = bits_in_prefix(prefix)
        pointer = self._root
        nodes = new_dict_without_key("*", pointer)

        while nodes and prefix_bits:
            node_bits, children = nodes.popitem()
            common_bits = bits_in_common(node_bits, prefix_bits)
            if common_bits:
                prefix_bits = prefix_bits[len(common_bits):]
                if common_bits == node_bits:
                    pointer = children
                    nodes = new_dict_without_key("*", pointer)
                else:
                    del pointer[node_bits]
                    remaining_node_bits = node_bits[len(common_bits):]
                    pointer[common_bits] = {remaining_node_bits: children}
                    pointer = pointer[common_bits]
                    nodes = {}

        if prefix_bits:
            pointer[prefix_bits] = {}
            pointer = pointer[prefix_bits]

        route = Route(str(prefix), **attrs)
        routes = pointer.setdefault("*", [])

        if route not in routes:
            routes.append(route)
            self._counter += 1

    @sanitize
    def get(self, prefix, **attrs):
        """
        Returns a list of longest match `Route` objects for a given prefix,
        or an empty list otherwise.

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

        prefix_bits = bits_in_prefix(prefix)
        routes = self._root.get("*", [])
        nodes = new_dict_without_key("*", self._root)

        while nodes and prefix_bits:
            node_bits, children = nodes.popitem()
            common_bits = bits_in_common(node_bits, prefix_bits)
            if common_bits == node_bits:
                routes = children.get("*", routes)
                prefix_bits = prefix_bits[len(common_bits):]
                nodes = new_dict_without_key("*", children)

        return objs_with_all_attrs(routes, **attrs)

    def show(self, prefix=None, as_root=False, **attrs):
        """
        Returns a sorted list of all installed `Route` objects (default, when
        no arguments are provided).

        If `prefix` and/or `attrs` are provided, this will further filter the
        routing table to return matched `Route` object(s).

        If `prefix` is provided, it performs exact match check (not longest-
        match check).

        `as_root` requires `prefix` as it roots the `IPRadixTree` at the given
        prefix then recursively traverses the tree to yield all `Route` objects
        downstream (including the root `Route` object).
        """

        if as_root and prefix is None:
            err = "A prefix is required when as_root is True"
            raise TypeError(err)

        pointer = self._root

        if prefix is not None:
            nodes = new_dict_without_key("*", pointer)
            prefix_bits = bits_in_prefix(prefix)
            while nodes and prefix_bits:
                node_bits, children = nodes.popitem()
                common_bits = bits_in_common(node_bits, prefix_bits)
                if common_bits:
                    prefix_bits = prefix_bits[len(common_bits):]
                    if common_bits == node_bits:
                        pointer = children
                        nodes = new_dict_without_key("*", pointer)
            if prefix_bits:
                return []
            if not as_root:
                routes = pointer.get("*", [])
                return objs_with_all_attrs(routes, **attrs)

        return self._sort(self._traverse(pointer, **attrs))

    @sanitize
    def parent(self, prefix, **attrs):
        """
        Returns a list of direct parent `Route` objects for an existing
        `prefix`, or an empty list otherwise.

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

        prefix_bits = bits_in_prefix(prefix)
        pointer = self._root
        nodes = new_dict_without_key("*", pointer)
        routes = []

        while nodes and prefix_bits:
            node_bits, children = nodes.popitem()
            common_bits = bits_in_common(node_bits, prefix_bits)
            if common_bits == node_bits:
                routes = pointer.get("*", routes)
                prefix_bits = prefix_bits[len(common_bits):]
                pointer = children
                nodes = new_dict_without_key("*", pointer)

        if prefix_bits or "*" not in pointer:
            raise KeyError

        return objs_with_all_attrs(routes, **attrs)

    @sanitize
    def children(self, prefix, **attrs):
        """
        Returns a sorted list of children `Route` objects for an existing
        `prefix`, or an empty list otherwise.

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

        prefix_bits = bits_in_prefix(prefix)
        pointer = self._root
        nodes = new_dict_without_key("*", pointer)

        while nodes and prefix_bits:
            node_bits, children = nodes.popitem()
            common_bits = bits_in_common(node_bits, prefix_bits)
            if common_bits == node_bits:
                prefix_bits = prefix_bits[len(common_bits):]
                pointer = children
                nodes = new_dict_without_key("*", pointer)

        if prefix_bits or "*" not in pointer:
            raise KeyError

        # Ignore "*" marker so that the node is not child of itself
        pointer = new_dict_without_key("*", pointer)

        return self._sort(self._traverse(pointer, **attrs))

    @sanitize
    def match(self, prefix, **attrs):
        """
        Returns a sorted list of `Route` objects that share any prefix-bits
        with the given `prefix` (i.e. all possible matching routes, not just
        the longest-match).

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

        prefix_bits = bits_in_prefix(prefix)
        pointer = self._root
        routes = pointer.get("*", [])
        matches = routes.copy()
        nodes = new_dict_without_key("*", pointer)

        while nodes and prefix_bits:
            node_bits, children = nodes.popitem()
            common_bits = bits_in_common(node_bits, prefix_bits)
            if common_bits == node_bits:
                prefix_bits = prefix_bits[len(common_bits):]
                pointer = children
                routes = pointer.get("*")
                if routes is not None:
                    matches += routes
                nodes = new_dict_without_key("*", pointer)

        return self._sort(objs_with_all_attrs(matches, **attrs))

    def wcmatch(self, address, wildcard, **attrs):
        """
        Returns a sorted list of `Route` objects that overlap with a `wildcard`
        `address` range.

        When `attrs` are provided, this will further filter the routing table
        to return matched `Route` object(s).
        """

        matches = []

        wc_start, wc_end = int_wildcard_boundaries(address, wildcard)

        routes = self._traverse(self._root, **attrs)

        for route in routes:
            network_id, bc_address = int_prefix_boundaries(route.prefix)
            if (network_id & wc_end) == network_id and (wc_start & bc_address) == wc_start:
                matches.append(route)

        return self._sort(matches)

    @sanitize
    def delete(self, prefix, **attrs):
        """
        Deletes an existing `prefix` from the `IPRadixTree` and releases its
        associations with the `Route` object(s).

        When `attrs` are provided, this will further filter the deletion
        of the `Route` object(s).
        """

        prefix_bits = bits_in_prefix(prefix)
        pointer = self._root
        nodes = new_dict_without_key("*", pointer)
        parents = []

        while nodes and prefix_bits:
            node_bits, children = nodes.popitem()
            common_bits = bits_in_common(node_bits, prefix_bits)
            if common_bits == node_bits:
                prefix_bits = prefix_bits[len(common_bits):]
                # Store current node as parent before moving the pointer to its
                # children, then ensure that the parents list only has previous
                # node and current node (that has just been stored as parent),
                # this fixes the number of lookback operations to 2, e.g. when
                # deleting a child from the current node [-1] then checking if
                # a merge operation is required with its parent node [-2]
                parents.append([pointer, node_bits, children])
                parents = parents[-2:]
                pointer = children
                nodes = new_dict_without_key("*", pointer)

        if prefix_bits:
            raise KeyError

        routes = pointer["*"]

        if attrs:
            something_removed = False
            for route in routes.copy():
                if has_all_attrs(route, **attrs):
                    routes.remove(route)
                    self._counter -= 1
                    something_removed = True
            if not something_removed:
                f_attrs = ", ".join("{}={}".format(attr, val) for attr, val in attrs.items())
                err = "No route for {} with [{}] attributes combined."
                raise RoutingTableValidationError(err.format(prefix, f_attrs))

        if not attrs or not routes:
            del pointer["*"]
            while parents:
                parent, parent_bits, children = parents.pop()
                if not children:
                    del parent[parent_bits]
                elif len(children) == 1:
                    child_bits, child = children.popitem()
                    del parent[parent_bits]
                    parent_bits += child_bits
                    parent[parent_bits] = child
            self._counter -= len(routes)

    @sanitize
    def flush(self, prefix=None, **attrs):
        """
        This method extends the `delete` method's functionality by allowing
        attribute-based deletion.

        If no `prefix` nor `attrs` are provided, the entire `IPRadixTree`
        object is flushed and all `Route` objects' associations are released.
        """

        if prefix is not None:
            return self.delete(prefix, **attrs)
        if not attrs:
            self._root.clear()
            self._counter = 0

        nodes = list(self._root.items())

        while nodes:
            node_bits, children = nodes.pop()
            if node_bits == "*":
                routes = children
                for route in routes.copy():
                    if has_all_attrs(route, **attrs):
                        routes.remove(route)
                        self._counter -= 1
                if not routes:
                    self.delete(route.prefix)
            else:
                nodes.extend(children.items())
