# IP Routing Table implementation in Python

An Implementation of IP Routing Table using two types of retrieval trees:
- Prefix Tree
- PATRICIA Trie (Radix of 2)

The tree (Routing Table) is built by adding IP prefix's binary digits (bits) in an ordered, key-value pair fashion. Each added IP prefix will be pointing to one or more `Route` objects.
Once the tree is built, various traversal operations can be performed.

The creation of this module was inspired by `iproute2` utility in Linux and `pytricia` Python module (implemented in C).

> Minimum supported version: Python 3.4, Requirements: None

## Route object

The `Route` object is a container for routing-attributes; it holds a property attribute `prefix` and can hold an arbitrary number of custom routing-attributes.

:warning: The `Route` object is automatically instantiated and referenced by the tree object (`IPPrefixTree` or `IPRadixTree`) when an IP prefix is added, i.e. user doesn't manually instantiate the `Route` object, instead, user just needs to know how to access or modify the `Route` objects when returned by the operations on the tree object.

```
from pyroutingtable import Route

>>> route = Route("8.8.8.8/32", via="192.168.1.1")
>>> route
    Route(prefix=8.8.8.8/32, via=192.168.1.1)
>>> route.prefix
    '8.8.8.8/32'
>>> route.via
    '192.168.1.1'
>>> route.via = "192.168.1.254"
>>> route.dev = "eth0"
>>> route.proto = "bgp"
>>> route
    Route(prefix=8.8.8.8/32, via=192.168.1.254, dev=eth0, proto=bgp)
>>> dict(route)
    {'prefix': '8.8.8.8/32', 'via': '192.168.1.254', 'dev': 'eth0', 'proto': 'bgp'}

>>> route6 = Route("2002:abcd::/32", via="fd00::1")
>>> route6
    Route(prefix=2002:abcd::/32, via=fd00::1)
>>> route6.prefix
    '2002:abcd::/32'
>>> route6.via
    'fd00::1'
>>> route6.via = "fd00::fffe"
>>> route6.dev = "eth0"
>>> route6.proto = "bgp"
>>> route6
    Route(prefix=2002:abcd::/32, via=fd00::fffe, dev=eth0, proto=bgp)
>>> dict(route6)
    {'prefix': '2002:abcd::/32', 'via': 'fd00::fffe', 'dev': 'eth0', 'proto': 'bgp'}
```

> Unlike the custom routing-attributes (e.g. `via`, `dev`), the `prefix` attribute can't be changed once the `Route` object is created, because an IP prefix once added in a tree object will always have one or more `Route` objects associated with it, thus, any attempt to change the prefix information will result in a broken tree.

## IPPrefixTree and IPRadixTree objects

Both `IPPrefixTree` and `IPRadixTree` are containers for the `Route` objects, and while they **both achieve the same exact target**, user can opt to use one or the other based on the execution environment:
- `IPPrefixTree` consumes more memory, however, it's quite fast for any kind of operation (e.g. `add`, `get` or `delete`)
- `IPRadixTree` is a compact, space-optimized version of the `IPPrefixTree`. It shines when dealing with IPv6 as it compresses common bits of the IPv6 prefixes before storing them, but this comes at a cost of the execution time of the requested operation.

:bulb: Nowadays there won't be a significant difference -in terms of lookup speed- when using either implementation, however, throughout this documentation, `IPPrefixTree` will be used with IPv4 and `IPRadixTree` with IPv6.

A `Route` object will be instantiated automatically when `add` method is used and released when `delete` or `flush` methods are used. Query operations on the `IPPrefixTree` or `IPRadixTree` object return a list of `Route` objects.

No arguments required for instantiating `IPPrefixTree` or `IPRadixTree` objects.

```
from pyroutingtable import IPPrefixTree, IPRadixTree

>>> rib = IPPrefixTree()
>>> rib6 = IPRadixTree()
```

### Methods

#### `add(prefix, **attrs)`

Extends the tree by new `prefix` and a `Route` object. If the `prefix` exists already but with different attributes, another `Route` object will be added.

Custom route attributes `attrs` can be passed as kwargs to allow attribute-based filtration in lookup operations.

Equivalent `iproute2` commands in Linux: 
- `ip route add blackhole PREFIX` (default behavior)
- `ip route add PREFIX [ via ADDRESS ] [ dev STRING ] [ attribute ATTR ] ...` (with custom routing-attributes)

