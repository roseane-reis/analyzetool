import copy
from hashlib import new
import numpy as np
import os
import sys
import math
from time import gmtime, strftime
import subprocess, threading
import itertools

headers = {"prmheader": """##############################
##                          ##
##  Force Field Definition  ##
##                          ##
##############################

forcefield              HIPPO-FORGE_DERIVED

bond-cubic              -2.55
bond-quartic            3.793125
angle-cubic             -0.014
angle-quartic           0.000056
angle-pentic            -0.0000007
angle-sextic            0.000000022
opbendtype              ALLINGER
opbend-cubic            -0.014
opbend-quartic          0.000056
opbend-pentic           -0.0000007
opbend-sextic           0.000000022
torsionunit             0.5
dielectric              1.0
polarization            MUTUAL
d-equals-p
rep-12-scale            0.0
rep-13-scale            0.0
rep-14-scale            0.4
rep-15-scale            0.8
disp-12-scale           0.0
disp-13-scale           0.0
disp-14-scale           0.4
disp-15-scale           0.8
mpole-12-scale          0.0
mpole-13-scale          0.0
mpole-14-scale          0.4
mpole-15-scale          0.8
polar-12-scale          0.0
polar-13-scale          0.5
polar-14-scale          1.0
polar-15-scale          1.0
polar-12-intra          0.0
polar-13-intra          0.0
polar-14-intra          0.0
polar-15-intra          0.5
direct-11-scale         0.0
direct-12-scale         1.0
direct-13-scale         1.0
direct-14-scale         1.0
mutual-11-scale         1.0
mutual-12-scale         1.0
mutual-13-scale         1.0
mutual-14-scale         1.0
induce-12-scale         0.2
induce-13-scale         1.0
induce-14-scale         1.0
induce-15-scale         1.0


""",

"atomdef": """#############################
##                         ##
##  Atom Type Definitions  ##
##                         ##
############################# """,

"multipole": """###################################
##                               ##
##  Atomic Multipole Parameters  ##
##                               ##
###################################""",

"polarize": """########################################
##                                    ##
##  Dipole Polarizability Parameters  ##
##                                    ##
########################################""",

"vdw": """####################################
##                                ##
##    Van der Waals Parameters    ##
##                                ##
####################################""",

"charge": """########################################
##                                    ##
##  Atomic Partial Charge Parameters  ##
##                                    ##
########################################""",

"chgpen": """#####################################
##                                 ##
##  Charge Penetration Parameters  ##
##                                 ##
#####################################""",

"dispersion": """#####################################
##                                 ##
##  Dispersion Parameters          ##
##                                 ##
#####################################""",

"repulsion": """####################################
##                                ##
##      Repulsion Parameters      ##
##                                ##
####################################""",

"chgtrn": """####################################
##                                ##
##   Charge Transfer Parameters   ##
##                                ##
####################################""",

"bond": """####################################
##                                ##
##   Bond Stretching Parameters   ##
##                                ##
####################################""",

"angle": """####################################
##                                ##
##    Angle Bending Parameters    ##
##                                ##
####################################""",

"strbnd": """####################################
##                                ##
##     Stretch-Bend Parameters    ##
##                                ##
####################################""",

"ureybrad": """####################################
##                                ##
##     Urey-Bradley Parameters    ##
##                                ##
####################################""",

"opbend": """####################################
##                                ##
##  Out-of-Plane Bend Parameters  ##
##                                ##
####################################""",

"torsion": """####################################
##                                ##
##      Torsional Parameters      ##
##                                ##
####################################""",

"imptors": """#####################################
##                                 ##
##  Improper Torsional Parameters  ##
##                                 ##
#####################################""",

"cflux": """####################################
##                                ##
##     Charge Flux Parameters     ##
##                                ##
####################################""",

"exchpol": """####################################
##                                ##
##      Exchange Polarization     ##
##                                ##
####################################""",

}

keyliq = f"""parameters          fn.prm
integrator respa

dcd-archive
tau-pressure      5.00
tau-temperature   1.0
barostat          langevin
volume-trial      5

digits            10
printout          500

a-axis            30.0
cutoff            7
neighbor-list
ewald
dewald

polarization      mutual               
polar-eps         1e-05                     
polar-predict     aspc
#########################
"""
keygas = f"""parameters          fn.prm
integrator        stochastic

dcd-archive
tau-temperature   0.1
volume-scale      molecular
THERMOSTAT        BUSSI
BAROSTAT          MONTECARLO

digits            10
printout          5000

polarization      mutual               
polar-eps         1e-06       

fix-chgpen
#########################
"""      
def compute_total_charge(mcharges,factors):
    return(mcharges*factors).sum()
def multipole_factors(refprm):
    nmpol = len(refprm['multipole'][1])
    mcharges = [refprm['multipole'][1][k][0] for k in range(nmpol)]
    mcharges = np.array(mcharges)
    
    factors = np.ones(nmpol,dtype=int)
    
    if np.abs(mcharges.sum()) < 1e-5:
        return factors
    
    r = 20
    ncombs = itertools.combinations_with_replacement(range(1,20),nmpol)
    tested = []
    for a in ncombs:
        if np.array(a).sum == nmpol:
            continue
        for b in itertools.permutations(a):
            b1 = list(b)
            if b1 in tested:
                continue
            res = compute_total_charge(mcharges,b)
            if np.abs(res) < 1e-5:
                del tested
                return np.array(b,dtype=int)
            if b1 not in tested:
                tested.append(b1)

