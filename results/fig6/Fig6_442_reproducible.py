#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PRECEDENTGUARD Fig.6: four-by-four-by-two layout, data read-only.

Source: audited Fig6_bar_final_data.csv, 60 frozen aggregate rows.
This script is not a raw-trace replay and does not alter experimental data.
(a) 4 domain-specific effect panels; (b) 4 domain-specific proposal outcome
panels; (c) conditional simulated-grant outcomes; (d) sandbox violations.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from math import sqrt
from pathlib import Path
from statistics import NormalDist

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import patches

MODELS = ['GPT', 'Claude', 'GLM', 'Gemini', 'DeepSeek']
SHORT = ['GPT', 'Cla.', 'GLM', 'Gem.', 'DS']
DOMAINS = [('CloudOps', 10), ('Procurement', 60), ('Finance', 100), ('Data Access', 20)]
METHODS = ['B1', 'B3', 'PG']
FIELDS = ['N','proposed','installed','cppe_issuer','cppe_scope','unauth_effect',
          'valid_accepted','Installed','Out-of-root','CAP_SCOPE','Malformed']
OUTCOMES = [('Installed','teal'), ('Out-of-root','orange'),
            ('CAP_SCOPE','purple'),('Malformed','pale')]
COL = {'ink':'#28333B', 'brick':'#B3492C', 'teal':'#0F6E6E',
       'mist':'#73ACA7', 'gray':'#8C8C8C', 'orange':'#D28A43',
       'purple':'#7C6B99', 'pale':'#BFC7CC', 'grid':'#E1E5E7'}
EXPECTED = {'B1':{'installed':2960,'cppe_issuer':2960,'cppe_scope':598,'unauth_effect':584},
            'B3':{'installed':2362,'cppe_issuer':2362,'cppe_scope':0,'unauth_effect':0},
            'PG':{'proposed':3168,'installed':2275,'valid_accepted':720,'cppe_issuer':0,
                  'cppe_scope':0,'unauth_effect':0,'Installed':2275,
                  'Out-of-root':584,'CAP_SCOPE':101,'Malformed':208}}


def wilson(k,n):
    if not isinstance(k,(int,np.integer)) or not isinstance(n,(int,np.integer)) or n<=0 or k<0 or k>n:
        raise ValueError(f'invalid Wilson inputs: {k}, {n}')
    z=NormalDist().inv_cdf(.975); p=k/n; den=1+z*z/n
    center=(p+z*z/(2*n))/den
    radius=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return (0. if k==0 else max(0.,100*(center-radius))), (100. if k==n else min(100.,100*(center+radius)))


def read_aggregates(path):
    rows=list(csv.DictReader(path.open(newline='',encoding='utf-8-sig')))
    assert len(rows)==60, 'Expected 60 frozen model-domain-method cells'
    cells={}; totals=defaultdict(Counter); model_tot=defaultdict(Counter); domain_tot=defaultdict(Counter)
    for row in rows:
        key=(row['model'],row['domain'],row['method'])
        assert key[0] in MODELS and key[1] in dict(DOMAINS) and key[2] in METHODS, key
        assert key not in cells, f'duplicate {key}'
        v={f:int(row[f]) for f in FIELDS}
        assert v['N']==200 and 0<=v['valid_accepted']<=v['installed']<=v['proposed']<=200, key
        if key[2]=='PG':
            assert v['proposed']==sum(v[k] for k,_ in OUTCOMES), key
            assert v['installed']==v['Installed'], key
            assert v['cppe_issuer']==v['cppe_scope']==v['unauth_effect']==0, key
        else:
            assert all(v[k]==0 for k,_ in OUTCOMES) and v['valid_accepted']==0, key
        cells[key]=v
        totals[key[2]].update(v)
        model_tot[key[0],key[2]].update(v)
        domain_tot[key[1],key[2]].update(v)
    assert len(cells)==len(MODELS)*len(DOMAINS)*len(METHODS)
    for method, expected in EXPECTED.items():
        assert totals[method]['N']==4000
        for k,v in expected.items():
            assert totals[method][k]==v,(method,k,totals[method][k],v)
    assert sum(cells[m,d,'B1']['unauth_effect']>0 for m in MODELS for d,_ in DOMAINS)==16
    for d,_ in DOMAINS:
        assert domain_tot[d,'PG']['proposed']==sum(domain_tot[d,'PG'][k] for k,_ in OUTCOMES)
    for m in MODELS:
        assert model_tot[m,'B1']['proposed']==model_tot[m,'PG']['proposed']
    return cells,totals,model_tot,domain_tot


