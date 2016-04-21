import sys

# os.environ['R_LIBS_USER'] = '/project/projectdirs/metatlas/r_pkgs/'
curr_ld_lib_path = ''

# os.environ['LD_LIBRARY_PATH'] = curr_ld_lib_path + ':/project/projectdirs/openmsi/jupyterhub_libs/boost_1_55_0/lib' + ':/project/projectdirs/openmsi/jupyterhub_libs/lib'

# sys.path.insert(0, '/project/projectdirs/metatlas/python_pkgs/')
sys.path.insert(0,'/global/project/projectdirs/metatlas/anaconda/lib/python2.7/site-packages' )

from metatlas import metatlas_objects as metob
from metatlas import h5_query as h5q
sys.path.append('/global/project/projectdirs/openmsi/jupyterhub_libs/anaconda/lib/python2.7/site-packages')

import qgrid

from matplotlib import pyplot as plt
import pandas as pd
import os
import tables
import pickle


import dill

import numpy as np

from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem import Draw
# from rdkit.Chem.rdMolDescriptors import ExactMolWt
from rdkit.Chem import Descriptors
from rdkit.Chem import rdMolDescriptors
from rdkit.Chem import AllChem
from rdkit.Chem import Draw
from rdkit.Chem import rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D
from rdkit.Chem.Draw import IPythonConsole
from IPython.display import SVG,display




#import sys
#from metatlas import metatlas_objects as metob
#from metatlas import h5_query as h5q
#import qgrid
from matplotlib import pyplot as plt
#import pandas as pd
import re
import os
#import tables
#import pickle
import dill
import numpy as np
#from rdkit import Chem
#from rdkit.Chem import AllChem
#from rdkit.Chem import Draw
## from rdkit.Chem.rdMolDescriptors import ExactMolWt
#from rdkit.Chem import Descriptors
#from rdkit.Chem import rdMolDescriptors
#from rdkit.Chem import AllChem
#from rdkit.Chem import Draw
#from rdkit.Chem import rdDepictor
#from rdkit.Chem.Draw import rdMolDraw2D
#from rdkit.Chem.Draw import IPythonConsole
#from IPython.display import SVG,display
from collections import defaultdict
#import time
#from textwrap import wrap
#from matplotlib.backends.backend_pdf import PdfPages
import os.path
from itertools import cycle


    
def getcommonletters(strlist):
    """
    Parameters
    ----------
    strlist

    Returns
    -------

    """
    return ''.join([x[0] for x in zip(*strlist) if reduce(lambda a,b:(a == b) and a or None,x)])


def findcommonstart(strlist):
    """
    Parameters
    ----------
    strlist

    Returns
    -------

    """
    strlist = strlist[:]
    prev = None
    while True:
        common = getcommonletters(strlist)
        if common == prev:
            break
        strlist.append(common)
        prev = common

    return getcommonletters(strlist)


def get_data(fname):
    """
    Parameters
    ----------
    fname

    Returns
    -------

    """
    with open(fname,'r') as f:
        data = dill.load(f)

    return data


def get_group_names(data):
    """
    Parameters
    ----------
    data

    Returns
    -------

    """
    group_names = []
    for i,d in enumerate(data):
        newstr = d[0]['group'].name
        group_names.append(newstr)

    return group_names


def get_file_names(data):
    """
    Parameters
    ----------
    data

    Returns
    -------

    """
    file_names = []
    for i,d in enumerate(data):
        newstr = os.path.basename(d[0]['lcmsrun'].hdf5_file)
        file_names.append(newstr)
   
    return file_names