def process_prm(prmfn):
    
    f = open(prmfn)
    prmfile0 = f.readlines()
    f.close()
    
    prmfile = [line for line in prmfile0 if line[0] != '#']
    prmfile = np.array(prmfile)
    prmfile = prmfile[prmfile != '\n']
    nstart = 0
    for k,line in enumerate(prmfile):
        if line[:6] == 'atom  ':
            nstart = k
            break
    
    mfactors = []
    for k,line in enumerate(prmfile0):
        if 'multipole_factors' in line:
            line = line.strip("\n")
            s = line.split('=')
            if len(s) < 2:
                s = line.split(':')
            
            s2 = s[1].split(',')
            s3 = []
            for a in s2:
                aa = [ai for ai in a if ai.isdigit()]
                if len(aa) > 0:
                    s3.append(int("".join(aa)))

            mfactors = s3
            break

    bg = np.array([a[:5] for a in prmfile])
    atms = prmfile[bg=='atom ']
    bnd = prmfile[nstart:][bg[nstart:]=='bond ']
    angl = prmfile[nstart:][bg[nstart:]=='angle']
    strb = prmfile[nstart:][bg[nstart:]=='strbn']
    opbe = prmfile[nstart:][bg[nstart:]=='opben']
    tors = prmfile[nstart:][bg[nstart:]=='torsi']
    pol = prmfile[nstart:][bg[nstart:]=='polar']  
    cpen = prmfile[nstart:][bg[nstart:]=='chgpe']
    disp = prmfile[nstart:][bg[nstart:]=='dispe']
    rep = prmfile[nstart:][bg[nstart:]=='repul']
    ctrn = prmfile[nstart:][bg[nstart:]=='chgtr']
    bflx = prmfile[nstart:][bg[nstart:]=='bndcf']
    aflx = prmfile[nstart:][bg[nstart:]=='angcf']
    exchp = prmfile[nstart:][bg[nstart:]=='exchp']
    
    vdwt = prmfile[nstart:][bg[nstart:]=='vdw  ']
    chg = prmfile[nstart:][bg[nstart:]=='charg']
    itor = prmfile[nstart:][bg[nstart:]=='impto']
    urey = prmfile[nstart:][bg[nstart:]=='ureyb']

    minds = np.where('multi' == bg)[0]
    
    mlines = []
    if len(minds) != 0:
        mlines = prmfile[minds[0]:minds[-1]+5] 
        mlines = [a for a in mlines if len(a) > 5 and a.split()[0] != '#']
    
    # atom types
    atoms = []
    atmtyp = []
    bond = [[],[],[]]
    angle = [[],[],[],[]]
    strbnd = [[],[],[]]
    opbend = [[],[]]
    torsion = [[],[]]
    multipoles = [[],[]]
    bndcflux = [[],[]]
    angcflux = [[],[]]
    exchpol = []
    imptors = [[],[]]
    ureybrad = [[],[],[]]

    typcls = {}
    tclasses = []
    for k,lin in enumerate(atms):
        t = int(lin.split()[1])
        cl = int(lin.split()[2])
        typcls[t] = cl
        atmtyp.append(t)
        tclasses.append(cl)

        nm = lin.split('"')
        atmline = nm[0].split()[2:] + [nm[1]] + nm[2].split()
        atoms.append(atmline)
    
    tclasses = list(set(tclasses))
    tclasses = sorted(tclasses)
    nclas = len(tclasses)
    clspos = {t:i for i,t in enumerate(tclasses)}

    atmtyp = sorted(atmtyp)
    atmpos = {t:i for i,t in enumerate(atmtyp)}
    natms = len(atmtyp)
    #sort
    chgpen = np.zeros((nclas,2))
    dispersion = np.zeros((nclas))
    repulsion = np.zeros((nclas,3))
    chgtrn = np.zeros((nclas,2))
    polarize = [[0]*natms,[0]*natms]

    charge = np.zeros(nclas)
    vdw = np.zeros((nclas,2))
    for k in range(nclas):
        if len(cpen) > 0:
            tl = int(cpen[k].split()[1])
            i = clspos[tl]
            v1 = float(cpen[k].split()[2])
            v2 = float(cpen[k].split()[3])
            chgpen[i] = [v1,v2]
        ##
        if len(disp) > 0:
            tl = int(disp[k].split()[1])
            i = clspos[tl]
            v1 = float(disp[k].split()[2])
            dispersion[i] = v1
        ##
        if len(rep) > 0:
            tl = int(rep[k].split()[1])
            i = clspos[tl]
            v1 = float(rep[k].split()[2])
            v2 = float(rep[k].split()[3])
            v3 = float(rep[k].split()[4])
            repulsion[i] = [v1,v2,v3]
        ##
        if len(ctrn) > 0:
            tl = int(ctrn[k].split()[1])
            i = clspos[tl]
            v1 = float(ctrn[k].split()[2])
            v2 = float(ctrn[k].split()[3])
            chgtrn[i] = [v1,v2]

        if len(vdwt) > 0:
            tl = int(vdwt[k].split()[1])
            i = clspos[tl]
            v1 = float(vdwt[k].split()[2])
            v2 = float(vdwt[k].split()[3])
            vdw[i] = [v1,v2]

        if len(chg) > 0:
            tl = int(chg[k].split()[1])
            i = clspos[tl]
            v1 = float(chg[k].split()[2])
            charge[i] = v1
    
    if len(pol) > 0:
        for k in range(natms):
            s = pol[k].split()
            i = atmpos[int(s[1])]
            v1 = float(s[2])
            polarize[0][i] = v1

            ## test for amoeba 0.39 in polarize
            if len(s) > 3:
                itest = float(s[3])
                if itest.is_integer():
                    con = [int(a) for a in s[3:]]
                else:
                    con = [int(a) for a in s[4:]]
                polarize[1][i] = con
                ##

    if len(mlines) > 0:    
        for i,line in enumerate(mlines[::5]):
            if '#' in line:
                line = line.split('#')[0]
            typs = line.split()[1:-1]
            typs = [int(a) for a in typs]
            vals = [float(line.split()[-1])]
            
            for z,k in enumerate(mlines[i*5+1:i*5+5]):
                s = k.split()
                if z == 3:
                    vals += [float(a) for a in s[:-1]]
                else:
                    vals += [float(a) for a in s]
            multipoles[0].append(typs)
            multipoles[1].append(vals)

    for line in bnd:
        typs = line.split()[1:3]
        val = [float(a) for a in line.split()[3:5]]
        bond[0].append(typs)
        bond[1].append(val[0])
        bond[2].append(val[1])
        
    for line in angl:
        s = line.split()
        typs = [int(bb) for bb in s[1:4]]
        val = [float(a) for a in s[4:6]]
        angle[0].append(typs)
        angle[1].append(val[0])
        angle[2].append(val[1])

        if len(s) > 6:
            angle[3].append(s[6])
        else:
            angle[3].append("")


    for line in strb:
        typs = line.split()[1:4]
        val = [float(a) for a in line.split()[4:6]]
        strbnd[0].append(typs)
        strbnd[1].append(val[0])
        strbnd[2].append(val[1])
    
    for line in urey:
        typs = line.split()[1:4]
        val = [float(a) for a in line.split()[4:6]]
        ureybrad[0].append(typs)
        ureybrad[1].append(val[0])
        ureybrad[2].append(val[1])

    for line in opbe:
        typs = line.split()[1:5]
        val = float(line.split()[5])
        opbend[0].append(typs)
        opbend[1].append(val)
    
    for line in tors:
        typs = line.split()[1:5]
        val = [float(a) for a in line.split()[5:]]
        torsion[0].append(typs)
        torsion[1].append(val)

    for line in itor:
        typs = line.split()[1:5]
        val = [float(a) for a in line.split()[5:]]
        imptors[0].append(typs)
        imptors[1].append(val)

    for line in bflx:
        typs = line.split()[1:3]
        val = float(line.split()[3])
        bndcflux[0].append(typs)
        bndcflux[1].append(val)
        
    for line in aflx:
        typs = line.split()[1:4]
        val = [float(a) for a in line.split()[4:]]
        angcflux[0].append(typs)
        angcflux[1].append(val)

    for line in exchp:
        val = [float(a) for a in line.split()[1:]]
        exchpol.append(val)
    
    if len(exchpol) > 0:
        exchpol = np.array(exchpol)
        exchpol = exchpol[np.argsort(exchpol[:,0])]

    prmdict = {'atom': atoms,
            'types': atmtyp,
            'typcls': typcls,
            'bond': bond,
            'angle': angle,
            'strbnd': strbnd,
            'ureybrad': ureybrad,
            'opbend': opbend,
            'torsion': torsion,
            'imptors': imptors,
            'charge': charge,
            'vdw': vdw,
            'chgpen': chgpen,
            'dispersion': dispersion,
            'repulsion': repulsion,
            'polarize': polarize,
            'bndcflux': bndcflux,
            'angcflux': angcflux,
            'chgtrn': chgtrn,
            'multipole': multipoles,
            'multipole_factors': mfactors,
            'exchpol': np.asarray(exchpol)  }


    return prmdict

