import re,subprocess
def g(*a): return subprocess.run(['git',*a],capture_output=True,text=True).stdout
A,S1,B='539d16963','8b9749601','origin/main'
N=re.compile(r"\b(?:test|it)(?:\.todo|\.skip)?\(\s*(?:'((?:[^'\\]|\\.)*)'|\"([^\"]*)\"|`([^`]*)`)",re.S)
def names(r,f): return {(m[0] or m[1] or m[2]) for m in N.findall(g('show',f'{r}:{f}'))}
tot=0
for l in g('diff','--name-status','--no-renames',A,B,'--','frontend/src','frontend/e2e').splitlines():
    st,f=l.split('\t')
    if '.test.ts' not in f and '.spec.ts' not in f: continue
    if st!='M': continue
    a,b,s=names(A,f),names(B,f),names(S1,f)
    weg=a-b
    print(f'{f.split("components/")[-1]}: vorher {len(a)} main {len(b)} S1 {len(s)}; entfallen {len(weg)}, neu {len(b-a)}, in S1 noch {len(weg&s)}')
    for n in sorted(weg): tot+=1; print('    -',('[S1] ' if n in s else '')+n[:150])
print('entfallen gesamt',tot)
