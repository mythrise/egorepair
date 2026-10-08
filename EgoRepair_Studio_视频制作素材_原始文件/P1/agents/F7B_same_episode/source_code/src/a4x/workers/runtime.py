"""All third-party caches are experiment-local, including GPU compiler caches."""
import os
import uuid
from pathlib import Path
from a4x.paths import WORKSPACE
from a4x.agents.ledger import checked_path

CACHE_NAMES={'TMPDIR':'tmp','XDG_CACHE_HOME':'cache','XDG_CONFIG_HOME':'config','XDG_DATA_HOME':'data','UV_CACHE_DIR':'cache/uv','PIP_CACHE_DIR':'cache/pip','HF_HOME':'cache/huggingface','HF_DATASETS_CACHE':'cache/hf_datasets','HF_LEROBOT_HOME':'cache/lerobot','TORCH_HOME':'cache/torch','MPLCONFIGDIR':'cache/matplotlib','CUDA_CACHE_PATH':'cache/cuda','TRITON_CACHE_DIR':'cache/triton','TORCHINDUCTOR_CACHE_DIR':'cache/torchinductor','TORCH_EXTENSIONS_DIR':'cache/torch_extensions','NUMBA_CACHE_DIR':'cache/numba','WANDB_DIR':'wandb','WANDB_CACHE_DIR':'cache/wandb','WANDB_DATA_DIR':'cache/wandb_data','WANDB_CONFIG_DIR':'cache/wandb_config','WANDB_ARTIFACT_DIR':'cache/wandb_artifacts','HF_HUB_CACHE':'cache/huggingface/hub'}
def local_environment(cache_root=None):
    # Strip secret-bearing inherited settings; cloud transport is separately gated by the registered public packet.
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('KEY','TOKEN','SECRET','PASSWORD'))}
    for key,name in CACHE_NAMES.items():
        p=Path(cache_root)/name if cache_root is not None else WORKSPACE/'.runtime'/name
        if key=='TMPDIR' and cache_root is None:p=p/('worker_'+str(uuid.uuid4()))
        if not p.absolute().is_relative_to(WORKSPACE):raise ValueError('Cache root outside experiment')
        for ancestor in [p,*p.parents]:
            if ancestor==WORKSPACE.parent:break
            if ancestor.is_symlink():raise ValueError('Symlink cache ancestry')
        p.mkdir(parents=True,exist_ok=True)
        for base,directories,files in os.walk(p,followlinks=False):
            for descendant in [Path(base)/name for name in directories+files]:
                if descendant.is_symlink():raise ValueError('Symlink cache descendant')
        env[key]=str(p)
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(WORKSPACE/'src'),OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',CUDA_VISIBLE_DEVICES='',WANDB_MODE='disabled')
    return env