def prm_from_key(keys,prmd={},exclude_prm=[]):
    indpterms = ["bond",'angle','strbnd','opbend','torsion',
                 'bndcflux','angcflux',"polarize","chgpen",
                 'dispersion','repulsion','chgtrn']

    bond = [[],[],[]]
    angle = [[],[],[],[]]
    strbnd = [[],[],[]]
    opbend = [[],[]]
    torsion = [[],[]]
    multipole = [[],[]]
    bndcflux = [[],[]]
    angcflux = [[],[]]
    polarize = [[],[],[]]
    chgpen = []
    dispersion = []
    repulsion = []
    chgtrn = []

    if isinstance(keys,str):
        keyfn = [keys]
    elif isinstance(keys,list):
        keyfn = keys

    prmfile = []
    for fname in keyfn:
        f = open(fname)
        prmfile += f.readlines()
        f.close()

    prmfile = np.array(prmfile)
    prmfile = prmfile[prmfile != '\n']
    prmfile = [a for a in prmfile if '#' != a.split()[0]]
    prmfile = [a for a in prmfile if '##' not in a]
    prmfile = np.array(prmfile)
    indp_ = []

    uniq = []
    for k,line in enumerate(prmfile):
        s = line.split()
        term = s[0]
        if term in indpterms:
            indp_.append([term,s])
            if term not in uniq:
                uniq.append(term)
        if term == 'multipole':
            indp_.append([term,k])

            if term not in uniq:
                uniq.append(term)
    
    if len(indp_) == 0:
        return
    
    for line in indp_:
        term = line[0]
        s = line[1]
        if term == 'bond':
            typs = [int(bb) for bb in s[1:3]]
            val = [float(a) for a in s[3:5]]
            bond[0].append(typs)
            bond[1].append(val[0])
            bond[2].append(val[1])
        if term == 'angle':
            typs = [int(bb) for bb in s[1:4]]
            val = [float(a) for a in s[4:6]]
            angle[0].append(typs)
            angle[1].append(val[0])
            angle[2].append(val[1])

            if len(s) > 6:
                angle[3].append(s[6])
            else:
                angle[3].append("")
        if term == 'strbnd':
            typs = [int(bb) for bb in s[1:4]]
            val = [float(a) for a in s[4:6]]
            strbnd[0].append(typs)
            strbnd[1].append(val[0])
            strbnd[2].append(val[1])
        if term == 'opbend':
            typs = [int(bb) for bb in s[1:5]]
            val = float(s[5])
            opbend[0].append(typs)
            opbend[1].append(val)
        if term == 'torsion':
            typs = [int(bb) for bb in s[1:5]]
            val = [float(a) for a in s[5:]]
            torsion[0].append(typs)
            torsion[1].append(val)
        if term == 'bndcflux':
            typs = [int(bb) for bb in s[1:3]]
            val = float(s[3])
            if np.isnan(val):
                val = 0.0
            bndcflux[0].append(typs)
            bndcflux[1].append(val)
        if term == 'angcflux':
            typs = [int(bb) for bb in s[1:4]]
            val = [float(a) for a in s[4:]]
            for ii,a in enumerate(val):
                if np.isnan(a):
                    val[ii] = 0.0
            angcflux[0].append(typs)
            angcflux[1].append(val)
        if term == 'multipole':
            s2 = prmfile[s].split('#')
            s1 = s2[0]
            typs = s1.split()[1:-1]
            typs = [int(a) for a in typs]
            vals = [float(s1.split()[-1])]
            
            for z,l2 in enumerate(prmfile[s+1:s+5]):
                s3 = l2.split()
                if z == 3:
                    vals += [float(a) for a in s3[:-1]]
                else:
                    vals += [float(a) for a in s3]
            multipole[0].append(typs)
            multipole[1].append(vals)
        
        if term == 'polarize':
            i = int(s[1])
            v1 = float(s[2])
            polarize[0].append(i)
            polarize[1].append(v1)

            if len(s) > 3:
                v2 = float(s[3])
                if v2 < 1 or not v2.is_integer():
                    nst = 4
                else:
                    nst = 3 
                
                con = [int(a) for a in s[nst:]]
                polarize[2].append(con) 
            else:
                polarize[2].append(0)

        if term == 'chgpen':
            chgpen.append([float(a) for a in s[1:]])

        if term == 'dispersion':
            dispersion.append([float(a) for a in s[1:]])
        
        if term == 'repulsion':
            repulsion.append([float(a) for a in s[1:]])
        
        if term == 'chgtrn':
            chgtrn.append([float(a) for a in s[1:]])
    
    chgpen = np.array(chgpen)
    dispersion = np.array(dispersion)
    repulsion = np.array(repulsion)
    chgtrn = np.array(chgtrn)
    prmout = {}
    for term in uniq:
        prmout[term] = locals()[term]

    if len(prmd) > 0:
        orig_typ = prmd['types']
        for term,ref in prmd.items():
            if term in exclude_prm:
                continue
            nref = len(ref)
            if term not in prmout.keys():
                continue
            if term == 'polarize':
                for nit,nnt in enumerate(polarize[0]):
                    if nnt in orig_typ:
                        for it,nt in enumerate(orig_typ):
                            if nnt == nt:
                                prmd[term][0][it] = polarize[1][nit]
                                oldcon = prmd[term][1][it]
                                newcon = polarize[2][nit]
                                if oldcon != newcon:
                                    print(f"Connectivity for {nt} differs!")
                                    print(f"Input con. {oldcon}")
                                    print(f"From new prms con. {newcon}")
                                prmd[term][1][it] = newcon
                                break
                    else:
                        print(f"{nnt} not in original list of types, skipping")
            elif term == 'chgpen':
                tt = np.array(prmd['types'])
                for k in range(chgpen.shape[0]):
                    typ = chgpen[k][0]
                    if typ in tt:  ## assumes type == class
                        ii = np.where(typ==tt)[0]
                        rtyp = tt[ii[0]]
                    else:
                        continue
                    prmd['chgpen'][ii[0]] = chgpen[k][1:]
            elif term == 'dispersion':
                tt = np.array(prmd['types'])
                for k in range(dispersion.shape[0]):
                    typ = dispersion[k][0]
                    if typ in tt:  ## assumes type == class
                        ii = np.where(typ==tt)[0]
                        rtyp = tt[ii[0]]
                    else:
                        continue
                    prmd['dispersion'][ii[0]] = dispersion[k][1]
            elif term == 'repulsion':
                tt = np.array(prmd['types'])
                for k in range(repulsion.shape[0]):
                    typ = repulsion[k][0]
                    if typ in tt:  ## assumes type == class
                        ii = np.where(typ==tt)[0]
                        rtyp = tt[ii[0]]
                    else:
                        continue
                    prmd['repulsion'][ii[0]] = repulsion[k][1:]
            elif term == 'chgtrn':
                tt = np.array(prmd['types'])
                for k in range(chgtrn.shape[0]):
                    typ = chgtrn[k][0]
                    if typ in tt:  ## assumes type == class
                        ii = np.where(typ==tt)[0]
                        rtyp = tt[ii[0]]
                    else:
                        continue
                    prmd['chgtrn'][ii[0]] = chgtrn[k][1:]
            elif term == 'multipole':
                for ii,typs in enumerate(multipole[0]):
                    for kk,rtyps in enumerate(prmd[term][0]):
                        if typs == rtyps:
                            prmd[term][1][kk] = multipole[1][ii].copy()
                            break
            else:
                for k,val in enumerate(prmout[term][0]):
                    found = False
                    for p,r in enumerate(ref[0]):
                        if r == val:
                            for a in range(nref):
                                prmd[term][a][p] = prmout[term][a][k]
                            found = True
                            break
                    
                    if not found:
                        for a in range(nref):
                            prmd[term][a].append(prmout[term][a][k])
        
        return prmout,prmd

    else:
        return prmout