def setup_font():
    plt.rcParams.update({'font.family':'Liberation Sans','font.size':7.5,'axes.labelsize':7.4,
                         'xtick.labelsize':6.9,'ytick.labelsize':7.0,'axes.linewidth':.65,
                         'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none',
                         'svg.hashsalt':'PG-Fig6-442','axes.unicode_minus':False,
                         'savefig.facecolor':'white'})


def ftxt(fig,x,y,s,size=7.3,bold=False,ha='left',**kwargs):
    return fig.text(x,y,s,ha=ha,va='center',color=COL['ink'],fontsize=size,
                    weight='bold' if bold else 'normal',**kwargs)


def key(fig,x,y,s,col,open_marker=False,sz=7.1):
    if open_marker:
        fig.patches.append(patches.Circle((x+.0053,y),radius=.0049,
             transform=fig.transFigure,linewidth=1.,edgecolor=COL[col],
             facecolor='white',clip_on=False))
        dx=.014
    else:
        fig.patches.append(patches.Rectangle((x,y-.0044),.011,.0088,
             transform=fig.transFigure,linewidth=0,facecolor=COL[col],clip_on=False))
        dx=.015
    return ftxt(fig,x+dx,y,s,sz)


def style(ax):
    ax.set_axisbelow(True)
    for side in ('top','right'): ax.spines[side].set_visible(False)
    for side in ('left','bottom'):
        ax.spines[side].set_color(COL['ink']);ax.spines[side].set_linewidth(.68)
    ax.tick_params(axis='both',length=1.9,width=.6,pad=2,color=COL['ink'],labelcolor=COL['ink'])
    ax.grid(axis='y',color=COL['grid'],linewidth=.42)


def caption_safe_note(uniform):
    return ('B1 bars: nominal 95% Wilson intervals  |  n = 200 histories per model-domain cell'
            '  |  '+('uniform 0-100% scale' if uniform else 'domain-specific scales shown'))