def get_compound_names(data):
    """
    Parameters
    ----------
    data

    Returns
    -------

    """
    compound_names = []
    compound_objects = []
    for i,d in enumerate(data[0]):
        # if label: use label
        # else if compound: use compound name
        # else no name
        compound_objects.append(d['identification'])
        if len(d['identification'].compound) > 0:
            _str = d['identification'].compound[0].name
        else:
            _str = d['identification'].name
        newstr = '%s_%s_%s_%5.2f'%(_str,d['identification'].mz_references[0].detected_polarity,
                d['identification'].mz_references[0].adduct,d['identification'].rt_references[0].rt_peak)
        newstr = re.sub('\.', 'p', newstr) #2 or more in regexp

        newstr = re.sub('[\[\]]','',newstr)
        newstr = re.sub('[^A-Za-z0-9+-]+', '_', newstr)
        newstr = re.sub('i_[A-Za-z]+_i_', '', newstr)
        if newstr[0] == '_':
            newstr = newstr[1:]
        if newstr[0] == '-':
            newstr = newstr[1:]
        if newstr[-1] == '_':
            newstr = newstr[:-1]

        newstr = re.sub('[^A-Za-z0-9]{2,}', '', newstr) #2 or more in regexp
        compound_names.append(newstr)

    #If duplicate compound names exist, then append them with a number
    D = defaultdict(list)
    for i,item in enumerate(compound_names):
        D[item].append(i)
    D = {k:v for k,v in D.items() if len(v)>1}
    for k in D.keys():
        for i,f in enumerate(D[k]):
            compound_names[f] = '%s%d'%(compound_names[f],i)
   
    return (compound_names, compound_objects)


def plot_all_compounds_for_each_file(**kwargs):
    """
    Parameters
    ----------
    kwargs

    Returns
    -------

    """
    data = get_data(os.path.expandvars(kwargs['input_fname']))
    compound_names = get_compound_names(data)[0]
    file_names = get_file_names(data)

    nCols = kwargs['nCols']
    scale_y = kwargs['scale_y']
    output_loc = os.path.expandvars(kwargs['output_loc'])
#
#    data = kwargs['data']
#    nCols = kwargs['nCols']
#    file_names = kwargs['file_names']
#    compound_names = kwargs['compound_names']
#    scale_y = kwargs['scale_y']
#    output_fname = kwargs['output_fname']

    nRows = int(np.ceil(len(compound_names)/float(nCols)))
    print nRows
    print len(compound_names) 
    
    xmin = 0
    xmax = 210
    subrange = float(xmax-xmin)/float(nCols) # scale factor for the x-axis
 
    y_max = list()
    if scale_y:
        for file_idx,my_file in enumerate(file_names):
            temp = -1
            counter = 0
            for compound_idx,compound in enumerate(compound_names):
                d = data[file_idx][compound_idx]
                if len(d['data']['eic']['rt']) > 0:
                    counter += 1
                    y = max(d['data']['eic']['intensity'])
                    if y > temp:
                        temp = y
            #y_max.append(temp)
            y_max += [temp] * counter
    else:
        for file_idx,my_file in enumerate(file_names):
            for compound_idx,compound in enumerate(compound_names):
                d = data[file_idx][compound_idx]
                if len(d['data']['eic']['rt']) > 0:
                    y_max.append(max(d['data']['eic']['intensity']))
    y_max = cycle(y_max)




    # create ouput dir
    if not os.path.exists(output_loc):
        os.makedirs(output_loc)


    for file_idx,my_file in enumerate(file_names):
        ax = plt.subplot(111)#, aspect='equal')
        plt.setp(ax, 'frame_on', False)
        ax.set_ylim([0, nRows+4])
      
        col = 0
        row = nRows+3
        counter = 1
        
        for compound_idx,compound in enumerate(compound_names):  
            if col == nCols:
                row -= 1.3
                col = 0
                        
            d = data[file_idx][compound_idx]

            rt_min = d['identification'].rt_references[0].rt_min
            rt_max = d['identification'].rt_references[0].rt_max
            rt_peak = d['identification'].rt_references[0].rt_peak

            if len(d['data']['eic']['rt']) > 0:
                x = d['data']['eic']['rt']
                y = d['data']['eic']['intensity']
                y = y/y_max.next()
                new_x = (x-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2) ## remapping the x-range
                xlbl = np.array_str(np.linspace(min(x), max(x), 8), precision=2)
                rt_min_ = (rt_min-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2)
                rt_max_ = (rt_max-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2)
                rt_peak_ = (rt_peak-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2)
                ax.plot(new_x, y+row,'k-')#,ms=1, mew=0, mfc='b', alpha=1.0)]
                #ax.annotate('plot={}'.format(col+1),(max(new_x)/2+col*subrange,row-0.1), size=5,ha='center')
                ax.annotate(xlbl,(min(new_x),row-0.1), size=2)
                ax.annotate('{0},{1},{2},{3}'.format(compound,rt_min, rt_peak, rt_max),(min(new_x),row-0.2), size=2)#,ha='center')
                myWhere = np.logical_and(new_x>=rt_min_, new_x<=rt_max_ )
                ax.fill_between(new_x,min(y)+row,y+row,myWhere, facecolor='c', alpha=0.3)
                col += 1
            else:
                new_x = (x-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2) ## remapping the x-range
                ax.plot(new_x, new_x-new_x+row,'r-')#,ms=1, mew=0, mfc='b', alpha=1.0)]
                ax.annotate(compound,(min(new_x),row-0.1), size=2)
                col += 1
            counter += 1
        
        plt.title(my_file)
        fig = plt.gcf()
        fig.set_size_inches(11, 8.5)
        #fig.savefig('/home/jimmy/ben2/neg/' + my_file + '-' + str(counter) + '.pdf')
        fig.savefig(os.path.join(output_loc, my_file + '-' + str(counter) + '.pdf'))
        plt.clf()