def write_key(prmfn,fnout,prmout=[],prmd={},opt='gas',path=""):
    deftprm = "~/tinker/params/hippo19.prm"
    currdir = os.getcwd()

    if len(path) > 0:
        currdir = path

    prmkey = prmfn
    if not os.path.isfile(prmfn) and not os.path.isfile(f"{currdir}/{prmfn}"):
        prmkey = deftprm
    
    if opt == 'liquid':
        keyfile = keyliq.replace("fn.prm",prmkey)
    else:
        keyfile = keygas.replace("fn.prm",prmkey)

    if len(prmout) == 0:
        with open(fnout,'w') as thefile:
            thefile.write(keyfile)
        return
    
    if len(prmd) == 0:
        if os.path.isfile(prmfn):
            prmdict = process_prm(prmfn)
        if os.path.isfile(f"{currdir}/{prmfn}"):
            prmdict = process_prm(f"{currdir}/{prmfn}")
    else:
        prmdict = prmd

    origtyp = np.array(prmdict['types'])
    sorttypes = np.argsort(origtyp)

    prmfile = ""
    term = 'atom'
    typcls = {}
    for k in sorttypes:
        t = prmdict['types'][k]
        v = prmdict[term][k]
        acls = int(v[0])
        typcls[t] = acls

        aline = f"{term:13s} {t:3d}  {acls:3d}    {v[1]:6s}"
        lnm = 28-len(v[2])
        v[2] = v[2].strip('"')
        aline += f'"{v[2]}"{" ":{lnm}s} {int(v[3]):3d} {float(v[4]):9.3f} {int(v[5]):4d}\n'
        prmfile += aline 
    prmfile+='\n'

    indpterms = ["bond",'angle','bndcflux','angcflux','multipole']
    typbterms = ["polarize","chgpen","dispersion","repulsion","chgtrn"]

    indp_ = []
    typb_ = []
    for term in prmout:
        if term in indpterms:
            indp_.append(term)
        if term in typbterms:
            typb_.append(term)
    
    if len(indp_):
        for term in prmout:
            if term == 'bond':
                for k,v in enumerate(prmdict[term][1]):
                    if isinstance(prmdict[term][0][k],str):
                        prmdict[term][0][k] = prmdict[term][0][k].split()
                    c = "  ".join(prmdict[term][0][k])
                    v2 = prmdict[term][2][k]
                    prmfile += f"{term:12s}  {c:<15s}{v:10.6f} {v2:10.6f}\n"
                prmfile+='\n'
            if term == 'angle':
                for k,v in enumerate(prmdict[term][1]):
                    if isinstance(prmdict[term][0][k],str):
                        prmdict[term][0][k] = prmdict[term][0][k].split()
                    c = "  ".join(prmdict[term][0][k])
                    v2 = prmdict[term][2][k]
                    prmfile += f"{term:12s}  {c:<15s}{v:10.6f} {v2:12.6f}\n"
                prmfile+='\n'
            if term == 'strbnd':
                for k,v in enumerate(prmdict[term][1]):
                    if isinstance(prmdict[term][0][k],str):
                        prmdict[term][0][k] = prmdict[term][0][k].split()
                    c = "  ".join(prmdict[term][0][k])
                    v2 = prmdict[term][2][k]
                    prmfile += f"{term:12s}{c:<16s}{v:10.6f} {v2:10.6f}\n"
                prmfile+='\n'
            if term == 'opbend':
                for k,v in enumerate(prmdict[term][1]):
                    if isinstance(prmdict[term][0][k],str):
                        prmdict[term][0][k] = prmdict[term][0][k].split()
                    c = "  ".join(prmdict[term][0][k])
                    prmfile += f"{term:12s}{c:<25s} {v:12.6f}\n"
                prmfile+='\n'
            if term == 'bndcflux':
                for k,v in enumerate(prmdict[term][1]):
                    if isinstance(prmdict[term][0][k],str):
                        prmdict[term][0][k] = prmdict[term][0][k].split()
                    c = "  ".join(prmdict[term][0][k])
                    prmfile += f"{term:12s}  {c:<15s}{v:10.6f}\n"
                prmfile+='\n'
            if term == 'angcflux':
                for k,v in enumerate(prmdict[term][1]):
                    if isinstance(prmdict[term][0][k],str):
                        prmdict[term][0][k] = prmdict[term][0][k].split()
                    c = "  ".join(prmdict[term][0][k])
                    prmfile += f"{term:12s}  {c:<15s}{v[0]:10.6f}{v[1]:10.6f}{v[2]:10.6f}{v[3]:10.6f}\n"
                prmfile+='\n'
            if term == 'multipole':
                for k,v in enumerate(prmdict[term][1]):
                    if isinstance(prmdict[term][0][k],str):
                        prmdict[term][0][k] = prmdict[term][0][k].split()
                    c = "  ".join(prmdict[term][0][k])
                    prmfile += f"{term:12s} {c:<15s}{v[0]:10.6f}\n"
                    prmfile += f"{' ':28s}{v[1]:10.6f}{v[2]:10.6f}{v[3]:10.6f}\n"
                    prmfile += f"{' ':28s}{v[4]:10.6f}\n"
                    prmfile += f"{' ':28s}{v[5]:10.6f}{v[6]:10.6f}\n"
                    v9 = -(v[4]+v[6])
                    prmfile += f"{' ':28s}{v[7]:10.6f}{v[8]:10.6f}{v9:10.6f}\n"
                prmfile += "\n"
    if len(typb_):
        for k,t in enumerate(prmdict['types']):
            acls = typcls[t]

            term = "polarize"
            if term in typbterms:
                v = prmdict[term][0][k]
                c = "  ".join(prmdict[term][1][k])
                prmfile += f"{term:16s} {t:<11d}{v:10.6f}  {c}\n"

            term = "chgpen"
            if term in typbterms or 'dispersion' in typbterms:
                v = prmdict[term][k][0]
                cp = prmdict[term][k][1]
                prmfile += f"{term:16s} {acls:<11d}{v:8.4f} {cp:11.6f}\n"

                v = prmdict[term][k]
                prmfile += f"{term:16s} {acls:<11d}{v:10.6f}{cp:10.6f}\n"

            term = "repulsion"
            if term in typbterms:
                v = prmdict[term][k]
                prmfile += f"{term:16s} {acls:<11d}{v[0]:10.6f}{v[1]:10.6f}{v[2]:10.6f}\n"

            term = "chgtrn"
            if term in typbterms:
                v = prmdict[term][k][0]
                c = prmdict[term][k][1]
                prmfile += f"{term:16s} {acls:<11d}{v:10.6f}{c:10.6f}\n"


    if len(fnout) == 0:
        return keyfile+prmfile

    else:
        with open(fnout,'w') as thefile:
            thefile.write(keyfile+prmfile)
            return