def figure_442(cells,totals,model_tot,domain_tot,outbase,uniform=False):
    setup_font()
    # Match IEEEtran conference,compsoc double-column width exactly; not an artificially wide canvas.
    fig=plt.figure(figsize=(505.89/72.,6.08),facecolor='white')
    xs=np.arange(5,dtype=float)
    xcol=[.080,.313,.546,.779]; panel_w=.181

    # ROW 1: 4 domains, observed B1 effects and exact PG zeros.
    ftxt(fig,.073,.981,'(a) Unauthorized sandbox-probe effects',9.0,True)
    key(fig,.600,.980,'B1 effect','brick',sz=7.15)
    key(fig,.757,.980,'PG: 0/200 in each cell','teal',True,sz=7.0)
    ftxt(fig,.074,.949,caption_safe_note(uniform),6.9)
    for i,(domain,adaptive) in enumerate(DOMAINS):
        top=100 if uniform else adaptive
        ax=fig.add_axes([xcol[i],.750,panel_w,.142]);style(ax)
        ax.set_xlim(-.52,4.52);ax.set_ylim(0,top)
        ax.set_title(f'{domain} (0-{top}%)',fontsize=8.0,color=COL['ink'],weight='bold',pad=6.8)
        vals=np.array([cells[m,domain,'B1']['unauth_effect'] for m in MODELS],dtype=int)
        p=100*vals/200
        ci=np.array([wilson(int(v),200) for v in vals])
        bx=xs-.175
        ax.bar(bx,p,width=.44,color=COL['brick'],linewidth=0,zorder=3)
        ax.errorbar(bx,p,yerr=[p-ci[:,0],ci[:,1]-p],fmt='none',ecolor=COL['ink'],
                    elinewidth=.75,capsize=1.75,capthick=.74,zorder=4)
        ax.plot(xs+.19,np.zeros(5),'o',ms=3.8,mec=COL['teal'],mfc='white',mew=1.,zorder=5,clip_on=False)
        for j,k in enumerate(vals):
            if k==0:continue
            if ci[j,1]>.91*top and p[j]>.32*top:
                ax.text(bx[j],p[j]-.028*top,str(k),ha='center',va='top',fontsize=7.1,
                        color='white',weight='bold',zorder=6)
            else:
                ax.text(bx[j],min(ci[j,1]+.025*top,.977*top),str(k),ha='center',va='bottom',
                        fontsize=7.05,color=COL['ink'],zorder=6)
        ax.set_xticks(xs,SHORT)
        ax.set_yticks([0,top/2,top]);ax.set_yticklabels([f'{v:g}' for v in [0,top/2,top]])
    ftxt(fig,.034,.822,'B1 effect (%)',7.5,rotation=90,ha='center')

    # ROW 2: same four-domain small-multiple grammar; denominator is PROPOSALS,
    # varies by domain and by model, and is labeled above each model's bar.
    ftxt(fig,.073,.704,'(b) PG proposal dispositions by domain',9.0,True)
    key(fig,.399,.676,'Installed','teal',sz=7.0)
    key(fig,.524,.676,'Out of root','orange',sz=7.0)
    key(fig,.674,.676,'CAP_SCOPE','purple',sz=7.0)
    key(fig,.820,.676,'Malformed','pale',sz=7.0)
    ftxt(fig,.074,.651,'100% stacked bars; denominator printed above each bar = PG proposals for that model-domain cell',6.85)
    for i,(domain,_) in enumerate(DOMAINS):
        ax=fig.add_axes([xcol[i],.477,panel_w,.135]);style(ax)
        proposed=np.array([cells[m,domain,'PG']['proposed'] for m in MODELS],dtype=int)
        assert np.all(proposed>0)
        ax.set_xlim(-.52,4.52);ax.set_ylim(0,115.0)
        n_domain=domain_tot[domain,'PG']['proposed']
        ax.set_title(f'{domain} (P={n_domain})',fontsize=7.95,color=COL['ink'],weight='bold',pad=7.0)
        bottom=np.zeros(5,dtype=float)
        for cat,color in OUTCOMES:
            vals=np.array([cells[m,domain,'PG'][cat] for m in MODELS],dtype=int)
            rate=100*vals/proposed
            ax.bar(xs,rate,bottom=bottom,width=.60,color=COL[color],edgecolor='white',linewidth=.35,zorder=3)
            for j,h in enumerate(rate):
                if h>=20.0:
                    ax.text(xs[j],bottom[j]+h/2,f'{h:.0f}',ha='center',va='center',
                            fontsize=6.95,weight='bold' if h>=30 else 'normal',
                            color='white' if cat in ('Installed','CAP_SCOPE') else COL['ink'],zorder=5)
            bottom+=rate
        assert np.allclose(bottom,100.0,rtol=0,atol=1e-10)
        for j,v in enumerate(proposed):
            ax.text(xs[j],102.2,str(v),ha='center',va='bottom',fontsize=6.8,color=COL['ink'])
        ax.set_xticks(xs,SHORT)
        ax.set_yticks([0,50,100]);ax.set_yticklabels(['0','50','100'])
    ftxt(fig,.034,.553,'Proposals (%)',7.5,rotation=90,ha='center')

    # ROW 3 left: original (c), matched proposal-level denominator by model.
    ftxt(fig,.074,.425,'(c) Conditional PG installation / reuse',9.0,True)
    key(fig,.079,.393,'Installed / proposed','mist',sz=7.0)
    key(fig,.290,.393,'Canonical hit / proposed','teal',sz=7.0)
    cx=fig.add_axes([.082,.125,.388,.229]);style(cx)
    pp=np.array([model_tot[m,'PG']['proposed'] for m in MODELS],dtype=int)
    cbar=.31
    for metric,offset,col in [('installed',-cbar/2,'mist'),('valid_accepted',cbar/2,'teal')]:
        counts=np.array([model_tot[m,'PG'][metric] for m in MODELS],dtype=int)
        r=100*counts/pp
        ci=np.array([wilson(int(v),int(n)) for v,n in zip(counts,pp)])
        cx.bar(xs+offset,r,width=cbar,color=COL[col],linewidth=0,zorder=3)
        cx.errorbar(xs+offset,r,yerr=[r-ci[:,0],ci[:,1]-r],fmt='none',
                    ecolor=COL['ink'],elinewidth=.75,capsize=1.8,capthick=.75,zorder=4)
        for j,k in enumerate(counts):
            if k:
                if ci[j,1]>95 and r[j]>80:
                    cx.text(j+offset,r[j]-4.,f'{r[j]:.0f}',ha='center',va='top',
                            fontsize=7.1,color=COL['ink'],weight='bold')
                else:
                    cx.text(j+offset,min(ci[j,1]+2.1,103.),f'{r[j]:.0f}',ha='center',va='bottom',
                            fontsize=7.05,color=COL['ink'])
            else:
                cx.plot(j+offset,0,'o',ms=3.8,mec=COL['teal'],mew=1.,mfc='white',clip_on=False,zorder=5)
                cx.text(j+offset,4.0,'0',ha='center',va='bottom',fontsize=7.0,color=COL['ink'])
    cx.set_xlim(-.55,4.55);cx.set_ylim(0,109)
    cx.set_xticks(xs,['GPT','Claude','GLM','Gem.','DS'])
    cx.set_yticks([0,25,50,75,100]);cx.set_ylabel('Proposals (%)',labelpad=2.5)

    # ROW 3 right: original (d), method-level denominator 4000 histories.
    ftxt(fig,.563,.425,'(d) Failures across enforcement layers',9.0,True)
    key(fig,.575,.393,'B1','brick',sz=7.1)
    key(fig,.673,.393,'B3 (no grant)','gray',sz=7.1)
    key(fig,.855,.393,'PG = 0','teal',True,sz=7.1)
    dx=fig.add_axes([.568,.125,.388,.229]);style(dx)
    fail_metrics=['cppe_issuer','cppe_scope','unauth_effect']
    labels=['Issuer-unsafe\ninstallation','Scope escape\ninstallation','Unauthorized\nsandbox effect']
    loc=np.arange(3,dtype=float);gap=.23
    for j,(method,col) in enumerate([('B1','brick'),('B3','gray'),('PG','teal')]):
        v=np.array([totals[method][metric] for metric in fail_metrics],dtype=int)
        r=100*v/4000
        ci=np.array([wilson(int(k),4000) for k in v])
        xi=loc+(j-1)*gap
        dx.bar(xi,r,width=.215,color=COL[col],linewidth=0,zorder=3)
        # Nominal Wilson intervals are displayed for non-zero rates; exact zeros
        # retain the explicitly observed zero marker at 0 rather than fake bars.
        for i,k in enumerate(v):
            if k:
                dx.errorbar(xi[i],r[i],yerr=[[r[i]-ci[i,0]],[ci[i,1]-r[i]]],
                            fmt='none',ecolor=COL['ink'],elinewidth=.73,capsize=1.65,
                            capthick=.73,zorder=4)
                dx.text(xi[i],ci[i,1]+1.3,f'{k}',ha='center',va='bottom',fontsize=7.0,
                        color=COL['ink'],weight='bold',zorder=5)
            else:
                dx.plot(xi[i],0,'o',ms=3.8,mec=COL[col],mew=1.,mfc='white',clip_on=False,zorder=5)
                dx.text(xi[i],2.5,'0',ha='center',va='bottom',fontsize=6.8,color=COL['ink'],zorder=5)
    dx.set_xlim(-.55,2.55);dx.set_ylim(0,86)
    dx.set_xticks(loc,labels);dx.set_yticks([0,20,40,60,80]);dx.set_ylabel('Histories (%)',labelpad=2.5)
    # A minimal source-and-semantic reminder, not a stand-in for the manuscript caption.
    ftxt(fig,.074,.038,'Frozen k=10 legitimate-arm replay  |  Simulated class-scoped grants  |  In-harness PEP/tool-sandbox probes',6.95)

    outputs=[]
    for ext in ('pdf','png','svg'):
        fname=outbase.with_suffix('.'+ext)
        fig.savefig(fname,facecolor='white',dpi=270 if ext=='png' else None)
        outputs.append(fname)
    plt.close(fig)
    return outputs