def plot_all_files_for_each_compound(**kwargs):
    """
    Parameters
    ----------
    kwargs

    Returns
    -------

    """

    data = get_data(os.path.expandvars(kwargs['input_fname']))
    compound_names = get_compound_names(data)[0]
    file_names = get_file_names(data)
    nCols = kwargs['nCols']
    scale_y = kwargs['scale_y']
    output_loc = os.path.expandvars(kwargs['output_loc'])

    nRows = int(np.ceil(len(file_names)/float(nCols)))
    print 'nrows = ', nRows 
    
    xmin = 0
    xmax = 210
    subrange = float(xmax-xmin)/float(nCols) # scale factor for the x-axis
 

    y_max = list()
    if scale_y:
        for compound_idx,compound in enumerate(compound_names):
            temp = -1
            counter = 0
            for file_idx,my_file in enumerate(file_names):
                d = data[file_idx][compound_idx]
                if len(d['data']['eic']['rt']) > 0:
                    counter += 1
                    y = max(d['data']['eic']['intensity'])
                    if y > temp:
                        temp = y
            y_max += [temp] * counter
    else:
        for compound_idx,compound in enumerate(compound_names):
            for file_idx,my_file in enumerate(file_names):
                d = data[file_idx][compound_idx]
                if len(d['data']['eic']['rt']) > 0:
                    y_max.append(max(d['data']['eic']['intensity']))

    print "length of ymax is ", len(y_max)
    y_max = cycle(y_max)



    # create ouput dir
    if not os.path.exists(output_loc):
        os.makedirs(output_loc)

    for compound_idx,compound in enumerate(compound_names):
        ax = plt.subplot(111)#, aspect='equal')
        plt.setp(ax, 'frame_on', False)
        ax.set_ylim([0, nRows+7])
      
        col = 0
        row = nRows+6
        counter = 1
        
        for file_idx,my_file in enumerate(file_names):  
            if col == nCols:
                row -= 1.3
                col = 0
                        
            d = data[file_idx][compound_idx]
            #file_name = compound_names[compound_idx]
                    
            rt_min = d['identification'].rt_references[0].rt_min
            rt_max = d['identification'].rt_references[0].rt_max
            rt_peak = d['identification'].rt_references[0].rt_peak

            if len(d['data']['eic']['rt']) > 0:
                x = d['data']['eic']['rt']
                y = d['data']['eic']['intensity']
                y = y/y_max.next()
                new_x = (x-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2) ## remapping the x-range
                xlbl = np.array_str(np.linspace(min(x), max(x), 8), precision=2)
                rt_min_ = (rt_min-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2)
                rt_max_ = (rt_max-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2)
                rt_peak_ = (rt_peak-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2)
                ax.plot(new_x, y+row,'k-')#,ms=1, mew=0, mfc='b', alpha=1.0)]
                #ax.annotate('plot={}'.format(col+1),(max(new_x)/2+col*subrange,row-0.1), size=5,ha='center')
                ax.annotate(xlbl,(min(new_x),row-0.1), size=2)
                ax.annotate('{0},{1},{2},{3}'.format(my_file,rt_min, rt_peak, rt_max),(min(new_x),row-0.2), size=2)#,ha='center')
                myWhere = np.logical_and(new_x>=rt_min_, new_x<=rt_max_ )
                ax.fill_between(new_x,min(y)+row,y+row,myWhere, facecolor='c', alpha=0.3)
                col += 1
            else:
                new_x = (x-x[0])*subrange/float(x[-1]-x[0])+col*(subrange+2) ## remapping the x-range
                ax.plot(new_x, y-y+row,'r-')#,ms=1, mew=0, mfc='b', alpha=1.0)]
                ax.annotate(my_file,(min(new_x),row-0.1), size=1)
                col += 1
            counter += 1
        
        plt.title(compound)
        fig = plt.gcf()
        fig.set_size_inches(11, 8.5)
        #fig.savefig('/tmp/' + compound + '-' + str(counter) + '.pdf')
        fig.savefig(os.path.join(output_loc, compound + '-' + str(counter) + '.pdf'))
        plt.clf()


        
  