def write_prm(prmdict,fnout,mfactors=[]):

    #Sort the types in ascending order
    origtyp = np.array(prmdict['types'])
    sorttypes = np.argsort(origtyp)

    prmfile = headers['prmheader']+headers['atomdef']+'\n\n\n'
    
    term = 'atom'
    typcls = {}
    for k in sorttypes:
        t = prmdict['types'][k]
        v = prmdict[term][k]
        acls = int(v[0])
        typcls[t] = acls

        aline = f"{term:11s} {t:3d}  {acls:3d}    {v[1]:6s}"
        lnm = 28-len(v[2])
        v[2] = v[2].strip('"')
        aline += f'"{v[2]}"{" ":{lnm}s} {int(v[3]):3d} {float(v[4]):9.3f} {int(v[5]):4d}\n'
        prmfile += aline 
    
    term = "multipole"
    if len(prmdict[term][0]) > 0:
        prmfile += '\n\n'+headers[term]+'\n\n\n'
        # get charge factors
        factors = []
        if 'multipole_factors' in prmdict.keys():
            factors = np.array(prmdict['multipole_factors'],dtype=int)
        if len(mfactors) != 0:
            factors = np.array(mfactors,dtype=int)    
        if len(factors) == 0:
            factors = multipole_factors(prmdict)

        nmpol = factors.shape[0]
        l = ""
        for k in range(nmpol-1):
            if k != 0:
                l+='+'
            if factors[k] == 1:
                l += f'c{k+1}'
            else:
                l += f'{factors[k]}*c{k+1}'
        for k,v in enumerate(prmdict[term][1]):
            v2 = prmdict[term][0][k]

            if isinstance(v2,str):
                v2 = v2.split()
            c = ""
            for ts in v2:
                c += f"{int(ts):4d} "
            
            first_line = f"{term:11s}{c:<27s}{v[0]:10.6f}\n"
            if k == nmpol-1:
                if nmpol == 2:
                    first_line = f"{term:11s}{c:<27s}{v[0]:10.6f} # -{l}"
                elif nmpol > 2:
                    first_line = f"{term:11s}{c:<27s}{v[0]:10.6f} # -({l})"
                if factors[k] > 1:
                    first_line += f"/{factors[k]}\n"
                else:
                    first_line += f"\n"

            prmfile += first_line
            prmfile += f"{' ':38s}{v[1]:10.6f} {v[2]:10.6f} {v[3]:10.6f}\n"
            prmfile += f"{' ':38s}{v[4]:10.6f}\n"
            prmfile += f"{' ':38s}{v[5]:10.6f} {v[6]:10.6f}\n"
            v9 = -(v[4]+v[6])
            prmfile += f"{' ':38}{v[7]:10.6f} {v[8]:10.6f} {v9:10.6f}\n"
        
        # Multipole factors line
        l = f"[ {factors[0]}"
        for k,fc in enumerate(factors):
            if k > 0:
                l += f",{fc}"
        prmfile += f"## multipole_factors = {l} ] \n"

    term = 'polarize'
    if np.sum(prmdict[term][0]) != 0:
        prmfile += '\n\n'+headers[term]+'\n\n'
        for k in sorttypes:
            t = prmdict['types'][k]
            v = prmdict[term][0][k]
            v2 = prmdict[term][1][k]
            c = ""

            if isinstance(v2,list):
                for ts in v2:
                    c += f"  {int(ts):3d}"
            prmfile += f"{term:16s} {t:<11d}{v:10.6f}{c}\n"

    try:
        term = "vdw"
        if np.sum(prmdict[term]) != 0:
            prmfile += '\n\n'+headers[term]+'\n\n'
            for k in sorttypes:
                tt = prmdict['types'][k]
                t = typcls[tt]
                v = prmdict[term][k]
                prmfile += f"{term:16s} {t:<11d}{v[0]:8.4f} {v[1]:12.6f}\n"
    except:
        None
    try:
        term = "charge"
        if np.sum(prmdict[term]) != 0:
            prmfile += '\n\n'+headers[term]+'\n\n'
            for k in sorttypes:
                tt = prmdict['types'][k]
                t = typcls[tt]
                v = prmdict[term][k]
                prmfile += f"{term:16s} {t:<11d}{v:10.6f}\n"
    except:
        None
    
    term = "chgpen"
    if np.sum(prmdict[term]) > 0:
        prmfile += '\n\n'+headers[term]+'\n\n'
        for k in sorttypes:
            tt = prmdict['types'][k]
            t = typcls[tt]
            v = prmdict[term][k]
            prmfile += f"{term:16s} {t:<11d}{v[0]:8.4f} {v[1]:12.6f}\n"

    term = "dispersion"
    if np.sum(prmdict[term]) > 0:
        prmfile += '\n\n'+headers[term]+'\n\n'
        for k in sorttypes:
            tt = prmdict['types'][k]
            t = typcls[tt]
            cp = prmdict["chgpen"][k][1]
            v = prmdict[term][k]
            prmfile += f"{term:16s} {t:<11d}{v:10.6f} {cp:10.6f}\n"

    term = "repulsion"
    if np.sum(prmdict[term]) > 0:
        prmfile += '\n\n'+headers[term]+'\n\n'
        for k in sorttypes:
            tt = prmdict['types'][k]
            t = typcls[tt]
            v = prmdict[term][k]
            prmfile += f"{term:16s} {t:<11d}{v[0]:10.6f} {v[1]:10.6f} {v[2]:10.6f}\n"

    term = "chgtrn"
    if np.sum(prmdict[term]) > 0:
        prmfile += '\n\n'+headers[term]+'\n\n'
        for k in sorttypes:
            tt = prmdict['types'][k]
            t = typcls[tt]
            v = prmdict[term][k][0]
            c = prmdict[term][k][1]
            prmfile += f"{term:16s} {t:<11d}{v:10.6f} {c:10.6f}\n"

    term = "bond"
    if len(prmdict[term][0]) > 0:
        prmfile += '\n\n'+headers[term]+'\n\n'
        for k,v in enumerate(prmdict[term][1]):
            v1 = [int(a) for a in prmdict[term][0][k]]
            c = f"{v1[0]:3d}  {v1[1]:3d}"
            v2 = prmdict[term][2][k]
            prmfile += f"{term:12s}{c:<16s}{v:10.6f} {v2:10.6f}\n"
    
    term = "angle"
    if len(prmdict[term][0]) > 0:
        prmfile += '\n\n'+headers[term]+'\n\n'
        for k,v in enumerate(prmdict[term][1]):
            v1 = [int(a) for a in prmdict[term][0][k]]
            c = f"{v1[0]:3d}  {v1[1]:3d}  {v1[2]:3d}"
            v2 = prmdict[term][2][k]
            v3 = prmdict[term][3][k]

            prmfile += f"{term:12s}{c:<16s}{v:10.6f} {v2:10.3f}"
            if len(v3) > 0:
                prmfile += f" {v3:10s}\n"
            else:
                prmfile += '\n'
        
    term = "strbnd"
    if len(prmdict[term][0]) > 0:
        prmfile += '\n\n'+headers[term]+'\n\n'
        for k,v in enumerate(prmdict[term][1]):
            v1 = [int(a) for a in prmdict[term][0][k]]
            c = f"{v1[0]:3d}  {v1[1]:3d}  {v1[2]:3d}"
            v2 = prmdict[term][2][k]
            prmfile += f"{term:12s}{c:<16s}{v:10.6f} {v2:10.6f}\n"

    try:
        term = "ureybrad"
        if len(prmdict[term][0]) > 0:
            prmfile += '\n\n'+headers[term]+'\n\n'
            for k,v in enumerate(prmdict[term][1]):
                v1 = [int(a) for a in prmdict[term][0][k]]
                c = f"{v1[0]:3d}  {v1[1]:3d}  {v1[2]:3d}"
                v2 = prmdict[term][2][k]
                prmfile += f"{term:12s}{c:<16s}{v:10.6f} {v2:10.6f}\n"
    except:
        None

    term = "opbend"
    if len(prmdict[term][0]) > 0:
        prmfile += '\n\n'+headers[term]+'\n\n'
        for k,v in enumerate(prmdict[term][1]):
            v1 = [int(a) for a in prmdict[term][0][k]]
            c = f"{v1[0]:3d}  {v1[1]:3d}  {v1[2]:3d}  {v1[3]:3d}"
            prmfile += f"{term:12s}{c:<25s} {v:12.6f}\n"
    
    term = "torsion"
    if len(prmdict[term][0]) > 0:
        prmfile += '\n\n'+headers[term]+'\n\n'
        for k,v in enumerate(prmdict[term][1]):
            v1 = [int(a) for a in prmdict[term][0][k]]
            if np.sum(v1) == 0:
                continue
            c = f"{v1[0]:3d}  {v1[1]:3d}  {v1[2]:3d}  {v1[3]:3d}"
            lin = f"{term:12s}{c:<25s} "
            for i in range(0,len(v),3):
                v1 = v[i]
                v2 = v[i+1]
                v3 = int(v[i+2])
                lin += f"{v1:7.3f} {v2:2.1f} {v3:d}"
            prmfile += lin + '\n'
    
    try:
        term = "imptors"
        if len(prmdict[term][0]) > 0:
            prmfile += '\n\n'+headers[term]+'\n\n'
            for k,v in enumerate(prmdict[term][1]):
                v1 = [int(a) for a in prmdict[term][0][k]]
                c = f"{v1[0]:3d}  {v1[1]:3d}  {v1[2]:3d}  {v1[3]:3d}"
                lin = f"{term:12s}{c:<25s} "
                for i in range(0,len(v),3):
                    v1 = v[i]
                    v2 = v[i+1]
                    v3 = int(v[i+2])
                    lin += f"{v1:7.3f} {v2:2.1f} {v3:d}"
                prmfile += lin + '\n'
    except:
        None

    term = "bndcflux"
    if len(prmdict[term][0]) > 0:
        prmfile += '\n\n'+headers['cflux']+'\n\n'
        for k,v in enumerate(prmdict[term][1]):
            v1 = [int(a) for a in prmdict[term][0][k]]
            c = f"{v1[0]:3d}  {v1[1]:3d}"
            prmfile += f"{term:12s}{c:<16s}{v:10.6f}\n"
    term = "angcflux"
    if len(prmdict[term][0]) > 0:
        for k,v in enumerate(prmdict[term][1]):
            v1 = [int(a) for a in prmdict[term][0][k]]
            c = f"{v1[0]:3d}  {v1[1]:3d}  {v1[2]:3d}"
            prmfile += f"{term:12s}{c:<16s}{v[0]:10.6f} {v[1]:10.6f} {v[2]:10.6f} {v[3]:10.6f}\n"

    try:
        term = 'exchpol'
        if len(prmdict[term]) > 0:
            prmfile += '\n\n'+headers[term]+'\n\n'
            for vals in prmdict[term]:
                tt = int(vals[0])
                t = typcls[tt]
                v = vals[1:-1]
                ls = int(vals[-1])
                prmfile += f"{term:16s} {t:<11d}{v[0]:10.6f} {v[1]:10.6f} {v[2]:10.6f} {ls:<10d}\n"
    except:
        None

    with open(fnout,'w') as file:
        file.write(prmfile)

