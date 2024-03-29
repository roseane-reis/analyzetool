import copy
from hashlib import new
import numpy as np
import os
import sys
import math
from time import gmtime, strftime
import subprocess, threading

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
rep-14-scale            1.0
rep-15-scale            1.0
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

def process_prm(prmfn):
    
    f = open(prmfn)
    prmfile = f.readlines()
    f.close()
    
    prmfile = np.array(prmfile)
    prmfile = prmfile[prmfile != '\n']
    nstart = 0
    for k,line in enumerate(prmfile):
        if line[:6] == 'atom  ':
            nstart = k
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
    
    minds = np.where('multi' == bg)[0]
    
    mlines = []
    if len(minds) != 0:
        mlines = prmfile[minds[0]:minds[-1]+5] 
    
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
    for k in range(nclas):
        tl = int(cpen[k].split()[1])
        i = clspos[tl]
        v1 = float(cpen[k].split()[2])
        v2 = float(cpen[k].split()[3])
        chgpen[i] = [v1,v2]
        ##
        tl = int(disp[k].split()[1])
        i = clspos[tl]
        v1 = float(disp[k].split()[2])
        dispersion[i] = v1
        ##
        tl = int(rep[k].split()[1])
        i = clspos[tl]
        v1 = float(rep[k].split()[2])
        v2 = float(rep[k].split()[3])
        v3 = float(rep[k].split()[4])
        repulsion[i] = [v1,v2,v3]
        ##
        tl = int(ctrn[k].split()[1])
        i = clspos[tl]
        v1 = float(ctrn[k].split()[2])
        v2 = float(ctrn[k].split()[3])
        chgtrn[i] = [v1,v2]
    
    for k in range(natms):
        s = pol[k].split()
        i = atmpos[int(s[1])]
        v1 = float(s[2])
        polarize[0][i] = v1
        polarize[1][i] = s[3:]        
        ##

    if len(mlines) > 0:    
        for i,line in enumerate(mlines[::5]):
            typs = line.split()[1:-1]
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
        typs = s[1:4]
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
            'opbend': opbend,
            'torsion': torsion,
            'chgpen': chgpen,
            'dispersion': dispersion,
            'repulsion': repulsion,
            'polarize': polarize,
            'bndcflux': bndcflux,
            'angcflux': angcflux,
            'chgtrn': chgtrn,
            'multipole': multipoles,
            'exchpol': np.asarray(exchpol)  }


    return prmdict

def write_prm(prmdict,fnout):

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
    prmfile += '\n\n'+headers[term]+'\n\n\n'
    for k,v in enumerate(prmdict[term][1]):
        v2 = prmdict[term][0][k]
        c = ""
        for ts in v2:
            c += f"{int(ts):4d} "
        prmfile += f"{term:11s}{c:<27s}{v[0]:10.6f}\n"
        prmfile += f"{' ':38s}{v[1]:10.6f} {v[2]:10.6f} {v[3]:10.6f}\n"
        prmfile += f"{' ':38s}{v[4]:10.6f}\n"
        prmfile += f"{' ':38s}{v[5]:10.6f} {v[6]:10.6f}\n"
        v9 = -(v[4]+v[6])
        prmfile += f"{' ':38}{v[7]:10.6f} {v[8]:10.6f} {v9:10.6f}\n"
    
    term = 'polarize'
    prmfile += '\n\n'+headers[term]+'\n\n'
    for k in sorttypes:
        t = prmdict['types'][k]
        v = prmdict[term][0][k]
        v2 = prmdict[term][1][k]
        c = ""
        for ts in v2:
            c += f"  {int(ts):3d}"
        prmfile += f"{term:16s} {t:<11d}{v:10.6f}{c}\n"

    term = "chgpen"
    prmfile += '\n\n'+headers[term]+'\n\n'
    for k in sorttypes:
        tt = prmdict['types'][k]
        t = typcls[tt]
        v = prmdict[term][k]
        prmfile += f"{term:16s} {t:<11d}{v[0]:8.4f} {v[1]:12.6f}\n"

    term = "dispersion"
    prmfile += '\n\n'+headers[term]+'\n\n'
    for k in sorttypes:
        tt = prmdict['types'][k]
        t = typcls[tt]
        cp = prmdict["chgpen"][k][1]
        v = prmdict[term][k]
        prmfile += f"{term:16s} {t:<11d}{v:10.6f} {cp:10.6f}\n"

    term = "repulsion"
    prmfile += '\n\n'+headers[term]+'\n\n'
    for k in sorttypes:
        tt = prmdict['types'][k]
        t = typcls[tt]
        v = prmdict[term][k]
        prmfile += f"{term:16s} {t:<11d}{v[0]:10.6f} {v[1]:10.6f} {v[2]:10.6f}\n"

    term = "chgtrn"
    prmfile += '\n\n'+headers[term]+'\n\n'
    for k in sorttypes:
        tt = prmdict['types'][k]
        t = typcls[tt]
        v = prmdict[term][k][0]
        c = prmdict[term][k][1]
        prmfile += f"{term:16s} {t:<11d}{v:10.6f} {c:10.6f}\n"

    term = "bond"
    prmfile += '\n\n'+headers[term]+'\n\n'
    # if term in prmdict.keys():
    for k,v in enumerate(prmdict[term][1]):
        v1 = [int(a) for a in prmdict[term][0][k]]
        c = f"{v1[0]:3d}  {v1[1]:3d}"
        v2 = prmdict[term][2][k]
        prmfile += f"{term:12s}{c:<16s}{v:10.6f} {v2:10.6f}\n"
    
    term = "angle"
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
    prmfile += '\n\n'+headers[term]+'\n\n'
    for k,v in enumerate(prmdict[term][1]):
        v1 = [int(a) for a in prmdict[term][0][k]]
        c = f"{v1[0]:3d}  {v1[1]:3d}  {v1[2]:3d}"
        v2 = prmdict[term][2][k]
        prmfile += f"{term:12s}{c:<16s}{v:10.6f} {v2:10.6f}\n"

    term = "opbend"
    prmfile += '\n\n'+headers[term]+'\n\n'
    for k,v in enumerate(prmdict[term][1]):
        v1 = [int(a) for a in prmdict[term][0][k]]
        c = f"{v1[0]:3d}  {v1[1]:3d}  {v1[2]:3d}  {v1[3]:3d}"
        prmfile += f"{term:12s}{c:<25s} {v:12.6f}\n"
    
    term = "torsion"
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

    term = "bndcflux"
    prmfile += '\n\n'+headers['cflux']+'\n\n'
    for k,v in enumerate(prmdict[term][1]):
        v1 = [int(a) for a in prmdict[term][0][k]]
        c = f"{v1[0]:3d}  {v1[1]:3d}"
        prmfile += f"{term:12s}{c:<16s}{v:10.6f}\n"
    term = "angcflux"
    for k,v in enumerate(prmdict[term][1]):
        v1 = [int(a) for a in prmdict[term][0][k]]
        c = f"{v1[0]:3d}  {v1[1]:3d}  {v1[2]:3d}"
        prmfile += f"{term:12s}{c:<16s}{v[0]:10.6f} {v[1]:10.6f} {v[2]:10.6f} {v[3]:10.6f}\n"

    term = 'exchpol'
    if len(prmdict[term]) > 0:
        prmfile += '\n\n'+headers[term]+'\n\n'
        for vals in prmdict[term]:
            tt = int(vals[0])
            t = typcls[tt]
            v = vals[1:-1]
            ls = int(vals[-1])
            prmfile += f"{term:16s} {t:<11d}{v[0]:10.6f} {v[1]:10.6f} {v[2]:10.6f} {ls:<10d}\n"

    with open(fnout,'w') as file:
        file.write(prmfile)