""" contribution from Hans de Winter """
def _InitialiseNeutralisationReactions():
    patts= (
        # Imidazoles
        ('[n+;H]','n'),
        # Amines
        ('[N+;!H0]','N'),
        # Carboxylic acids and alcohols
        ('[$([O-]);!$([O-][#7])]','O'),
        # Thiols
        ('[S-;X1]','S'),
        # Sulfonamides
        ('[$([N-;X2]S(=O)=O)]','N'),
        # Enamines
        ('[$([N-;X2][C,N]=C)]','N'),
        # Tetrazoles
        ('[n-]','[nH]'),
        # Sulfoxides
        ('[$([S-]=O)]','S'),
        # Amides
        ('[$([N-]C=O)]','N'),
        )
    return [(Chem.MolFromSmarts(x),Chem.MolFromSmiles(y,False)) for x,y in patts]

_reactions=None
def NeutraliseCharges(mol, reactions=None):
    global _reactions
    if reactions is None:
        if _reactions is None:
            _reactions=_InitialiseNeutralisationReactions()
        reactions=_reactions
#     mol = Chem.MolFromSmiles(smiles)
    replaced = False
    for i,(reactant, product) in enumerate(reactions):
        while mol.HasSubstructMatch(reactant):
            replaced = True
            rms = AllChem.ReplaceSubstructs(mol, reactant, product)
            rms_smiles = Chem.MolToSmiles(rms[0])
            mol = Chem.MolFromSmiles(rms_smiles)
    if replaced:
        return (mol, True) #Chem.MolToSmiles(mol,True)
    else:
        return (mol, False)
def drawStructure_ShowingFragment(pactolus_tree,fragment_idx,myMol,myMol_w_Hs):

    drawer = rdMolDraw2D.MolDraw2DSVG(600,300)

    fragment_atoms = np.where(pactolus_tree[fragment_idx]['atom_bool_arr'])[0]
    mark_atoms_no_H = []
    for a_index in fragment_atoms:
        if myMol_w_Hs.GetAtomWithIdx(a_index).GetSymbol() != 'H':
            mark_atoms_no_H.append(a_index)

    rdDepictor.Compute2DCoords(myMol)

    drawer.DrawMolecule(myMol,highlightAtoms=mark_atoms_no_H)
    drawer.FinishDrawing()
    svg = drawer.GetDrawingText().replace('svg:','')
    return svg

