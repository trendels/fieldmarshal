API Reference
=============

.. currentmodule:: fieldmarshal

.. function:: struct(slots=True, auto_attribts=True, \*\*kw)

   Wrapper around ``attr.s``. Takes the same arguments but defaults to
   ``slots=True`` and ``auto_attribs=True``.

.. autofunction:: field

.. autoclass:: Hook

.. autoclass:: Options

.. autoclass:: Registry
   :members:

.. function:: marshal

Standalone version of :meth:`Registry.marshal` that uses the default registry.

.. function:: marshal_json

Standalone version of :meth:`Registry.marshal_json` that uses the default registry.

.. function:: unmarshal

Standalone version of :meth:`Registry.unmarshal` that uses the default registry.

.. function:: unmarshal_json

Standalone version of :meth:`Registry.unmarshal_json` that uses the default registry.