```
from pyroutingtable import IPPrefixTree, IPRadixTree

>>> rib = IPPrefixTree()
>>> rib.add("4.2.2.2/32")
>>> rib.add("8.8.8.8/32", via="192.168.1.1", dev="eth0", proto="ospf")

>>> rib6 = IPRadixTree()
>>> rib6.add("2001::/16")
>>> rib6.add("2002::/16", via="fe80::1", dev="eth0", proto="ospfv3")
```

#### `get(prefix, **attrs)`

Returns a list of longest match `Route` objects for a given `prefix`, or an empty list otherwise.

When `attrs` are provided, this will further filter the routing table to return matched `Route` object(s).

Equivalent `iproute2` command in Linux: 
- `ip route get ADDRESS [ attribute ATTR ] ...`

```
from pyroutingtable import IPPrefixTree, IPRadixTree

>>> rib = IPPrefixTree()
>>> rib.add("192.168.1.0/24", via="10.0.0.1")
>>> rib.add("192.168.1.0/24", via="10.0.0.2")
>>> rib.add("192.168.1.0/25")
>>> rib.get("192.168.1.1")
    [Route(prefix=192.168.1.0/25)]
>>> rib.get("192.168.1.128")
    [Route(prefix=192.168.1.0/24, via=10.0.0.1),
     Route(prefix=192.168.1.0/24, via=10.0.0.2)]
>>> rib.get("192.168.1.128", via="10.0.0.2")
    [Route(prefix=192.168.1.0/24, via=10.0.0.2)]
>>> rib.get("192.168.0.0")
    []

>>> rib6 = IPRadixTree()
>>> rib6.add("2a01:db8:acad::/124", via="fd00::1")
>>> rib6.add("2a01:db8:acad::/124", via="fd00::2")
>>> rib6.add("2a01:db8:acad::/125")
>>> rib6.get("2a01:db8:acad::7")
    [Route(prefix=2a01:db8:acad::/125)]
>>> rib6.get("2a01:db8:acad::8")
    [Route(prefix=2a01:db8:acad::/124, via=fd00::1),
     Route(prefix=2a01:db8:acad::/124, via=fd00::2)]
>>> rib6.get("2a01:db8:acad::8", via="fd00::2")
    [Route(prefix=2a01:db8:acad::/124, via=fd00::2)]
>>> rib6.get("2a01:db8:acad::10")
    []
```

#### `show(prefix=None, as_root=False, **attrs)`

Returns a sorted list of all installed `Route` objects (default, when no arguments are provided).

If `prefix` and/or `attrs` are provided, this will further filter the routing table to return matched `Route` object(s).

If `prefix` is provided, it performs exact match check (not longest-match check).

`as_root` requires `prefix` as it roots the tree at the given `prefix` then recursively traverses the tree to yield all `Route` objects downstream (including the root `Route` object).

Equivalent `iproute2` commands in Linux:
- `ip route show exact PREFIX [ attribute ATTR ] ...` (default behavior)
- `ip route show root PREFIX [ attribute ATTR ] ...` (when `as_root` is True)