def drawStructure_Fragment(pactolus_tree,fragment_idx,myMol,myMol_w_Hs):
    fragment_atoms = np.where(pactolus_tree[fragment_idx]['atom_bool_arr'])[0]
    depth_of_hit = np.sum(pactolus_tree[fragment_idx]['bond_bool_arr'])
    mol2 = deepcopy(myMol_w_Hs)
    # Now set the atoms you'd like to remove to dummy atoms with atomic number 0
    fragment_atoms = np.where(pactolus_tree[fragment_idx]['atom_bool_arr']==False)[0]
    for f in fragment_atoms:
        mol2.GetAtomWithIdx(f).SetAtomicNum(0)

    # Now remove dummy atoms using a query
    mol3 = Chem.DeleteSubstructs(mol2, Chem.MolFromSmarts('[#0]'))
    mol3 = Chem.RemoveHs(mol3)
    # You get what you are looking for
    return moltosvg(mol3),depth_of_hit


def moltosvg(mol,molSize=(450,150),kekulize=True):
    mc = Chem.Mol(mol.ToBinary())
    if kekulize:
        try:
            Chem.Kekulize(mc)
        except:
            mc = Chem.Mol(mol.ToBinary())
    if not mc.GetNumConformers():
        rdDepictor.Compute2DCoords(mc)
    drawer = rdMolDraw2D.MolDraw2DSVG(molSize[0],molSize[1])
    drawer.DrawMolecule(mc)
    drawer.FinishDrawing()
    svg = drawer.GetDrawingText()
    # It seems that the svg renderer used doesn't quite hit the spec.
    # Here are some fixes to make it work in the notebook, although I think
    # the underlying issue needs to be resolved at the generation step
    return svg.replace('svg:','')

def get_ion_from_fragment(frag_info,spectrum):
    hit_indices = np.where(np.sum(frag_info,axis=1))
    hit = spectrum[hit_indices,:][0]
    return hit,hit_indices



#plot msms and annotate
#compound name
#formula
#adduct
#theoretical m/z
#histogram of retention times
#scatter plot of retention time with peak area
#retention time
#print all chromatograms
#structure

def make_output_dataframe(**kwargs):
    data = get_data(os.path.expandvars(kwargs['input_fname']))
    compound_names = get_compound_names(data)[0]
    file_names = get_file_names(data)
    group_names = get_group_names(data)
    output_loc = os.path.expandvars(kwargs['output_loc'])
    fieldname = kwargs['fieldname']
    
    if not os.path.exists(output_loc):
        os.makedirs(output_loc)
    
    df = pd.DataFrame( index=compound_names, columns=file_names, dtype=float)

    # peak_height['compound'] = compound_list
    # peak_height.set_index('compound',drop=True)
    for i,dd in enumerate(data):
        for j,d in enumerate(dd):
            if not d['data']['ms1_summary'][fieldname]:
                df.ix[compound_names[j],file_names[i]] = 0
            else:
                df.ix[compound_names[j],file_names[i]] = d['data']['ms1_summary'][fieldname]  
    columns = []
    for i,f in enumerate(file_names):
        columns.append((group_names[i],f))
    df.columns = pd.MultiIndex.from_tuples(columns,names=['group', 'file'])

    df.to_csv(os.path.join(output_loc, fieldname + '.tab'),sep='\t')
    return df

def file_with_max_precursor_intensity(data,compound_idx):
    idx = []
    my_max = 0
    for i,d in enumerate(data):
        if type(d[compound_idx]['data']['msms']['data']) != list:#.has_key('precursor_intensity'):
            temp = d[compound_idx]['data']['msms']['data']
            m = np.max(temp['precursor_intensity'])
            if m > my_max:
                my_max = m
                idx = i
    return idx,my_max