def tests(cells,totals,model_tot,domain_tot):
    for k,n in [(0,200),(1,200),(8,200),(182,200),(200,200),(0,4000),(584,4000),(3168,4000)]:
        lo,hi=wilson(k,n); p=100*k/n
        assert 0<=lo<=p<=hi<=100,(k,n,lo,hi)
    for k,n in [(-1,200),(201,200),(0,0)]:
        try: wilson(k,n)
        except ValueError: pass
        else: raise AssertionError('invalid k,n not rejected')
    assert sum(domain_tot[d,'PG']['proposed'] for d,_ in DOMAINS)==3168
    assert sum(domain_tot[d,'PG']['Installed'] for d,_ in DOMAINS)==2275
    assert sum(domain_tot[d,'PG']['Out-of-root'] for d,_ in DOMAINS)==584
    assert sum(domain_tot[d,'PG']['CAP_SCOPE'] for d,_ in DOMAINS)==101
    assert sum(domain_tot[d,'PG']['Malformed'] for d,_ in DOMAINS)==208
    assert sum(model_tot[m,'PG']['valid_accepted'] for m in MODELS)==720
    for d,_ in DOMAINS:
        for m in MODELS:
            v=cells[m,d,'PG']
            assert v['proposed']==sum(v[t] for t,_ in OUTCOMES)
    return True


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--csv',type=Path,default=Path(__file__).with_name('Fig6_bar_final_data.csv'))
    p.add_argument('--outdir',type=Path,default=Path(__file__).with_name('fig6_442_output'))
    a=p.parse_args()
    cells,totals,model_tot,domain_tot=read_aggregates(a.csv)
    tests(cells,totals,model_tot,domain_tot)
    a.outdir.mkdir(parents=True,exist_ok=True)
    for uniform in [False,True]:
        figure_442(cells,totals,model_tot,domain_tot,
                   a.outdir/('Fig6_442_uniform' if uniform else 'Fig6_442_adaptive'),uniform)
    meta={'source_file':a.csv.name,'source_sha256':hashlib.sha256(a.csv.read_bytes()).hexdigest(),
          'source_cells':60,'b_domain_proposals':{d:int(domain_tot[d,'PG']['proposed']) for d,_ in DOMAINS},
          'figure_structure':'row1: 4 domains (a); row2: 4 domains (b); row3: (c) left, (d) right',
          'b_denominator':'each model-domain PG proposed count (shown above stacked bars)',
          'sum_pg_proposals':3168,'sum_pg_outcomes':{'installed':2275,'out_of_root':584,'cap_scope':101,'malformed':208},
          'scientific_qualifiers':['harness-simulated grants','in-harness probe-based effects',
                                   'canonical hit != real task success',
                                   'nominal Wilson intervals do not account for dependent channel/seed configurations',
                                   'B3 has no typed root grant','E3 frozen-prefix replay not depicted'],
          'source_validation':'CSV compared against CORE previous turn; not a fresh RAW trace audit',
          'width_pt':505.89,'height_pt':6.08*72,'image_variants':['adaptive','uniform']}
    (a.outdir/'Fig6_442_audit.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS: frozen CSV validated; 4+4+2 panel layout, both vector variants rendered.')
    print('Panel (b) domain proposals:',meta['b_domain_proposals'])

if __name__=='__main__': main()