```
from pyroutingtable import IPPrefixTree, IPRadixTree

>>> rib = IPPrefixTree()
>>> rib.add("192.168.1.0/24", via="10.0.0.1", dev="eth0")
>>> rib.add("192.168.1.0/25", via="10.0.0.1", dev="eth0")
>>> rib.add("192.168.1.0/26", via="10.0.0.2", dev="eth0")
>>> rib.add("192.168.1.0/27", via="10.3.3.3", dev="eth1")
>>> rib.show()
    [Route(prefix=192.168.1.0/24, via=10.0.0.1, dev=eth0),
     Route(prefix=192.168.1.0/25, via=10.0.0.1, dev=eth0),
     Route(prefix=192.168.1.0/26, via=10.0.0.2, dev=eth0),
     Route(prefix=192.168.1.0/27, via=10.3.3.3, dev=eth1)]
>>> rib.show(via="10.0.0.1", dev="eth0")
    [Route(prefix=192.168.1.0/24, via=10.0.0.1, dev=eth0),
     Route(prefix=192.168.1.0/25, via=10.0.0.1, dev=eth0)]
>>> rib.show("192.168.1.0/28")
    []
>>> rib.show("192.168.1.0/24")
    [Route(prefix=192.168.1.0/24, via=10.0.0.1, dev=eth0)]
>>> rib.show("192.168.1.0/25", as_root=True)
    [Route(prefix=192.168.1.0/25, via=10.0.0.1, dev=eth0),
     Route(prefix=192.168.1.0/26, via=10.0.0.2, dev=eth0),
     Route(prefix=192.168.1.0/27, via=10.3.3.3, dev=eth1)]
>>> rib.show("192.168.0.0/16", as_root=True)
    [Route(prefix=192.168.1.0/24, via=10.0.0.1, dev=eth0),
     Route(prefix=192.168.1.0/25, via=10.0.0.1, dev=eth0),
     Route(prefix=192.168.1.0/26, via=10.0.0.2, dev=eth0),
     Route(prefix=192.168.1.0/27, via=10.3.3.3, dev=eth1)]

>>> rib6 = IPRadixTree()
>>> rib6.add("2002::/16", via="fd00::1", dev="eth0")
>>> rib6.add("2002::/17", via="fd00::1", dev="eth0")
>>> rib6.add("2002::/18", via="fd00::2", dev="eth0")
>>> rib6.add("2002::/19", via="fcde::f", dev="eth1")
>>> rib6.show()
    [Route(prefix=2002::/16, via=fd00::1, dev=eth0),
     Route(prefix=2002::/17, via=fd00::1, dev=eth0),
     Route(prefix=2002::/18, via=fd00::2, dev=eth0),
     Route(prefix=2002::/19, via=fcde::f, dev=eth1)]
>>> rib6.show(via="fd00::1", dev="eth0")
    [Route(prefix=2002::/16, via=fd00::1, dev=eth0),
     Route(prefix=2002::/17, via=fd00::1, dev=eth0)]
>>> rib6.show("2002::/20")
    []
>>> rib6.show("2002::/16")
    [Route(prefix=2002::/16, via=fd00::1, dev=eth0)]
>>> rib6.show("2002::/17", as_root=True)
    [Route(prefix=2002::/17, via=fd00::1, dev=eth0),
     Route(prefix=2002::/18, via=fd00::2, dev=eth0),
     Route(prefix=2002::/19, via=fcde::f, dev=eth1)]
>>> rib6.show("2000::/8", as_root=True)
    [Route(prefix=2002::/16, via=fd00::1, dev=eth0),
     Route(prefix=2002::/17, via=fd00::1, dev=eth0),
     Route(prefix=2002::/18, via=fd00::2, dev=eth0),
     Route(prefix=2002::/19, via=fcde::f, dev=eth1)]
```

#### `parent(prefix, **attrs)`

Returns a list of direct parent `Route` objects for **an existing** `prefix`, or an empty list otherwise.

When `attrs` are provided, this will further filter the routing table to return matched `Route` object(s).

```
from pyroutingtable import IPPrefixTree, IPRadixTree

>>> rib = IPPrefixTree()
>>> rib.add("192.168.1.0/24", proto="bgp")
>>> rib.add("192.168.1.0/24", proto="ospf")
>>> rib.add("192.168.1.0/25")
>>> rib.add("192.168.1.0/26")
>>> rib.parent("192.168.1.0/26")
    [Route(prefix=192.168.1.0/25)]
>>> rib.parent("192.168.1.0/25")
    [Route(prefix=192.168.1.0/24, proto=bgp),
     Route(prefix=192.168.1.0/24, proto=ospf)]
>>> rib.parent("192.168.1.0/25", proto="ospf")
    [Route(prefix=192.168.1.0/24, proto=ospf)]
>>> rib.parent("192.168.1.0/24")
    []

>>> rib6 = IPRadixTree()
>>> rib6.add("2a01::/16", proto="bgp")
>>> rib6.add("2a01::/16", proto="ospfv3")
>>> rib6.add("2a01:db8::/32")
>>> rib6.add("2a01:db8:acad::/48")
>>> rib6.parent("2a01:db8:acad::/48")
    [Route(prefix=2a01:db8::/32)]
>>> rib6.parent("2a01:db8::/32")
    [Route(prefix=2a01::/16, proto=bgp),
     Route(prefix=2a01::/16, proto=ospfv3)]
>>> rib6.parent("2a01:db8::/32", proto="ospfv3")
    [Route(prefix=2a01::/16, proto=ospfv3)]
>>> rib6.parent("2a01::/16")
    []
```

