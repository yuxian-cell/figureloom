"""Inventory the installed Grapher type library without starting Grapher."""

from __future__ import annotations

import json
from pathlib import Path

import pythoncom


def main() -> None:
    library = pythoncom.LoadTypeLib(str(Path(r"C:\Program Files\Golden Software\Grapher\Grapher.tlb")))
    types = []
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attributes = info.GetTypeAttr()
        methods = []
        for method_index in range(attributes.cFuncs):
            function = info.GetFuncDesc(method_index)
            methods.append({"name": info.GetNames(function.memid)[0], "dispid": function.memid})
        properties = []
        for property_index in range(attributes.cVars):
            variable = info.GetVarDesc(property_index)
            properties.append({"name": info.GetNames(variable.memid)[0], "dispid": variable.memid})
        types.append({
            "name": library.GetDocumentation(index)[0],
            "kind": attributes.typekind,
            "iid": str(attributes.iid),
            "methods": methods,
            "properties": properties,
        })
    print(json.dumps({"type_count": len(types), "types": types}, indent=2))


if __name__ == "__main__":
    main()