def update_types(newprms,maptypes,mapclas=None,fnout=None):
    # maptypes {old: new}
    updprms = copy.deepcopy(newprms)

    doclass = False
    typcls_old = {}
    #  typcls[t] = cl
    try:
        typcls_old = updprms['typcls']
    except:
        updprms['typcls'] = {}
        for k in range(len(updprms['types'])):
            t = updprms['types'][k]
            cl = int(updprms['atom'][k][0])
            typcls_old[t] = cl

            updprms['typcls'][t] = cl
    
    newmapclas = {0:0}
    typcls = {}
    oldcls = []
    newcls = []
    for t,cl in typcls_old.items():
        try:
            newcl = mapclas[cl]
        except:
            newcl = cl
        
        newmapclas[cl] = newcl
        oldcls.append(cl)
        newcls.append(newcl)

    clspos_old = np.argsort(oldcls)
    newcls = np.array(newcls)[clspos_old]
    clspos = np.argsort(newcls)
    
    updprms['typcls'] = {}
    typcls = {}
    atmpos_old = {}
    for k in range(len(newprms['types'])):
        old = newprms['types'][k]

        try:
            new = maptypes[old]
        except:
            maptypes[old] = old
            new = old
        
        updprms['types'][k] = new
        atmpos_old[new] = k

        oldcls = typcls_old[old] # class of old atom type
        newcl = newmapclas[oldcls]
        updprms['typcls'][new] = newcl
        typcls[new] = newcl

    

    newtypes = sorted(updprms['types'])
    updprms['types'] = newtypes
    natms = len(newprms['types'])
    polarize = [[0]*natms,[0]*natms]

    atoms = []
    classes = []
    for k in range(len(updprms['types'])):
        typ = updprms['types'][k]
        oldk = atmpos_old[typ]

        newcl = typcls[typ]
        classes.append(newcl)
        atmline = copy.deepcopy(newprms['atom'][oldk])
        atmline[0] = newcl
        atoms.append(atmline)
        #polarize
        if len(newprms['polarize'][1]) > 0:
            if isinstance(newprms['polarize'][1][oldk],list):
                v1 = [int(a) for a in newprms['polarize'][1][oldk]]
                vnew = [maptypes[a] for a in v1]
                polarize[1][k] = vnew

            polarize[0][k] = newprms['polarize'][0][oldk]
    
    updprms['polarize'] = polarize
    updprms['atom'] = atoms

    nparrays = ['vdw','charge','chgpen','dispersion','repulsion','chgtrn']

    ncls = len(classes)
    for k,oldk in enumerate(clspos):
        for term in nparrays:
            try:
                updprms[term][k] = newprms[term][oldk].copy()
            except:
                None

    terms_update = ['bond', 'angle', 'strbnd', 'ureybrad','opbend', 'torsion','imptors', 'bndcflux', 'angcflux']
    for term in terms_update:
        try:
            for k,line in enumerate(newprms[term][0]):
                v = [int(a) for a in line]
                vnew = [newmapclas[a] for a in v]
                updprms[term][0][k] = vnew
        except:
            None
        
    for k,line in enumerate(newprms['multipole'][0]):
        v = [int(a) for a in line]
        vnew = [maptypes[np.abs(a)] for a in v]
        
        for i in range(len(v)):
            if v[i] < 0:
                vnew[i] *= -1
        updprms['multipole'][0][k] = vnew

    if len(updprms['exchpol']) > 0:
        for k,vals in enumerate(updprms['exchpol']):
            old = int(vals[0])
            new = newmapclas[old]
            updprms['exchpol'][k][0] = float(new)
        
        nsort = np.argsort(updprms['exchpol'][:,0])
        updprms['exchpol'] = updprms['exchpol'][nsort]

    if fnout != None:
        write_prm(updprms,fnout)

    return updprms

