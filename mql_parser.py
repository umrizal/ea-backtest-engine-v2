import re

class MQL5Parser:
    def __init__(self, mql_code):
        self.code = mql_code or ""
        self.ast = {
            "properties": {},
            "inputs": {},
            "indicators": [],
            "entry_conditions": {"buy": [], "sell": []},
            "risk_management": {}
        }
        self.parse()

    def parse(self):
        if not self.code.strip():
            return self.ast

        # 1. Parse Properties (#property)
        props = re.findall(r'#property\s+(\w+)\s+(.+)', self.code)
        for k, v in props:
            self.ast["properties"][k] = v.strip()

        # 2. Parse Inputs & Sinputs
        inputs = re.findall(r'(?:input|sinput)\s+(int|double|float|bool|string)\s+(\w+)\s*=\s*([^;]+);', self.code)
        for dtype, var_name, val in inputs:
            val_clean = val.split('//')[0].strip()
            if dtype == 'bool':
                self.ast["inputs"][var_name] = True if val_clean.lower() == 'true' else False
            elif dtype in ['double', 'float']:
                self.ast["inputs"][var_name] = float(val_clean)
            elif dtype == 'int':
                self.ast["inputs"][var_name] = int(float(val_clean))
            else:
                self.ast["inputs"][var_name] = val_clean.replace('"', '')

        # 3. Parse Calls to iMA, iRSI, iMACD, iBands
        if 'iMA' in self.code:
            self.ast["indicators"].append({"type": "iMA", "params": re.findall(r'iMA\s*\((.*?)\)', self.code)})
        if 'iRSI' in self.code:
            self.ast["indicators"].append({"type": "iRSI", "params": re.findall(r'iRSI\s*\((.*?)\)', self.code)})
        if 'iMACD' in self.code:
            self.ast["indicators"].append({"type": "iMACD", "params": re.findall(r'iMACD\s*\((.*?)\)', self.code)})

        return self.ast
