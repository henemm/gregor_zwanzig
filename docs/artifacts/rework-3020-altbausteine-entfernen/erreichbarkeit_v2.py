import re,os,sys
from pathlib import Path
S=Path(sys.argv[1]).resolve()
def istest(p): s=str(p); return '__tests__' in s or '.test.' in s or '.spec.' in s or '/e2e/' in s
files=[p for p in S.rglob('*') if p.suffix in('.ts','.svelte','.js') and p.is_file()]
prod=[p for p in files if not istest(p)]
IMP=re.compile(r"""(?:import|export)\s+(?:type\s+)?([^'";]*?)\s*from\s*['"]([^'"]+)['"]|import\s*['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]\s*\)""",re.S)
def res(f,spec):
    if spec.startswith('$lib'): b=S/'lib'/spec[4:].lstrip('/')
    elif spec.startswith('.'): b=(f.parent/spec)
    else: return None
    b=Path(os.path.normpath(b))
    for c in [b,Path(str(b)+'.ts'),Path(str(b)+'.svelte'),Path(str(b)+'.js'),Path(str(b)+'.svelte.ts'),b/'index.ts',Path(re.sub(r'\.js$','.ts',str(b)))]:
        if c.is_file(): return c
def edges(f):
    t=re.sub(r"(?m)^\s*//.*$","",f.read_text(errors="ignore")); out=[]
    for m in IMP.finditer(t):
        sp=m.group(2) or m.group(3) or m.group(4); r=res(f,sp)
        if not r: continue
        names=re.findall(r'\b([A-Za-z_]\w*)(?:\s+as\s+\w+)?\s*(?=[,}])',(m.group(1) or '')) if '{' in (m.group(1) or '') else None
        out.append((r,names,m.group(0).startswith('export'),m.group(1) or ''))
    return out
E={f:[e for e in edges(f) if not (f.name=="index.ts" and "WeatherMetricsTab" in e[3])] for f in prod}
def expname(clause):
    return [ (a.strip().split(' as ')[-1].strip()) for a in re.sub(r'[{}]','',clause.replace('type ','')).split(',') if a.strip()]
roots=[f for f in prod if '/routes/' in str(f) or f.name.startswith(('hooks','app','service-worker'))]
seen=set(); st=list(roots); bn=set()
def isbarrel(f): return f.name=='index.ts'
while st:
    f=st.pop()
    if f in seen or f not in E: continue
    seen.add(f)
    for r,n,ex,cl in E[f]:
        if isbarrel(r) and n is not None and not ex:
            # name level
            for r2,n2,ex2,cl2 in E.get(r,[]):
                if not ex2: st.append(r2); continue
                names=expname(cl2)
                if cl2.strip().startswith('*') or set(names)&set(n): 
                    if isbarrel(r2) and not cl2.strip().startswith('*'): st.append(r2)
                    else: st.append(r2)
        elif r in E: st.append(r)
dead=sorted(f for f in prod if f not in seen and not isbarrel(f))
tests=[f for f in files if istest(f)]
txt={t:t.read_text(errors='ignore') for t in tests}
for d in dead:
    nt=[t for t in tests if re.search(r'\b'+re.escape(d.stem.replace('.svelte',''))+r'(\.svelte|\.ts|\.js)?[\'"`]',txt[t])]
    print(d.relative_to(S),sum(1 for _ in open(d,errors='ignore')),'tests:',len(nt))
