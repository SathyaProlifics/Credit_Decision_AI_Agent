import importlib, pkgutil, sys

try:
    m = importlib.import_module('strands_tools')
except Exception as e:
    print('IMPORT_ERROR', e)
    sys.exit(1)

print('MODULE', m.__name__)

names = [n for n in dir(m) if not n.startswith('_')]
print('\nNAMES:')
for n in names:
    obj = getattr(m, n)
    print(f'{n} : {type(obj).__name__}')

print('\nSUBMODULES:')
if hasattr(m, '__path__'):
    for info in pkgutil.iter_modules(m.__path__):
        print(info.name)
else:
    print('(none)')