def combine_params(dictlist,molnames,fnout=None):
    nmols = len(molnames)

    prmdict = dictlist[0]
    nm = molnames[0]
    newdict = copy.deepcopy(prmdict)
    for k,line in enumerate(prmdict['atom']):
        atomnm = line[2].strip('"')
        newname = f'"{nm}_{atomnm}"'
        newdict['atom'][k][2] = newname

    nparrays = ['vdw','charge','chgpen','dispersion','repulsion','chgtrn','exchpol']
    for n in range(1,nmols):
        nm = molnames[n]
        prmdict = dictlist[n]

        for term,vals in prmdict.items():
            if term == 'atom':
                nvals = copy.deepcopy(vals)
                for k,line in enumerate(vals):
                    atomnm = line[2].strip('"')
                    newname = f'"{nm}_{atomnm}"'
                    nvals[k][2] = newname
                newdict[term] += nvals
            
            elif term == 'types':
                newdict[term] += vals

            elif term in nparrays:
                try:
                    newdict[term] = np.append(newdict[term],vals,axis=0)
                except:
                    if term == 'exchpol':
                        newdict[term] = vals

            elif term == 'typcls':
                for t,cl in vals.items():
                    newdict[term][t] = cl
            elif term == 'multipole_factors':
                newdict[term] += vals
            else:
                for k in range(len(vals)):
                    newdict[term][k] += vals[k]

    for n in range(1,nmols):
        nm = molnames[n]
        prmdict = dictlist[n]

        for k,line in enumerate(prmdict['atom']):
            atomnm = line[2].strip('"')
            newname = f'"{nm}_{atomnm}"'
            prmdict['atom'][k][2] = newname

    if fnout != None:
        write_prm(newdict,fnout)

    return newdict

def update_xyztypes(xyzfn,fnout="",newcoords=[],maptypes=None):
    if isinstance(xyzfn,list):
        thefile = xyzfn
    else:
        test = xyzfn.split('\n')
        if len(test) > 2:
            thefile = test
        else:
            if os.path.isfile(xyzfn):
                f = open(xyzfn)
                thefile = f.readlines()
                f.close()
            else:
                print("XYZ file does not exist!")
                return

    newxyz = "".join(thefile[:1])
    for line in thefile[1:]:
        try:
            s = line.split()
            s[2] = float(s[2]) ## x
            s[3] = float(s[3]) ## y
            s[4] = float(s[4]) ## z
            s[0] = int(s[0]) ## atom ID
            s[5] = int(s[5]) ## type
        except:
            newxyz += line
            continue

        if len(newcoords) > 0:
            atomID = s[0]
            k = atomID-1

            s[2:5] = newcoords[k]   
        
        con = [int(a) for a in s[6:]]
        ## newtype
        if isinstance(maptypes,dict):
            try:
                s[5] = maptypes[s[5]]
            except:
                None
                
        newxyz += f"{s[0]:6d}  {s[1]:<2s} {s[2]:12.6f} {s[3]:12.6f} {s[4]:12.6f} {s[5]:5d}"
        for a in con:
            newxyz += f" {a:5d}"
            
        newxyz += '\n'

    if len(fnout) > 0:
        with open(fnout,'w') as outfile:
            outfile.write("".join(newxyz))  
    else:
        return newxyz

def combine_xyz(xyzfiles,fnout="",newcoords=[],maptypes=None,xyztitle='molecule'):

    newxyz = [""]
    total = 0
    for xyzfn in xyzfiles:
        if isinstance(xyzfn,list):
            infile = xyzfn
        else:
            test = xyzfn.split('\n')
            if len(test) > 2:
                infile = xyzfn.split('\n')
            else:
                if os.path.isfile(xyzfn):
                    f = open(xyzfn)
                    infile = f.readlines()
                    f.close()
                else:
                    print("XYZ file does not exist!")
                    return

        for line in infile[1:]:
            try:
                s = line.split()
                s[2] = float(s[2]) ## x
                s[3] = float(s[3]) ## y
                s[4] = float(s[4]) ## z
                s[0] = int(s[0]) + total ## atom ID
                s[5] = int(s[5]) ## type
            except:
                continue

            if len(newcoords) > 0:
                atomID = s[0]
                k = atomID-1

                s[2:5] = newcoords[k]      

            if isinstance(maptypes,dict):
                try:
                    s[5] = maptypes[s[5]]
                except:
                    None                                                                                                                                                                                                                                                                                                                                                                

            con = [int(a) for a in s[6:]]                
            newline = f"{s[0]:6d}  {s[1]:<2s} {s[2]:12.6f} {s[3]:12.6f} {s[4]:12.6f} {s[5]:5d}"
            for a in con:
                newline += f" {a+total:5d}"
                
            newline += '\n'
            newxyz.append(newline)

        n0 = int(infile[0].split()[0])
        total += n0
    
    newxyz[0] = f"{total:6d}  {xyztitle}\n"

    if len(fnout) > 0:
        with open(fnout,'w') as outfile:
            outfile.write("".join(newxyz))  
    else:
        return newxyz
    

def split_xyz(xyzfn,natms,writeout=True,fnout=[],newcoords=[],maptypes=None,xyztitle=[]):
    test = xyzfn.split('\n')
    bname = ""
    if len(test) > 2:
        infile = xyzfn.split('\n')
    else:
        try:
            f = open(xyzfn)
            infile = f.readlines()
            f.close()
            bname = xyzfn[:-4]
        except:
            print("XYZ file does not exist!")
            return
    
    title = " ".join(infile[0].split()[1:])
    
    xyzfiles = []
    start = 1
    for n in natms:
        mol = infile[start:n+start]
        xyzfiles.append(mol)
        start += n

    oldid = 0
    newfiles = []
    fnames = []
    for nmol,xyzf in enumerate(xyzfiles):
        if len(xyztitle) > 0:
            title=xyztitle[nmol]
            newxyz = [f" {natms[nmol]} {title} \n"]
        else:
            newxyz = [f" {natms[nmol]} {title}-mol{nmol+1} \n"]
        for k,line in enumerate(xyzf):
            try:
                s = line.split()
                s[2] = float(s[2]) ## x
                s[3] = float(s[3]) ## y
                s[4] = float(s[4]) ## z
                s[0] = k+1 ## atom ID
                s[5] = int(s[5]) ## type
            except:
                continue

            if len(newcoords) > 0:
                atomID = k+oldid

                s[2:5] = newcoords[atomID]      

            if isinstance(maptypes,dict):
                try:
                    s[5] = maptypes[s[5]]
                except:
                    None                                                                                                                                                                                                                                                                                                                                                                

            con = [int(a) for a in s[6:]]                
            newline = f"{s[0]:6d}  {s[1]:<2s} {s[2]:12.6f} {s[3]:12.6f} {s[4]:12.6f} {s[5]:5d}"
            for a in con:
                newline += f" {a-oldid:5d}"
                
            newline += '\n'
            newxyz.append(newline)
        newfiles.append(newxyz)
        oldid += natms[nmol]

        if len(bname) == 0:
            fnames.append(f"{xyztitle}-mol{nmol+1}.xyz")
        else:
            fnames.append(f"{bname}-mol{nmol+1}.xyz")
       
    if writeout:
        if len(fnout) != 0:
            fnames = fnout
        for k,fn in enumerate(fnames):
            with open(fn,'w') as outfile:
                outfile.write("".join(newfiles[k]))  
    else:
        return newfiles
    
