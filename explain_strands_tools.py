import importlib, pkgutil, sys

try:
    pkg = importlib.import_module('strands_tools')
except Exception as e:
    print('IMPORT_ERROR', e)
    sys.exit(1)

submods = [info.name for info in pkgutil.iter_modules(pkg.__path__)]
for name in sorted(submods):
    full = f'strands_tools.{name}'
    try:
        m = importlib.import_module(full)
    except Exception as e:
        print(f'--- {name} : IMPORT_ERROR -> {e}')
        continue
    doc = (m.__doc__ or '').strip().splitlines()
    doc0 = doc[0].strip() if doc else ''
    if doc0 == '':
        # try to get doc from module-level variables
        doc0 = '(no module docstring)'
    exports = [n for n in dir(m) if not n.startswith('_')]
    # keep only callable/class or variables that look like tools
    short_exports = []
    for n in exports:
        try:
            obj = getattr(m, n)
            t = type(obj).__name__
            short_exports.append(f'{n}({t})')
        except Exception:
            short_exports.append(n)
    print(f'--- {name}')
    print('doc:', doc0)
    if short_exports:
        print('exports:', ', '.join(short_exports[:10]) + (', ...' if len(short_exports)>10 else ''))
    else:
        print('exports: (none)')

print('\nDone')