#### `children(prefix, **attrs)`

Returns a sorted list of children `Route` objects for **an existing** `prefix`, or an empty list otherwise.

When `attrs` are provided, this will further filter the routing table to return matched `Route` object(s).

```
from pyroutingtable import IPPrefixTree, IPRadixTree

>>> rib = IPPrefixTree()
>>> rib.add("192.168.1.0/24", via="10.0.0.1")
>>> rib.add("192.168.1.0/25", via="10.0.0.2")
>>> rib.add("192.168.1.0/26", via="10.0.0.3")
>>> rib.children("192.168.1.0/24")
    [Route(prefix=192.168.1.0/25, via=10.0.0.2),
     Route(prefix=192.168.1.0/26, via=10.0.0.3)]
>>> rib.children("192.168.1.0/24", via="10.0.0.2")
    [Route(prefix=192.168.1.0/25, via=10.0.0.2)]
>>> rib.children("192.168.1.0/25")
    [Route(prefix=192.168.1.0/26, via=10.0.0.3)]
>>> rib.children("192.168.1.0/26")
    []

>>> rib6 = IPRadixTree()
>>> rib6.add("2a01::/16", via="fd00:f00d:beef::1")
>>> rib6.add("2a01:db8::/32", via="fd00:f00d:beef::2")
>>> rib6.add("2a01:db8:acad::/48", via="fd00:f00d:beef::3")
>>> rib6.children("2a01::/16")
    [Route(prefix=2a01:db8::/32, via=fd00:f00d:beef::2),
     Route(prefix=2a01:db8:acad::/48, via=fd00:f00d:beef::3)]
>>> rib6.children("2a01::/16", via="fd00:f00d:beef::2")
    [Route(prefix=2a01:db8::/32, via=fd00:f00d:beef::2)]
>>> rib6.children("2a01:db8::/32")
    [Route(prefix=2a01:db8:acad::/48, via=fd00:f00d:beef::3)]
>>> rib6.children("2a01:db8:acad::/48")
    []
```

#### `match(prefix, **attrs)`

Returns a sorted list of `Route` objects that share any prefix-bits with the given `prefix` (i.e. all possible matching routes, not just the longest-match).

When `attrs` are provided, this will further filter the routing table to return matched `Route` object(s).

Equivalent `iproute2` command in Linux:
- `ip route show match PREFIX [ attribute ATTR ] ...`

```
from pyroutingtable import IPPrefixTree, IPRadixTree

>>> rib = IPPrefixTree()
>>> rib.add("0.0.0.0/1", via="192.168.1.1", dev="eth0")
>>> rib.add("10.0.1.0/24", via="192.168.1.1", dev="eth0")
>>> rib.add("10.0.1.128/25", via="192.168.2.1", dev="eth1")
>>> rib.match("10.0.1.192/26")
    [Route(prefix=0.0.0.0/1, via=192.168.1.1, dev=eth0),
     Route(prefix=10.0.1.0/24, via=192.168.1.1, dev=eth0),
     Route(prefix=10.0.1.128/25, via=192.168.2.1, dev=eth1)]
>>> rib.match("10.0.1.192/26", via="192.168.1.1")
    [Route(prefix=0.0.0.0/1, via=192.168.1.1, dev=eth0),
     Route(prefix=10.0.1.0/24, via=192.168.1.1, dev=eth0)]
>>> rib.match("10.0.1.0/24")
    [Route(prefix=0.0.0.0/1, via=192.168.1.1, dev=eth0),
     Route(prefix=10.0.1.0/24, via=192.168.1.1, dev=eth0)]
>>> rib.match("8.8.8.8")
    [Route(prefix=0.0.0.0/1, via=192.168.1.1, dev=eth0)]
>>> rib.match("200.100.50.25")
    []

>>> rib6 = IPRadixTree()
>>> rib6.add("::/1", via="fd00:f00d:beef::1", dev="eth0")
>>> rib6.add("2a01:db8::/32", via="fd00:f00d:beef::1", dev="eth0")
>>> rib6.add("2a01:db8:acad::/48", via="fcde::c0ff:e", dev="eth1")
>>> rib6.match("2a01:db8:acad:1::/64")
    [Route(prefix=::/1, via=fd00:f00d:beef::1, dev=eth0),
     Route(prefix=2a01:db8::/32, via=fd00:f00d:beef::1, dev=eth0),
     Route(prefix=2a01:db8:acad::/48, via=fcde::c0ff:e, dev=eth1)]
>>> rib6.match("2a01:db8:acad:1::/64", via="fd00:f00d:beef::1")
    [Route(prefix=::/1, via=fd00:f00d:beef::1, dev=eth0),
     Route(prefix=2a01:db8::/32, via=fd00:f00d:beef::1, dev=eth0)]
>>> rib6.match("2a01:db8::/32")
    [Route(prefix=::/1, via=fd00:f00d:beef::1, dev=eth0),
     Route(prefix=2a01:db8::/32, via=fd00:f00d:beef::1, dev=eth0)]
>>> rib6.match("2345::")
    [Route(prefix=::/1, via=fd00:f00d:beef::1, dev=eth0)]
>>> rib6.match("abcd::")
    []
```