def read_xyz_file(xyzfn,returnfile=False):
    if isinstance(xyzfn,list):
        thefile = xyzfn
    else:
        test = xyzfn.split('\n')
        if len(test) > 2:
            thefile = xyzfn.split('\n')
        else:
            if os.path.isfile(xyzfn):
                f = open(xyzfn)
                thefile = f.readlines()
                f.close()
            else:
                print("XYZ file does not exist!")
                return

    test1 = thefile[2].split()[0]
    ni = 0
    st = 2
    if test1.isdigit():
        ni = 1
    
    s = thefile[1].split()
    try:
        s[ni+1] = float(s[ni+1])
        s[ni+2] = float(s[ni+2])
        s[ni+3] = float(s[ni+3])
        if ni == 1:
            int(s[0])
        if s[ni].isalpha() and len(s[ni]) <= 2:
            st = 1
    except:
        None

    natms = int(thefile[0].split()[0])

    coords = []
    atommap = []
    tinkertypes = []
    for line in thefile[st:st+natms]:
        s = line.split()
        if len(s) == 0 or len(s) < 3:
            continue
        s[ni+1] = float(s[ni+1])
        s[ni+2] = float(s[ni+2])
        s[ni+3] = float(s[ni+3])
        s[ni] = ''.join([i for i in s[ni] if not i.isdigit()])
        atommap.append(s[ni])
        coords.append(s[ni+1:ni+4])

        if len(s) > 5:
            typ = s[ni+4] = int(s[ni+4])
            tinkertypes.append(typ)
    
    coords = np.array(coords)
    natm = coords.shape[0]
    if len(tinkertypes) > 0:
        info = list(zip(tinkertypes,atommap))

        if returnfile:
            return coords,info,thefile
        return coords,info
    else:
        if returnfile:
            return coords,np.array(atommap),thefile
        return coords,np.array(atommap)
    
def number_of_frames(xyzfn):
    if isinstance(xyzfn,list):
        thefile = xyzfn
        openfile = False
    else:
        test = xyzfn.split('\n')
        if len(test) > 2:
            thefile = xyzfn.split('\n')
            openfile = False
        else:
            if os.path.isfile(xyzfn):
                openfile = True
            else:
                print("XYZ file does not exist!")
                return

    if openfile:
        thefile = []
        lread = 0
        f = open(xyzfn)
        for a in range(3):
            thefile += f.readline()
            lread+=1
        f.close()

        thefile = "".join(thefile)
        thefile = thefile.split('\n')
    
    test = thefile[2].split()[0]
    if test.isdigit():
        st = 1
        ni = 1
    else:
        st = 2
        ni = 0

    natms = int(thefile[0].split()[0])
    nlines = st+natms

    if openfile:
        lread = 0
        with open(xyzfn) as thefile:
            for line in thefile:
                if line != '\n':
                    lread += 1
        
        nframes = lread/nlines
    else:
        thefile = [a for a in thefile if a != '\n']
        nframes = len(thefile)/nlines
    
    return nframes

def rawxyz_txyz(xyzfn,typemap,connect,fnout="",xyztitle='XYZ coords'):
    test = xyzfn.split('\n')
    if len(test) > 2:
        infile = xyzfn.split('\n')
    else:
        try:
            f = open(xyzfn)
            infile = f.readlines()
            f.close()
        except:
            print("XYZ file does not exist!")
            return
    
    if len(xyztitle) > 0:
        title = xyztitle
    else:
        title = infile[1].strip('\n')
    
    natm = int(infile[0].split()[0])
    
    newxyz = [f" {natm} {title} \n"]
    c = 0
    for k,line in enumerate(infile[2:]):
        s = line.split()
        if len(s) < 4:
            continue

        s[1] = float(s[1]) ## x
        s[2] = float(s[2]) ## y
        s[3] = float(s[3]) ## z
        typ = typemap[c][0]
        el = typemap[c][1]
        con = connect[c]
        
        atmid = c+1

        con = [int(a) for a in con]                
        newline = f"{atmid:6d}  {el:<2s} {s[1]:12.6f} {s[2]:12.6f} {s[3]:12.6f} {typ:5d}"
        for a in con:
            newline += f" {a+1:5d}"
            
        newline += '\n'
        newxyz.append(newline)
        c+=1
    
    newline += '\n'
    if len(fnout) > 0:
        with open(fnout,'w') as outfile:
            outfile.write("".join(newxyz))  
        return
    else:
        return newxyz

def rawxyz_txyz_notypes(xyzfn,fnout="",tinkerpath="~/tinker",xyztitle='XYZ coords'):
    bsdir = os.getcwd()
    test = xyzfn.split('\n')
    bname = ""
    if len(test) > 2:
        infile = xyzfn.split('\n')
    else:
        try:
            f = open(xyzfn)
            infile = f.readlines()
            f.close()
            bname = xyzfn[:-4]
        except:
            print("XYZ file does not exist!")
            return
    
    if len(xyztitle) > 0:
        title = xyztitle
    else:
        title = infile[1]
    
    natm = int(infile[0].split()[0])
    
    newxyz = [f" {natm} {title} \n"]
    c = 0
    for k,line in enumerate(infile[1:]):
        try:
            s = line.split()
            s[1] = float(s[1]) ## x
            s[2] = float(s[2]) ## y
            s[3] = float(s[3]) ## z
            c += 1
        except:
            continue
        
        atmid = c
        newline = f"{atmid:6d}  {s[0]:<2s} {s[1]:12.6f} {s[2]:12.6f} {s[3]:12.6f} \n"
        
        newxyz.append(newline)
    
    input_ ="""
9
8


"""
    if len(fnout) > 0:
        tt = fnout.split('/')
        if len(tt) > 2:
            fnout1 = tt[-1]
            destdir = "/".join(tt[:-1])
        else:
            fnout1 = fnout
            destdir = ""
    
    else:
        fnout1 = "test_tinkerfn.xyz"

    with open(f"{bsdir}/{fnout1}",'w') as outfile:
        outfile.write("".join(newxyz))

    with open(f"{bsdir}/input_tinker_conv10",'w') as outfile:
        outfile.write(input_)

    os.system(f"{tinkerpath}/bin/xyzedit {fnout1} < input_tinker_conv10")

    f = open(f"{fnout1}_2")
    xyzfinal = f.readlines()
    f.close()

    os.system(f"rm {fnout1}* input_tinker_conv10")

    if len(fnout) > 0:
        with open(fnout,'w') as outfile:
            outfile.write("".join(xyzfinal))  
        
        keyfn = f"{destdir}/{fnout1[:-4]}.key"
        keyin = f"""parameters  {tinkerpath}/basic.prm \n"""
        with open(keyfn,'w') as outfile:
            outfile.write(keyin)
    else:
        return xyzfinal

def write_rawxyz(xyzfn,fnout="",newcoords=[],xyztitle=''):
    """Use typeout txyz for tinker xyz"""
    coords,atommap,thefile = read_xyz_file(xyzfn,True)

    natms = coords.shape[0]

    newxyz = f"{natms}\n"
    if len(xyztitle) == 0:
        newxyz += "".join(thefile[1:2])
    else:
        newxyz += xyztitle.strip('\n') + '\n'
    
    for k,s in enumerate(coords):
        try:
            el = atommap[k][1]
        except:
            el = atommap[k]
        
        if len(newcoords) > 0:
            s = newcoords[k]   
                        
        newxyz += f"{el:2s}  {s[0]:12.6f} {s[1]:12.6f} {s[2]:12.6f} \n"
        
    if len(fnout) > 0:
        with open(fnout,'w') as outfile:
            outfile.write("".join(newxyz))  
    else:
        return newxyz