def update_types(newprms,maptypes,mapclas=None,fnout=None):
    # maptypes {old: new}
    updprms = copy.deepcopy(newprms)

    doclass = False
    typcls_old = {}
    #  typcls[t] = cl
    try:
        typcls_old = newprms['typcls']
    except:
        newprms['typcls'] = {}
        for k in range(len(newprms['types'])):
            t = newprms['types'][k]
            cl = int(newprms['atom'][k][0])
            typcls_old[t] = cl

            newprms['typcls'][t] = cl
    
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
        atmline = newprms['atom'][oldk]
        atmline[0] = newcl
        atoms.append(atmline)
        #polarize
        v1 = [int(a) for a in newprms['polarize'][1][oldk]]
        vnew = [maptypes[a] for a in v1]

        polarize[0][k] = newprms['polarize'][0][oldk]
        polarize[1][k] = vnew

        print(k,oldk,atmline,newcl,typ)
    
    updprms['polarize'] = polarize
    updprms['atom'] = atoms

    nparrays = ['chgpen','dispersion','repulsion','chgtrn']

    ncls = len(classes)
    for k,oldk in enumerate(clspos):
        for term in nparrays:
            updprms[term][k] = newprms[term][oldk].copy()


    terms_update = ['bond', 'angle', 'strbnd', 'opbend', 'torsion','bndcflux', 'angcflux']
    for term in terms_update:
        for k,line in enumerate(newprms[term][0]):
            v = [int(a) for a in line]
            vnew = [newmapclas[a] for a in v]
            updprms[term][0][k] = vnew
        
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

    nparrays = ['chgpen','dispersion','repulsion','chgtrn','exchpol']
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

    test = xyzfn.split('\n')
    if len(test) > 2:
        infile = xyzfn
    else:
        try:
            f = open(xyzfn)
            infile = f.readlines()
            f.close()
        except:
            print("XYZ file does not exist!")
            return

    newxyz = "".join(infile[:1])
    for line in infile[1:]:
        try:
            s = line.split()
            s[2] = float(s[2]) ## x
            s[3] = float(s[3]) ## y
            s[4] = float(s[4]) ## z
            s[0] = int(s[0]) ## atom ID
            s[5] = int(s[5]) ## type
        except:
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
        test = xyzfn.split('\n')
        if len(test) > 2:
            infile = xyzfn
        else:
            try:
                f = open(xyzfn)
                infile = f.readlines()
                f.close()
            except:
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
    

def split_xyz(xyzfn,natms,writeout=True,fnout=[],newcoords=[],maptypes=None,xyztitle=''):
    test = xyzfn.split('\n')
    bname = ""
    if len(test) > 2:
        infile = xyzfn
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
    