#### `wcmatch(address, wildcard, **attrs)`

Returns a sorted list of `Route` objects that overlap with a wildcard address range.

When `attrs` are provided, this will further filter the routing table to return matched `Route` object(s).

```
from pyroutingtable import IPPrefixTree, IPRadixTree

>>> rib = IPPrefixTree()
>>> rib.add("192.168.0.0/23", via="10.0.0.1")
>>> rib.add("192.168.1.0/24", via="10.0.0.1")
>>> rib.add("192.168.2.0/25", via="10.0.0.2")
>>> rib.add("192.168.3.0/26", via="10.0.0.2")
>>> rib.add("192.168.4.0/27", via="10.0.0.3")
>>> rib.wcmatch("192.168.0.10", "0.0.3.0")
    [Route(prefix=192.168.0.0/23, via=10.0.0.1),
     Route(prefix=192.168.1.0/24, via=10.0.0.1),
     Route(prefix=192.168.2.0/25, via=10.0.0.2),
     Route(prefix=192.168.3.0/26, via=10.0.0.2)]
>>> rib.wcmatch("192.168.0.10", "0.0.255.0", via="10.0.0.3")
    [Route(prefix=192.168.4.0/27, via=10.0.0.3)]

>>> rib6 = IPRadixTree()
>>> rib6.add("2a01:db8:acad::/63", via="fd00::1")
>>> rib6.add("2a01:db8:acad:1::/64", via="fd00::1")
>>> rib6.add("2a01:db8:acad:2::/65", via="fd00::2")
>>> rib6.add("2a01:db8:acad:3::/66", via="fd00::2")
>>> rib6.add("2a01:db8:acad:4::/67", via="fd00::3")
>>> rib6.wcmatch("2a01:db8:acad::a", "0:0:0:3::")
    [Route(prefix=2a01:db8:acad::/63, via=fd00::1),
     Route(prefix=2a01:db8:acad:1::/64, via=fd00::1),
     Route(prefix=2a01:db8:acad:2::/65, via=fd00::2),
     Route(prefix=2a01:db8:acad:3::/66, via=fd00::2)]
>>> rib6.wcmatch("2a01:db8:acad::", "0:0:0:ffff::", via="fd00::3")
    [Route(prefix=2a01:db8:acad:4::/67, via=fd00::3)]
```

#### `delete(prefix, **attrs)`

Deletes **an existing** `prefix` from the tree and releases its associations with the `Route` object(s).

When `attrs` are provided, this will further filter the deletion of the `Route` object(s).

Equivalent `iproute2` command in Linux:
- `ip route del PREFIX [ attribute ATTR ] ...`