def plot_errorbar_plots(df,**kwargs):#df,compound_list,project_label):
    
    data = get_data(os.path.expandvars(kwargs['input_fname']))
    compound_names = get_compound_names(data)[0]
    file_names = get_file_names(data)
    output_loc = os.path.expandvars(kwargs['output_loc'])
    
    if not os.path.exists(output_loc):
        os.makedirs(output_loc)
        

    for compound in compound_names:
        m = df.ix[compound].groupby(level='group').mean()
        e = df.ix[compound].groupby(level='group').std()
        c = df.ix[compound].groupby(level='group').count()

        for i in range(len(e)):
            if c[i]>0:
                e[i] = e[i] / c[i]**0.5

        f, ax = plt.subplots(1, 1,figsize=(20,12))
        m.plot(yerr=e, kind='bar',ax=ax)
        ax.set_title(compound,fontsize=12,weight='bold')
        plt.tight_layout()
        f.savefig(os.path.join(output_loc, compound + '_errorbar.pdf'))

        f.clear()
        plt.close('all')#f.clear()


def make_identification_figure(**kwargs):#data,file_idx,compound_idx,export_name,project_label):
    #  d = 'data/%s/identification/'%project_label
    
    data = get_data(os.path.expandvars(kwargs['input_fname']))
    compound_names = get_compound_names(data)[0]
    file_names = get_file_names(data)
    output_loc = os.path.expandvars(kwargs['output_loc'])
    
    if not os.path.exists(output_loc):
        os.makedirs(output_loc)
    
    
    for compound_idx in range(len(compound_names)):
        file_idx, m = file_with_max_precursor_intensity(data,compound_idx)
        if m:
            fig = plt.figure(figsize=(20,20))
        #     fig = plt.figure()
            ax = fig.add_subplot(211)
            ax.set_title(compound_names[compound_idx],fontsize=12,weight='bold')
            ax.set_xlabel('m/z',fontsize=12,weight='bold')
            ax.set_ylabel('intensity',fontsize=12,weight='bold')

            #TODO: iterate across all collision energies
            precursor_intensity = data[file_idx][compound_idx]['data']['msms']['data']['precursor_intensity']
            idx_max = np.argwhere(precursor_intensity == np.max(precursor_intensity)).flatten() 

            mz = data[file_idx][compound_idx]['data']['msms']['data']['mz'][idx_max]
            zeros = np.zeros(data[file_idx][compound_idx]['data']['msms']['data']['mz'][idx_max].shape)
            intensity = data[file_idx][compound_idx]['data']['msms']['data']['i'][idx_max]

            ax.vlines(mz,zeros,intensity,colors='r',linewidth = 2)
            sx = np.argsort(intensity)[::-1]
            labels = [1.001e9]
            for i in sx:
                if np.min(np.abs(mz[i] - labels)) > 0.1 and intensity[i] > 0.02 * np.max(intensity):
                    ax.annotate('%5.4f'%mz[i], xy=(mz[i], 1.01*intensity[i]),rotation = 90, horizontalalignment = 'center', verticalalignment = 'left')
                    labels.append(mz[i])

            plt.tight_layout()
            L = plt.ylim()
            plt.ylim(L[0],L[1]*1.12)
            if data[file_idx][compound_idx]['identification'].compound:
                inchi =  data[file_idx][compound_idx]['identification'].compound[0].inchi
                myMol = Chem.MolFromInchi(inchi.encode('utf-8'))
                myMol,neutralised = NeutraliseCharges(myMol)
                image = Draw.MolToImage(myMol, size = (300,300) )
                ax2 = fig.add_subplot(223)
                ax2.imshow(image)
                ax2.axis('off')
            #     SVG(moltosvg(myMol))

            ax3 = fig.add_subplot(224)
            ax3.set_xlim(0,1)
            mz_theoretical = data[file_idx][compound_idx]['identification'].mz_references[0].mz
            mz_measured = data[file_idx][compound_idx]['data']['ms1_summary']['mz_centroid']
            if not mz_measured:
                mz_measured = 0

            delta_mz = abs(mz_theoretical - mz_measured)
            delta_ppm = delta_mz / mz_theoretical * 1e6

            rt_theoretical = data[file_idx][compound_idx]['identification'].rt_references[0].rt_peak
            rt_measured = data[file_idx][compound_idx]['data']['ms1_summary']['rt_peak']
            if not rt_measured:
                rt_measured = 0
            ax3.text(0,1,'%s'%os.path.basename(data[file_idx][compound_idx]['lcmsrun'].hdf5_file),fontsize=12)
            ax3.text(0,0.95,'%s %s'%(compound_names[compound_idx], data[file_idx][compound_idx]['identification'].mz_references[0].adduct),fontsize=12)
            ax3.text(0,0.9,'m/z theoretical = %5.4f, measured = %5.4f, %5.4f ppm difference'%(mz_theoretical, mz_measured, delta_ppm),fontsize=12)
            ax3.text(0,0.85,'Expected Elution of %5.2f minutes, %5.2f min actual'%(rt_theoretical,rt_measured),fontsize=12)
            ax3.set_ylim(0.2,1.01)
            ax3.axis('off')
        #     plt.show()
            fig.savefig(os.path.join(output_loc, compound_names[compound_idx] + '.pdf'))
            fig.clear()
            plt.close('all')#f.clear()

