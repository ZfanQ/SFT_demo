#!/usr/bin/env python3
"""Export a reproducible scientific throughput/latency tradeoff figure."""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    models=[('qwen3_8b','Qwen3-8B / Ollama','#0072B2','o'),
            ('qwen35_9b_llamacpp','Qwen3.5-9B / direct llama.cpp','#D55E00','s'),
            ('gemma4_12b_llamacpp','Gemma-4-12B / direct llama.cpp','#009E73','^')]
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    plt.rcParams.update({'font.size':10})
    for label,name,color,marker in models:
        result=json.loads((args.root/label/'analysis.json').read_text())
        assert result['state']=='verified_complete' and result['timed_requests']==1800
        groups=sorted(result['aggregates'],key=lambda x:x['parallel'])
        axes[0].plot([x['parallel'] for x in groups],[x['documents_per_minute'] for x in groups],
                     color=color,marker=marker,label=name,linewidth=1.7,markersize=6)
        axes[1].plot([x['p95_latency_s'] for x in groups],[x['documents_per_minute'] for x in groups],
                     color=color,marker=marker,linewidth=1.7,markersize=6)
        for group in groups:
            axes[1].annotate(str(group['parallel']),
                             (group['p95_latency_s'],group['documents_per_minute']),
                             xytext=(5,5),textcoords='offset points',fontsize=9,color=color)
    axes[0].set(xlabel='Concurrent requests',ylabel='Throughput (paper/profile scores / minute)',xticks=[2,4,8],
                title='Same 200 abstracts × 3 fixed profiles')
    axes[1].set(xlabel='p95 active-request latency (seconds)',ylabel='Throughput (paper/profile scores / minute)',
                title='Throughput–latency tradeoff; labels = concurrency')
    for ax in axes:
        ax.grid(alpha=.22);ax.spines[['top','right']].set_visible(False)
        ax.margins(x=.18,y=.22)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=3,frameon=False,fontsize=9)
    fig.suptitle('H100 MIG: short-output relevance scoring, Q4_K_M',fontsize=12)
    for ext in ['png','pdf','svg']:
        fig.savefig(args.root/f'throughput_latency.{ext}',dpi=220,bbox_inches='tight')
    metadata={'matplotlib_version':matplotlib.__version__,
              'plot_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'verified_timed_requests':5400,'formats':['png','pdf','svg'],
              'png_dpi':220,'error_bars':'Not estimated; one pass per paper/profile/concurrency cell.'}
    (args.root/'plot_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    plt.close(fig)


if __name__=='__main__':main()