```
from pyroutingtable import IPPrefixTree, IPRadixTree

>>> rib = IPPrefixTree()
>>> rib.add("192.168.1.0/24", via="10.0.0.1")
>>> rib.add("192.168.1.0/24", via="10.0.0.2")
>>> rib.add("192.168.1.0/24", via="10.0.0.3")
>>> rib.add("192.168.1.0/25", via="10.0.0.4")
>>> rib.delete("192.168.1.0/24", via="10.0.0.1")
>>> rib.show("192.168.1.0/24")
    [Route(prefix=192.168.1.0/24, via=10.0.0.2),
     Route(prefix=192.168.1.0/24, via=10.0.0.3)]
>>> rib.delete("192.168.1.0/24")
>>> rib.show("192.168.1.0/24")
    []
>>> rib.show()
    [Route(prefix=192.168.1.0/25, via=10.0.0.4)]

>>> rib6 = IPRadixTree()
>>> rib6.add("2a01:db8:acad:1::/64", via="fd00::1")
>>> rib6.add("2a01:db8:acad:1::/64", via="fd00::2")
>>> rib6.add("2a01:db8:acad:1::/64", via="fd00::3")
>>> rib6.add("2a01:db8:acad:1::/65", via="fd00::4")
>>> rib6.delete("2a01:db8:acad:1::/64", via="fd00::1")
>>> rib6.show("2a01:db8:acad:1::/64")
    [Route(prefix=2a01:db8:acad:1::/64, via=fd00::2),
     Route(prefix=2a01:db8:acad:1::/64, via=fd00::3)]
>>> rib6.delete("2a01:db8:acad:1::/64")
>>> rib6.show("2a01:db8:acad:1::/64")
    []
>>> rib6.show()
    [Route(prefix=2a01:db8:acad:1::/65, via=fd00::4)]
```

#### `flush(prefix=None, **attrs)`

This method extends the `delete` method's functionality by allowing attribute-based deletion.

If no `prefix` nor `attrs` are provided, the entire tree is flushed and all `Route` objects' associations are released.

Equivalent `iproute2` command in Linux:
- `ip route flush [ exact PREFIX ] [ attribute ATTR ] ...`

```
from pyroutingtable import IPPrefixTree, IPRadixTree

>>> rib = IPPrefixTree()
>>> rib.add("192.168.1.0/24", via="10.0.0.1", proto="bgp")
>>> rib.add("192.168.2.0/24", via="10.0.0.2", proto="bgp")
>>> rib.add("192.168.3.0/24", via="10.0.0.3", proto="ospf")
>>> rib.flush(proto="bgp")
>>> rib.show()
    [Route(prefix=192.168.3.0/24, via=10.0.0.3, proto=ospf)]
>>> rib.flush()
>>> rib.show()
    []

>>> rib6 = IPRadixTree()
>>> rib6.add("2a01:db8:acad:1::/64", via="fd00::1", proto="bgp")
>>> rib6.add("2a01:db8:acad:2::/64", via="fd00::2", proto="bgp")
>>> rib6.add("2a01:db8:acad:3::/64", via="fd00::3", proto="ospfv3")
>>> rib6.flush(proto="bgp")
>>> rib6.show()
    [Route(prefix=2a01:db8:acad:3::/64, via=fd00::3, proto=ospfv3)]
>>> rib6.flush()
>>> rib6.show()
    []
```

#### Misc / Special Methods

Iterations, Containment (route-ability), Size

```
from pyroutingtable import IPPrefixTree, IPRadixTree

>>> rib = IPPrefixTree()
>>> rib.add("192.168.1.0/24", via="10.0.0.1")
>>> rib.add("192.168.1.0/25", via="10.0.0.2")
>>> rib.add("192.168.1.0/26", via="10.0.0.3")

>>> "192.168.1.1" in rib
    True

>>> for route in rib:
...    print(route.prefix, route.via)
...
    192.168.1.0/26 10.0.0.3
    192.168.1.0/25 10.0.0.2
    192.168.1.0/24 10.0.0.1

>>> len(rib)
    3

>>> list(rib)
    [Route(prefix=192.168.1.0/26, via=10.0.0.3),
     Route(prefix=192.168.1.0/25, via=10.0.0.2),
     Route(prefix=192.168.1.0/24, via=10.0.0.1)]

>>> rib6 = IPRadixTree()
>>> rib6.add("2a01:db8:acad:1::/64", via="fd00::1")
>>> rib6.add("2a01:db8:acad:1::/65", via="fd00::2")
>>> rib6.add("2a01:db8:acad:1::/66", via="fd00::3")

>>> "2a01:db8:acad:1::1" in rib6
    True

>>> for route6 in rib6:
...     print(route6.prefix, route6.via)
...
    2a01:db8:acad:1::/66 fd00::3
    2a01:db8:acad:1::/65 fd00::2
    2a01:db8:acad:1::/64 fd00::1

>>> len(rib6)
    3

>>> list(rib6)
    [Route(prefix=2a01:db8:acad:1::/66, via=fd00::3),
     Route(prefix=2a01:db8:acad:1::/65, via=fd00::2),
     Route(prefix=2a01:db8:acad:1::/64, via=fd00::1)]
```