def export_atlas_to_spreadsheet(myAtlas,output_filename):
    # myAtlases = [atlas[0],atlas[1]] #concatenate the atlases you want to use
    # myAtlases = [atlas[0]]
    compound_list = []
    for i in range(len(myAtlas.compound_identifications)):
        if myAtlas.compound_identifications[i].compound:
            compound_list.append(myAtlas.compound_identifications[i].compound[0].name)
        else:
            compound_list.append(myAtlas.compound_identifications[i].name)

    cols = ['inchi',
     'mono_isotopic_molecular_weight',
     'creation_time',
     'description',
     'formula',
     'functional_sets',
     'last_modified',
     'reference_xrefs',
     'synonyms',
     'unique_id',
     'url',
     'username']

        # print myAtlas[0].compound_identifications[0].compound
    atlas_export = pd.DataFrame( index=compound_list, columns=cols)

    atlas_export['name'] = compound_list
    atlas_export.set_index('name',drop=True)
    for i in range(len(myAtlas.compound_identifications)):
        if myAtlas.compound_identifications[i].compound:
            n = myAtlas.compound_identifications[i].compound[0].name
        else:
            n = myAtlas.compound_identifications[i].name
        if myAtlas.compound_identifications[i].compound:
            for c in cols:
                    g = getattr(myAtlas.compound_identifications[i].compound[0],c)
                    if g:
                        atlas_export.ix[n,c] = getattr(myAtlas.compound_identifications[i].compound[0],c)
        atlas_export.ix[n, 'label'] = myAtlas.compound_identifications[i].name
        atlas_export.ix[n,'rt_min'] = myAtlas.compound_identifications[i].rt_references[0].rt_min
        atlas_export.ix[n,'rt_max'] = myAtlas.compound_identifications[i].rt_references[0].rt_max
        atlas_export.ix[n,'rt_peak'] = myAtlas.compound_identifications[i].rt_references[0].rt_peak
        atlas_export.ix[n,'mz'] = myAtlas.compound_identifications[i].mz_references[0].mz
        atlas_export.ix[n,'mz_tolerance'] = myAtlas.compound_identifications[i].mz_references[0].mz_tolerance
        atlas_export.ix[n,'polarity'] = myAtlas.compound_identifications[i].mz_references[0].detected_polarity
    atlas_export.to_csv(output_filename)
        
if __name__ == '__main__':
    import sys

    input_fname = os.path.expandvars(sys.argv[1])
    output_loc = os.path.expandvars(sys.argv[2])



    nCols = 10
    argument = {'input_fname':input_fname,
                'nCols': nCols,
                'scale_y' : False,
                'output_loc': output_loc
               }

    plot_all_compounds_for_each_file(**argument)
    argument = {'input_fname':input_fname,
                'nCols': 20,
                'scale_y' : False,
                'output_loc': '/home/jimmy/ben/neg/unscaled/allfiles'
                }
    plot_all_files_for_each_compound(**argument)




