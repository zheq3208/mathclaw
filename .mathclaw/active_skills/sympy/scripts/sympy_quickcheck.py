import argparse
import sympy as sp

parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=["simplify", "factor", "expand", "solve"])
parser.add_argument("expr")
parser.add_argument("--symbol", default="x")
args = parser.parse_args()

x = sp.symbols(args.symbol)
expr = sp.sympify(args.expr)
if args.mode == "simplify":
    print(sp.simplify(expr))
elif args.mode == "factor":
    print(sp.factor(expr))
elif args.mode == "expand":
    print(sp.expand(expr))
else:
    print(sp.solve(expr, x))
