# ============================================================
# mql_parser.py
# Pintarin Laboratorium EA - Basic MQL5 AST Parser (Stage 1)
# ============================================================

import re
from typing import Any, Dict, List


class MQL5Parser:
    def __init__(self, mql_code: str = ""):
        self.code = mql_code or ""
        self.ast: Dict[str, Any] = {
            "properties": {},
            "inputs": {},
            "indicators": [],
            "entry_conditions": {"buy": [], "sell": []},
            "risk_management": {},
            "functions": [],
        }
        self.parse()

    def parse(self) -> Dict[str, Any]:
        if not self.code.strip():
            return self.ast

        # 1. Properties
        props = re.findall(r"#property\s+(\w+)\s+(.+)", self.code)
        for k, v in props:
            self.ast["properties"][k] = v.strip().strip('"')

        # 2. Inputs (input / sinput)
        # Support: input double Lot = 0.1;  // comment
        inputs = re.findall(
            r"(?:input|sinput)\s+(int|double|float|bool|string|long|ulong)\s+(\w+)\s*=\s*([^;]+);",
            self.code,
            re.IGNORECASE,
        )
        for dtype, var_name, val in inputs:
            val_clean = val.split("//")[0].strip().strip('"')
            dtype = dtype.lower()
            try:
                if dtype == "bool":
                    self.ast["inputs"][var_name] = val_clean.lower() in ("true", "1")
                elif dtype in ("double", "float"):
                    self.ast["inputs"][var_name] = float(val_clean)
                elif dtype in ("int", "long", "ulong"):
                    self.ast["inputs"][var_name] = int(float(val_clean))
                else:
                    self.ast["inputs"][var_name] = val_clean
            except ValueError:
                self.ast["inputs"][var_name] = val_clean

        # 3. Indicator calls
        indicator_patterns = [
            ("iMA", r"iMA\s*\((.*?)\)"),
            ("iRSI", r"iRSI\s*\((.*?)\)"),
            ("iMACD", r"iMACD\s*\((.*?)\)"),
            ("iBands", r"iBands\s*\((.*?)\)"),
            ("iStochastic", r"iStochastic\s*\((.*?)\)"),
            ("iATR", r"iATR\s*\((.*?)\)"),
            ("iADX", r"iADX\s*\((.*?)\)"),
            ("iCCI", r"iCCI\s*\((.*?)\)"),
            ("iSAR", r"iSAR\s*\((.*?)\)"),
            ("iCustom", r"iCustom\s*\((.*?)\)"),
        ]

        for itype, pattern in indicator_patterns:
            matches = re.findall(pattern, self.code, re.IGNORECASE | re.DOTALL)
            if matches:
                self.ast["indicators"].append(
                    {"type": itype, "params": matches, "count": len(matches)}
                )

        # 4. Detect common risk keywords
        code_lower = self.code.lower()
        if "martingale" in code_lower or "lotmultiplier" in code_lower:
            self.ast["risk_management"]["martingale"] = True
        if "grid" in code_lower or "layer" in code_lower:
            self.ast["risk_management"]["grid"] = True
        if "trailing" in code_lower:
            self.ast["risk_management"]["trailing"] = True

        # 5. Function names (OnTick, OnInit, OnDeinit, dll)
        funcs = re.findall(r"(?:void|int|bool|double|string)\s+(\w+)\s*\(", self.code)
        self.ast["functions"] = list(set(funcs))

        return self.ast

    def get_input(self, name: str, default: Any = None) -> Any:
        return self.ast["inputs"].get(name, default)

    def has_indicator(self, itype: str) -> bool:
        return any(i["type"].lower() == itype.lower() for i in self.ast["indicators"])
