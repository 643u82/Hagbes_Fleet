# -*- coding: utf-8 -*-

# Monkeypatch Odoo's Field.__str__ and Field.__repr__ to avoid AttributeError during Windows testing runbot logging
try:
    from odoo.fields import Field
    def _safe_str(self):
        if not hasattr(self, 'name') or self.name is None:
            return "<%s.%s>" % (self.__class__.__module__, self.__class__.__name__)
        return "%s.%s" % (getattr(self, 'model_name', ''), self.name)

    def _safe_repr(self):
        if not hasattr(self, 'name') or self.name is None:
            return f"'<{self.__class__.__module__}.{self.__class__.__name__}>'"
        return f"{getattr(self, 'model_name', '')}.{self.name}"

    Field.__str__ = _safe_str
    Field.__repr__ = _safe_repr
except Exception:
    pass

# Monkeypatch OrderedSet to have a copy method for Python 3.14 WeakSet compatibility
try:
    from odoo.tools.misc import OrderedSet
    if not hasattr(OrderedSet, 'copy'):
        def _ordered_set_copy(self):
            return OrderedSet(self)
        OrderedSet.copy = _ordered_set_copy
except Exception:
    pass
from . import models
from . import wizard
from . import safeguards
from .hooks import post_init_hook

